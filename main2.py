#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main2.py - Pipeline Profesional Amazon → MercadoLibre CBT
═══════════════════════════════════════════════════════════════════════════════
Pipeline completo con validación IA, retry inteligente y tracking de estado.

Flujo optimizado:
1. Pre-flight checks (credenciales, conexión, rate limits)
2. Download: Descarga datos de Amazon SP-API con retry
3. Transform: Transforma con IA + validación completa
4. Validate: Validación IA de imágenes y categorías
5. Publish: Publicación en MercadoLibre CBT con retry inteligente
6. Sync: Sincronización multi-marketplace

Características:
- ✅ Validación IA pre-publicación (imágenes + categorías)
- ✅ Retry inteligente con estrategias diferentes
- ✅ Base de datos SQLite para tracking
- ✅ Health checks automáticos
- ✅ Rate limiting inteligente
- ✅ Logs detallados por fase
- ✅ Modo dry-run para testing
- ✅ Recuperación de errores automática
- ✅ Reportes detallados con estadísticas

Autor: Pipeline v2.0 Optimizado
Fecha: 2025-01-03
"""

import os
import sys
import json
import time
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
from dotenv import load_dotenv
import traceback

# ═══════════════════════════════════════════════════════════════════════════
# AUTO-ACTIVACIÓN DE VENV
# ═══════════════════════════════════════════════════════════════════════════

# DISABLED: Causing issues with background execution
# if sys.prefix == sys.base_prefix:
#     vpy = Path(__file__).parent / "venv" / "bin" / "python"
#     if vpy.exists():
#         print(f"⚙️  Activando entorno virtual: {vpy}")
#         os.execv(str(vpy), [str(vpy)] + sys.argv)

load_dotenv(override=True)

# ═══════════════════════════════════════════════════════════════════════════
# IMPORTS DE MÓDULOS PROPIOS
# ═══════════════════════════════════════════════════════════════════════════

from src.amazon_api import get_product_data_from_asin
from src.transform_mapper_new import build_mini_ml, load_json_file, save_json_file
from src.unified_transformer import transform_amazon_to_ml_unified
from src.ai_validators import validate_listing_complete
from src.smart_categorizer import categorize_with_ai
from src.mainglobal import publish_item
from src.auto_fixer import auto_fix

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════

class Config:
    """Configuración centralizada del pipeline"""

    # Directorios
    ASINS_FILE = Path("resources/asins.txt")
    AMAZON_JSON_DIR = Path("storage/asins_json")
    MINI_ML_DIR = Path("storage/logs/publish_ready")
    OUTPUT_JSON_DIR = Path("outputs/json")
    LOGS_DIR = Path("storage/logs/pipeline")
    DB_PATH = Path("storage/pipeline_state.db")

    # Retry configuration
    MAX_DOWNLOAD_RETRIES = 3
    MAX_TRANSFORM_RETRIES = 2
    MAX_PUBLISH_RETRIES = 3

    # Delays (seconds)
    RETRY_DELAY = 5
    PUBLISH_DELAY = 3
    RATE_LIMIT_DELAY = 10

    # Flags
    DRY_RUN = False
    SKIP_VALIDATION = False
    FORCE_REGENERATE = False

    @classmethod
    def setup_directories(cls):
        """Crea todos los directorios necesarios"""
        for path in [cls.AMAZON_JSON_DIR, cls.MINI_ML_DIR,
                     cls.OUTPUT_JSON_DIR, cls.LOGS_DIR]:
            path.mkdir(parents=True, exist_ok=True)
        cls.DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class Status(Enum):
    """Estados del pipeline"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    TRANSFORMING = "transforming"
    TRANSFORMED = "transformed"
    VALIDATING = "validating"
    VALIDATED = "validated"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    SKIPPED = "skipped"


# ═══════════════════════════════════════════════════════════════════════════
# BASE DE DATOS Y TRACKING
# ═══════════════════════════════════════════════════════════════════════════

