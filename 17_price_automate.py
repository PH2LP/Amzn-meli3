#!/usr/bin/env python3
"""
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
PRICE_MARKUP_MAX = 100  # 100% máximo para automatización
PRICE_MARKUP_MIN = 15  # 15% mínimo
USE_TAX = os.getenv("USE_TAX", "true").lower() == "true"
TAX_RATE = 0.07
FULFILLMENT_FEE = 4.0
MAX_WORKERS = 15  # Número de threads paralelos (balance entre velocidad y confiabilidad)
RETRY_ATTEMPTS = 2  # Número de reintentos para errores temporales

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

def create_automation(item_id: str, min_price: float, max_price: float) -> bool:
    """
    Crea automatización de precios para un item

    Args:
        item_id: ID del item en ML
        min_price: Precio mínimo (15% markup)
        max_price: Precio máximo (35% markup actual)

    Returns:
        True si se creó correctamente
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
            return True
        elif response.status_code == 412:
            # Item no elegible para automatización - silencioso
            return False
        else:
            # Solo mostrar otros errores
            error_msg = response.text[:200] if len(response.text) > 200 else response.text
            log(f"    ⚠️  Error HTTP {response.status_code}: {error_msg}", Colors.YELLOW)
            return False

    except Exception as e:
        log(f"    ❌ Error creando automatización: {e}", Colors.RED)
        return False

def process_local_item(local_item_id: str, site_id: str, min_price: float, max_price: float, stats: dict, asin: str = None) -> dict:
    """
    Procesa un item local (para paralelización)
    OPTIMIZADO: Intenta crear directamente, solo verifica si ya existe cuando falla

    Returns:
        dict con resultado del procesamiento
    """
    result = {
        "site_id": site_id,
        "item_id": local_item_id,
        "success": False,
        "action": None,
        "error": None
    }

    try:
        # OPTIMIZACIÓN: Intentar crear directamente (1 llamada API en vez de 2)
        url = f"https://api.mercadolibre.com/marketplace/items/{local_item_id}/prices/automate"
        headers = {
            "Authorization": f"Bearer {ML_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "rule_id": "INT",
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2)
        }

        # Intentar POST (crear) con reintentos
        last_error = None
        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=15)
                break  # Éxito, salir del loop
            except (requests.Timeout, requests.ConnectionError) as e:
                last_error = e
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(0.5)  # Esperar antes de reintentar
                    continue
                else:
                    # Último intento falló
                    raise

        if response.status_code == 200:
            # Creado exitosamente
            result["action"] = "created"
            result["success"] = True
            with stats_lock:
                stats["created"] += 1
            print(f"\r✅ {site_id}: {local_item_id} - Creado (Min: ${min_price:.2f}, Max: ${max_price:.2f})                    ")

        elif response.status_code == 412:
            # Ya existe, intentar PUT (actualizar) con reintentos
            for attempt in range(RETRY_ATTEMPTS):
                try:
                    response = requests.put(url, headers=headers, json=payload, timeout=15)
                    break
                except (requests.Timeout, requests.ConnectionError):
                    if attempt < RETRY_ATTEMPTS - 1:
                        time.sleep(0.5)
                        continue
                    else:
                        raise

            if response.status_code == 200:
                result["action"] = "updated"
                result["success"] = True
                with stats_lock:
                    stats["updated"] += 1
                print(f"\r🔄 {site_id}: {local_item_id} - Actualizado (Min: ${min_price:.2f}, Max: ${max_price:.2f})                    ")
            else:
                # PUT falló, verificar si ya está configurado con los mismos valores
                get_resp = requests.get(url, headers=headers, timeout=5)
                if get_resp.status_code == 200:
                    current = get_resp.json()
                    current_min = current.get("min_price")
                    current_max = current.get("max_price")

                    if abs(current_min - min_price) < 0.01 and abs(current_max - max_price) < 0.01:
                        result["action"] = "already_configured"
                        result["success"] = True
                        with stats_lock:
                            stats["already_configured"] += 1
                    else:
                        result["action"] = "update_failed"
                        with stats_lock:
                            stats["errors"] += 1
                else:
                    result["action"] = "update_failed"
                    with stats_lock:
                        stats["errors"] += 1

        elif response.status_code == 400:
            # Error 400 - contar pero no mostrar cada uno
            with stats_lock:
                stats["errors"] += 1
            result["action"] = "error_400"

        else:
            # Otros errores
            with stats_lock:
                stats["errors"] += 1
            result["action"] = f"error_{response.status_code}"

    except Exception as e:
        result["error"] = str(e)
        with stats_lock:
            stats["errors"] += 1

    return result

