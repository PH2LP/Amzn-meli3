#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 02_publish.py - PUBLICAR PRODUCTOS (1 POR 1)
# ═══════════════════════════════════════════════════════════════════════════════
# 
# ¿Qué hace?
#   Publica productos de Amazon en MercadoLibre de forma secuencial.
#   Lee ASINs desde asins.txt y los publica uno por uno.
# 
# Comando:
#   python3 02_publish.py
# 
# ═══════════════════════════════════════════════════════════════════════════════
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
# CONTROL DE VERBOSIDAD GLOBAL
# ═══════════════════════════════════════════════════════════════════════════
os.environ['PIPELINE_QUIET_MODE'] = '1'  # Activar modo silencioso en todos los módulos

# ═══════════════════════════════════════════════════════════════════════════
# AUTO-ACTIVACIÓN DE VENV
# ═══════════════════════════════════════════════════════════════════════════

if sys.prefix == sys.base_prefix:
    vpy = Path(__file__).parent / "venv" / "bin" / "python"
    if vpy.exists():
        print(f"⚙️  Activando entorno virtual: {vpy}")
        os.execv(str(vpy), [str(vpy)] + sys.argv)

load_dotenv(override=True)

# ═══════════════════════════════════════════════════════════════════════════
# IMPORTS DE MÓDULOS PROPIOS
# ═══════════════════════════════════════════════════════════════════════════

from src.integrations.amazon_api import get_product_data_from_asin
from src.integrations.amazon_pricing import get_prime_offer
from src.pipeline.transform_mapper_new import build_mini_ml, load_json_file, save_json_file
from src.pipeline.unified_transformer import transform_amazon_to_ml_unified
from src.pipeline.ai_validators import validate_listing_complete
from src.integrations.smart_categorizer import categorize_with_ai
from src.integrations.mainglobal import publish_item

# Telegram notifications (optional)
try:
    from scripts.tools import telegram_publishing_notifier as tg_notifier
except ImportError:
    tg_notifier = None

# Importar save_listing para guardar site_items en DB
from scripts.tools.save_listing_data import save_listing

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════

class Config:
    """Configuración centralizada del pipeline"""

    # Directorios
    ASINS_FILE = Path("asins.txt") if Path("asins.txt").exists() else Path("data/asins.txt")
    AMAZON_JSON_DIR = Path("storage/asins_json")
    MINI_ML_DIR = Path("storage/logs/publish_ready")
    OUTPUT_JSON_DIR = Path("outputs/json")
    LOGS_DIR = Path("storage/logs/pipeline")
    DB_PATH = Path("storage/pipeline_state.db")
    GTIN_ISSUES_LOG = Path("storage/logs/gtin_issues.json")
    CATEGORY_BLACKLIST = Path("storage/category_blacklist_global.json")

    # Retry configuration
    MAX_DOWNLOAD_RETRIES = 3
    MAX_TRANSFORM_RETRIES = 2
    MAX_PUBLISH_RETRIES = 5  # Límite de 5 intentos con categorías alternativas

    # Delays (seconds)
    RETRY_DELAY = 5
    PUBLISH_DELAY = 3
    RATE_LIMIT_DELAY = 10

    # Flags
    DRY_RUN = False
    SKIP_VALIDATION = True  # Validación IA desactivada por defecto
    FORCE_REGENERATE = True  # SIEMPRE regenerar, NO usar caché

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
# GTIN ISSUES LOGGING
# ═══════════════════════════════════════════════════════════════════════════