class PipelineDB:
    """Gestión de base de datos para tracking del pipeline"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Inicializa la base de datos y tablas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT,
                completed_at TEXT,
                total_asins INTEGER,
                success_count INTEGER,
                failed_count INTEGER,
                status TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS asin_status (
                asin TEXT PRIMARY KEY,
                status TEXT,
                last_error TEXT,
                retry_count INTEGER DEFAULT 0,
                download_attempts INTEGER DEFAULT 0,
                transform_attempts INTEGER DEFAULT 0,
                publish_attempts INTEGER DEFAULT 0,
                item_id TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asin TEXT,
                phase TEXT,
                message TEXT,
                level TEXT,
                timestamp TEXT
            )
        """)

        conn.commit()
        conn.close()

    def create_run(self, run_id: str, total_asins: int) -> None:
        """Crea un nuevo registro de ejecución"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO pipeline_runs
            (run_id, started_at, total_asins, success_count, failed_count, status)
            VALUES (?, ?, ?, 0, 0, 'running')
        """, (run_id, datetime.now().isoformat(), total_asins))

        conn.commit()
        conn.close()

    def update_asin_status(self, asin: str, status: Status,
                          error: Optional[str] = None,
                          item_id: Optional[str] = None) -> None:
        """Actualiza el estado de un ASIN"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO asin_status (asin, status, last_error, item_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(asin) DO UPDATE SET
                status = excluded.status,
                last_error = excluded.last_error,
                item_id = excluded.item_id,
                updated_at = excluded.updated_at
        """, (asin, status.value, error, item_id,
              datetime.now().isoformat(), datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def increment_retry(self, asin: str, phase: str) -> int:
        """Incrementa el contador de reintentos y retorna el nuevo valor"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        field = f"{phase}_attempts"
        cursor.execute(f"""
            UPDATE asin_status
            SET {field} = {field} + 1,
                retry_count = retry_count + 1,
                updated_at = ?
            WHERE asin = ?
        """, (datetime.now().isoformat(), asin))

        cursor.execute(f"""
            SELECT {field} FROM asin_status WHERE asin = ?
        """, (asin,))

        result = cursor.fetchone()
        conn.commit()
        conn.close()

        return result[0] if result else 0

    def log(self, asin: str, phase: str, message: str, level: str = "INFO") -> None:
        """Registra un log en la base de datos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO logs (asin, phase, message, level, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (asin, phase, message, level, datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def get_asin_status(self, asin: str) -> Optional[Dict]:
        """Obtiene el estado actual de un ASIN"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT asin, status, last_error, retry_count, item_id
            FROM asin_status WHERE asin = ?
        """, (asin,))

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                "asin": result[0],
                "status": result[1],
                "last_error": result[2],
                "retry_count": result[3],
                "item_id": result[4]
            }
        return None

    def get_statistics(self) -> Dict:
        """Obtiene estadísticas del pipeline"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT status, COUNT(*)
            FROM asin_status
            GROUP BY status
        """)

        stats = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()

        return stats


# ═══════════════════════════════════════════════════════════════════════════
# HEALTH CHECKS Y PRE-FLIGHT
# ═══════════════════════════════════════════════════════════════════════════