def update_automation(item_id: str, min_price: float, max_price: float) -> bool:
    """
    Actualiza automatización existente
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
            return True
        elif response.status_code == 412:
            # Item no elegible para automatización - silencioso
            return False
        else:
            error_msg = response.text[:200] if len(response.text) > 200 else response.text
            log(f"    ⚠️  Error HTTP {response.status_code}: {error_msg}", Colors.YELLOW)
            return False

    except Exception as e:
        log(f"    ❌ Error actualizando automatización: {e}", Colors.RED)
        return False

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
        "skipped": 0,
        "not_eligible": 0  # Items con error 412
    }

    # Iniciar cronómetro
    import time
    start_time = time.time()

    # Calcular total de items (expandiendo CBTs a site_items)
    total_items = 0
    for _, item_id, _, _, site_items_json in listings:
        if item_id and item_id.startswith("CBT") and site_items_json:
            try:
                site_items = json.loads(site_items_json) if isinstance(site_items_json, str) else site_items_json
                total_items += len([si for si in site_items if isinstance(si, dict) and si.get("item_id")])
            except:
                pass
        else:
            total_items += 1

    log(f"   Total items a procesar (expandido): {total_items}", Colors.CYAN)
    print()

    # Procesar cada listing
    items_processed = 0
    for i, (asin, item_id, costo_amazon, price_usd_current, site_items_json) in enumerate(listings, 1):
        stats["total"] += 1

        # Mostrar progreso SIEMPRE (en cada listing)
        print(f"\r[{i}/{len(listings)} CBTs | {items_processed}/{total_items} items] ✅ {stats['created']} | 🔄 {stats['updated']} | ⊗ {stats['errors']}     ", end="", flush=True)

        # Calcular precios
        min_price = compute_price(costo_amazon, PRICE_MARKUP_MIN)
        max_price = compute_price(costo_amazon, PRICE_MARKUP_MAX)

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

            # Procesar en paralelo con límite de workers
            if local_items_to_process:
                with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(local_items_to_process))) as executor:
                    futures = [
                        executor.submit(process_local_item, item_id, site_id, min_price, max_price, stats, asin)
                        for item_id, site_id in local_items_to_process
                    ]

                    # Esperar a que terminen todos
                    for future in as_completed(futures):
                        try:
                            future.result()
                            items_processed += 1
                        except Exception as e:
                            with stats_lock:
                                stats["errors"] += 1
                            items_processed += 1

        else:
            items_processed += 1
            # Item local o CBT sin site_items: aplicar directamente (OPTIMIZADO)
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

            # Intentar POST (crear)
            response = requests.post(url, headers=headers, json=payload, timeout=10)

            if response.status_code == 200:
                stats["created"] += 1
                print(f"\r✅ {asin} ({item_id}) - Creado (Min: ${min_price:.2f}, Max: ${max_price:.2f})                    ")

            elif response.status_code == 412:
                # Ya existe, intentar PUT (actualizar)
                response = requests.put(url, headers=headers, json=payload, timeout=10)

                if response.status_code == 200:
                    stats["updated"] += 1
                    print(f"\r🔄 {asin} ({item_id}) - Actualizado (Min: ${min_price:.2f}, Max: ${max_price:.2f})                    ")
                else:
                    # PUT falló, verificar si ya está configurado
                    get_resp = requests.get(url, headers=headers, timeout=5)
                    if get_resp.status_code == 200:
                        current = get_resp.json()
                        current_min = current.get("min_price")
                        current_max = current.get("max_price")

                        if abs(current_min - min_price) < 0.01 and abs(current_max - max_price) < 0.01:
                            stats["already_configured"] += 1
                        else:
                            stats["errors"] += 1
                    else:
                        stats["errors"] += 1

            else:
                stats["errors"] += 1

        # Sin rate limiting - ya está optimizado con paralelización

    # Calcular tiempo total
    elapsed_time = time.time() - start_time
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)

    # Resumen final
    print()
    log("="*80, Colors.BLUE)
    log("📊 RESUMEN FINAL:", Colors.BLUE)
    log("="*80, Colors.BLUE)
    log(f"   Total procesados:        {stats['total']}")
    log(f"   ✅ Creados:              {stats['created']}", Colors.GREEN)
    log(f"   🔄 Actualizados:         {stats['updated']}", Colors.CYAN)
    log(f"   ✓ Ya configurados:       {stats['already_configured']}", Colors.YELLOW)
    log(f"   ⊗ Salteados (errores):   {stats['errors']}", Colors.RED)
    log(f"   ⏱️  Tiempo total:          {minutes}m {seconds}s", Colors.CYAN)
    log("="*80, Colors.BLUE)
    print()

    # Estadísticas adicionales
    total_successful = stats['created'] + stats['updated'] + stats['already_configured']
    success_rate = (total_successful / total_items * 100) if total_items > 0 else 0

    log(f"📈 Tasa de éxito: {success_rate:.1f}% ({total_successful}/{total_items} items)", Colors.CYAN)
    log(f"   Items procesados: {total_successful + stats['errors']}/{total_items}", Colors.CYAN)

    if stats["created"] + stats["updated"] > 0:
        log(f"✅ Automatización activada en {stats['created'] + stats['updated']} items!", Colors.GREEN)
        log("💡 Los precios se ajustarán automáticamente entre 15% y 100% de ganancia", Colors.CYAN)
    else:
        log("ℹ️  No se crearon ni actualizaron automatizaciones nuevas", Colors.YELLOW)

    if stats['errors'] > 0:
        log(f"\n⚠️  {stats['errors']} items fueron salteados (inactivos, no elegibles, o errores)", Colors.YELLOW)

        # Preguntar si quiere reintentar los errores
        retry = input("\n¿Reintentar items que fallaron? (s/N): ")
        if retry.lower() == 's':
            log("\n🔄 Reintentando items que fallaron...", Colors.CYAN)
            # TODO: Implementar retry aquí
            log("⚠️  Función de retry aún no implementada", Colors.YELLOW)

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
