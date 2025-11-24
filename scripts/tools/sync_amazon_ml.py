#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO DE SINCRONIZACIÓN AMAZON <-> MERCADOLIBRE
================================================
Este script sincroniza automáticamente los listings de MercadoLibre con Amazon:
- Detecta productos pausados/descontinuados en Amazon → Pausa en ML
- Detecta cambios de precio en Amazon → Actualiza precio en ML proporcionalmente
- Aplica filtro de Fast Fulfillment (pausa productos con backorder o >24h warehouse time)
- Se ejecuta cada 3 días vía cron job

Filtros aplicados (desde amazon_pricing.py):
- Solo productos Prime + FBA
- availabilityType = "NOW" con maximumHours ≤ 24
- O availabilityType = "FUTURE_WITH_DATE" con ≤7 días
- Rechaza backorders largos y productos sin fecha

Configuración del cron job:
0 9 */3 * * cd /Users/felipemelucci/Desktop/revancha && ./venv/bin/python3 sync_amazon_ml.py >> logs/sync_amazon_ml.log 2>&1
"""

import os
import sys
import json
import sqlite3
import requests
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(override=True)

# Agregar directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.integrations.amazon_pricing import get_prime_offers_batch_optimized

# Importar notificaciones Telegram (bot separado para sync)
try:
    from telegram_sync_notifier import (
        notify_sync_success,
        notify_sync_error,
        notify_price_update,
        notify_listing_paused,
        notify_listing_reactivated,
        notify_sync_start,
        notify_sync_complete,
        is_configured as telegram_configured
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    def notify_sync_success(*args, **kwargs): pass
    def notify_sync_error(*args, **kwargs): pass
    def notify_price_update(*args, **kwargs): pass
    def notify_listing_paused(*args, **kwargs): pass
    def notify_listing_reactivated(*args, **kwargs): pass
    def notify_sync_start(*args, **kwargs): pass
    def notify_sync_complete(*args, **kwargs): pass
    def telegram_configured(): return False

# Configuración
DB_PATH = "storage/listings_database.db"
LOG_DIR = Path("logs/sync")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# APIs
SPAPI_BASE = "https://sellingpartnerapi-na.amazon.com"
MARKETPLACE_ID = "ATVPDKIKX0DER"  # Amazon US
ML_API = "https://api.mercadolibre.com"
ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")

# Configuración de precios
PRICE_MARKUP_PERCENT = float(os.getenv("PRICE_MARKUP", 500))

# ============================================================
# FUNCIONES PARA AMAZON SP-API
# ============================================================

def get_amazon_access_token():
    """Obtiene access token de Amazon usando LWA"""
    client_id = os.getenv("LWA_CLIENT_ID")
    client_secret = os.getenv("LWA_CLIENT_SECRET")
    refresh_token = os.getenv("REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise RuntimeError("❌ Faltan credenciales de Amazon en .env")

    url = "https://api.amazon.com/auth/o2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    try:
        r = requests.post(url, data=data, timeout=15)
        r.raise_for_status()
        return r.json()["access_token"]
    except Exception as e:
        raise RuntimeError(f"❌ Error obteniendo token de Amazon: {e}")


def check_amazon_product_status_from_cache(asin, prime_offer_cache):
    """
    Verifica el estado de un producto usando el cache de ofertas Prime.

    Esta versión optimizada usa datos pre-cargados en batch en vez de
    hacer requests individuales a Amazon (4x más rápido).

    Args:
        asin: ASIN del producto
        prime_offer_cache: Dict con {asin: prime_offer} pre-cargado con batch

    Returns:
        dict: {
            "available": bool,
            "price": float or None,
            "buyable": bool,
            "status": str  # "active", "unavailable", "not_found", "error"
        }
    """
    result = {
        "available": False,
        "price": None,
        "buyable": False,
        "status": "unknown",
        "error": None
    }

    # Verificar si tenemos datos Prime para este ASIN
    if asin not in prime_offer_cache:
        result["status"] = "error"
        result["error"] = "ASIN no encontrado en cache de pricing"
        return result

    prime_offer = prime_offer_cache[asin]

    if prime_offer:
        # Tiene oferta Prime activa
        result["price"] = prime_offer["price"]
        result["buyable"] = True
        result["available"] = True
        result["status"] = "active"
    else:
        # No hay oferta Prime = producto no disponible para nosotros
        result["status"] = "no_prime"
        result["error"] = "Sin oferta Prime activa"
        result["available"] = False

    return result


# ============================================================
# FUNCIONES PARA MERCADOLIBRE API
# ============================================================

def ml_http_get(url, params=None):
    """GET request a ML con manejo de errores"""
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"⚠️ Error GET {url}: {e}")
        return None


def ml_http_put(url, body):
    """PUT request a ML para actualizar items"""
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}
    try:
        r = requests.put(url, headers=headers, json=body, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"⚠️ Error PUT {url}: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"   Response: {e.response.text[:500]}")
        return None


def pause_ml_listing(item_id, site_items=None, price_usd=None):
    """
    Pausa una publicación CBT en MercadoLibre poniendo stock en 0.

    Para productos CBT, la forma de "pausar" efectivamente es poner
    available_quantity en 0. Esto hace que el producto aparezca como
    "sin stock" en MercadoLibre, evitando ventas cuando no hay disponibilidad
    en Amazon.

    Nota: El status "paused" en la API no oculta el producto del sitio web.
    Solo setting stock=0 previene ventas de productos no disponibles.

    Args:
        item_id: CBT item ID global
        site_items: JSON string o lista con info de países (no usado)
        price_usd: Precio actual del producto en USD (no usado)

    Returns:
        bool: True si se pausó exitosamente (stock=0)
    """
    url = f"{ML_API}/global/items/{item_id}"

    # Para productos CBT globales, ponemos stock en 0
    body = {"available_quantity": 0}

    print(f"   📦 Poniendo stock en 0 (sin disponibilidad)...")
    result = ml_http_put(url, body)

    if result is not None:
        print(f"   ✅ Stock actualizado a 0 exitosamente")

        # Actualizar en BD
        try:
            update_listing_stock_in_db(item_id, 0)
        except Exception as e:
            print(f"   ⚠️ Error actualizando BD: {e}")

        return True
    else:
        print(f"   ❌ Error actualizando stock")
        return False


def reactivate_ml_listing(item_id, quantity=10):
    """
    Reactiva una publicación CBT en MercadoLibre poniendo stock > 0.

    Cuando un producto vuelve a estar disponible en Amazon después de
    haber estado sin stock, esta función restaura el inventario en ML.

    Args:
        item_id: CBT item ID global
        quantity: Cantidad de stock a establecer (default: 10)

    Returns:
        bool: True si se reactivó exitosamente
    """
    url = f"{ML_API}/global/items/{item_id}"

    # Poner stock disponible
    body = {"available_quantity": quantity}

    print(f"   ♻️ Reactivando producto (stock: {quantity})...")
    result = ml_http_put(url, body)

    if result is not None:
        print(f"   ✅ Producto reactivado exitosamente")

        # Actualizar en BD
        try:
            update_listing_stock_in_db(item_id, quantity)
        except Exception as e:
            print(f"   ⚠️ Error actualizando BD: {e}")

        return True
    else:
        print(f"   ❌ Error reactivando producto")
        return False


def update_ml_price(item_id, new_price_usd, site_items=None):
    """
    Actualiza el precio de una publicación CBT en ML.
    Si site_items está disponible, actualiza por país.
    Sino, intenta actualizar el precio global.

    Args:
        item_id: CBT item ID global
        new_price_usd: Nuevo precio en USD
        site_items: Lista de dicts con {site_id, item_id, status} por país

    Returns:
        tuple: (success: bool, failed_countries: list)
    """
    import json

    url = f"{ML_API}/global/items/{item_id}"
    failed_countries = []

    # Si tenemos site_items, actualizar por país
    if site_items:
        try:
            site_items_list = json.loads(site_items) if isinstance(site_items, str) else site_items
        except:
            site_items_list = None

        if site_items_list:
            print(f"   🌍 Actualizando precio por país usando site_listings...")

            # Construir array de site_listings con listing_item_id
            site_listings = []
            for site_item in site_items_list:
                # Solo incluir países que tienen item_id Y que NO tienen error
                # Esto excluye MLM fulfillment y otros que no soportan net_proceeds
                has_item_id = site_item.get("item_id") is not None
                has_error = site_item.get("error") is not None

                if has_item_id and not has_error:
                    site_listings.append({
                        "logistic_type": site_item.get("logistic_type", "remote"),
                        "listing_item_id": site_item.get("item_id"),
                        "net_proceeds": round(new_price_usd, 2)
                    })
                elif has_error:
                    # Log para debug: qué países se están saltando
                    site_id = site_item.get("site_id", "unknown")
                    error_code = site_item.get("error", {}).get("code", "unknown")
                    print(f"      ⏭️  Saltando {site_id}: {error_code}")

            if site_listings:
                body = {"site_listings": site_listings}

                print(f"      Actualizando {len(site_listings)} país(es)...")
                result = ml_http_put(url, body)

                if result is None:
                    # Si falla, marcar todos como fallidos
                    failed_countries = [s["listing_item_id"][:3] for s in site_listings]
                    print(f"      ❌ Error en actualización masiva")
                    return (False, failed_countries)
                else:
                    print(f"      ✅ Actualizado correctamente")

                    # Actualizar en BD
                    try:
                        update_listing_price_in_db(item_id, new_price_usd)
                    except Exception as e:
                        print(f"      ⚠️ Error actualizando BD: {e}")

                    return (True, [])
            else:
                print(f"      ⚠️ No hay países válidos para actualizar")
                return (False, [])

    # Fallback: intentar actualizar net_proceeds global (puede no funcionar si no hay site_items)
    print(f"   ⚠️ Sin site_items, intentando actualización global...")
    body = {"net_proceeds": round(new_price_usd, 2)}
    result = ml_http_put(url, body)
    return (result is not None, failed_countries)


# ============================================================
# FUNCIONES DE BASE DE DATOS
# ============================================================

def get_all_published_listings():
    """
    Obtiene todos los listings publicados desde la base de datos.
    Retorna lista de dicts con: item_id, asin, price_usd, site_items
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT item_id, asin, price_usd, title, site_items
        FROM listings
        WHERE item_id IS NOT NULL
        ORDER BY date_updated DESC
    """)

    listings = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return listings


def update_listing_price_in_db(item_id, new_price_usd):
    """Actualiza el precio almacenado en la BD"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE listings
        SET price_usd = ?,
            date_updated = ?
        WHERE item_id = ?
    """, (new_price_usd, datetime.now().isoformat(), item_id))

    conn.commit()
    conn.close()


def update_listing_stock_in_db(item_id, stock):
    """Actualiza el stock almacenado en la BD (campo auxiliar para tracking)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Verificar si existe columna 'stock' en la tabla
    cursor.execute("PRAGMA table_info(listings)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'stock' not in columns:
        # Agregar columna stock si no existe
        cursor.execute("ALTER TABLE listings ADD COLUMN stock INTEGER DEFAULT 10")

    cursor.execute("""
        UPDATE listings
        SET stock = ?,
            date_updated = ?
        WHERE item_id = ?
    """, (stock, datetime.now().isoformat(), item_id))

    conn.commit()
    conn.close()


# ============================================================
# LÓGICA PRINCIPAL DE SINCRONIZACIÓN
# ============================================================

def calculate_new_ml_price(amazon_price_usd):
    """
    Calcula el nuevo precio de ML para sincronización.

    Fórmula: (Amazon + Tax 7% + $4 USD) × (1 + Markup 30%)

    Ejemplo con Amazon = $35.99:
    - Tax 7%: $35.99 × 0.07 = $2.52
    - 3PL Fee: $4.00
    - Costo: $35.99 + $2.52 + $4.00 = $42.51
    - Markup 30%: $42.51 × 1.30 = $55.26 USD

    DEBE coincidir con compute_price() de transform_mapper_new.py
    """
    # Paso 1: Precio base de Amazon
    base_price = amazon_price_usd

    # Paso 2: Agregar tax 7%
    TAX_PERCENT = 7.0
    tax_amount = round(base_price * (TAX_PERCENT / 100.0), 2)

    # Paso 3: Agregar 3PL fee $4 USD
    THREE_PL_FEE = 4.0

    # Paso 4: Costo total = Amazon + Tax 7% + $4 USD
    total_cost = round(base_price + tax_amount + THREE_PL_FEE, 2)

    # Paso 5: Agregar markup 30%
    MARKUP_PERCENT = 30.0
    final_price = round(total_cost * (1.0 + MARKUP_PERCENT / 100.0), 2)

    return final_price


def sync_one_listing(listing, prime_offer_cache, changes_log):
    """
    Sincroniza un solo listing con Amazon.

    Args:
        listing: dict con item_id, asin, price_usd, title
        prime_offer_cache: dict con {asin: prime_offer} pre-cargado
        changes_log: lista para registrar cambios

    Returns:
        dict con resultado de la sincronización
    """
    item_id = listing["item_id"]
    asin = listing["asin"]
    current_price = listing["price_usd"]
    title = listing["title"]
    site_items = listing.get("site_items")  # Países donde está publicado

    print(f"\n{'='*80}")
    print(f"🔄 Sincronizando: {asin}")
    print(f"   ML Item ID: {item_id}")
    print(f"   Título: {title[:60]}...")
    print(f"   Precio actual ML: ${current_price} USD")

    # Consultar estado en Amazon usando cache pre-cargado
    print(f"   📡 Verificando datos Prime (desde cache batch)...")
    amazon_status = check_amazon_product_status_from_cache(asin, prime_offer_cache)

    result = {
        "item_id": item_id,
        "asin": asin,
        "action": "none",
        "success": False,
        "message": "",
        "amazon_status": amazon_status
    }

    # Caso 1: Producto sin Prime / No cumple Fast Fulfillment → Pausar en ML
    if amazon_status["status"] == "no_prime":
        # Obtener razón del rechazo desde prime_offer
        prime_offer = prime_offer_cache.get(asin)
        pause_reason = amazon_status.get('error', 'Sin oferta Prime activa')

        # Mejorar mensaje si fue rechazado por fast fulfillment
        if prime_offer is None:
            print(f"   ⚠️ PRODUCTO RECHAZADO POR FILTROS")
            print(f"   📋 Razón: {pause_reason}")
            print(f"   ⏸️ ACCIÓN: Pausar publicación")
        else:
            print(f"   ⚠️ PRODUCTO SIN AMAZON PRIME")
            print(f"   ⏸️ ACCIÓN: Pausar publicación (solo publicamos productos Prime)")

        if pause_ml_listing(item_id, site_items, current_price):
            result["action"] = "paused"
            result["success"] = True
            result["message"] = f"Pausado: {pause_reason}"
            print(f"   ✅ Publicación pausada exitosamente")

            if telegram_configured():
                notify_listing_paused(asin, item_id, pause_reason)
        else:
            result["action"] = "pause_failed"
            result["message"] = "Error al pausar publicación"
            print(f"   ❌ Error pausando publicación")

    # Caso 2: Producto no disponible en Amazon → Pausar en ML
    elif amazon_status["status"] in ["not_found", "unavailable", "unreleased"]:
        print(f"   ⚠️ Estado Amazon: {amazon_status['status']}")
        print(f"   ⚠️ Razón: {amazon_status.get('error', 'Desconocida')}")
        print(f"   ⏸️ ACCIÓN: Pausar publicación en ML")

        if pause_ml_listing(item_id, site_items, current_price):
            result["action"] = "paused"
            result["success"] = True
            reason = amazon_status.get('error', 'No disponible en Amazon')
            result["message"] = f"Pausado: {reason}"
            print(f"   ✅ Publicación pausada exitosamente")

            # Notificar por Telegram
            if telegram_configured():
                notify_listing_paused(asin, item_id, reason)
        else:
            result["action"] = "pause_failed"
            result["message"] = "Error al pausar publicación"
            print(f"   ❌ Error pausando publicación")

    # Caso 2: Producto activo pero sin precio
    elif amazon_status["status"] == "active" and not amazon_status["price"]:
        print(f"   ℹ️ Producto activo pero sin precio disponible")
        print(f"   ⏸️ ACCIÓN: Pausar publicación en ML por precaución")

        if pause_ml_listing(item_id, site_items, current_price):
            result["action"] = "paused"
            result["success"] = True
            reason = "Sin precio en Amazon"
            result["message"] = f"Pausado: {reason}"
            print(f"   ✅ Publicación pausada exitosamente")

            # Notificar por Telegram
            if telegram_configured():
                notify_listing_paused(asin, item_id, reason)
        else:
            result["action"] = "pause_failed"
            result["message"] = "Error al pausar publicación"
            print(f"   ❌ Error pausando publicación")

    # Caso 3: Producto activo con precio → Verificar si cambió
    elif amazon_status["status"] == "active" and amazon_status["price"]:
        amazon_price = amazon_status["price"]
        new_ml_price = calculate_new_ml_price(amazon_price)

        print(f"   ✅ Producto disponible en Amazon")
        print(f"   💰 Precio Amazon: ${amazon_price} USD")
        print(f"   💰 Precio ML calculado (con {PRICE_MARKUP_PERCENT}% markup): ${new_ml_price} USD")

        # REACTIVACIÓN: Si el producto estaba sin stock en ML, reactivarlo primero
        # Consultamos el stock actual en ML
        ml_item_data = ml_http_get(f"{ML_API}/items/{item_id}", params={})
        if ml_item_data:
            current_ml_stock = ml_item_data.get("available_quantity", 10)

            if current_ml_stock == 0:
                print(f"   ℹ️ Producto tiene stock=0 en ML, reactivando...")
                if reactivate_ml_listing(item_id, quantity=10):
                    result["action"] = "reactivated"
                    result["success"] = True
                    result["message"] = "Producto reactivado (stock: 0 → 10)"
                    print(f"   ✅ Producto reactivado exitosamente")

                    # Notificar por Telegram
                    if telegram_configured():
                        notify_listing_reactivated(asin, item_id)
                else:
                    print(f"   ❌ Error reactivando producto")


        # Calcular diferencia porcentual
        if current_price and current_price > 0:
            price_diff_percent = abs((new_ml_price - current_price) / current_price * 100)
        else:
            price_diff_percent = 100  # Si no hay precio anterior, actualizar

        # Solo actualizar si la diferencia es mayor al 2%
        PRICE_CHANGE_THRESHOLD = 2.0

        if price_diff_percent > PRICE_CHANGE_THRESHOLD:
            print(f"   📊 Cambio de precio: {price_diff_percent:.1f}% (umbral: {PRICE_CHANGE_THRESHOLD}%)")
            print(f"   🔄 ACCIÓN: Actualizar precio en ML")

            success, failed_countries = update_ml_price(item_id, new_ml_price, site_items)

            if success:
                # Actualizar también en BD
                update_listing_price_in_db(item_id, new_ml_price)

                result["action"] = "price_updated"
                result["success"] = True
                result["message"] = f"Precio actualizado: ${current_price} → ${new_ml_price} USD"
                result["old_price"] = current_price
                result["new_price"] = new_ml_price
                print(f"   ✅ Precio actualizado exitosamente")

                # Notificar por Telegram
                if telegram_configured():
                    # Obtener países desde site_items
                    countries = []
                    if site_items:
                        try:
                            import json
                            site_items_list = json.loads(site_items) if isinstance(site_items, str) else site_items
                            countries = [s.get("site_id", "") for s in site_items_list if not s.get("error")]
                        except:
                            countries = ["MLM", "MLB", "MLC", "MCO", "MLA"]
                    else:
                        countries = ["Global"]

                    notify_price_update(asin, current_price, new_ml_price, countries)
            else:
                result["action"] = "price_update_failed"
                result["message"] = "Error al actualizar precio"
                print(f"   ❌ Error actualizando precio")

                # Notificar error por Telegram
                if telegram_configured():
                    error_msg = f"Error actualizando precio"
                    if failed_countries:
                        error_msg += f" en países: {', '.join(failed_countries)}"
                    notify_sync_error(asin, error_msg)

            # Si algunos países fallaron pero no todos
            if failed_countries:
                print(f"   ⚠️ Países con errores: {', '.join(failed_countries)}")
        else:
            print(f"   ℹ️ Diferencia de precio: {price_diff_percent:.1f}% (menor al umbral)")
            print(f"   ✅ No se requiere actualización")
            result["action"] = "no_change"
            result["success"] = True
            result["message"] = "Sin cambios significativos"

    # Caso 4: Error consultando Amazon
    else:
        print(f"   ⚠️ Error consultando Amazon: {amazon_status.get('error', 'Desconocido')}")
        result["action"] = "error"
        result["message"] = amazon_status.get("error", "Error desconocido")

    # Registrar cambio en el log
    changes_log.append(result)

    return result


def main():
    """Función principal de sincronización"""
    start_time = datetime.now()

    print("=" * 80)
    print("🔄 SINCRONIZACIÓN AMAZON → MERCADOLIBRE")
    print("=" * 80)
    print(f"📅 Fecha: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Markup configurado: {PRICE_MARKUP_PERCENT}%")
    print()

    # Verificar que existe la BD
    if not os.path.exists(DB_PATH):
        print(f"❌ No se encontró la base de datos: {DB_PATH}")
        print("   Ejecuta primero save_listing_data.py para crear la BD")
        sys.exit(1)

    # Obtener todos los listings publicados
    print("📋 Cargando listings desde la base de datos...")
    listings = get_all_published_listings()

    if not listings:
        print("⚠️ No se encontraron listings publicados en la BD")
        print("   Asegúrate de que los listings tengan item_id asignado")
        sys.exit(0)

    print(f"✅ Encontrados {len(listings)} listings para sincronizar\n")

    # Notificar inicio de sync
    if telegram_configured():
        notify_sync_start(len(listings))

    # Extraer todos los ASINs para hacer batch request
    asins = [listing["asin"] for listing in listings]

    # Obtener precios Prime en BATCH (mucho más rápido que individual)
    print(f"📊 Obteniendo precios Prime de {len(asins)} productos en BATCH...")
    print(f"   (Endpoint optimizado: 20 ASINs por request, 4x más rápido)\n")

    prime_offer_cache = get_prime_offers_batch_optimized(asins, batch_size=20, show_progress=True)

    print(f"\n✅ Cache de precios Prime cargado ({len(prime_offer_cache)} productos)\n")

    # Log de cambios
    changes_log = []

    # Estadísticas
    stats = {
        "total": len(listings),
        "paused": 0,
        "price_updated": 0,
        "no_change": 0,
        "errors": 0
    }

    # Sincronizar cada listing (usando cache, sin delays)
    for i, listing in enumerate(listings, 1):
        print(f"\n[{i}/{len(listings)}]", end=" ")

        result = sync_one_listing(listing, prime_offer_cache, changes_log)

        # Actualizar estadísticas
        if result["success"]:
            if result["action"] == "paused":
                stats["paused"] += 1
            elif result["action"] == "price_updated":
                stats["price_updated"] += 1
            elif result["action"] == "no_change":
                stats["no_change"] += 1
        else:
            stats["errors"] += 1

        # Ya NO necesitamos delay entre listings porque usamos cache pre-cargado
        # El delay ya se manejó en get_prime_offers_batch_optimized()

    # Guardar log de cambios
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"sync_{timestamp}.json"

    log_data = {
        "timestamp": datetime.now().isoformat(),
        "statistics": stats,
        "changes": changes_log
    }

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    # Calcular duración
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds() / 60  # en minutos

    # Resumen final
    print("\n" + "=" * 80)
    print("📊 RESUMEN DE SINCRONIZACIÓN")
    print("=" * 80)
    print(f"Total procesados:     {stats['total']}")
    print(f"Publicaciones pausadas: {stats['paused']}")
    print(f"Precios actualizados:   {stats['price_updated']}")
    print(f"Sin cambios:            {stats['no_change']}")
    print(f"Errores:                {stats['errors']}")
    print()
    print(f"📄 Log guardado en: {log_file}")
    print(f"⏱️ Duración: {duration:.1f} minutos")
    print("\n✅ Sincronización completada")

    # Notificar finalización de sync
    if telegram_configured():
        notify_sync_complete(stats, duration)


if __name__ == "__main__":
    main()