class HealthChecker:
    """Verificación de salud del sistema antes de iniciar"""

    @staticmethod
    def check_credentials() -> Tuple[bool, List[str]]:
        """Verifica que todas las credenciales necesarias estén configuradas"""
        errors = []

        if not os.getenv("ML_ACCESS_TOKEN"):
            errors.append("❌ Falta ML_ACCESS_TOKEN en .env")

        if not os.getenv("AMZ_CLIENT_ID"):
            errors.append("❌ Faltan credenciales de Amazon SP-API")

        if not os.getenv("OPENAI_API_KEY"):
            errors.append("⚠️  Sin OPENAI_API_KEY (algunas funciones IA no estarán disponibles)")

        return len(errors) == 0, errors

    @staticmethod
    def check_api_connectivity() -> Tuple[bool, List[str]]:
        """Verifica conectividad con APIs"""
        import requests
        errors = []

        # Check MercadoLibre API
        try:
            token = os.getenv("ML_ACCESS_TOKEN")
            response = requests.get(
                "https://api.mercadolibre.com/users/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            if response.status_code != 200:
                errors.append(f"❌ ML API error: {response.status_code}")
        except Exception as e:
            errors.append(f"❌ No se puede conectar a ML API: {e}")

        # Check OpenAI API
        if os.getenv("OPENAI_API_KEY"):
            try:
                from openai import OpenAI
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                # Simple test call
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=5
                )
                if not response:
                    errors.append("❌ OpenAI API no responde correctamente")
            except Exception as e:
                errors.append(f"❌ Error OpenAI API: {e}")

        return len(errors) == 0, errors

    @staticmethod
    def run_all_checks() -> bool:
        """Ejecuta todas las verificaciones de salud"""
        print("\n" + "="*70)
        print("🏥 PRE-FLIGHT HEALTH CHECKS")
        print("="*70 + "\n")

        all_ok = True

        # Check credentials
        print("🔑 Verificando credenciales...")
        creds_ok, creds_errors = HealthChecker.check_credentials()
        if creds_ok:
            print("   ✅ Todas las credenciales configuradas")
        else:
            all_ok = False
            for error in creds_errors:
                print(f"   {error}")

        # Check API connectivity
        print("\n🌐 Verificando conectividad API...")
        api_ok, api_errors = HealthChecker.check_api_connectivity()
        if api_ok:
            print("   ✅ Todas las APIs disponibles")
        else:
            all_ok = False
            for error in api_errors:
                print(f"   {error}")

        # Check directories
        print("\n📁 Verificando directorios...")
        Config.setup_directories()
        print("   ✅ Todos los directorios creados")

        print("\n" + "="*70)
        if all_ok:
            print("✅ TODOS LOS CHECKS PASARON - SISTEMA LISTO")
        else:
            print("❌ ALGUNOS CHECKS FALLARON - REVISAR CONFIGURACIÓN")
        print("="*70 + "\n")

        return all_ok


# ═══════════════════════════════════════════════════════════════════════════
# PIPELINE PHASES
# ═══════════════════════════════════════════════════════════════════════════

class PipelinePhase:
    """Clase base para las fases del pipeline"""

    def __init__(self, db: PipelineDB):
        self.db = db

    def log(self, asin: str, message: str, level: str = "INFO"):
        """Log helper"""
        phase = self.__class__.__name__.replace("Phase", "").lower()
        self.db.log(asin, phase, message, level)

        # También imprimir en consola
        icon = {"INFO": "ℹ️", "ERROR": "❌", "WARNING": "⚠️", "SUCCESS": "✅"}.get(level, "📝")
        print(f"{icon} [{phase}] {asin}: {message}")


class DownloadPhase(PipelinePhase):
    """Fase de descarga desde Amazon SP-API"""

    def execute(self, asin: str) -> bool:
        """Descarga datos de Amazon para un ASIN"""
        json_path = Config.AMAZON_JSON_DIR / f"{asin}.json"

        # Si ya existe y no es force regenerate, skip
        if json_path.exists() and not Config.FORCE_REGENERATE:
            self.log(asin, "Ya descargado, saltando...", "INFO")
            self.db.update_asin_status(asin, Status.DOWNLOADED)
            return True

        max_retries = Config.MAX_DOWNLOAD_RETRIES

        for attempt in range(1, max_retries + 1):
            try:
                self.db.update_asin_status(asin, Status.DOWNLOADING)
                retry_num = self.db.increment_retry(asin, "download")

                if attempt > 1:
                    self.log(asin, f"Reintento {attempt}/{max_retries}", "WARNING")
                    time.sleep(Config.RETRY_DELAY * attempt)  # Exponential backoff

                self.log(asin, "Descargando desde Amazon SP-API...", "INFO")
                get_product_data_from_asin(asin, save_path=str(json_path))

                if json_path.exists():
                    self.log(asin, "Descarga exitosa", "SUCCESS")
                    self.db.update_asin_status(asin, Status.DOWNLOADED)
                    return True
                else:
                    raise Exception("Archivo no creado después de descarga")

            except Exception as e:
                error_msg = str(e)
                self.log(asin, f"Error en intento {attempt}: {error_msg}", "ERROR")

                if attempt == max_retries:
                    self.db.update_asin_status(asin, Status.FAILED, error_msg)
                    return False

        return False


