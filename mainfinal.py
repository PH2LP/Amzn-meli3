#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mainfinal.py - Pipeline Definitivo Amazon → MercadoLibre CBT
═══════════════════════════════════════════════════════════════════════════════

ARQUITECTURA COMPLETA:
1. Lee ASINs desde resources/asins.txt
2. Carga JSONs de Amazon desde storage/asins_json/
3. Detecta categoría ML con CategoryMatcherV2 (embeddings + IA)
4. Obtiene schema dinámico de ML API (con cache)
5. Llena TODOS los atributos con IA (GPT-4o-mini)
6. Calcula net proceeds (Amazon price + tax × 1.35)
7. Validación exhaustiva pre-publicación
8. Publica en CBT multi-país
9. Tracking completo en SQLite
10. Reportes detallados

TARGET: 95%+ success rate
Autor: Pipeline Final v1.0
Fecha: 2025-01-04
"""

import os
import sys
import json
import time
import sqlite3
import traceback
import requests
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from dotenv import load_dotenv

# ═══════════════════════════════════════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════════════════════════════════════

load_dotenv(override=True)

# Imports de módulos propios
from src.category_matcher_v2 import CategoryMatcherV2
from openai import OpenAI


# ═══════════════════════════════════════════════════════════════════════════
# 1. CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════

class Config:
    """Configuración centralizada del pipeline"""

    # Directorios
    ASINS_FILE = Path("resources/asins.txt")
    AMAZON_JSON_DIR = Path("storage/asins_json")
    SCHEMAS_DIR = Path("storage/schemas")
    LOGS_DIR = Path("storage/logs/mainfinal")
    REPORTS_DIR = Path("storage/reports")
    DB_PATH = Path("storage/pipeline_final.db")

    # Credenciales
    ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Pricing
    PRICE_MARKUP = float(os.getenv("PRICE_MARKUP", "35"))  # 35%

    # IA
    AI_MODEL = "gpt-4o-mini"
    AI_TEMPERATURE = 0.2
    AI_MAX_TOKENS = 800

    # Validación
    MIN_IMAGE_SIZE = 500  # px
    MIN_PACKAGE_DIM = 3.0  # cm
    MIN_PACKAGE_WEIGHT = 50.0  # g
    MIN_VOLUME = 0.02  # (width * height * length) / 5000
    MIN_NET_PROCEEDS = 1.0  # USD

    # Rate Limiting
    PUBLISH_DELAY = 2  # segundos entre publicaciones
    RETRY_DELAY = 5  # segundos entre reintentos
    MAX_RETRIES = 3

    # ML API
    ML_API_BASE = "https://api.mercadolibre.com"

    # Cache TTL
    SCHEMA_CACHE_DAYS = 7

    @classmethod
    def setup_directories(cls):
        """Crea directorios necesarios"""
        for path in [cls.AMAZON_JSON_DIR, cls.SCHEMAS_DIR, cls.LOGS_DIR, cls.REPORTS_DIR]:
            path.mkdir(parents=True, exist_ok=True)
        cls.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls):
        """Valida que las configuraciones críticas estén presentes"""
        errors = []

        if not cls.ML_ACCESS_TOKEN:
            errors.append("ML_ACCESS_TOKEN no encontrado en .env")

        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY no encontrado en .env")

        if not cls.ASINS_FILE.exists():
            errors.append(f"Archivo {cls.ASINS_FILE} no existe")

        return errors


# ═══════════════════════════════════════════════════════════════════════════
# 2. DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CategoryResult:
    """Resultado de detección de categoría"""
    category_id: str
    category_name: str
    category_path: str
    confidence: float
    method: str


@dataclass
class PriceResult:
    """Resultado de cálculo de precio"""
    price_amazon: float
    tax_usd: float
    cost_usd: float
    markup_percent: float
    net_proceeds_usd: float


@dataclass
class ValidationResult:
    """Resultado de validación pre-publicación"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


@dataclass
class PublishResult:
    """Resultado de publicación"""
    success: bool
    item_id: Optional[str]
    countries: List[str]
    site_items: List[Dict]
    permalink: Optional[str]
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# 3. BASE DE DATOS
# ═══════════════════════════════════════════════════════════════════════════

