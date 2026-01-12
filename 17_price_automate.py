#!/usr/bin/env python3
"""

python3 17_price_automate.py 

Activa automatización de precios en MercadoLibre
Lee precios desde la DB y configura min_price (15% markup) y max_price (80% markup)
"""

import os
import sys
import json
import sqlite3
import requests
import time
from pathlib import Path
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Cargar .env
load_dotenv(override=True)

# Configuración
DB_PATH = "storage/listings_database.db"
ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
PRICE_MARKUP_MAX = float(os.getenv("PRICE_AUTOMATE_MAX_MARKUP", "80"))  # Leer desde .env
PRICE_MARKUP_MIN = float(os.getenv("PRICE_AUTOMATE_MIN_MARKUP", "15"))  # Leer desde .env
USE_TAX = os.getenv("USE_TAX", "true").lower() == "true"
TAX_RATE = 0.07
FULFILLMENT_FEE = 4.0
MAX_WORKERS = 10  # Número de threads paralelos

# Lock para stats thread-safe
stats_lock = Lock()

# Colores
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

def log(msg, color=Colors.NC):
    print(f"{color}{msg}{Colors.NC}")

def compute_price(base_usd: float, markup_percent: float) -> float:
    """
    Calcula precio con markup específico
    DEBE coincidir con calculate_new_ml_price() de sync_amazon_ml.py

    Args:
        base_usd: Precio base de Amazon
        markup_percent: Porcentaje de markup (ej: 15 para 15%)

    Returns:
        Precio final en USD
    """
    tax = round(base_usd * TAX_RATE, 2) if USE_TAX else 0.0
    total_cost = round(base_usd + tax + FULFILLMENT_FEE, 2)
    final_price = round(total_cost * (1.0 + markup_percent / 100.0), 2)
    return final_price

def get_listings_from_db():
    """
    Obtiene listings de la DB con precio y item_id

    Returns:
        Lista de tuplas (asin, item_id, costo_amazon, price_usd_current, site_items)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT asin, item_id, costo_amazon, price_usd, site_items
        FROM listings
        WHERE item_id IS NOT NULL
        AND costo_amazon IS NOT NULL
        AND costo_amazon > 0
    """)

    listings = cursor.fetchall()
    conn.close()

    return listings

def get_automation_status(item_id: str) -> dict:
    """
    Verifica si ya existe automatización para este item

    Returns:
        dict con la configuración actual o None si no existe
    """
    try:
        url = f"https://api.mercadolibre.com/marketplace/items/{item_id}/prices/automate"
        headers = {"Authorization": f"Bearer {ML_TOKEN}"}

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            # No tiene automatización
            return None
        else:
            log(f"    ⚠️  Error verificando automatización: HTTP {response.status_code}", Colors.YELLOW)
            return None
    except Exception as e:
        log(f"    ⚠️  Error: {e}", Colors.YELLOW)
        return None

def create_automation(item_id: str, min_price: float, max_price: float) -> tuple:
    """
    Crea automatización de precios para un item

    Args:
        item_id: ID del item en ML
        min_price: Precio mínimo (15% markup)
        max_price: Precio máximo (35% markup actual)

    Returns:
        (True/False, error_message)
    """
    try:
        url = f"https://api.mercadolibre.com/marketplace/items/{item_id}/prices/automate"
        headers = {
            "Authorization": f"Bearer {ML_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "rule_id": "INT",  # Competir solo dentro de ML
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2)
        }

        response = requests.post(url, headers=headers, json=payload, timeout=15)

        if response.status_code == 200:
            return (True, None)
        elif response.status_code == 412:
            # Si ya existe, verificar si tiene los valores correctos
            try:
                error_data = response.json()
                if error_data.get('error') == 'automation_already_created':
                    # Verificar valores actuales
                    check_response = requests.get(url, headers=headers, timeout=10)
                    if check_response.status_code == 200:
                        current = check_response.json()
                        current_min = current.get('min_price')
                        current_max = current.get('max_price')

                        if abs(current_min - min_price) < 0.01 and abs(current_max - max_price) < 0.01:
                            return (True, "already_configured")
                        else:
                            # Actualizar con valores correctos
                            return update_automation(item_id, min_price, max_price)
            except:
                pass

            try:
                error_data = response.json()
                error_msg = f"HTTP {response.status_code}: {error_data.get('error', 'unknown')}"
            except:
                error_msg = f"HTTP {response.status_code}"
            return (False, error_msg)
        else:
            try:
                error_data = response.json()
                error_msg = f"HTTP {response.status_code}: {error_data.get('error', 'unknown')}"
            except:
                error_msg = f"HTTP {response.status_code}"
            return (False, error_msg)

    except Exception as e:
        return (False, str(e))