class TransformPhase(PipelinePhase):
    """Fase de transformación de Amazon a MercadoLibre"""

    def execute(self, asin: str) -> bool:
        """Transforma JSON de Amazon a mini_ml"""
        amazon_path = Config.AMAZON_JSON_DIR / f"{asin}.json"
        mini_path = Config.MINI_ML_DIR / f"{asin}_mini_ml.json"

        # Validar que existe el archivo de Amazon
        if not amazon_path.exists():
            self.log(asin, "No existe JSON de Amazon", "ERROR")
            self.db.update_asin_status(asin, Status.FAILED, "Missing Amazon JSON")
            return False

        # Si ya existe y no es force regenerate, skip
        if mini_path.exists() and not Config.FORCE_REGENERATE:
            self.log(asin, "Ya transformado, saltando...", "INFO")
            self.db.update_asin_status(asin, Status.TRANSFORMED)
            return True

        max_retries = Config.MAX_TRANSFORM_RETRIES

        for attempt in range(1, max_retries + 1):
            try:
                self.db.update_asin_status(asin, Status.TRANSFORMING)
                retry_num = self.db.increment_retry(asin, "transform")

                if attempt > 1:
                    self.log(asin, f"Reintento transformación {attempt}/{max_retries}", "WARNING")
                    time.sleep(Config.RETRY_DELAY)

                self.log(asin, "Cargando JSON de Amazon...", "INFO")
                amazon_json = load_json_file(str(amazon_path))

                # Intentar transformación unificada con IA primero
                self.log(asin, "Transformando con IA unificada...", "INFO")
                mini_ml = build_mini_ml(amazon_json)

                if not mini_ml:
                    raise Exception("build_mini_ml retornó None")

                # Validar que tenga campos básicos
                if not mini_ml.get("title_ai") and not mini_ml.get("title"):
                    raise Exception("Mini ML sin título")

                if not mini_ml.get("category_id"):
                    raise Exception("Mini ML sin categoría")

                # Guardar mini_ml
                save_json_file(str(mini_path), mini_ml)

                # También copiar a outputs/json para compatibilidad
                output_path = Config.OUTPUT_JSON_DIR / f"{asin}.json"
                save_json_file(str(output_path), amazon_json)

                self.log(asin, f"Transformación completa: {mini_ml.get('category_id')}", "SUCCESS")
                self.log(asin, f"  → Atributos: {len(mini_ml.get('attributes_mapped', {}))}", "INFO")
                self.log(asin, f"  → Imágenes: {len(mini_ml.get('images', []))}", "INFO")

                self.db.update_asin_status(asin, Status.TRANSFORMED)
                return True

            except Exception as e:
                error_msg = str(e)
                self.log(asin, f"Error transformación: {error_msg}", "ERROR")

                if attempt == max_retries:
                    self.db.update_asin_status(asin, Status.FAILED, error_msg)
                    return False

        return False


class ValidationPhase(PipelinePhase):
    """Fase de validación IA pre-publicación"""

    def execute(self, asin: str) -> bool:
        """Valida listing con IA antes de publicar"""
        mini_path = Config.MINI_ML_DIR / f"{asin}_mini_ml.json"

        if not mini_path.exists():
            self.log(asin, "No existe mini_ml para validar", "ERROR")
            return False

        # Si se skipea validación (para testing rápido)
        if Config.SKIP_VALIDATION:
            self.log(asin, "Validación IA omitida (skip flag activo)", "WARNING")
            self.db.update_asin_status(asin, Status.VALIDATED)
            return True

        try:
            self.db.update_asin_status(asin, Status.VALIDATING)
            self.log(asin, "Ejecutando validación IA completa...", "INFO")

            mini_ml = load_json_file(str(mini_path))

            # Validación IA completa (solo warnings, NO bloquea publicación)
            validation_result = validate_listing_complete(mini_ml)

            if not validation_result["ready_to_publish"]:
                self.log(asin, "Validación IA: WARNINGS detectados (NO BLOQUEA)", "WARNING")

                # Registrar problemas como warnings (NO bloquea)
                if validation_result["critical_issues"]:
                    for issue in validation_result["critical_issues"]:
                        self.log(asin, f"  ⚠️ {issue}", "WARNING")

                if validation_result["warnings"]:
                    for warning in validation_result["warnings"]:
                        self.log(asin, f"  ⚠️ {warning}", "WARNING")

                # ✅ CONTINUAR CON PUBLICACIÓN (no rechazar)
                self.log(asin, "✅ Continuando con publicación...", "INFO")

            # Mostrar resultados de validación
            img_val = validation_result.get("image_validation", {})
            cat_val = validation_result.get("category_validation", {})

            self.log(asin, "Validación IA: COMPLETADA", "SUCCESS")
            self.log(asin, f"  → Imágenes: {'✅' if img_val.get('valid') else '⚠️'}", "INFO")
            self.log(asin, f"  → Categoría: {'✅' if cat_val.get('valid') else '⚠️'} ({cat_val.get('confidence', 0):.0%})", "INFO")

            self.db.update_asin_status(asin, Status.VALIDATED)
            return True

        except Exception as e:
            error_msg = str(e)
            self.log(asin, f"Error en validación: {error_msg}", "ERROR")
            self.db.update_asin_status(asin, Status.FAILED, error_msg)
            return False