def log_gtin_issue(asin: str, gtin: str, category_id: str, error_code: str, error_message: str, mini_ml_data: dict = None):
    """Registra productos con problemas de GTIN"""
    from datetime import datetime

    log_file = Config.GTIN_ISSUES_LOG

    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            try:
                issues = json.load(f)
            except json.JSONDecodeError:
                issues = []
    else:
        issues = []

    issue_entry = {
        "asin": asin,
        "gtin": gtin,
        "category_id": category_id,
        "category_name": mini_ml_data.get("category_name") if mini_ml_data else None,
        "error_code": error_code,
        "error_message": error_message,
        "timestamp": datetime.now().isoformat(),
        "product_title": mini_ml_data.get("title_ai") if mini_ml_data else None,
        "brand": mini_ml_data.get("brand") if mini_ml_data else None,
        "price": mini_ml_data.get("price") if mini_ml_data else None
    }

    issues.append(issue_entry)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(issues, f, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY BLACKLIST CHECK
# ═══════════════════════════════════════════════════════════════════════════

def is_category_blacklisted(category_id: str) -> Tuple[bool, Optional[dict]]:
    """
    Verifica si una categoría está en la blacklist global (caza/armas/táctico)

    Returns:
        (is_blacklisted, category_info)
        - is_blacklisted: True si la categoría está prohibida
        - category_info: Información de la categoría prohibida (name, reason, etc)
    """
    try:
        blacklist_file = Config.CATEGORY_BLACKLIST
        if not blacklist_file.exists():
            return False, None

        with open(blacklist_file, 'r', encoding='utf-8') as f:
            blacklist_data = json.load(f)

        if category_id in blacklist_data.get('blacklist', []):
            category_info = blacklist_data.get('details', {}).get(category_id, {})
            return True, category_info

        return False, None

    except Exception as e:
        print(f"⚠️  Error al verificar blacklist: {e}")
        return False, None


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
        """Ejecuta todas las verificaciones de salud - versión compacta"""
        checks = []

        # Check credentials
        creds_ok, creds_errors = HealthChecker.check_credentials()
        checks.append(("Creds", creds_ok))

        # Check API connectivity
        api_ok, api_errors = HealthChecker.check_api_connectivity()
        checks.append(("APIs", api_ok))

        # Check directories
        Config.setup_directories()
        checks.append(("Dirs", True))

        # Print compacto
        status_str = " | ".join([f"{name} {'✓' if ok else '✗'}" for name, ok in checks])
        print(f"Pre-flight: {status_str}")

        all_ok = all(ok for _, ok in checks)

        if not all_ok:
            if not creds_ok:
                for error in creds_errors:
                    print(f"  {error}")
            if not api_ok:
                for error in api_errors:
                    print(f"  {error}")

        return all_ok


# ═══════════════════════════════════════════════════════════════════════════
# PIPELINE PHASES
# ═══════════════════════════════════════════════════════════════════════════

class PipelinePhase:
    """Clase base para las fases del pipeline"""

    def __init__(self, db: PipelineDB):
        self.db = db

    def log(self, asin: str, message: str, level: str = "INFO"):
        """Log helper - silencioso, solo a DB"""
        phase = self.__class__.__name__.replace("Phase", "").lower()
        self.db.log(asin, phase, message, level)
        # NO imprimir nada en consola, solo guardar en DB


class DownloadPhase(PipelinePhase):
    """Fase de descarga desde Amazon SP-API"""

    def execute(self, asin: str) -> bool:
        """Descarga datos de Amazon para un ASIN"""
        json_path = Config.AMAZON_JSON_DIR / f"{asin}.json"

        # Si ya existe y no es force regenerate, skip (sin print)
        if json_path.exists() and not Config.FORCE_REGENERATE:
            self.db.update_asin_status(asin, Status.DOWNLOADED)
            return True

        max_retries = Config.MAX_DOWNLOAD_RETRIES

        for attempt in range(1, max_retries + 1):
            try:
                self.db.update_asin_status(asin, Status.DOWNLOADING)
                retry_num = self.db.increment_retry(asin, "download")

                if attempt > 1:
                    self.log(asin, f"Reintento descarga {attempt}/{max_retries}", "WARNING")
                    time.sleep(Config.RETRY_DELAY * attempt)

                get_product_data_from_asin(asin, save_path=str(json_path))

                if json_path.exists():
                    # Obtener precio Prime y agregarlo al JSON
                    self.log(asin, "Obteniendo precio Prime...", "INFO")
                    prime_offer = get_prime_offer(asin)

                    if prime_offer:
                        # Cargar el JSON existente
                        with open(json_path, 'r', encoding='utf-8') as f:
                            product_data = json.load(f)

                        # Agregar el precio al JSON
                        product_data['prime_pricing'] = prime_offer

                        # Guardar el JSON actualizado
                        with open(json_path, 'w', encoding='utf-8') as f:
                            json.dump(product_data, f, ensure_ascii=False, indent=2)

                        self.log(asin, f"Amazon ✓ | Precio Prime: ${prime_offer['price']}", "SUCCESS")
                        self.db.update_asin_status(asin, Status.DOWNLOADED)
                        return True
                    else:
                        # Sin precio Prime = no procesamos este producto
                        error_msg = "No tiene oferta Prime activa"
                        self.log(asin, f"❌ {error_msg}", "ERROR")
                        self.db.update_asin_status(asin, Status.FAILED, error_msg)
                        return False
                else:
                    raise Exception("Archivo no creado")

            except Exception as e:
                error_msg = str(e)
                if attempt == max_retries:
                    self.log(asin, f"Error descarga: {error_msg[:50]}", "ERROR")
                    self.db.update_asin_status(asin, Status.FAILED, error_msg)
                    return False

        return False


class TransformPhase(PipelinePhase):
    """Fase de transformación de Amazon a MercadoLibre"""

    def execute(self, asin: str, blocked_categories: Optional[List[str]] = None) -> bool:
        """
        Transforma JSON de Amazon a mini_ml
        blocked_categories: Lista de categorías a excluir (para retry con alternativas)
        """
        amazon_path = Config.AMAZON_JSON_DIR / f"{asin}.json"
        mini_path = Config.MINI_ML_DIR / f"{asin}_mini_ml.json"

        # Validar que existe el archivo de Amazon
        if not amazon_path.exists():
            self.log(asin, "Falta JSON Amazon", "ERROR")
            self.db.update_asin_status(asin, Status.FAILED, "Missing Amazon JSON")
            return False

        # Si ya existe, verificar si necesita retry por categoría bloqueada
        if mini_path.exists() and not Config.FORCE_REGENERATE:
            try:
                existing_mini = load_json_file(str(mini_path))
                retry_blocked = existing_mini.get("retry_blocked_sites", [])

                if retry_blocked:
                    self.log(asin, f"Retry categoría para: {', '.join(retry_blocked)}", "WARNING")
                else:
                    self.db.update_asin_status(asin, Status.TRANSFORMED)
                    return True
            except Exception as e:
                self.log(asin, "Error leyendo mini_ml, regenerando", "WARNING")

        max_retries = Config.MAX_TRANSFORM_RETRIES

        for attempt in range(1, max_retries + 1):
            try:
                self.db.update_asin_status(asin, Status.TRANSFORMING)
                retry_num = self.db.increment_retry(asin, "transform")

                if attempt > 1:
                    self.log(asin, f"Reintento transform {attempt}/{max_retries}", "WARNING")
                    time.sleep(Config.RETRY_DELAY)

                amazon_json = load_json_file(str(amazon_path))

                if blocked_categories:
                    self.log(asin, f"Excluyendo categorías: {blocked_categories}", "WARNING")

                mini_ml = build_mini_ml(amazon_json, excluded_categories=blocked_categories)

                if not mini_ml:
                    raise Exception("build_mini_ml retornó None")

                if not mini_ml.get("title_ai") and not mini_ml.get("title"):
                    raise Exception("Sin título")

                if not mini_ml.get("category_id"):
                    raise Exception("Sin categoría")

                save_json_file(str(mini_path), mini_ml)
                output_path = Config.OUTPUT_JSON_DIR / f"{asin}.json"
                save_json_file(str(output_path), amazon_json)

                cat_id = mini_ml.get('category_id')
                attrs = len(mini_ml.get('attributes_mapped', {}))
                imgs = len(mini_ml.get('images', []))
                self.log(asin, f"Transform ✓ → {cat_id} ({attrs} attrs, {imgs} imgs)", "SUCCESS")

                self.db.update_asin_status(asin, Status.TRANSFORMED)
                return True

            except Exception as e:
                error_msg = str(e)
                if attempt == max_retries:
                    self.log(asin, f"Error transform: {error_msg[:50]}", "ERROR")
                    self.db.update_asin_status(asin, Status.FAILED, error_msg)
                    return False

        return False


class ValidationPhase(PipelinePhase):
    """Fase de validación IA pre-publicación"""

    def execute(self, asin: str) -> bool:
        """Valida listing con IA antes de publicar"""
        mini_path = Config.MINI_ML_DIR / f"{asin}_mini_ml.json"

        if not mini_path.exists():
            self.log(asin, "Falta mini_ml", "ERROR")
            return False

        # Si se skipea validación (para testing rápido) - sin print
        if Config.SKIP_VALIDATION:
            self.db.update_asin_status(asin, Status.VALIDATED)
            return True

        try:
            self.db.update_asin_status(asin, Status.VALIDATING)
            mini_ml = load_json_file(str(mini_path))
            validation_result = validate_listing_complete(mini_ml)

            if not validation_result["ready_to_publish"]:
                issues = []
                if validation_result["critical_issues"]:
                    issues.extend(validation_result["critical_issues"][:2])

                error_msg = "; ".join(issues[:2])
                self.log(asin, f"Validación fallida: {error_msg[:60]}", "ERROR")
                self.db.update_asin_status(asin, Status.FAILED, f"Validation: {error_msg}")
                return False

            cat_val = validation_result.get("category_validation", {})
            conf = cat_val.get('confidence', 0)
            self.log(asin, f"Validación ✓ (conf: {conf:.0%})", "SUCCESS")

            self.db.update_asin_status(asin, Status.VALIDATED)
            return True

        except Exception as e:
            error_msg = str(e)
            self.log(asin, f"Error validación: {error_msg[:50]}", "ERROR")
            self.db.update_asin_status(asin, Status.FAILED, error_msg)
            return False


class PublishPhase(PipelinePhase):
    """Fase de publicación en MercadoLibre CBT"""

    def execute(self, asin: str) -> Optional[dict]:
        """Publica producto en MercadoLibre CBT

        Returns:
            dict con {item_id, countries_ok, countries_failed} o None si falla
        """
        mini_path = Config.MINI_ML_DIR / f"{asin}_mini_ml.json"

        if not mini_path.exists():
            self.log(asin, "Falta mini_ml", "ERROR")
            return None

        # Modo dry-run - sin print
        if Config.DRY_RUN:
            self.db.update_asin_status(asin, Status.PUBLISHED, item_id="DRY_RUN")
            return {"item_id": "DRY_RUN_ID", "countries_ok": ["DRY"], "countries_failed": []}

        max_retries = Config.MAX_PUBLISH_RETRIES
        successful_sites = []  # Trackear países donde ya tuvo éxito (evita duplicados)
        all_item_ids = []  # Trackear TODOS los item_ids generados (para cleanup si falla)
        item_id = None  # Inicializar antes del loop
        countries_failed = []  # Inicializar para evitar NameError en returns

        for attempt in range(1, max_retries + 1):
            try:
                self.db.update_asin_status(asin, Status.PUBLISHING)
                retry_num = self.db.increment_retry(asin, "publish")

                if attempt > 1:
                    self.log(asin, f"Retry publish {attempt}/{max_retries}", "WARNING")
                    time.sleep(Config.RETRY_DELAY * attempt)

                mini_ml = load_json_file(str(mini_path))

                # 🔹 Log de debug para verificar exclusiones
                if successful_sites:
                    self.log(asin, f"Excluyendo países ya publicados: {', '.join(successful_sites)}", "INFO")

                result = publish_item(mini_ml, excluded_sites=successful_sites if successful_sites else None)

                if result is None:
                    raise Exception("Publicación abortada (dimensiones/imágenes inválidas)")

                item_id = result.get("item_id") or result.get("id")

                if item_id:
                    # 🔹 Guardar este item_id para tracking
                    if item_id not in all_item_ids:
                        all_item_ids.append(item_id)

                    site_items = result.get("site_items", [])

                    # Extraer países exitosos y fallidos (usar dict para evitar duplicados)
                    countries_ok_dict = {}  # site_id → True si tiene item_id
                    countries_failed_dict = {}  # site_id → {site_id, error} con detalles del error

                    for s in site_items:
                        # ✅ Saltar elementos que no son diccionarios
                        if not isinstance(s, dict):
                            continue
                        site_id = s.get("site_id")
                        if not site_id:
                            continue
                        # Priorizar éxito: si tiene item_id → país exitoso
                        if s.get("item_id"):
                            countries_ok_dict[site_id] = True
                            countries_failed_dict.pop(site_id, None)  # Remover de fallidos
                            # 🔹 CRÍTICO: Agregar a successful_sites INMEDIATAMENTE
                            if site_id not in successful_sites:
                                successful_sites.append(site_id)
                        # Solo marcar como fallido si no hay éxito previo
                        elif s.get("error") and site_id not in countries_ok_dict:
                            countries_failed_dict[site_id] = {
                                "site_id": site_id,
                                "error": s.get("error")
                            }

                    countries_ok = list(countries_ok_dict.keys())
                    countries_failed = list(countries_failed_dict.values())  # Ahora es lista de dicts con detalles
                    countries_failed_ids = list(countries_failed_dict.keys())  # Solo IDs para logs internos

                    # ✅ Filtrar solo elementos dict válidos antes de acceder con .get()
                    successful = [s for s in site_items if isinstance(s, dict) and s.get("item_id")]
                    failed = [s for s in site_items if isinstance(s, dict) and s.get("error")]

                    self.log(asin, f"Publicado ✓ → {item_id} ({len(countries_ok)} países)", "SUCCESS")
                    if countries_failed_ids:
                        self.log(asin, f"{len(countries_failed_ids)} países con error", "WARNING")

                    # Detectar si hay categoría bloqueada en algunos países
                    blocked_sites = []
                    for site_item in failed:
                        # ✅ Verificar que site_item y error son dicts
                        if not isinstance(site_item, dict):
                            continue
                        site_id = site_item.get("site_id")
                        error_obj = site_item.get("error")
                        if error_obj and isinstance(error_obj, dict):
                            causes = error_obj.get("cause", [])
                            for cause in causes:
                                if isinstance(cause, dict) and cause.get("code") == "item.not_allowed":
                                    blocked_sites.append(site_id)
                                    break

                    # Si hay países bloqueados pero también exitosos, intentar con otra categoría
                    if blocked_sites and successful:
                        # ✅ Filtrar solo elementos dict válidos antes de acceder con .get()
                        ok_sites = ', '.join([s.get('site_id') for s in successful if isinstance(s, dict)])
                        blocked = ', '.join(blocked_sites)
                        self.log(asin, f"Parcial: OK={ok_sites} | Bloq={blocked}", "WARNING")

                        # 🔹 Los site_ids exitosos ya fueron agregados a successful_sites en el loop de arriba (línea 743-744)
                        # No necesitamos volver a agregarlos aquí

                        # Regenerar con nueva categoría para países bloqueados
                        if attempt < max_retries:
                            current_category = mini_ml.get("category_id")
                            blocked_categories = mini_ml.get("blocked_categories", [])
                            if current_category not in blocked_categories:
                                blocked_categories.append(current_category)

                            self.log(asin, f"Buscando cat alternativa para {blocked}", "WARNING")

                            transform_phase = TransformPhase(self.db)
                            mini_ml_regenerated = transform_phase.execute(asin, blocked_categories=blocked_categories)

                            if mini_ml_regenerated:
                                continue
                            else:
                                self.log(asin, "Sin cat alternativa, aceptando parcial", "WARNING")
                                self.db.update_asin_status(asin, Status.PUBLISHED, item_id=item_id)
                                return {
                                    "item_id": item_id,
                                    "countries_ok": countries_ok,
                                    "countries_failed": countries_failed
                                }
                        else:
                            self.log(asin, f"Límite alcanzado, aceptando parcial", "WARNING")
                            self.db.update_asin_status(asin, Status.PUBLISHED, item_id=item_id)
                            return {
                                "item_id": item_id,
                                "countries_ok": countries_ok,
                                "countries_failed": countries_failed
                            }

                    # Si todos los países tuvieron éxito, marcar como publicado
                    if not blocked_sites:
                        self.db.update_asin_status(asin, Status.PUBLISHED, item_id=item_id)
                        return {
                            "item_id": item_id,
                            "countries_ok": countries_ok,
                            "countries_failed": countries_failed
                        }

                    # Si todos los países fallaron por categoría bloqueada, intentar con otra categoría
                    # (este caso se maneja abajo en el bloque de excepciones)
                else:
                    raise Exception(f"Publicación sin ID: {result}")

            except Exception as e:
                error_str = str(e)

                # Error de GTIN duplicado (código 3701)
                if "3701" in error_str or "invalid_product_identifier" in error_str:
                    mini_ml = load_json_file(str(mini_path))

                    if mini_ml.get("force_no_gtin"):
                        error_msg = "GTIN duplicado y sin GTIN rechazado"
                        self.log(asin, error_msg, "ERROR")
                        log_gtin_issue(
                            asin=asin,
                            gtin=mini_ml.get("gtin"),
                            category_id=mini_ml.get("category_id"),
                            error_code="3701",
                            error_message="GTIN duplicado. Sin GTIN también rechazado",
                            mini_ml_data=mini_ml
                        )
                        self.db.update_asin_status(asin, Status.FAILED, "GTIN duplicated")
                        return {"error": error_msg, "error_code": "3701"}

                    self.log(asin, "GTIN duplicado → Retry sin GTIN", "WARNING")
                    mini_ml["force_no_gtin"] = True
                    mini_ml["last_error"] = "GTIN_REUSED"
                    save_json_file(str(mini_path), mini_ml)
                    continue

                # Error 7810: GTIN requerido pero no disponible
                if "7810" in error_str or ("missing_conditional_required" in error_str and "GTIN" in error_str):
                    mini_ml = load_json_file(str(mini_path))
                    current_category = mini_ml.get("category_id")
                    blocked_categories = mini_ml.get("blocked_categories", [])

                    self.log(asin, f"Cat {current_category} requiere GTIN", "WARNING")

                    if current_category and current_category not in blocked_categories:
                        blocked_categories.append(current_category)

                    if attempt < max_retries:
                        self.log(asin, "Buscando cat sin req GTIN", "WARNING")

                        transform_phase = TransformPhase(self.db)
                        mini_ml_regenerated = transform_phase.execute(asin, blocked_categories=blocked_categories)

                        if mini_ml_regenerated:
                            continue
                        else:
                            error_msg = "No hay categoría alternativa sin GTIN"
                            self.log(asin, error_msg, "ERROR")
                            log_gtin_issue(
                                asin=asin,
                                gtin=mini_ml.get("gtin"),
                                category_id=current_category,
                                error_code="7810",
                                error_message="Cat requiere GTIN. Sin alternativas",
                                mini_ml_data=mini_ml
                            )
                            self.db.update_asin_status(asin, Status.FAILED, "Cat requires GTIN")
                            return {"error": error_msg, "error_code": "7810"}
                    else:
                        error_msg = f"Límite alcanzado buscando cat sin GTIN ({max_retries} intentos)"
                        self.log(asin, error_msg, "ERROR")
                        log_gtin_issue(
                            asin=asin,
                            gtin=mini_ml.get("gtin"),
                            category_id=current_category,
                            error_code="7810",
                            error_message=f"Cat requiere GTIN. Límite {max_retries}",
                            mini_ml_data=mini_ml
                        )
                        self.db.update_asin_status(asin, Status.FAILED, "Cat requires GTIN - limit")
                        return {"error": error_msg, "error_code": "7810"}


                # ========================================================================
                # CLASIFICACIÓN MEJORADA DE ERRORES DE ML
                # ========================================================================
                # Traducir errores técnicos a lenguaje humano ANTES de decidir acción
                import re
                human_error = None
                is_category_error = False  # Flag para saber si es problema de categoría

                # Log del error crudo para debugging
                self.log(asin, f"Error ML (raw): {error_str[:200]}", "DEBUG")

                # 1. Errores de CATEGORÍA (solo estos justifican regenerar categoría)
                if "not_allowed" in error_str.lower():
                    human_error = "Categoría no permitida en este país"
                    is_category_error = True
                elif "category" in error_str.lower() and "invalid" in error_str.lower():
                    human_error = "Categoría inválida para este producto"
                    is_category_error = True
                elif "Title and photos did not match" in error_str:
                    human_error = "Título e imágenes no coinciden con la categoría"
                    is_category_error = True

                # 2. Errores de ATRIBUTOS (NO regenerar categoría, faltan datos)
                elif "required_attribute" in error_str.lower() or "missing_required" in error_str.lower():
                    match = re.search(r'attribute["\s:]+([A-Z_]+)', error_str)
                    if match:
                        attr = match.group(1)
                        human_error = f"Falta atributo requerido: {attr}"
                    else:
                        human_error = "Faltan atributos requeridos"

                # 3. Errores de DIMENSIONES/PESO (NO regenerar categoría, producto no apto)
                elif "package_height" in error_str.lower():
                    human_error = "Producto muy alto para MercadoLibre"
                elif "package_weight" in error_str.lower():
                    human_error = "Producto muy pesado para MercadoLibre"
                elif "package_length" in error_str.lower():
                    human_error = "Producto muy largo para MercadoLibre"
                elif "package_width" in error_str.lower():
                    human_error = "Producto muy ancho para MercadoLibre"
                elif "package_dimensions" in error_str.lower():
                    human_error = "Dimensiones del producto inválidas"

                # 4. Errores de IMÁGENES (NO regenerar categoría, problema de imágenes)
                elif "pictures" in error_str.lower() or "image" in error_str.lower():
                    human_error = "Error en las imágenes del producto"

                # 5. Errores de TÍTULO/DESCRIPCIÓN (NO regenerar categoría, problema de texto)
                elif "title" in error_str.lower() and ("invalid" in error_str.lower() or "prohibited" in error_str.lower()):
                    human_error = "Título contiene palabras prohibidas o inválidas"

                # 6. Errores de PRECIO (NO regenerar categoría, ajustar precio)
                elif "price" in error_str.lower() and ("invalid" in error_str.lower() or "minimum" in error_str.lower()):
                    human_error = "Precio fuera del rango permitido"

                # 7. Errores de STOCK/CANTIDAD
                elif "available_quantity" in error_str.lower():
                    human_error = "Cantidad disponible inválida"

                # 8. Error genérico con código 5004 (extraer código específico)
                elif "5004" in error_str:
                    match = re.search(r'"code":\s*"([^"]+)"', error_str)
                    if match:
                        code = match.group(1).replace("item.", "").replace("_", " ")
                        human_error = f"Error ML: {code}"
                    else:
                        human_error = "Error de validación de MercadoLibre"

                # 9. Si no pudimos identificar el error específico, mostrar raw
                if not human_error:
                    # Extraer mensaje útil del error JSON si es posible
                    try:
                        import json
                        if "{" in error_str:
                            json_start = error_str.find("{")
                            error_dict = json.loads(error_str[json_start:])
                            # Intentar extraer mensaje útil
                            if "message" in error_dict:
                                human_error = f"Error ML: {error_dict['message'][:60]}"
                            elif "cause" in error_dict and error_dict["cause"]:
                                cause = error_dict["cause"][0] if isinstance(error_dict["cause"], list) else error_dict["cause"]
                                human_error = f"Error ML: {cause.get('code', 'unknown')}"
                            else:
                                human_error = f"Error de validación: {error_str[:80]}"
                        else:
                            human_error = f"Error: {error_str[:80]}"
                    except:
                        human_error = f"Error: {error_str[:80]}"

                error_msg = human_error
                self.log(asin, f"Error detectado: {human_error}", "WARNING")

                # ========================================================================
                # DECISIÓN: ¿Regenerar categoría o abortar?
                # ========================================================================

                # SOLO regenerar categoría si es_category_error == True
                if is_category_error and attempt < max_retries:
                    self.log(asin, "Error de categoría → Intentando con categoría alternativa", "WARNING")

                    mini_ml = load_json_file(str(mini_path))
                    current_category = mini_ml.get("category_id")
                    blocked_categories = mini_ml.get("blocked_categories", [])

                    if current_category and current_category not in blocked_categories:
                        blocked_categories.append(current_category)

                    transform_phase = TransformPhase(self.db)
                    mini_ml_regenerated = transform_phase.execute(asin, blocked_categories=blocked_categories)

                    if mini_ml_regenerated:
                        continue  # Reintentar con nueva categoría
                    else:
                        # No hay categoría alternativa
                        if successful_sites:
                            self.log(asin, f"Sin cat alternativa, aceptando parcial ({len(successful_sites)} países)", "WARNING")
                            self.db.update_asin_status(asin, Status.PUBLISHED, item_id=item_id)
                            return {
                                "item_id": item_id,
                                "countries_ok": successful_sites,
                                "countries_failed": countries_failed,
                                "partial_success": True,
                                "error": error_msg
                            }
                        else:
                            self.log(asin, "Sin categoría alternativa disponible", "ERROR")
                            self.db.update_asin_status(asin, Status.FAILED, "No alt category")
                            return {"error": error_msg}
                else:
                    # NO es error de categoría, o ya agotamos intentos
                    # NO regenerar, abortar con error específico

                    # Si hay publicación parcial, preservarla
                    if item_id and successful_sites:
                        self.log(asin, f"⚠️ Publicación parcial: {item_id} en {len(successful_sites)} países", "WARNING")
                        self.db.update_asin_status(asin, Status.PUBLISHED, item_id=item_id)
                        return {
                            "item_id": item_id,
                            "countries_ok": successful_sites,
                            "countries_failed": countries_failed,
                            "partial_success": True,
                            "error": error_msg
                        }
                    else:
                        # Sin éxito parcial, marcar como failed
                        self.log(asin, f"Error no recuperable: {error_msg}", "ERROR")
                        self.db.update_asin_status(asin, Status.FAILED, error_msg[:200])
                        return {"error": error_msg}

                # Error de rate limiting
                if "429" in error_str or "rate" in error_str.lower():
                    self.log(asin, f"Rate limit, esperando {Config.RATE_LIMIT_DELAY}s", "WARNING")
                    time.sleep(Config.RATE_LIMIT_DELAY)
                    continue

                # Último intento
                if attempt == max_retries:
                    # Intentar extraer el JSON del error para Telegram
                    error_for_telegram = error_str
                    if "{" in error_str:
                        try:
                            # Extraer solo la parte JSON del error
                            import json
                            json_start = error_str.find("{")
                            json_part = error_str[json_start:]
                            error_dict = json.loads(json_part)
                            error_for_telegram = error_dict  # Pasar dict directamente
                        except:
                            # Si no se puede parsear, usar string completo
                            error_for_telegram = error_str[:100]

                    error_msg = error_str[:100] if error_str else "Error desconocido en publicación"
                    self.log(asin, f"Error: {error_msg[:60]}", "ERROR")

                    # Si tenemos publicación parcial, preservar esa información
                    if item_id and successful_sites:
                        self.log(asin, f"⚠️ Máx intentos, pero publicado en {len(successful_sites)} países: {item_id}", "WARNING")
                        self.db.update_asin_status(asin, Status.PUBLISHED, item_id=item_id)
                        return {
                            "item_id": item_id,
                            "countries_ok": successful_sites,
                            "countries_failed": countries_failed,  # ← FIXED
                            "partial_success": True,
                            "max_retries_reached": True,
                            "error": error_for_telegram
                        }
                    else:
                        # Fallo total
                        self.db.update_asin_status(asin, Status.FAILED, error_str[:500])
                        return {"error": error_for_telegram}

        # Si salimos del loop sin éxito
        if item_id and successful_sites:
            # Hay publicación parcial
            self.log(asin, f"⚠️ Máx intentos, pero publicado en {len(successful_sites)} países: {item_id}", "WARNING")
            self.db.update_asin_status(asin, Status.PUBLISHED, item_id=item_id)
            return {
                "item_id": item_id,
                "countries_ok": successful_sites,
                "countries_failed": countries_failed,  # ← FIXED
                "partial_success": True,
                "max_retries_reached": True,
                "error": "Máximo de intentos alcanzado, pero publicado parcialmente"
            }
        else:
            # Fallo total
            return {"error": "Máximo de intentos alcanzado sin éxito"}


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
            all_asins = [
                line.strip().upper()
                for line in f
                if line.strip() and not line.startswith("#")
            ]

        # Filtrar duplicados contra BD de productos ya publicados
        from src.pipeline.duplicate_checker import filter_asins_batch
        print(f"\n🔍 Verificando {len(all_asins)} ASINs contra BD...")
        result = filter_asins_batch(all_asins, verbose=False)
        asins = result['new_asins']

        if result['stats']['duplicate_by_asin'] > 0:
            print(f"⏭️  Skipped {result['stats']['duplicate_by_asin']} ASINs ya publicados")
        print(f"✅ Procesando {len(asins)} ASINs nuevos\n")

        return asins

    def process_asin(self, asin: str, index: int, total: int) -> Dict:
        """Procesa un ASIN completo a través de todas las fases"""

        print(f"[{index}/{total}] {asin}")

        result = {
            "asin": asin,
            "success": False,
            "item_id": None,
            "phase": None
        }

        # Fase 1: Download
        print("  ↓ Amazon      ", end="", flush=True)
        if not self.download_phase.execute(asin):
            print("✗")
            result["phase"] = "download"
            return result
        print("✓")

        # Fase 2: Transform
        print("  ↓ Transform   ", end="", flush=True)
        if not self.transform_phase.execute(asin):
            print("✗")
            result["phase"] = "transform"
            return result

        # Obtener info de categoría para mostrar
        mini_path = Config.MINI_ML_DIR / f"{asin}_mini_ml.json"
        cat_info = ""
        product_title = None  # Guardar el título para usarlo en notificaciones
        if mini_path.exists():
            try:
                from src.pipeline.transform_mapper_new import load_json_file
                mini = load_json_file(str(mini_path))
                cat_id = mini.get("category_id", "")

                # ═══════════════════════════════════════════════════════════
                # CHECK: Verificar si la categoría está prohibida (caza/armas/táctico)
                # ═══════════════════════════════════════════════════════════
                is_blacklisted, blacklist_info = is_category_blacklisted(cat_id)
                if is_blacklisted:
                    cat_name = blacklist_info.get("name", cat_id)
                    reason = blacklist_info.get("reason", "Categoría prohibida")
                    print(f"✗")
                    print(f"  🚫 SKIP: Categoría prohibida {cat_id} ({cat_name})")
                    print(f"       Razón: {reason}")
                    result["phase"] = "blacklist_category"
                    result["skip_reason"] = f"Categoría prohibida: {cat_name} - {reason}"
                    return result

                attrs = len(mini.get("attributes_mapped", {}))
                imgs = len(mini.get("images", []))
                cat_info = f" {cat_id} ({attrs}a, {imgs}i)"
                product_title = mini.get("title_ai")  # Extraer título (campo correcto)
            except:
                pass

        # Fallback: si no hay título del mini_ml, intentar obtenerlo del ASIN JSON
        if not product_title:
            try:
                from src.pipeline.transform_mapper_new import load_json_file
                asin_json_path = Config.ASINS_JSON_DIR / f"{asin}.json"
                if asin_json_path.exists():
                    asin_json = load_json_file(str(asin_json_path))
                    # Buscar título en diferentes ubicaciones del JSON de Amazon
                    product_title = (
                        asin_json.get("title") or
                        asin_json.get("product", {}).get("title") or
                        asin_json.get("data", {}).get("title")
                    )
            except:
                pass

        print(f"✓{cat_info}")

        # Fase 3: Validation (skip si está desactivada)
        if not Config.SKIP_VALIDATION:
            print("  ↓ Validation  ", end="", flush=True)
            if not self.validation_phase.execute(asin):
                print("✗")
                result["phase"] = "validation"
                return result
            print("✓")

        # Fase 4: Publish
        print("  ↓ Publish     ", end="", flush=True)
        publish_result = self.publish_phase.execute(asin)

        # Verificar si fue exitoso (tiene item_id) o falló (tiene error)
        if publish_result and publish_result.get("item_id"):
            result["success"] = True
            result["item_id"] = publish_result.get("item_id")
            result["countries_ok"] = publish_result.get("countries_ok", [])
            result["countries_failed"] = publish_result.get("countries_failed", [])
            result["title"] = product_title  # Agregar título al resultado
            result["phase"] = "published"

            # Verificar si es publicación parcial con retry o máximo de intentos
            result["partial_success"] = publish_result.get("partial_success", False)
            result["max_retries_reached"] = publish_result.get("max_retries_reached", False)

            # Si hay error adicional (publicación parcial), guardarlo
            if publish_result.get("error"):
                result["error"] = publish_result.get("error")

            # Mostrar resultado detallado
            countries_str = ", ".join(result["countries_ok"]) if result["countries_ok"] else "ninguno"

            if result["partial_success"]:
                if result["max_retries_reached"]:
                    print(f"⚠ {result.get('item_id', 'N/A')} (parcial, intentos agotados)")
                else:
                    print(f"⚠ {result.get('item_id', 'N/A')} (parcial)")
            else:
                print(f"✓ {result.get('item_id', 'N/A')}")

            print(f"      ✅ Publicado en: {countries_str}")
            if result["countries_failed"]:
                # countries_failed ahora es lista de dicts con {site_id, error}
                failed_countries = result["countries_failed"]
                if isinstance(failed_countries, list) and failed_countries:
                    if isinstance(failed_countries[0], dict):
                        # Formato nuevo con detalles
                        failed_str = ", ".join([f.get("site_id", "?") for f in failed_countries])
                    else:
                        # Formato viejo (solo site_ids)
                        failed_str = ", ".join(failed_countries)
                else:
                    failed_str = "desconocidos"
                print(f"      ⚠️  Falló en: {failed_str}")
        else:
            print("✗")
            result["phase"] = "publish"
            result["title"] = product_title  # Agregar título también en caso de error

            # Extraer y mostrar el error
            if publish_result and isinstance(publish_result, dict):
                error = publish_result.get("error", "Error desconocido")
                error_code = publish_result.get("error_code", "")

                # Guardar error en result para Telegram
                result["error"] = error
                result["error_code"] = error_code

                # Mostrar en consola
                error_str = str(error) if error else "Error desconocido"
                if error_code:
                    print(f"      ❌ [{error_code}] {error_str[:70]}")
                else:
                    print(f"      ❌ {error_str[:80]}")
            else:
                result["error"] = "Error desconocido en publicación"
                print(f"      ❌ Error desconocido")

        print()  # Línea en blanco al final
        return result

    def run(self, asins: List[str]) -> Dict:
        """Ejecuta el pipeline completo para todos los ASINs"""

        if not asins:
            print("❌ No hay ASINs para procesar")
            return {"success": 0, "failed": 0}

        # Crear registro de ejecución
        self.db.create_run(self.run_id, len(asins))

        flags = []
        if Config.DRY_RUN:
            flags.append("DRY-RUN")
        if Config.SKIP_VALIDATION:
            flags.append("No-IA-Val")

        flags_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"\n🚀 PIPELINE v2.0 | Run: {self.run_id} | {len(asins)} ASIN(s){flags_str}\n")

        results = {
            "success": [],
            "failed": [],
            "skipped": []
        }

        start_time = time.time()

        # Notificar inicio de batch
        if tg_notifier and tg_notifier.is_configured():
            tg_notifier.notify_batch_start(len(asins), self.run_id)

        # Contador global de productos procesados (independiente de success/fail)
        processed_count = 0

        for i, asin in enumerate(asins, 1):
            try:
                result = self.process_asin(asin, i, len(asins))

                # Incrementar contador SOLO cuando hay un resultado definitivo (éxito o error de publicación)
                # No incrementar para productos que fallan en download/transform/validation
                if result["success"] or result["phase"] == "publish":
                    processed_count += 1

                if result["success"]:
                    results["success"].append(asin)
                    # Notificar éxito (UN SOLO MENSAJE)
                    if tg_notifier and tg_notifier.is_configured():
                        countries_ok = result.get("countries_ok", [])
                        countries_failed_details = result.get("countries_failed", [])  # Ahora incluye detalles de errores
                        item_id = result.get("item_id", "N/A")
                        title = result.get("title")  # Obtener título del resultado

                        # Verificar si es publicación parcial
                        is_partial = result.get("partial_success", False)
                        max_retries = result.get("max_retries_reached", False)
                        partial_error = result.get("error") if is_partial else None

                        if is_partial:
                            # Notificación especial para publicación parcial
                            tg_notifier.notify_partial_success(
                                asin, item_id, countries_ok, countries_failed_details,
                                title, processed_count, len(asins), max_retries, partial_error
                            )
                        else:
                            # Notificación normal de éxito
                            tg_notifier.notify_publish_success(
                                asin, item_id, countries_ok, countries_failed_details,
                                title, processed_count, len(asins)
                            )
                else:
                    results["failed"].append(asin)
                    # Notificar error SOLO si llegó a la fase de publicación
                    if result["phase"] == "publish" and tg_notifier and tg_notifier.is_configured():
                        error_msg = result.get("error", "Unknown error")
                        title = result.get("title")  # Obtener título del resultado
                        tg_notifier.notify_publish_error(asin, error_msg, processed_count, len(asins), title)

                # Rate limiting entre productos
                if i < len(asins) and not Config.DRY_RUN:
                    time.sleep(Config.PUBLISH_DELAY)

            except KeyboardInterrupt:
                print("\n\n⚠️  Interrumpido por usuario")
                break
            except Exception as e:
                print(f"\n❌ Error crítico en {asin}: {str(e)[:60]}")
                results["failed"].append(asin)

        # Calcular tiempo total
        elapsed_time = time.time() - start_time

        # Notificar finalización de batch
        if tg_notifier and tg_notifier.is_configured():
            duration_minutes = elapsed_time / 60
            tg_notifier.notify_batch_complete(
                len(asins),
                len(results["success"]),
                len(results["failed"]),
                duration_minutes
            )

        # Reporte final
        self.print_final_report(results, elapsed_time)

        return results

    def print_final_report(self, results: Dict, elapsed_time: float):
        """Imprime reporte final ultra compacto"""

        total = len(results["success"]) + len(results["failed"]) + len(results["skipped"])

        if results["failed"]:
            print(f"\n⚠️  Fallidos ({len(results['failed'])}):")
            for asin in results["failed"]:
                print(asin)

        print(f"\n✅ {len(results['success'])} OK | ❌ {len(results['failed'])} FAIL | ⏱️  {elapsed_time/60:.1f} min\n")

        # Guardar reporte en archivo (sin print)
        report_path = Config.LOGS_DIR / f"report_{self.run_id}.json"
        stats = self.db.get_statistics()
        with open(report_path, "w") as f:
            json.dump({
                "run_id": self.run_id,
                "timestamp": datetime.now().isoformat(),
                "elapsed_seconds": elapsed_time,
                "results": results,
                "statistics": stats
            }, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """Punto de entrada principal"""

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline Amazon → MercadoLibre CBT v2.0")
    parser.add_argument("--dry-run", action="store_true", help="Simular publicaciones sin enviar a ML")
    parser.add_argument("--enable-validation", action="store_true", help="Activar validación IA (está desactivada por defecto)")
    parser.add_argument("--force-regenerate", action="store_true", help="Forzar regeneración de archivos existentes")
    parser.add_argument("--skip-health-check", action="store_true", help="Saltar verificaciones de salud")
    parser.add_argument("--asin", type=str, help="Procesar solo un ASIN específico")
    parser.add_argument("--asins-file", type=str, help="Archivo con lista de ASINs (default: data/asins.txt)")

    args = parser.parse_args()

    # Configurar flags
    Config.DRY_RUN = args.dry_run
    # Si se pasa --enable-validation, activar (SKIP_VALIDATION = False)
    if args.enable_validation:
        Config.SKIP_VALIDATION = False
    # De lo contrario, mantener el default de Config (True)
    # Solo sobrescribir FORCE_REGENERATE si se pasa el flag explícitamente
    if args.force_regenerate:
        Config.FORCE_REGENERATE = True
    # De lo contrario, mantener el default de Config class (True)

    # Configurar archivo de ASINs
    if args.asins_file:
        Config.ASINS_FILE = Path(args.asins_file)

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