class PipelineDatabase:
    """Base de datos para tracking del pipeline"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Inicializa las tablas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Tabla de estado de ASINs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS asin_status (
                asin TEXT PRIMARY KEY,
                status TEXT,
                category_id TEXT,
                category_name TEXT,
                item_id TEXT,
                countries TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Tabla de logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asin TEXT,
                phase TEXT,
                message TEXT,
                level TEXT,
                timestamp TEXT
            )
        """)

        # Tabla de precios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pricing_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asin TEXT,
                price_amazon REAL,
                tax_usd REAL,
                cost_usd REAL,
                markup_percent REAL,
                net_proceeds_usd REAL,
                timestamp TEXT
            )
        """)

        conn.commit()
        conn.close()

    def update_status(self, asin: str, status: str, **kwargs):
        """Actualiza el estado de un ASIN"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        # Obtener valores opcionales
        category_id = kwargs.get('category_id')
        category_name = kwargs.get('category_name')
        item_id = kwargs.get('item_id')
        countries = json.dumps(kwargs.get('countries', [])) if kwargs.get('countries') else None
        error_message = kwargs.get('error_message')

        cursor.execute("""
            INSERT INTO asin_status
            (asin, status, category_id, category_name, item_id, countries, error_message, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asin) DO UPDATE SET
                status = excluded.status,
                category_id = COALESCE(excluded.category_id, category_id),
                category_name = COALESCE(excluded.category_name, category_name),
                item_id = COALESCE(excluded.item_id, item_id),
                countries = COALESCE(excluded.countries, countries),
                error_message = excluded.error_message,
                updated_at = excluded.updated_at,
                retry_count = retry_count + 1
        """, (asin, status, category_id, category_name, item_id, countries, error_message, now, now))

        conn.commit()
        conn.close()

    def log(self, asin: str, phase: str, message: str, level: str = "INFO"):
        """Registra un log"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO processing_logs (asin, phase, message, level, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (asin, phase, message, level, datetime.now().isoformat()))

        conn.commit()
        conn.close()

        # También imprimir
        icons = {"INFO": "ℹ️", "ERROR": "❌", "WARNING": "⚠️", "SUCCESS": "✅"}
        icon = icons.get(level, "📝")
        print(f"  {icon} [{phase}] {message}")

    def save_price(self, asin: str, price_result: PriceResult):
        """Guarda el historial de precios"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO pricing_history
            (asin, price_amazon, tax_usd, cost_usd, markup_percent, net_proceeds_usd, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            asin,
            price_result.price_amazon,
            price_result.tax_usd,
            price_result.cost_usd,
            price_result.markup_percent,
            price_result.net_proceeds_usd,
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

    def get_statistics(self) -> Dict:
        """Obtiene estadísticas del pipeline"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Contar por status
        cursor.execute("SELECT status, COUNT(*) FROM asin_status GROUP BY status")
        stats = {row[0]: row[1] for row in cursor.fetchall()}

        # Total procesados
        cursor.execute("SELECT COUNT(*) FROM asin_status")
        total = cursor.fetchone()[0]

        # Categorías más usadas
        cursor.execute("""
            SELECT category_name, COUNT(*) as count
            FROM asin_status
            WHERE category_name IS NOT NULL
            GROUP BY category_name
            ORDER BY count DESC
            LIMIT 5
        """)
        top_categories = {row[0]: row[1] for row in cursor.fetchall()}

        # Precio promedio
        cursor.execute("SELECT AVG(net_proceeds_usd) FROM pricing_history")
        avg_price = cursor.fetchone()[0] or 0

        conn.close()

        return {
            "status_counts": stats,
            "total": total,
            "top_categories": top_categories,
            "avg_net_proceeds": round(avg_price, 2)
        }


# ═══════════════════════════════════════════════════════════════════════════
# 4. DATA LOADER
# ═══════════════════════════════════════════════════════════════════════════

class DataLoader:
    """Carga datos de entrada"""

    @staticmethod
    def load_asins_from_file(file_path: Path) -> List[str]:
        """Carga ASINs desde archivo"""
        if not file_path.exists():
            raise FileNotFoundError(f"Archivo {file_path} no encontrado")

        asins = []
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Ignorar líneas vacías y comentarios
                if not line or line.startswith('#'):
                    continue

                # Validar formato ASIN (10 caracteres alfanuméricos)
                asin = line.upper()
                if len(asin) == 10 and asin.isalnum():
                    asins.append(asin)
                else:
                    print(f"⚠️  ASIN inválido ignorado: {line}")

        # Eliminar duplicados manteniendo orden
        unique_asins = []
        seen = set()
        for asin in asins:
            if asin not in seen:
                unique_asins.append(asin)
                seen.add(asin)

        return unique_asins

    @staticmethod
    def load_amazon_json(asin: str, json_dir: Path) -> Dict:
        """Carga JSON de Amazon para un ASIN"""
        json_path = json_dir / f"{asin}.json"

        if not json_path.exists():
            raise FileNotFoundError(f"JSON no encontrado: {json_path}")

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Validar campos mínimos
        if not data.get('asin') and not data.get('ASIN'):
            raise ValueError(f"JSON no contiene ASIN: {json_path}")

        # Buscar título en varios lugares
        title = (data.get('title') or
                data.get('product_title') or
                data.get('name'))

        # Buscar en attributes.item_name
        if not title and data.get('attributes', {}).get('item_name'):
            item_name = data['attributes']['item_name']
            if isinstance(item_name, list) and item_name:
                title = item_name[0].get('value', '') if isinstance(item_name[0], dict) else str(item_name[0])

        if not title:
            raise ValueError(f"JSON no contiene título: {json_path}")

        return data


# ═══════════════════════════════════════════════════════════════════════════
# 5. CATEGORY DETECTOR
# ═══════════════════════════════════════════════════════════════════════════

class CategoryDetector:
    """Detecta categoría ML usando CategoryMatcherV2"""

    def __init__(self, db: PipelineDatabase):
        self.db = db
        self.matcher = None  # Lazy initialization

    def _get_matcher(self):
        """Lazy initialization del matcher"""
        if self.matcher is None:
            print("🚀 Inicializando CategoryMatcherV2...")
            self.matcher = CategoryMatcherV2()
        return self.matcher

    def detect_category(self, asin: str, amazon_json: Dict) -> CategoryResult:
        """Detecta la mejor categoría para el producto"""
        matcher = self._get_matcher()

        # Preparar datos del producto
        product_data = {
            'title': amazon_json.get('title') or amazon_json.get('product_title', ''),
            'description': self._extract_description(amazon_json),
            'brand': self._extract_brand(amazon_json),
            'features': self._extract_features(amazon_json),
            'productType': amazon_json.get('productType'),
            'browseClassification': amazon_json.get('browseClassification')
        }

        # Llamar al matcher
        result = matcher.find_category(product_data, top_k=30, use_ai=True)

        # Validar confianza
        if result['confidence'] < 0.75:
            self.db.log(asin, "category",
                       f"Confianza baja: {result['confidence']:.2f}", "WARNING")

        return CategoryResult(
            category_id=result['category_id'],
            category_name=result['category_name'],
            category_path=result['category_path'],
            confidence=result['confidence'],
            method=result['method']
        )

    def _extract_description(self, amazon_json: Dict) -> str:
        """Extrae descripción del JSON de Amazon"""
        # Intentar varios campos
        desc = (amazon_json.get('description') or
                amazon_json.get('product_description') or
                amazon_json.get('productDescription') or '')

        # Si no hay descripción, usar bullet points
        if not desc:
            bullets = self._extract_features(amazon_json)
            if bullets:
                desc = ' '.join(bullets[:5])

        return desc[:1000]  # Limitar longitud

    def _extract_brand(self, amazon_json: Dict) -> str:
        """Extrae marca del JSON de Amazon"""
        # Intentar varios campos
        brand = (amazon_json.get('brand') or
                amazon_json.get('manufacturer') or
                amazon_json.get('brandName') or '')

        # También buscar en attributes
        if not brand and amazon_json.get('attributes'):
            attrs = amazon_json['attributes']
            if isinstance(attrs, dict):
                brand_list = attrs.get('brand', [])
                if brand_list and isinstance(brand_list, list):
                    brand = brand_list[0].get('value', '') if isinstance(brand_list[0], dict) else str(brand_list[0])

        return brand

    def _extract_features(self, amazon_json: Dict) -> List[str]:
        """Extrae características/bullet points del JSON de Amazon"""
        features = []

        # Buscar en varios campos posibles
        if amazon_json.get('bullet_points'):
            features = amazon_json['bullet_points']
        elif amazon_json.get('features'):
            features = amazon_json['features']
        elif amazon_json.get('attributes', {}).get('bullet_point'):
            bullet_attr = amazon_json['attributes']['bullet_point']
            if isinstance(bullet_attr, list):
                features = [b.get('value', '') if isinstance(b, dict) else str(b) for b in bullet_attr]

        # Limpiar y filtrar
        features = [f.strip() for f in features if f and isinstance(f, str)]
        return features[:10]  # Máximo 10 features


# ═══════════════════════════════════════════════════════════════════════════
# 6. SCHEMA MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class SchemaManager:
    """Gestiona obtención y cache de schemas de categorías ML"""

    def __init__(self, cache_dir: Path, ml_token: str):
        self.cache_dir = cache_dir
        self.ml_token = ml_token
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_category_schema(self, category_id: str) -> Dict:
        """Obtiene el schema de una categoría (con cache)"""
        # Verificar cache
        cache_path = self.cache_dir / f"{category_id}.json"

        if self._is_cache_valid(cache_path):
            print(f"📦 Schema {category_id} desde cache")
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        # Descargar desde API
        print(f"🌐 Descargando schema {category_id} desde ML API...")
        schema = self._fetch_schema_from_api(category_id)

        # Guardar en cache
        if schema:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(schema, f, indent=2, ensure_ascii=False)

        return schema

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Verifica si el cache es válido (existe y no expiró)"""
        if not cache_path.exists():
            return False

        # Verificar edad del archivo
        mod_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - mod_time

        return age.days < Config.SCHEMA_CACHE_DAYS

    def _fetch_schema_from_api(self, category_id: str) -> Dict:
        """Descarga schema desde ML API"""
        # Intentar primero con attributes (endpoint más común)
        url = f"{Config.ML_API_BASE}/categories/{category_id}/attributes"
        headers = {"Authorization": f"Bearer {self.ml_token}"}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            raw_schema = response.json()

            # Verificar si es un error
            if isinstance(raw_schema, dict) and 'status' in raw_schema and raw_schema.get('status') >= 400:
                raise ValueError(f"ML API error: {raw_schema.get('message', 'Unknown error')}")

            # Debe ser una lista de atributos
            if not isinstance(raw_schema, list):
                raise ValueError(f"Respuesta inesperada de ML API: {type(raw_schema)}")

            # Procesar schema
            schema = {}
            for attr in raw_schema:
                attr_id = attr.get('id')
                if not attr_id:
                    continue

                schema[attr_id] = {
                    'id': attr_id,
                    'name': attr.get('name', ''),
                    'value_type': attr.get('value_type', 'string'),
                    'values': {
                        v['name']: v['id']
                        for v in attr.get('values', [])
                        if v.get('id') and v.get('name')
                    },
                    'allowed_units': [u['id'] for u in attr.get('allowed_units', [])],
                    'tags': attr.get('tags', {}),  # tags es un dict
                    'hierarchy': attr.get('hierarchy', ''),
                    'relevance': attr.get('relevance', 0)
                }

            print(f"✅ Schema {category_id}: {len(schema)} atributos descargados")
            return schema

        except requests.exceptions.RequestException as e:
            print(f"❌ Error descargando schema {category_id}: {e}")
            return {}

    def parse_required_attributes(self, schema: Dict) -> List[str]:
        """Extrae la lista de atributos obligatorios"""
        required = []

        for attr_id, attr_data in schema.items():
            tags = attr_data.get('tags', {})
            if tags.get('required') or tags.get('catalog_required'):
                required.append(attr_id)

        # Siempre incluir estos como obligatorios
        always_required = ['BRAND', 'ITEM_CONDITION', 'PACKAGE_HEIGHT',
                          'PACKAGE_LENGTH', 'PACKAGE_WIDTH', 'PACKAGE_WEIGHT', 'SELLER_SKU']

        for attr in always_required:
            if attr not in required:
                required.append(attr)

        return required


# ═══════════════════════════════════════════════════════════════════════════
# 7. ATTRIBUTE FILLER
# ═══════════════════════════════════════════════════════════════════════════

class AttributeFiller:
    """Completa atributos usando IA"""

    def __init__(self, openai_client: OpenAI, db: PipelineDatabase):
        self.client = openai_client
        self.db = db

    def fill_all_attributes(
        self,
        asin: str,
        amazon_json: Dict,
        category_id: str,
        category_name: str,
        schema: Dict
    ) -> Dict[str, Any]:
        """Completa todos los atributos necesarios"""

        # 1. Mapeo automático (sin IA)
        mapped_attrs = self._auto_map_attributes(amazon_json)

        # 2. Identificar atributos requeridos faltantes
        schema_manager = SchemaManager(Config.SCHEMAS_DIR, Config.ML_ACCESS_TOKEN)
        required_attrs = schema_manager.parse_required_attributes(schema)

        missing = [attr for attr in required_attrs if attr not in mapped_attrs]

        if missing:
            self.db.log(asin, "attributes",
                       f"Faltantes: {len(missing)} atributos - usando IA", "INFO")

            # 3. Completar con IA
            ai_filled = self._fill_with_ai(
                amazon_json,
                category_id,
                category_name,
                schema,
                missing
            )

            # Merge
            mapped_attrs.update(ai_filled)

        # 4. Validar que todos los required estén presentes
        still_missing = [attr for attr in required_attrs if attr not in mapped_attrs]

        if still_missing:
            self.db.log(asin, "attributes",
                       f"AÚN faltan: {', '.join(still_missing)}", "WARNING")

        return mapped_attrs

    def _auto_map_attributes(self, amazon_json: Dict) -> Dict[str, Any]:
        """Mapeo automático sin IA"""
        attrs = {}

        # SELLER_SKU = ASIN
        asin = amazon_json.get('asin') or amazon_json.get('ASIN', '')
        if asin:
            attrs['SELLER_SKU'] = {
                'id': 'SELLER_SKU',
                'value_name': asin
            }

        # ITEM_CONDITION = New (siempre)
        attrs['ITEM_CONDITION'] = {
            'id': 'ITEM_CONDITION',
            'value_id': '2230284',
            'value_name': 'New'
        }

        # GTIN (si existe)
        gtin = self._extract_gtin(amazon_json)
        if gtin:
            attrs['GTIN'] = {
                'id': 'GTIN',
                'value_name': gtin
            }

        # Dimensiones
        dimensions = self._extract_dimensions(amazon_json)
        if dimensions:
            if dimensions.get('length'):
                attrs['PACKAGE_LENGTH'] = {
                    'id': 'PACKAGE_LENGTH',
                    'value_name': f"{dimensions['length']} cm"
                }
            if dimensions.get('width'):
                attrs['PACKAGE_WIDTH'] = {
                    'id': 'PACKAGE_WIDTH',
                    'value_name': f"{dimensions['width']} cm"
                }
            if dimensions.get('height'):
                attrs['PACKAGE_HEIGHT'] = {
                    'id': 'PACKAGE_HEIGHT',
                    'value_name': f"{dimensions['height']} cm"
                }
            if dimensions.get('weight'):
                attrs['PACKAGE_WEIGHT'] = {
                    'id': 'PACKAGE_WEIGHT',
                    'value_name': f"{dimensions['weight']} g"
                }

        # BRAND
        brand = self._extract_brand(amazon_json)
        if brand:
            attrs['BRAND'] = {
                'id': 'BRAND',
                'value_name': brand
            }

        # MODEL
        model = self._extract_model(amazon_json)
        if model:
            attrs['MODEL'] = {
                'id': 'MODEL',
                'value_name': model
            }

        return attrs

    def _extract_gtin(self, amazon_json: Dict) -> Optional[str]:
        """Extrae GTIN/UPC/EAN del JSON de Amazon"""
        # Buscar en varios campos
        gtin = (amazon_json.get('gtin') or
                amazon_json.get('upc') or
                amazon_json.get('ean') or
                amazon_json.get('barcode') or '')

        # Buscar en attributes
        if not gtin and amazon_json.get('attributes'):
            attrs = amazon_json['attributes']
            if isinstance(attrs, dict):
                for key in ['externally_assigned_product_identifier', 'gtin', 'upc', 'ean']:
                    if key in attrs:
                        val = attrs[key]
                        if isinstance(val, list) and val:
                            gtin = val[0].get('value', '') if isinstance(val[0], dict) else str(val[0])
                            if gtin:
                                break

        return gtin if gtin and len(gtin) >= 8 else None

    def _extract_dimensions(self, amazon_json: Dict) -> Dict[str, float]:
        """Extrae dimensiones del JSON de Amazon"""
        dims = {}

        # Buscar en varios campos
        if amazon_json.get('dimensions'):
            d = amazon_json['dimensions']
            dims['length'] = self._parse_dimension(d.get('length'))
            dims['width'] = self._parse_dimension(d.get('width'))
            dims['height'] = self._parse_dimension(d.get('height'))

        if amazon_json.get('weight'):
            dims['weight'] = self._parse_weight(amazon_json['weight'])

        # Buscar en attributes
        if amazon_json.get('attributes'):
            attrs = amazon_json['attributes']
            if isinstance(attrs, dict):
                # Item dimensions
                for key in ['item_length', 'item_width', 'item_height']:
                    if key in attrs:
                        val = attrs[key]
                        if isinstance(val, list) and val:
                            dim_val = val[0].get('value', '') if isinstance(val[0], dict) else str(val[0])
                            parsed = self._parse_dimension(dim_val)
                            if parsed:
                                dims[key.replace('item_', '')] = parsed

                # Weight
                if 'item_weight' in attrs:
                    val = attrs['item_weight']
                    if isinstance(val, list) and val:
                        weight_val = val[0].get('value', '') if isinstance(val[0], dict) else str(val[0])
                        parsed = self._parse_weight(weight_val)
                        if parsed:
                            dims['weight'] = parsed

        # Validar mínimos
        if dims.get('length') and dims['length'] < Config.MIN_PACKAGE_DIM:
            dims['length'] = Config.MIN_PACKAGE_DIM
        if dims.get('width') and dims['width'] < Config.MIN_PACKAGE_DIM:
            dims['width'] = Config.MIN_PACKAGE_DIM
        if dims.get('height') and dims['height'] < Config.MIN_PACKAGE_DIM:
            dims['height'] = Config.MIN_PACKAGE_DIM
        if dims.get('weight') and dims['weight'] < Config.MIN_PACKAGE_WEIGHT:
            dims['weight'] = Config.MIN_PACKAGE_WEIGHT

        return dims

    def _parse_dimension(self, value: Any) -> Optional[float]:
        """Parsea una dimensión a cm"""
        if not value:
            return None

        value_str = str(value).lower()

        # Extraer número
        match = re.search(r'([\d.]+)', value_str)
        if not match:
            return None

        number = float(match.group(1))

        # Convertir unidades
        if 'inch' in value_str or 'in' in value_str or '"' in value_str:
            number = number * 2.54  # inches to cm
        elif 'm' in value_str and 'cm' not in value_str and 'mm' not in value_str:
            number = number * 100  # meters to cm
        elif 'mm' in value_str:
            number = number / 10  # mm to cm
        # Si es cm o sin unidad, dejar como está

        return round(number, 2)

    def _parse_weight(self, value: Any) -> Optional[float]:
        """Parsea un peso a gramos"""
        if not value:
            return None

        value_str = str(value).lower()

        # Extraer número
        match = re.search(r'([\d.]+)', value_str)
        if not match:
            return None

        number = float(match.group(1))

        # Convertir unidades
        if 'kg' in value_str or 'kilogram' in value_str:
            number = number * 1000  # kg to g
        elif 'lb' in value_str or 'pound' in value_str:
            number = number * 453.592  # lb to g
        elif 'oz' in value_str or 'ounce' in value_str:
            number = number * 28.3495  # oz to g
        # Si es g o sin unidad, dejar como está

        return round(number, 2)

    def _extract_brand(self, amazon_json: Dict) -> Optional[str]:
        """Extrae marca del JSON"""
        brand = (amazon_json.get('brand') or
                amazon_json.get('manufacturer') or
                amazon_json.get('brandName') or '')

        if not brand and amazon_json.get('attributes'):
            attrs = amazon_json['attributes']
            if isinstance(attrs, dict):
                brand_list = attrs.get('brand', [])
                if brand_list and isinstance(brand_list, list):
                    brand = brand_list[0].get('value', '') if isinstance(brand_list[0], dict) else str(brand_list[0])

        return brand if brand else None

    def _extract_model(self, amazon_json: Dict) -> Optional[str]:
        """Extrae modelo del JSON"""
        model = (amazon_json.get('model') or
                amazon_json.get('model_number') or
                amazon_json.get('modelNumber') or '')

        if not model and amazon_json.get('attributes'):
            attrs = amazon_json['attributes']
            if isinstance(attrs, dict):
                model_list = attrs.get('model_number', []) or attrs.get('part_number', [])
                if model_list and isinstance(model_list, list):
                    model = model_list[0].get('value', '') if isinstance(model_list[0], dict) else str(model_list[0])

        return model if model else None

    def _fill_with_ai(
        self,
        amazon_json: Dict,
        category_id: str,
        category_name: str,
        schema: Dict,
        missing_attrs: List[str]
    ) -> Dict[str, Any]:
        """Completa atributos faltantes con IA"""

        # Preparar contexto del producto
        title = amazon_json.get('title') or amazon_json.get('product_title', '')
        description = amazon_json.get('description', '')[:500]
        brand = self._extract_brand(amazon_json) or 'N/A'
        features = []

        if amazon_json.get('attributes', {}).get('bullet_point'):
            bullets = amazon_json['attributes']['bullet_point']
            features = [b.get('value', '') if isinstance(b, dict) else str(b) for b in bullets[:5]]

        # Preparar información del schema para los atributos faltantes
        schema_info = []
        for attr_id in missing_attrs:
            if attr_id in schema:
                attr = schema[attr_id]
                info = f"\n- {attr_id} ({attr['name']}): tipo={attr['value_type']}"
                if attr['values']:
                    # Mostrar solo primeras 5 opciones
                    options = list(attr['values'].items())[:5]
                    info += f", opciones={dict(options)}"
                schema_info.append(info)

        schema_text = ''.join(schema_info)

        # Construir prompt
        prompt = f"""Eres un experto en completar atributos de productos para MercadoLibre.

PRODUCTO AMAZON:
- Título: {title}
- Descripción: {description}
- Marca: {brand}
- Características: {', '.join(features)}

CATEGORÍA ML: {category_id} - {category_name}

ATRIBUTOS OBLIGATORIOS FALTANTES:
{schema_text}

INSTRUCCIONES:
1. Para cada atributo faltante, extrae el valor del producto Amazon
2. Si el atributo es de tipo "list", elige el value_id Y value_name correctos del schema
3. Si es "string", escribe el valor textual
4. Si no puedes determinar el valor:
   - BRAND → "Generic"
   - MODEL → extraer del título o usar marca + tipo producto
   - COLOR → extraer del título o usar "Multicolor"
   - MATERIAL → extraer de características o usar "Mixed"
   - Dimensiones → estimar valores razonables (min: length/width/height >= 3 cm, weight >= 50 g)
   - Otros → valor por defecto razonable

REGLAS CRÍTICAS:
- Para dimensiones: SIEMPRE incluir unidad (ej: "10 cm", "500 g")
- Para list values: SIEMPRE incluir tanto value_id como value_name si están en el schema
- Para BRAND: si no hay marca, usar "Generic"
- Para WARRANTY: usar tipo "Seller warranty" y tiempo "30 days"

FORMATO DE RESPUESTA (JSON válido, sin texto adicional):
{{
  "BRAND": {{"id": "BRAND", "value_name": "Generic"}},
  "MODEL": {{"id": "MODEL", "value_name": "ABC-123"}},
  "COLOR": {{"id": "COLOR", "value_name": "Blue"}},
  "PACKAGE_LENGTH": {{"id": "PACKAGE_LENGTH", "value_name": "20 cm"}},
  "PACKAGE_WIDTH": {{"id": "PACKAGE_WIDTH", "value_name": "15 cm"}},
  "PACKAGE_HEIGHT": {{"id": "PACKAGE_HEIGHT", "value_name": "5 cm"}},
  "PACKAGE_WEIGHT": {{"id": "PACKAGE_WEIGHT", "value_name": "500 g"}}
}}

Responde SOLO con el JSON, sin explicaciones adicionales."""

        try:
            response = self.client.chat.completions.create(
                model=Config.AI_MODEL,
                temperature=Config.AI_TEMPERATURE,
                max_tokens=Config.AI_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content.strip()

            # Parsear JSON
            completed_attrs = json.loads(content)

            print(f"    🤖 IA completó {len(completed_attrs)} atributos")

            return completed_attrs

        except json.JSONDecodeError as e:
            print(f"    ⚠️  Error parseando respuesta IA: {e}")
            return self._get_fallback_attributes(missing_attrs)
        except Exception as e:
            print(f"    ⚠️  Error en IA: {e}")
            return self._get_fallback_attributes(missing_attrs)

    def _get_fallback_attributes(self, missing_attrs: List[str]) -> Dict[str, Any]:
        """Valores fallback para atributos faltantes"""
        fallbacks = {}

        for attr_id in missing_attrs:
            if attr_id == 'BRAND':
                fallbacks['BRAND'] = {'id': 'BRAND', 'value_name': 'Generic'}
            elif attr_id == 'MODEL':
                fallbacks['MODEL'] = {'id': 'MODEL', 'value_name': 'Standard'}
            elif attr_id == 'PACKAGE_LENGTH':
                fallbacks['PACKAGE_LENGTH'] = {'id': 'PACKAGE_LENGTH', 'value_name': '20 cm'}
            elif attr_id == 'PACKAGE_WIDTH':
                fallbacks['PACKAGE_WIDTH'] = {'id': 'PACKAGE_WIDTH', 'value_name': '15 cm'}
            elif attr_id == 'PACKAGE_HEIGHT':
                fallbacks['PACKAGE_HEIGHT'] = {'id': 'PACKAGE_HEIGHT', 'value_name': '5 cm'}
            elif attr_id == 'PACKAGE_WEIGHT':
                fallbacks['PACKAGE_WEIGHT'] = {'id': 'PACKAGE_WEIGHT', 'value_name': '500 g'}

        return fallbacks


# ═══════════════════════════════════════════════════════════════════════════
# 8. PRICING CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════

class PricingCalculator:
    """Calcula net proceeds según modelo de negocio"""

    def __init__(self, db: PipelineDatabase):
        self.db = db

    def calculate_net_proceeds(self, asin: str, amazon_json: Dict) -> PriceResult:
        """Calcula net proceeds desde Amazon price + tax"""

        # 1. Extraer precio de Amazon
        price_amazon = self._extract_price(amazon_json)

        if not price_amazon or price_amazon <= 0:
            raise ValueError(f"Precio inválido en JSON de Amazon: {price_amazon}")

        # 2. Extraer tax
        tax_usd = self._extract_tax(amazon_json)

        # 3. Calcular costo total
        cost_usd = price_amazon + tax_usd

        # 4. Aplicar markup
        markup_percent = Config.PRICE_MARKUP
        net_proceeds_usd = cost_usd * (1 + markup_percent / 100)
        net_proceeds_usd = round(net_proceeds_usd, 2)

        # 5. Validar mínimo
        if net_proceeds_usd < Config.MIN_NET_PROCEEDS:
            self.db.log(asin, "pricing",
                       f"Net proceeds {net_proceeds_usd} < mínimo {Config.MIN_NET_PROCEEDS}",
                       "WARNING")
            net_proceeds_usd = Config.MIN_NET_PROCEEDS

        return PriceResult(
            price_amazon=price_amazon,
            tax_usd=tax_usd,
            cost_usd=cost_usd,
            markup_percent=markup_percent,
            net_proceeds_usd=net_proceeds_usd
        )

    def _extract_price(self, amazon_json: Dict) -> float:
        """Extrae precio de Amazon del JSON"""
        # Buscar en varios campos posibles
        price = None

        # Campo directo
        if amazon_json.get('price'):
            p = amazon_json['price']
            if isinstance(p, dict):
                price = p.get('value') or p.get('amount')
            elif isinstance(p, (int, float)):
                price = p
            elif isinstance(p, str):
                # Parsear string "$19.99"
                match = re.search(r'([\d.]+)', str(p))
                if match:
                    price = float(match.group(1))

        # list_price
        if not price and amazon_json.get('list_price'):
            p = amazon_json['list_price']
            if isinstance(p, dict):
                price = p.get('value') or p.get('amount')
            elif isinstance(p, (int, float)):
                price = p

        # summaries > main_price
        if not price and amazon_json.get('summaries'):
            summaries = amazon_json['summaries']
            if isinstance(summaries, list) and summaries:
                main = summaries[0].get('main_price')
                if main:
                    price = main.get('value') or main.get('amount')

        # attributes > list_price
        if not price and amazon_json.get('attributes'):
            attrs = amazon_json['attributes']
            if isinstance(attrs, dict):
                list_price_attr = attrs.get('list_price', [])
                if list_price_attr and isinstance(list_price_attr, list):
                    price_val = list_price_attr[0].get('value', '') if isinstance(list_price_attr[0], dict) else str(list_price_attr[0])
                    match = re.search(r'([\d.]+)', str(price_val))
                    if match:
                        price = float(match.group(1))

        return float(price) if price else 0.0

    def _extract_tax(self, amazon_json: Dict) -> float:
        """Extrae tax del JSON de Amazon"""
        tax = 0.0

        # Buscar en varios campos
        if amazon_json.get('tax'):
            t = amazon_json['tax']
            if isinstance(t, dict):
                tax = t.get('value') or t.get('amount') or 0
            elif isinstance(t, (int, float)):
                tax = t

        if not tax and amazon_json.get('estimated_tax'):
            t = amazon_json['estimated_tax']
            if isinstance(t, dict):
                tax = t.get('value') or t.get('amount') or 0
            elif isinstance(t, (int, float)):
                tax = t

        return float(tax) if tax else 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 9. PRE-PUBLISH VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

class PrePublishValidator:
    """Validación exhaustiva pre-publicación"""

    @staticmethod
    def validate_all(mini_ml: Dict) -> ValidationResult:
        """Ejecuta todas las validaciones"""
        errors = []
        warnings = []

        # 1. Validar imágenes
        imgs = mini_ml.get('images', [])
        if not imgs:
            errors.append("Sin imágenes")
        elif len(imgs) < 1:
            errors.append("Menos de 1 imagen")

        # 2. Validar dimensiones
        attrs = mini_ml.get('attributes_mapped', {})

        try:
            length = PrePublishValidator._parse_number(attrs.get('PACKAGE_LENGTH', {}).get('value_name', '0'))
            width = PrePublishValidator._parse_number(attrs.get('PACKAGE_WIDTH', {}).get('value_name', '0'))
            height = PrePublishValidator._parse_number(attrs.get('PACKAGE_HEIGHT', {}).get('value_name', '0'))
            weight = PrePublishValidator._parse_number(attrs.get('PACKAGE_WEIGHT', {}).get('value_name', '0'))

            if length < Config.MIN_PACKAGE_DIM:
                errors.append(f"Length {length} < {Config.MIN_PACKAGE_DIM} cm")
            if width < Config.MIN_PACKAGE_DIM:
                errors.append(f"Width {width} < {Config.MIN_PACKAGE_DIM} cm")
            if height < Config.MIN_PACKAGE_DIM:
                errors.append(f"Height {height} < {Config.MIN_PACKAGE_DIM} cm")
            if weight < Config.MIN_PACKAGE_WEIGHT:
                errors.append(f"Weight {weight} < {Config.MIN_PACKAGE_WEIGHT} g")

            # Validar volumen
            volume = (width * height * length) / 5000
            if volume < Config.MIN_VOLUME:
                errors.append(f"Volumen {volume:.4f} < {Config.MIN_VOLUME}")

        except (ValueError, AttributeError) as e:
            errors.append(f"Error parseando dimensiones: {e}")

        # 3. Validar atributos obligatorios
        required = ['BRAND', 'ITEM_CONDITION', 'PACKAGE_HEIGHT', 'PACKAGE_LENGTH',
                   'PACKAGE_WIDTH', 'PACKAGE_WEIGHT', 'SELLER_SKU']

        for attr in required:
            if attr not in attrs:
                errors.append(f"Falta atributo obligatorio: {attr}")
            elif not attrs[attr].get('value_name'):
                errors.append(f"Atributo {attr} sin valor")

        # 4. Validar BRAND no vacío
        brand = attrs.get('BRAND', {}).get('value_name', '')
        if not brand or brand.strip() == '':
            errors.append("BRAND vacío")

        # 5. Validar precio
        price = mini_ml.get('price', {})
        if isinstance(price, dict):
            net_proceeds = price.get('net_proceeds_usd', 0)
            if net_proceeds < Config.MIN_NET_PROCEEDS:
                errors.append(f"Net proceeds {net_proceeds} < {Config.MIN_NET_PROCEEDS}")

        # 6. Validar categoría
        cat_id = mini_ml.get('category_id', '')
        if not cat_id or not cat_id.startswith('CBT'):
            errors.append(f"Categoría inválida: {cat_id}")

        # 7. Validar título
        title = mini_ml.get('title', '')
        if not title:
            errors.append("Título vacío")
        elif len(title) > 60:
            warnings.append(f"Título muy largo: {len(title)} caracteres (max 60)")

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )

    @staticmethod
    def _parse_number(value: str) -> float:
        """Parsea un número de un string como '10 cm' o '500 g'"""
        if not value:
            return 0.0

        match = re.search(r'([\d.]+)', str(value))
        if match:
            return float(match.group(1))
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 10. PUBLISHER
# ═══════════════════════════════════════════════════════════════════════════

class Publisher:
    """Publica productos en MercadoLibre CBT"""

    def __init__(self, ml_token: str, db: PipelineDatabase):
        self.ml_token = ml_token
        self.db = db

    def publish_to_ml(self, asin: str, mini_ml: Dict) -> PublishResult:
        """Publica un producto en ML CBT"""

        # Construir body de publicación
        body = self._build_publish_body(mini_ml, asin)

        # Log del body (solo para debug)
        # print(f"    📤 Body publicación: {json.dumps(body, indent=2)}")

        # Intentar publicar con retry
        for attempt in range(1, Config.MAX_RETRIES + 1):
            try:
                if attempt > 1:
                    self.db.log(asin, "publish", f"Reintento {attempt}/{Config.MAX_RETRIES}", "WARNING")
                    time.sleep(Config.RETRY_DELAY)

                # POST a ML API (endpoint global para CBT)
                url = f"{Config.ML_API_BASE}/global/items"
                headers = {
                    "Authorization": f"Bearer {self.ml_token}",
                    "Content-Type": "application/json"
                }

                response = requests.post(url, json=body, headers=headers, timeout=30)

                # Manejar respuesta
                if response.status_code == 201:
                    # Éxito
                    result = response.json()

                    item_id = result.get('id') or result.get('item_id')
                    site_items = result.get('site_items', [])
                    countries = [s['site_id'] for s in site_items if s.get('item_id')]
                    permalink = result.get('permalink')

                    return PublishResult(
                        success=True,
                        item_id=item_id,
                        countries=countries,
                        site_items=site_items,
                        permalink=permalink
                    )

                elif response.status_code == 429:
                    # Rate limit
                    self.db.log(asin, "publish", "Rate limited - esperando 10s", "WARNING")
                    time.sleep(10)
                    continue

                elif response.status_code == 500:
                    # Server error
                    self.db.log(asin, "publish", "ML server error - reintentando", "WARNING")
                    time.sleep(5)
                    continue

                else:
                    # Error de validación u otro
                    error_data = response.json() if response.text else {}
                    error_msg = self._parse_error_response(error_data)

                    # Log del error completo para debugging
                    print(f"\n❌ ML API ERROR DETAILS:")
                    print(f"   Status: {response.status_code}")
                    print(f"   Response: {json.dumps(error_data, indent=2)[:500]}")

                    return PublishResult(
                        success=False,
                        item_id=None,
                        countries=[],
                        site_items=[],
                        permalink=None,
                        error=f"HTTP {response.status_code}: {error_msg}"
                    )

            except requests.exceptions.Timeout:
                self.db.log(asin, "publish", "Timeout - reintentando", "WARNING")
                if attempt == Config.MAX_RETRIES:
                    return PublishResult(
                        success=False,
                        item_id=None,
                        countries=[],
                        site_items=[],
                        permalink=None,
                        error="Timeout después de 3 intentos"
                    )
                continue

            except Exception as e:
                return PublishResult(
                    success=False,
                    item_id=None,
                    countries=[],
                    site_items=[],
                    permalink=None,
                    error=str(e)
                )

        # Si llegamos aquí, fallaron todos los intentos
        return PublishResult(
            success=False,
            item_id=None,
            countries=[],
            site_items=[],
            permalink=None,
            error="Fallaron todos los reintentos"
        )

    def _build_publish_body(self, mini_ml: Dict, asin: str) -> Dict:
        """
        Construye el body para POST /global/items usando Net Proceeds.
        Referencia: https://developers.mercadolibre.com/en/docs/cross-border-trade-api/items-and-searches/publish-item
        """

        # Extraer datos
        category_id = mini_ml['category_id']
        title = mini_ml.get('title', 'Producto')
        images = mini_ml.get('images', [])
        attributes = mini_ml.get('attributes_mapped', {})
        price = mini_ml.get('price', {})

        # Construir attributes array
        attributes_array = []
        for attr_id, attr_data in attributes.items():
            attr_obj = {'id': attr_id}

            if 'value_id' in attr_data:
                attr_obj['value_id'] = attr_data['value_id']

            if 'value_name' in attr_data:
                attr_obj['value_name'] = attr_data['value_name']

            attributes_array.append(attr_obj)

        # Pictures
        pictures = [{'source': url} for url in images[:10]]  # Max 10 imágenes

        # Net proceeds (lo que el seller quiere recibir en USD)
        net_proceeds_usd = price.get('net_proceeds_usd', 0)

        # Sites to sell - CBT permite publicar en múltiples países simultáneamente
        sites_to_sell = [
            {
                'site_id': 'MLB',  # Brasil
                'logistic_type': 'remote',
                'title': title[:60]
            },
            {
                'site_id': 'MLA',  # Argentina
                'logistic_type': 'remote',
                'title': title[:60]
            },
            {
                'site_id': 'MLC',  # Chile
                'logistic_type': 'remote',
                'title': title[:60]
            },
            {
                'site_id': 'MCO',  # Colombia
                'logistic_type': 'remote',
                'title': title[:60]
            },
            {
                'site_id': 'MLM',  # México
                'logistic_type': 'remote',
                'title': title[:60]
            }
        ]

        # Sale terms (requerido para CBT)
        sale_terms = [
            {
                'id': 'WARRANTY_TYPE',
                'value_id': '2230279',  # Factory warranty
                'value_name': 'Factory warranty'
            },
            {
                'id': 'WARRANTY_TIME',
                'value_name': '90 days'
            }
        ]

        # Body final según formato CBT con Net Proceeds
        body = {
            'global_net_proceeds': net_proceeds_usd,  # ← Formato correcto
            'sites_to_sell': sites_to_sell,
            'currency_id': 'USD',
            'catalog_listing': False,
            'category_id': category_id,
            'sale_terms': sale_terms,
            'title': title[:60],
            'available_quantity': 999,
            'pictures': pictures,
            'attributes': attributes_array,
            'seller_custom_field': asin
        }

        return body

    def _parse_error_response(self, error_data: Dict) -> str:
        """Parsea el error de ML para obtener mensaje legible"""
        if not error_data:
            return "Error desconocido"

        # ML retorna errores en varios formatos
        if 'message' in error_data:
            return error_data['message']

        if 'error' in error_data:
            return error_data['error']

        if 'cause' in error_data:
            causes = error_data['cause']
            if isinstance(causes, list):
                return ', '.join([c.get('message', str(c)) for c in causes])
            return str(causes)

        return str(error_data)


# ═══════════════════════════════════════════════════════════════════════════
# 11. MAIN PIPELINE (ORQUESTADOR)
# ═══════════════════════════════════════════════════════════════════════════

class MainPipeline:
    """Orquestador principal del pipeline"""

    def __init__(self):
        # Setup
        Config.setup_directories()

        # Validar configuración
        errors = Config.validate()
        if errors:
            for error in errors:
                print(f"❌ {error}")
            raise RuntimeError("Configuración inválida")

        # Inicializar componentes
        self.db = PipelineDatabase(Config.DB_PATH)
        self.data_loader = DataLoader()
        self.category_detector = CategoryDetector(self.db)
        self.schema_manager = SchemaManager(Config.SCHEMAS_DIR, Config.ML_ACCESS_TOKEN)

        # OpenAI client
        openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.attribute_filler = AttributeFiller(openai_client, self.db)

        self.pricing_calculator = PricingCalculator(self.db)
        self.publisher = Publisher(Config.ML_ACCESS_TOKEN, self.db)

    def run(self, asins: List[str]) -> Dict[str, List[str]]:
        """Ejecuta el pipeline completo"""

        print("\n" + "="*70)
        print("🚀 MAINFINAL PIPELINE - INICIANDO")
        print("="*70)
        print(f"📋 ASINs a procesar: {len(asins)}")
        print(f"💰 Markup configurado: {Config.PRICE_MARKUP}%")
        print(f"🤖 IA: {Config.AI_MODEL}")
        print(f"🌍 Target: CBT (Brasil, Argentina, Chile, Colombia, México)")
        print("="*70 + "\n")

        results = {
            'success': [],
            'failed': []
        }

        start_time = time.time()

        for i, asin in enumerate(asins, 1):
            print(f"\n[{i}/{len(asins)}] 📦 {asin}")
            print("-" * 70)

            try:
                success = self._process_asin(asin)

                if success:
                    results['success'].append(asin)
                else:
                    results['failed'].append(asin)

                # Rate limiting entre productos
                if i < len(asins):
                    time.sleep(Config.PUBLISH_DELAY)

            except KeyboardInterrupt:
                print("\n\n⚠️  Interrumpido por usuario")
                break

            except Exception as e:
                print(f"  ❌ Error crítico: {e}")
                traceback.print_exc()
                results['failed'].append(asin)
                self.db.update_status(asin, 'error', error_message=str(e))

        # Reporte final
        elapsed = time.time() - start_time
        self._print_final_report(results, elapsed)

        return results

    def _process_asin(self, asin: str) -> bool:
        """Procesa un ASIN completo"""

        # FASE 1: Cargar JSON de Amazon
        try:
            amazon_json = self.data_loader.load_amazon_json(asin, Config.AMAZON_JSON_DIR)
            # Extraer título desde múltiples ubicaciones
            title = amazon_json.get('title') or amazon_json.get('product_title', '')
            if not title and amazon_json.get('attributes', {}).get('item_name'):
                item_name = amazon_json['attributes']['item_name']
                if isinstance(item_name, list) and item_name:
                    title = item_name[0].get('value', '') if isinstance(item_name[0], dict) else str(item_name[0])
            self.db.log(asin, "load", f"JSON cargado: {title[:50]}...", "SUCCESS")
        except FileNotFoundError:
            self.db.log(asin, "load", "JSON no encontrado", "ERROR")
            self.db.update_status(asin, 'failed', error_message="JSON no encontrado")
            return False
        except Exception as e:
            self.db.log(asin, "load", f"Error: {e}", "ERROR")
            self.db.update_status(asin, 'failed', error_message=str(e))
            return False

        # FASE 2: Detectar categoría
        try:
            self.db.log(asin, "category", "Detectando categoría...", "INFO")
            category_result = self.category_detector.detect_category(asin, amazon_json)
            self.db.log(asin, "category",
                       f"{category_result.category_id} ({category_result.category_name}) [confidence: {category_result.confidence:.2f}]",
                       "SUCCESS")
            self.db.update_status(asin, 'category_detected',
                                 category_id=category_result.category_id,
                                 category_name=category_result.category_name)
        except Exception as e:
            self.db.log(asin, "category", f"Error: {e}", "ERROR")
            self.db.update_status(asin, 'failed', error_message=f"Category detection: {e}")
            return False

        # FASE 3: Obtener schema
        try:
            schema = self.schema_manager.get_category_schema(category_result.category_id)
            if not schema:
                raise ValueError("Schema vacío")

            required_count = len(self.schema_manager.parse_required_attributes(schema))
            self.db.log(asin, "schema",
                       f"Schema obtenido: {len(schema)} atributos ({required_count} obligatorios)",
                       "SUCCESS")
        except Exception as e:
            self.db.log(asin, "schema", f"Error: {e}", "ERROR")
            self.db.update_status(asin, 'failed', error_message=f"Schema fetch: {e}")
            return False

        # FASE 4: Llenar atributos
        try:
            self.db.log(asin, "attributes", "Llenando atributos con IA...", "INFO")
            attributes = self.attribute_filler.fill_all_attributes(
                asin,
                amazon_json,
                category_result.category_id,
                category_result.category_name,
                schema
            )

            required = self.schema_manager.parse_required_attributes(schema)
            filled_required = sum(1 for r in required if r in attributes)
            optional_count = len(attributes) - filled_required

            self.db.log(asin, "attributes",
                       f"Atributos completados: {filled_required}/{len(required)} required + {optional_count} opcionales",
                       "SUCCESS")
        except Exception as e:
            self.db.log(asin, "attributes", f"Error: {e}", "ERROR")
            self.db.update_status(asin, 'failed', error_message=f"Attribute filling: {e}")
            return False

        # FASE 5: Calcular precio
        try:
            price_result = self.pricing_calculator.calculate_net_proceeds(asin, amazon_json)
            self.db.log(asin, "pricing",
                       f"${price_result.price_amazon} + ${price_result.tax_usd} tax = ${price_result.cost_usd} → net proceeds ${price_result.net_proceeds_usd} ({price_result.markup_percent}%)",
                       "SUCCESS")
            self.db.save_price(asin, price_result)
        except Exception as e:
            self.db.log(asin, "pricing", f"Error: {e}", "ERROR")
            self.db.update_status(asin, 'failed', error_message=f"Price calculation: {e}")
            return False

        # FASE 6: Construir mini_ml
        images = self._extract_images(amazon_json)

        mini_ml = {
            'asin': asin,
            'category_id': category_result.category_id,
            'category_name': category_result.category_name,
            'title': title[:60],
            'images': images,
            'attributes_mapped': attributes,
            'price': {
                'price_amazon': price_result.price_amazon,
                'tax_usd': price_result.tax_usd,
                'cost_usd': price_result.cost_usd,
                'markup_percent': price_result.markup_percent,
                'net_proceeds_usd': price_result.net_proceeds_usd
            }
        }

        # FASE 7: Validación pre-publicación
        validation = PrePublishValidator.validate_all(mini_ml)

        if not validation.is_valid:
            error_msg = f"Validación fallida: {', '.join(validation.errors)}"
            self.db.log(asin, "validation", error_msg, "ERROR")
            self.db.update_status(asin, 'validation_failed', error_message=error_msg)
            return False

        if validation.warnings:
            for warning in validation.warnings:
                self.db.log(asin, "validation", warning, "WARNING")

        self.db.log(asin, "validation", "PASSED (0 errors)", "SUCCESS")

        # FASE 8: Publicar
        try:
            self.db.log(asin, "publish", "Publicando en ML CBT...", "INFO")
            publish_result = self.publisher.publish_to_ml(asin, mini_ml)

            if publish_result.success:
                self.db.log(asin, "publish",
                           f"PUBLICADO: {publish_result.item_id}", "SUCCESS")

                # Log países
                for site_item in publish_result.site_items:
                    if site_item.get('item_id'):
                        self.db.log(asin, "publish",
                                   f"  → {site_item['site_id']}: {site_item['item_id']}", "INFO")

                self.db.update_status(asin, 'published',
                                     item_id=publish_result.item_id,
                                     countries=publish_result.countries)
                return True
            else:
                self.db.log(asin, "publish", f"Error: {publish_result.error}", "ERROR")
                self.db.update_status(asin, 'publish_failed', error_message=publish_result.error)
                return False

        except Exception as e:
            self.db.log(asin, "publish", f"Error: {e}", "ERROR")
            self.db.update_status(asin, 'publish_error', error_message=str(e))
            return False

    def _extract_images(self, amazon_json: Dict) -> List[str]:
        """
        Extrae URLs de imágenes del JSON de Amazon.
        Solo devuelve la imagen de mayor resolución por variante.
        """
        from collections import OrderedDict

        images_raw = []  # (variant, url, width, height, order_index)
        order = 0

        # Extraer imágenes de la estructura SP-API
        imgs = amazon_json.get("images") or []
        for item in imgs:
            if isinstance(item, dict):
                # Caso SP-API: {"marketplaceId": "...", "images": [{...}]}
                inner = item.get("images")
                if isinstance(inner, list):
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get("link"):
                            w = sub.get("width") or 0
                            h = sub.get("height") or 0
                            variant = sub.get("variant") or "MAIN"
                            images_raw.append((variant, sub["link"], w, h, order))
                            order += 1

        if not images_raw:
            return []

        # Agrupar por variante y elegir la de mayor resolución
        best_by_variant = OrderedDict()
        for variant, url, w, h, idx in images_raw:
            if variant not in best_by_variant:
                best_by_variant[variant] = (url, w, h, idx)
            else:
                old_url, old_w, old_h, old_idx = best_by_variant[variant]
                # Si la nueva tiene mayor resolución, reemplazar
                if (w * h) > (old_w * old_h):
                    best_by_variant[variant] = (url, w, h, idx)

        # Devolver solo las URLs (orden original por aparición de variante)
        return [data[0] for variant, data in best_by_variant.items()][:10]

    def _print_final_report(self, results: Dict, elapsed: float):
        """Imprime reporte final"""
        total = len(results['success']) + len(results['failed'])
        success_rate = (len(results['success']) / total * 100) if total > 0 else 0

        print("\n" + "="*70)
        print("📊 REPORTE FINAL")
        print("="*70)
        print(f"⏱️  Tiempo total: {elapsed/60:.1f} minutos")
        print(f"📦 Total procesados: {total}")
        print(f"✅ Publicados exitosamente: {len(results['success'])} ({success_rate:.1f}%)")
        print(f"❌ Fallidos: {len(results['failed'])} ({100-success_rate:.1f}%)")

        # Emoji según success rate
        if success_rate >= 95:
            print("\n🎉 EXCELENTE! Success rate >= 95%")
        elif success_rate >= 80:
            print("\n👍 BUENO - Success rate >= 80%")
        elif success_rate >= 50:
            print("\n⚠️  ACEPTABLE - Success rate >= 50%")
        else:
            print("\n❌ NECESITA MEJORAS - Success rate < 50%")

        # Estadísticas de DB
        stats = self.db.get_statistics()
        print(f"\n📈 ESTADÍSTICAS:")
        print(f"   Total en DB: {stats['total']}")

        if stats['status_counts']:
            for status, count in sorted(stats['status_counts'].items()):
                print(f"   {status}: {count}")

        if stats['top_categories']:
            print(f"\n🏆 TOP CATEGORÍAS:")
            for cat_name, count in stats['top_categories'].items():
                print(f"   {cat_name}: {count} productos")

        print(f"\n💰 Precio promedio net proceeds: ${stats['avg_net_proceeds']:.2f} USD")

        # ASINs fallidos
        if results['failed']:
            print(f"\n⚠️  ASINs fallidos:")
            for asin in results['failed'][:10]:
                print(f"   • {asin}")
            if len(results['failed']) > 10:
                print(f"   ... y {len(results['failed']) - 10} más")

        print("="*70 + "\n")

        # Guardar reporte JSON
        report_path = Config.REPORTS_DIR / f"mainfinal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'elapsed_seconds': elapsed,
                'success_rate': success_rate,
                'results': results,
                'statistics': stats
            }, f, indent=2)

        print(f"📄 Reporte guardado: {report_path}\n")


# ═══════════════════════════════════════════════════════════════════════════
# 12. MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """Entry point"""

    try:
        # Crear pipeline
        pipeline = MainPipeline()

        # Cargar ASINs
        asins = pipeline.data_loader.load_asins_from_file(Config.ASINS_FILE)

        if not asins:
            print("❌ No hay ASINs para procesar")
            return 1

        # Ejecutar
        results = pipeline.run(asins)

        # Exit code según success rate
        total = len(results['success']) + len(results['failed'])
        success_rate = (len(results['success']) / total * 100) if total > 0 else 0

        if success_rate >= 95:
            return 0  # Excelente
        elif success_rate >= 70:
            return 2  # Aceptable
        else:
            return 1  # Necesita mejoras

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrumpido por usuario")
        return 130

    except Exception as e:
        print(f"\n\n❌ Error fatal: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