class PublishPhase(PipelinePhase):
    """Fase de publicación en MercadoLibre CBT"""

    def execute(self, asin: str) -> Optional[str]:
        """Publica producto en MercadoLibre CBT"""
        mini_path = Config.MINI_ML_DIR / f"{asin}_mini_ml.json"

        if not mini_path.exists():
            self.log(asin, "No existe mini_ml para publicar", "ERROR")
            return None

        # Modo dry-run
        if Config.DRY_RUN:
            self.log(asin, "DRY RUN - Publicación simulada (no se envió a ML)", "WARNING")
            self.db.update_asin_status(asin, Status.PUBLISHED, item_id="DRY_RUN")
            return "DRY_RUN_ID"

        max_retries = Config.MAX_PUBLISH_RETRIES

        for attempt in range(1, max_retries + 1):
            try:
                self.db.update_asin_status(asin, Status.PUBLISHING)
                retry_num = self.db.increment_retry(asin, "publish")

                if attempt > 1:
                    self.log(asin, f"Reintento publicación {attempt}/{max_retries}", "WARNING")
                    time.sleep(Config.RETRY_DELAY * attempt)

                self.log(asin, "Cargando mini_ml...", "INFO")
                mini_ml = load_json_file(str(mini_path))

                self.log(asin, "Publicando en MercadoLibre CBT...", "INFO")
                result = publish_item(mini_ml)

                # Verificar resultado
                if result is None:
                    raise Exception("Publicación abortada (dimensiones/imágenes inválidas)")

                # Obtener item_id
                item_id = result.get("item_id") or result.get("id")

                if item_id:
                    self.log(asin, f"Publicado exitosamente: {item_id}", "SUCCESS")

                    # Información adicional
                    site_items = result.get("site_items", [])
                    successful = [s for s in site_items if s.get("item_id")]
                    failed = [s for s in site_items if s.get("error")]

                    self.log(asin, f"  → Publicado en {len(successful)} países", "INFO")
                    if failed:
                        self.log(asin, f"  → {len(failed)} países con errores", "WARNING")

                    self.db.update_asin_status(asin, Status.PUBLISHED, item_id=item_id)
                    return item_id
                else:
                    raise Exception(f"Publicación sin ID: {result}")

            except Exception as e:
                error_str = str(e)
                self.log(asin, f"Error publicación: {error_str[:200]}", "ERROR")

                # Error de rate limiting (manejar primero)
                if "429" in error_str or "rate" in error_str.lower():
                    self.log(asin, f"Rate limited → Esperando {Config.RATE_LIMIT_DELAY}s", "WARNING")
                    time.sleep(Config.RATE_LIMIT_DELAY)
                    continue

                # Intentar auto-corrección inteligente
                try:
                    # Cargar JSON de Amazon para referencia
                    amazon_path = Config.AMAZON_JSON_DIR / f"{asin}.json"
                    amazon_json = load_json_file(str(amazon_path)) if amazon_path.exists() else {}

                    # Cargar mini_ml actual
                    mini_ml = load_json_file(str(mini_path))

                    # Extraer error response si es disponible
                    error_response = {}
                    try:
                        # Intentar parsear JSON del error
                        import re
                        json_match = re.search(r'\{.*\}', error_str)
                        if json_match:
                            error_response = json.loads(json_match.group())
                    except:
                        error_response = {"message": error_str}

                    # Aplicar auto-corrección
                    mini_ml_fixed, fixes_applied = auto_fix(mini_ml, amazon_json, error_response)

                    if fixes_applied:
                        # Guardar mini_ml corregido
                        save_json_file(str(mini_path), mini_ml_fixed)
                        self.log(asin, "Auto-corrección aplicada → Reintentando", "WARNING")
                        continue  # Reintentar con correcciones

                except Exception as fix_error:
                    self.log(asin, f"Auto-corrección falló: {fix_error}", "WARNING")

                # Si no se pudo auto-corregir o es el último intento
                if attempt == max_retries:
                    self.db.update_asin_status(asin, Status.FAILED, error_str[:500])
                    return None

        return None