def process_local_item(local_item_id: str, site_id: str, min_price: float, max_price: float, stats: dict) -> dict:
    """
    Procesa un item local (para paralelización)

    Returns:
        dict con resultado del procesamiento
    """
    import time
    start_time = time.time()

    result = {
        "site_id": site_id,
        "item_id": local_item_id,
        "success": False,
        "action": None,
        "error": None,
        "http_status": None,
        "elapsed_time": 0,
        "error_message": None
    }

    try:
        # Verificar automatización existente
        current_automation = get_automation_status(local_item_id)

        if current_automation:
            current_min = current_automation.get("min_price")
            current_max = current_automation.get("max_price")

            if abs(current_min - min_price) < 0.01 and abs(current_max - max_price) < 0.01:
                result["action"] = "already_configured"
                result["success"] = True
                with stats_lock:
                    stats["already_configured"] += 1
            else:
                status, error_msg = update_automation(local_item_id, min_price, max_price)
                if status:
                    result["action"] = "updated"
                    result["success"] = True
                    with stats_lock:
                        stats["updated"] += 1
                else:
                    result["action"] = "update_failed"
                    result["error_message"] = error_msg
                    with stats_lock:
                        stats["errors"] += 1
        else:
            status, error_msg = create_automation(local_item_id, min_price, max_price)
            if status:
                result["action"] = "created"
                result["success"] = True
                with stats_lock:
                    stats["created"] += 1
            else:
                result["action"] = "create_failed"
                result["error_message"] = error_msg
                with stats_lock:
                    stats["errors"] += 1

    except Exception as e:
        result["error"] = str(e)
        with stats_lock:
            stats["errors"] += 1

    result["elapsed_time"] = time.time() - start_time
    return result

def update_automation(item_id: str, min_price: float, max_price: float) -> tuple:
    """
    Actualiza automatización existente

    Returns:
        (True/False, error_message)
    """
    try:
        url = f"https://api.mercadolibre.com/marketplace/items/{item_id}/prices/automate"
        headers = {
            "Authorization": f"Bearer {ML_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "rule_id": "INT",
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2)
        }

        response = requests.put(url, headers=headers, json=payload, timeout=15)

        if response.status_code == 200:
            return (True, None)
        elif response.status_code == 412:
            # Automatización pausada o bloqueada - intentar DELETE + CREATE
            try:
                error_data = response.json()
                if 'automation_operation_not_allowed' in error_data.get('error', ''):
                    # DELETE + CREATE
                    delete_response = requests.delete(url, headers=headers, timeout=10)
                    if delete_response.status_code in [200, 204]:
                        # Recrear
                        create_response = requests.post(url, headers=headers, json=payload, timeout=15)
                        if create_response.status_code == 200:
                            # Verificar si quedó pausada por item inactivo
                            check_response = requests.get(url, headers=headers, timeout=10)
                            if check_response.status_code == 200:
                                auto_data = check_response.json()
                                if auto_data.get('status') == 'PAUSED':
                                    status_detail = auto_data.get('status_detail', {})
                                    cause = status_detail.get('cause', 'unknown')
                                    return (True, f"paused_{cause}")
                            return (True, None)
            except:
                pass

            try:
                error_data = response.json()
                error_msg = f"HTTP {response.status_code}: {error_data.get('error', 'unknown')}"
            except:
                error_msg = f"HTTP {response.status_code}"
            return (False, error_msg)
        else:
            try:
                error_data = response.json()
                error_msg = f"HTTP {response.status_code}: {error_data.get('error', 'unknown')}"
            except:
                error_msg = f"HTTP {response.status_code}"
            return (False, error_msg)

    except Exception as e:
        return (False, str(e))