# ═══════════════════════════════════════════════════════════════════════════
# PIPELINE ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

class Pipeline:
    """Orquestador principal del pipeline"""

    def __init__(self, config: Config):
        self.config = config
        self.db = PipelineDB(config.DB_PATH)

        # Inicializar fases
        self.download_phase = DownloadPhase(self.db)
        self.transform_phase = TransformPhase(self.db)
        self.validation_phase = ValidationPhase(self.db)
        self.publish_phase = PublishPhase(self.db)

        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def load_asins(self) -> List[str]:
        """Carga lista de ASINs desde archivo"""
        if not Config.ASINS_FILE.exists():
            print(f"❌ No se encontró el archivo {Config.ASINS_FILE}")
            return []

        with open(Config.ASINS_FILE, "r") as f:
            asins = [
                line.strip().upper()
                for line in f
                if line.strip() and not line.startswith("#")
            ]

        print(f"📋 {len(asins)} ASINs cargados desde {Config.ASINS_FILE}")
        return asins

    def process_asin(self, asin: str, index: int, total: int) -> Dict:
        """Procesa un ASIN completo a través de todas las fases"""

        print(f"\n{'='*70}")
        print(f"📦 Procesando [{index}/{total}]: {asin}")
        print(f"{'='*70}")

        result = {
            "asin": asin,
            "success": False,
            "item_id": None,
            "phase": None
        }

        # Fase 1: Download
        if not self.download_phase.execute(asin):
            result["phase"] = "download"
            return result

        # Fase 2: Transform
        if not self.transform_phase.execute(asin):
            result["phase"] = "transform"
            return result

        # Fase 3: Validation
        if not self.validation_phase.execute(asin):
            result["phase"] = "validation"
            return result

        # Fase 4: Publish
        item_id = self.publish_phase.execute(asin)
        if item_id:
            result["success"] = True
            result["item_id"] = item_id
            result["phase"] = "published"
        else:
            result["phase"] = "publish"

        return result

    def run(self, asins: List[str]) -> Dict:
        """Ejecuta el pipeline completo para todos los ASINs"""

        if not asins:
            print("❌ No hay ASINs para procesar")
            return {"success": 0, "failed": 0}

        # Crear registro de ejecución
        self.db.create_run(self.run_id, len(asins))

        print("\n" + "="*70)
        print("🚀 INICIANDO PIPELINE AMAZON → MERCADOLIBRE CBT v2.0")
        print("="*70)
        print(f"📦 Total de productos: {len(asins)}")
        print(f"🆔 Run ID: {self.run_id}")
        if Config.DRY_RUN:
            print("⚠️  MODO DRY-RUN ACTIVO (no se publicará realmente)")
        if Config.SKIP_VALIDATION:
            print("⚠️  VALIDACIÓN IA DESACTIVADA")
        print("="*70 + "\n")

        results = {
            "success": [],
            "failed": [],
            "skipped": []
        }

        start_time = time.time()

        for i, asin in enumerate(asins, 1):
            try:
                result = self.process_asin(asin, i, len(asins))

                if result["success"]:
                    results["success"].append(asin)
                else:
                    results["failed"].append(asin)

                # Rate limiting entre productos
                if i < len(asins) and not Config.DRY_RUN:
                    print(f"\n⏱️  Esperando {Config.PUBLISH_DELAY}s antes del siguiente producto...")
                    time.sleep(Config.PUBLISH_DELAY)

            except KeyboardInterrupt:
                print("\n\n⚠️  Pipeline interrumpido por el usuario")
                break
            except Exception as e:
                print(f"\n❌ Error crítico procesando {asin}: {e}")
                traceback.print_exc()
                results["failed"].append(asin)

        # Calcular tiempo total
        elapsed_time = time.time() - start_time

        # Reporte final
        self.print_final_report(results, elapsed_time)

        return results

    def print_final_report(self, results: Dict, elapsed_time: float):
        """Imprime reporte final detallado"""

        total = len(results["success"]) + len(results["failed"]) + len(results["skipped"])

        print("\n" + "="*70)
        print("📊 REPORTE FINAL DEL PIPELINE")
        print("="*70)
        print(f"⏱️  Tiempo total: {elapsed_time/60:.1f} minutos")
        print(f"📦 Total procesados: {total}")
        print(f"✅ Exitosos: {len(results['success'])}/{total} ({len(results['success'])/total*100:.1f}%)")
        print(f"❌ Fallidos: {len(results['failed'])}/{total} ({len(results['failed'])/total*100:.1f}%)")

        if results["skipped"]:
            print(f"⏭️  Saltados: {len(results['skipped'])}/{total}")

        # Estadísticas de la base de datos
        stats = self.db.get_statistics()
        print(f"\n📈 ESTADÍSTICAS POR ESTADO:")
        for status, count in stats.items():
            print(f"   {status}: {count}")

        if results["failed"]:
            print(f"\n⚠️  ASINs fallidos:")
            for asin in results["failed"][:10]:  # Mostrar máximo 10
                status = self.db.get_asin_status(asin)
                if status:
                    error = status.get("last_error") or "Unknown"
                    error_msg = str(error)[:50] if error else "Unknown"
                    print(f"   • {asin}: {error_msg}")

            if len(results["failed"]) > 10:
                print(f"   ... y {len(results['failed']) - 10} más")

        print("\n" + "="*70)
        print("✅ PIPELINE COMPLETADO")
        print("="*70 + "\n")

        # Guardar reporte en archivo
        report_path = Config.LOGS_DIR / f"report_{self.run_id}.json"
        with open(report_path, "w") as f:
            json.dump({
                "run_id": self.run_id,
                "timestamp": datetime.now().isoformat(),
                "elapsed_seconds": elapsed_time,
                "results": results,
                "statistics": stats
            }, f, indent=2)

        print(f"📄 Reporte guardado en: {report_path}\n")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """Punto de entrada principal"""

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline Amazon → MercadoLibre CBT v2.0")
    parser.add_argument("--dry-run", action="store_true", help="Simular publicaciones sin enviar a ML")
    parser.add_argument("--skip-validation", action="store_true", help="Omitir validación IA")
    parser.add_argument("--force-regenerate", action="store_true", help="Forzar regeneración de archivos existentes")
    parser.add_argument("--skip-health-check", action="store_true", help="Saltar verificaciones de salud")
    parser.add_argument("--asin", type=str, help="Procesar solo un ASIN específico")

    args = parser.parse_args()

    # Configurar flags
    Config.DRY_RUN = args.dry_run
    Config.SKIP_VALIDATION = args.skip_validation
    Config.FORCE_REGENERATE = args.force_regenerate

    # Setup directories
    Config.setup_directories()

    # Health checks (a menos que se salte)
    if not args.skip_health_check:
        health_ok = HealthChecker.run_all_checks()
        if not health_ok:
            response = input("\n⚠️  Algunos health checks fallaron. ¿Continuar de todas formas? (y/N): ")
            if response.lower() != "y":
                print("❌ Pipeline abortado")
                sys.exit(1)

    # Crear pipeline
    pipeline = Pipeline(Config)

    # Cargar ASINs
    if args.asin:
        # Procesar solo un ASIN específico
        asins = [args.asin.upper()]
        print(f"🎯 Modo single ASIN: {args.asin}")
    else:
        asins = pipeline.load_asins()

    if not asins:
        print("❌ No hay ASINs para procesar")
        sys.exit(1)

    # Ejecutar pipeline
    try:
        results = pipeline.run(asins)

        # Exit code basado en resultados
        if len(results["failed"]) == 0:
            sys.exit(0)
        elif len(results["success"]) > 0:
            sys.exit(2)  # Parcialmente exitoso
        else:
            sys.exit(1)  # Todos fallaron

    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline interrumpido por el usuario")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Error fatal en el pipeline: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