def main():
    if not ML_TOKEN:
        log("❌ Error: ML_ACCESS_TOKEN no encontrado en .env", Colors.RED)
        sys.exit(1)

    log("\n" + "="*80, Colors.BLUE)
    log("ACTIVAR AUTOMATIZACIÓN DE PRECIOS EN MERCADOLIBRE", Colors.BLUE)
    log("="*80 + "\n", Colors.BLUE)

    # Mostrar configuración
    log("⚙️  CONFIGURACIÓN:", Colors.CYAN)
    log(f"   Markup máximo:           {int(PRICE_MARKUP_MAX)}%", Colors.GREEN)
    log(f"   Markup mínimo:           {int(PRICE_MARKUP_MIN)}%", Colors.YELLOW)
    tax_status = f"{int(TAX_RATE * 100)}% ACTIVADO" if USE_TAX else "DESACTIVADO"
    log(f"   Tax (Florida):           {tax_status}")
    log(f"   Fulfillment fee:         ${FULFILLMENT_FEE}")
    log(f"   Regla de competencia:    INT_EXT (Solo dentro de ML)", Colors.CYAN)
    print()

    # Confirmar
    confirm = input("¿Continuar con la activación de automatización? (s/N): ")
    if confirm.lower() != 's':
        log("❌ Operación cancelada", Colors.YELLOW)
        return
    print()

    # Obtener listings de la DB
    log("📊 Obteniendo listings de la DB...", Colors.CYAN)
    listings = get_listings_from_db()

    if not listings:
        log("❌ No se encontraron listings con precio en la DB", Colors.RED)
        return

    log(f"✅ Encontrados {len(listings)} listings con precio\n", Colors.GREEN)

    # Estadísticas
    stats = {
        "total": 0,
        "created": 0,
        "updated": 0,
        "already_configured": 0,
        "errors": 0,
        "skipped": 0
    }

    # Procesar cada listing
    for i, (asin, item_id, costo_amazon, price_usd_current, site_items_json) in enumerate(listings, 1):
        stats["total"] += 1

        # Calcular precios
        min_price = compute_price(costo_amazon, PRICE_MARKUP_MIN)
        max_price = compute_price(costo_amazon, PRICE_MARKUP_MAX)

        # Header con ASIN e Item ID global
        print()
        log(f"[{i}/{len(listings)}] {asin} → {item_id}", Colors.CYAN)
        log(f"   Costo: ${costo_amazon:.2f} | Min: ${min_price:.2f} | Max: ${max_price:.2f}", Colors.BLUE)

        # Parsear site_items
        site_items = []
        if site_items_json:
            try:
                site_items = json.loads(site_items_json) if isinstance(site_items_json, str) else site_items_json
            except:
                pass

        # Determinar si es CBT (global) o local
        is_cbt = item_id.startswith("CBT")

        if is_cbt and site_items:
            # CBT: aplicar a cada item local EN PARALELO
            # Preparar items locales para procesar
            local_items_to_process = []
            for site_item in site_items:
                if not isinstance(site_item, dict):
                    continue

                local_item_id = site_item.get("item_id")
                site_id = site_item.get("site_id")

                if local_item_id:
                    local_items_to_process.append((local_item_id, site_id))

            # Procesar en paralelo
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {
                    executor.submit(process_local_item, item_id, site_id, min_price, max_price, stats): (item_id, site_id)
                    for item_id, site_id in local_items_to_process
                }

                # Esperar resultados y mostrar
                for future in as_completed(futures):
                    result = future.result()
                    site_id = result["site_id"]
                    local_id = result["item_id"]
                    elapsed = result.get("elapsed_time", 0)

                    if result["success"]:
                        if result["action"] == "created":
                            log(f"      {site_id} ({local_id}): ✅ CREADO ({elapsed:.2f}s)", Colors.GREEN)
                        elif result["action"] == "updated":
                            log(f"      {site_id} ({local_id}): 🔄 ACTUALIZADO ({elapsed:.2f}s)", Colors.CYAN)
                        elif result["action"] == "already_configured":
                            log(f"      {site_id} ({local_id}): ✓ Ya configurado ({elapsed:.2f}s)", Colors.YELLOW)
                    else:
                        error_msg = result.get("error_message", "Error desconocido")
                        log(f"      {site_id} ({local_id}): ❌ {error_msg} ({elapsed:.2f}s)", Colors.RED)

        else:
            # Item local o CBT sin site_items: aplicar directamente
            current_automation = get_automation_status(item_id)

            if current_automation:
                current_min = current_automation.get("min_price")
                current_max = current_automation.get("max_price")

                if abs(current_min - min_price) < 0.01 and abs(current_max - max_price) < 0.01:
                    stats["already_configured"] += 1
                    log(f"   ✓ Ya configurado", Colors.YELLOW)
                else:
                    status, error_msg = update_automation(item_id, min_price, max_price)
                    if status:
                        stats["updated"] += 1
                        log(f"   🔄 ACTUALIZADO", Colors.CYAN)
                    else:
                        stats["errors"] += 1
                        log(f"   ❌ {error_msg}", Colors.RED)
            else:
                status, error_msg = create_automation(item_id, min_price, max_price)
                if status:
                    stats["created"] += 1
                    log(f"   ✅ CREADO", Colors.GREEN)
                else:
                    stats["errors"] += 1
                    log(f"   ❌ {error_msg}", Colors.RED)

        # Sin rate limiting - ya está optimizado con paralelización

    # Resumen final
    print()
    log("="*80, Colors.BLUE)
    log("📊 RESUMEN FINAL:", Colors.BLUE)
    log("="*80, Colors.BLUE)
    log(f"   Total procesados:        {stats['total']}")
    log(f"   ✅ Creados:              {stats['created']}", Colors.GREEN)
    log(f"   🔄 Actualizados:         {stats['updated']}", Colors.CYAN)
    log(f"   ✓ Ya configurados:       {stats['already_configured']}", Colors.YELLOW)
    log(f"   ❌ Errores:              {stats['errors']}", Colors.RED)
    log("="*80, Colors.BLUE)
    print()

    if stats["created"] + stats["updated"] > 0:
        log("✅ Automatización de precios activada!", Colors.GREEN)
        log("💡 Los precios se ajustarán automáticamente entre 15% y 35% de ganancia", Colors.CYAN)
    else:
        log("ℹ️  No se crearon ni actualizaron automatizaciones", Colors.YELLOW)
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Operación cancelada (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        log(f"\n❌ Error: {e}", Colors.RED)
        import traceback
        traceback.print_exc()
        sys.exit(1)
