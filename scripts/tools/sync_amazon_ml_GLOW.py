#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO DE SINCRONIZACIÓN AMAZON <-> MERCADOLIBRE (VERSIÓN V2 ADVANCED)
========================================================================
Este script sincroniza automáticamente los listings de MercadoLibre con Amazon:
- Detecta productos pausados/descontinuados en Amazon → Pausa en ML
- Detecta cambios de precio en Amazon → Actualiza precio en ML proporcionalmente
- Aplica filtro de Fast Fulfillment (delivery ≤ MAX_DELIVERY_DAYS)
- Se ejecuta cada 3 días vía cron job

NUEVA VERSIÓN V2 - Sistema Anti-Detección Profesional:
- ✅ Session Rotation (nueva sesión cada 100 requests)
- ✅ Exponential Backoff con Jitter (auto-recovery de bloqueos)
- ✅ Rate Limiting Inteligente (~0.5 req/sec)
- ✅ Randomized Processing Order
- ✅ User-Agent Rotation (10 navegadores diferentes)
- ✅ NO requiere delays manuales (todo integrado en la API)

Usa amazon_glow_api_v2_advanced.py para obtener:
- Precio REAL del HTML de Amazon.com
- Fecha de delivery REAL usando el zipcode configurado (BUYER_ZIPCODE en .env)
- Validación de disponibilidad y stock

Configuración del cron job:
0 9 */3 * * cd /Users/felipemelucci/Desktop/revancha && ./venv/bin/python3 scripts/tools/sync_amazon_ml_GLOW.py >> logs/sync_amazon_ml.log 2>&1
"""

import os
import sys
import json
import sqlite3
import requests
import time
import random
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
# override=False para respetar variables pasadas por script wrapper (28/29)
load_dotenv(override=False)

# Agregar directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.integrations.amazon_glow_api_v2_advanced import check_availability_v2_advanced
from src.integrations.mainglobal import refresh_ml_token

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

# Obtener token del .env local (mantenido actualizado por 08_token_loop.py)
def get_fresh_ml_token():
    """
    Lee el ML_ACCESS_TOKEN del .env local.

    El .env local es actualizado automáticamente cada 6 horas por 08_token_loop.py,
    por lo que siempre contiene un token fresco y válido.

    Returns:
        str: Token de MercadoLibre
    """
    env_token = os.getenv("ML_ACCESS_TOKEN")
    if env_token and env_token.startswith("APP_USR-"):
        print(f"✅ Usando token del .env local (últimos 10 chars: ...{env_token[-10:]})", flush=True)
        return env_token
    else:
        print(f"⚠️ Token no encontrado en .env", flush=True)
        return ""

# Obtener token fresco al inicio
ML_TOKEN = get_fresh_ml_token()
ML_USER_ID = os.getenv("ML_USER_ID")  # Para detectar items de otra cuenta

# Seller IDs conocidos de NEXO (diferentes por marketplace)
# Estos seller_ids corresponden a la cuenta NEXO en diferentes países
NEXO_SELLER_IDS = {
    "3047790551",  # User ID principal
    "3047796173",  # MCO (Colombia)
    "3048288440",  # MLM (México)
    "3048288454",  # MLB (Brasil)
    "3048288470",  # MLA (Argentina)
    "3048289672",  # MLC (Chile)
    "3048289692",  # MLM Fulfillment
}

# Seller IDs conocidos de ONEWORLD (cuenta anterior)
ONEWORLD_SELLER_IDS = {
    "2629800952",  # USONEWORLDARR
    "2629798326",  # USONEWORLDCOR
    "2629798354",  # USONEWORLDCLR
}

# Configuración de precios
PRICE_MARKUP_PERCENT = float(os.getenv("PRICE_MARKUP", 500))

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def is_wrong_account_item(site_items_json):
    """
    Verifica si un item pertenece a una cuenta diferente a la actual (ONEWORLD).

    Args:
        site_items_json: String JSON con site_items de la DB (array de objetos)

    Returns:
        bool: True si el item pertenece EXCLUSIVAMENTE a cuenta ONEWORLD (no NEXO)
    """
    if not site_items_json:
        return False

    try:
        site_items = json.loads(site_items_json)

        # Si no hay datos, no es error de cuenta diferente
        if not site_items:
            return False

        # Verificar si TODOS los seller_ids pertenecen a ONEWORLD
        # site_items es un ARRAY de objetos: [{"seller_id": ..., "site_id": ...}, ...]
        has_nexo = False
        has_oneworld = False

        for site_data in site_items:
            # Saltar entradas que tienen error (no tienen seller_id válido)
            if "error" in site_data:
                continue

            seller_id = str(site_data.get("seller_id", ""))

            # Verificar si es NEXO
            if seller_id in NEXO_SELLER_IDS:
                has_nexo = True
                break  # Si tiene al menos un NEXO, no es cuenta diferente

            # Verificar si es ONEWORLD
            if seller_id in ONEWORLD_SELLER_IDS:
                has_oneworld = True

        # Es cuenta diferente solo si tiene ONEWORLD pero NO tiene NEXO
        return has_oneworld and not has_nexo

    except (json.JSONDecodeError, AttributeError, TypeError):
        return False

# ============================================================
# FUNCIONES PARA GLOW API (PRECIO + DELIVERY)
# ============================================================

def get_glow_data_batch(asins: list, show_progress: bool = True) -> dict:
    """
    Obtiene precio y disponibilidad de múltiples ASINs usando Glow API.

    A diferencia de SP-API que da datos genéricos, Glow API obtiene:
    - Precio REAL del HTML de Amazon.com
    - Fecha de delivery REAL usando el zipcode configurado
    - Validación de Prime badge
    - Validación de stock

    Args:
        asins: Lista de ASINs
        show_progress: Mostrar progreso en consola

    Returns:
        Dict: {asin: glow_data} o {asin: None} si no cumple requisitos

        glow_data = {
            "price": 199.95,
            "delivery_date": "Wednesday, December 25",
            "days_until_delivery": 2,
            "is_fast_delivery": True,
            "prime_available": True,
            "in_stock": True
        }
    """
    if not asins:
        return {}

    # Configuración desde .env
    max_delivery_days = int(os.getenv("MAX_DELIVERY_DAYS", "3"))
    buyer_zipcode = os.getenv("BUYER_ZIPCODE", "33172")

    results = {}
    total = len(asins)

    if show_progress:
        print(f"🌐 Consultando Glow API para {total} productos...")
        print(f"   Zipcode: {buyer_zipcode}")
        print(f"   Max delivery: {max_delivery_days} días")
        print()

    for i, asin in enumerate(asins, 1):
        if show_progress:
            print(f"   [{i}/{total}] {asin}...", end=" ", flush=True)

        try:
            # Llamar a Glow API V2 Advanced (con anti-detección integrado)
            glow_result = check_availability_v2_advanced(asin, buyer_zipcode)

            # Verificar si tiene error
            if glow_result.get("error"):
                error_msg = str(glow_result.get("error")) if glow_result.get("error") else "Error desconocido"
                if show_progress:
                    print(f"❌ {error_msg[:50]}")
                results[asin] = None
                continue

            # Validar requisitos mínimos
            if not glow_result.get("available"):
                if show_progress:
                    print("❌ No disponible")
                results[asin] = None
                continue

            if not glow_result.get("price"):
                if show_progress:
                    print("❌ Sin precio")
                results[asin] = None
                continue

            # Validar delivery days (FREE delivery ≤ max_delivery_days)
            days_until = glow_result.get("days_until_delivery")
            delivery_date_text = glow_result.get("delivery_date", "")

            # Caso especial: delivery_date existe pero days_until es None (rango de fechas)
            if days_until is None:
                if delivery_date_text and show_progress:
                    # Mostrar el rango de fechas encontrado
                    print(f"❌ Llega entre {delivery_date_text[:50]} (sin fecha específica, RECHAZADO)")
                elif show_progress:
                    print(f"❌ Sin información de delivery (RECHAZADO)")
                results[asin] = None
                continue

            # Validar que no exceda max_delivery_days
            if days_until > max_delivery_days:
                if show_progress:
                    print(f"❌ Llega: {delivery_date_text[:30]}, Días: {days_until} (max: {max_delivery_days}, RECHAZADO)")
                results[asin] = None
                continue

            # ✅ El producto pasó todas las validaciones
            results[asin] = {
                "price": glow_result["price"],
                "delivery_date": glow_result.get("delivery_date"),
                "days_until_delivery": days_until,
                "is_fast_delivery": glow_result.get("is_fast_delivery", False),
                "prime_available": glow_result.get("prime_available", False),
                "in_stock": glow_result.get("in_stock", False)
            }

            if show_progress:
                print(f"✅ Precio: ${glow_result['price']:.2f}, Llega: {delivery_date_text[:30]}, Días: {days_until} (APROBADO)")

        except Exception as e:
            if show_progress:
                print(f"❌ Error: {str(e)[:50]}")
            results[asin] = None

        # NOTA: Los delays ya están manejados DENTRO de check_availability_v2_advanced()
        # con Session Rotation, Rate Limiting, y Exponential Backoff
        # No necesitamos delays adicionales aquí

    if show_progress:
        passed = sum(1 for v in results.values() if v is not None)
        print()
        print(f"✅ Resultados: {passed}/{total} productos aprobados")
        print()

    return results


def check_amazon_product_status_from_cache(asin, glow_cache):
    """
    Verifica el estado de un producto usando el cache de Glow API.

    Args:
        asin: ASIN del producto
        glow_cache: Dict con {asin: glow_data} pre-cargado con Glow API

    Returns:
        dict: {
            "available": bool,
            "price": float or None,
            "buyable": bool,
            "status": str,  # "active", "unavailable", "not_found", "error"
            "delivery_date": str,
            "days_until_delivery": int
        }
    """
    result = {
        "available": False,
        "price": None,
        "buyable": False,
        "status": "unknown",
        "error": None,
        "delivery_date": None,
        "days_until_delivery": None
    }

    # Verificar si tenemos datos de Glow para este ASIN
    if asin not in glow_cache:
        result["status"] = "error"
        result["error"] = "ASIN no encontrado en cache de Glow"
        return result

    glow_data = glow_cache[asin]

    if glow_data:
        # Producto disponible y cumple requisitos (precio + delivery rápido)
        result["price"] = glow_data["price"]
        result["buyable"] = True
        result["available"] = True
        result["status"] = "active"
        result["delivery_date"] = glow_data.get("delivery_date")
        result["days_until_delivery"] = glow_data.get("days_until_delivery")
        result["prime_available"] = glow_data.get("prime_available")
        result["in_stock"] = glow_data.get("in_stock")
    else:
        # No cumple requisitos (sin precio, delivery lento, no disponible, etc)
        result["status"] = "unavailable"
        result["error"] = "No cumple requisitos de fast delivery o sin precio"
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

    IMPORTANTE: A diferencia de los precios, el stock en CBT NO puede actualizarse
    por país usando site_listings. Solo se puede actualizar el stock global, y ML
    lo propaga automáticamente a todos los países.

    Nota: El status "paused" en la API no oculta el producto del sitio web.
    Solo setting stock=0 previene ventas de productos no disponibles.

    Args:
        item_id: CBT item ID global
        site_items: JSON string o lista con info de países (no usado para stock)
        price_usd: Precio actual del producto en USD (no usado)

    Returns:
        bool: True si se pausó exitosamente (stock=0)
    """
    url = f"{ML_API}/global/items/{item_id}"

    # Para productos CBT globales, ponemos stock en 0
    # Esto se propaga automáticamente a todos los países
    body = {"available_quantity": 0}

    print(f"   📦 Poniendo stock en 0 (sin disponibilidad)...")
    result = ml_http_put(url, body)

    if result is not None:
        print(f"   ✅ Stock actualizado a 0 exitosamente")
        print(f"   ℹ️  La propagación a todos los países puede tardar unos minutos")

        # Actualizar en BD
        try:
            update_listing_stock_in_db(item_id, 0)
        except Exception as e:
            print(f"   ⚠️ Error actualizando BD: {e}")

        return True
    else:
        print(f"   ❌ Error actualizando stock")
        return False


def reactivate_ml_listing(item_id, site_items=None, quantity=10):
    """
    Reactiva una publicación CBT en MercadoLibre poniendo stock > 0.

    Cuando un producto vuelve a estar disponible en Amazon después de
    haber estado sin stock, esta función restaura el inventario en ML.

    IMPORTANTE: A diferencia de los precios, el stock en CBT NO puede actualizarse
    por país usando site_listings. Solo se puede actualizar el stock global, y ML
    lo propaga automáticamente a todos los países.

    Args:
        item_id: CBT item ID global
        site_items: JSON string o lista con info de países (no usado para stock)
        quantity: Cantidad de stock a establecer (default: 10)

    Returns:
        bool: True si se reactivó exitosamente
    """
    url = f"{ML_API}/global/items/{item_id}"

    # Poner stock disponible
    # Esto se propaga automáticamente a todos los países
    body = {"available_quantity": quantity}

    print(f"   ♻️ Reactivando producto (stock: {quantity})...")
    result = ml_http_put(url, body)

    if result is not None:
        print(f"   ✅ Producto reactivado exitosamente")
        print(f"   ℹ️  La propagación a todos los países puede tardar unos minutos")

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
            print(f"   🌍 Actualizando precio por país (individual)...")

            # Filtrar países válidos
            valid_countries = []
            for site_item in site_items_list:
                has_item_id = site_item.get("item_id") is not None
                has_error = site_item.get("error") is not None

                if has_item_id and not has_error:
                    valid_countries.append(site_item)
                elif has_error:
                    site_id = site_item.get("site_id", "unknown")
                    error_code = site_item.get("error", {}).get("code", "unknown")
                    print(f"      ⏭️  Saltando {site_id}: {error_code}")

            if not valid_countries:
                print(f"      ⚠️ No hay países válidos para actualizar")
                return (False, [])

            # Actualizar país por país individualmente
            print(f"      Actualizando {len(valid_countries)} país(es) individualmente...")
            success_count = 0
            failed_countries = []

            for site_item in valid_countries:
                site_id = site_item.get("site_id")
                listing_item_id = site_item.get("item_id")

                # Request individual por país
                site_listings = [{
                    "logistic_type": site_item.get("logistic_type", "remote"),
                    "listing_item_id": listing_item_id,
                    "net_proceeds": round(new_price_usd, 2)
                }]

                body = {"site_listings": site_listings}
                result = ml_http_put(url, body)

                if result is None:
                    failed_countries.append(site_id)
                    print(f"      ❌ {site_id}: Error")
                else:
                    success_count += 1

            # Si al menos uno funcionó, considerar éxito
            if success_count > 0:
                print(f"      ✅ Actualizados {success_count}/{len(valid_countries)} países")

                # Actualizar en BD
                try:
                    update_listing_price_in_db(item_id, new_price_usd)
                except Exception as e:
                    print(f"      ⚠️ Error actualizando BD: {e}")

                if failed_countries:
                    print(f"      ⚠️ Países con errores: {', '.join(failed_countries)}")

                return (True, failed_countries)
            else:
                print(f"      ❌ Todos los países fallaron")
                return (False, failed_countries)

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
    Retorna lista de dicts con: item_id, asin, price_usd, amazon_price_last, site_items
    """
    print("   → Conectando a base de datos...", flush=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Verificar si existe columna amazon_price_last, si no existe crearla
    cursor.execute("PRAGMA table_info(listings)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'amazon_price_last' not in columns:
        print("   → Agregando columna amazon_price_last...", flush=True)
        cursor.execute("ALTER TABLE listings ADD COLUMN amazon_price_last REAL DEFAULT NULL")
        conn.commit()

    print("   → Ejecutando query SQL...", flush=True)
    cursor.execute("""
        SELECT item_id, asin, price_usd, amazon_price_last, title, site_items
        FROM listings
        WHERE item_id IS NOT NULL
        ORDER BY date_updated DESC
    """)

    print("   → Convirtiendo resultados...", flush=True)
    listings = [dict(row) for row in cursor.fetchall()]
    conn.close()
    print(f"   → Listo! {len(listings)} listings cargados", flush=True)
    return listings


def update_listing_price_in_db(item_id, new_price_usd, amazon_price=None):
    """
    Actualiza el precio almacenado en la BD.

    Args:
        item_id: ID del item en ML
        new_price_usd: Nuevo precio en ML (USD)
        amazon_price: Precio actual de Amazon (para tracking de cambios)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if amazon_price is not None:
        cursor.execute("""
            UPDATE listings
            SET price_usd = ?,
                amazon_price_last = ?,
                date_updated = ?
            WHERE item_id = ?
        """, (new_price_usd, amazon_price, datetime.now().isoformat(), item_id))
    else:
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

    Lee configuración desde .env:
    - PRICE_MARKUP: Porcentaje de markup (ej: 150 para 150%)
    - USE_TAX: true/false para aplicar tax 7%
    - FULFILLMENT_FEE: Fee 3PL en USD (default: 4.0)

    Fórmula: (Amazon + Tax [opcional] + Fee) × (1 + Markup%)

    Ejemplo con Amazon = $35.99, PRICE_MARKUP=30, USE_TAX=true:
    - Tax 7%: $35.99 × 0.07 = $2.52
    - 3PL Fee: $4.00
    - Costo: $35.99 + $2.52 + $4.00 = $42.51
    - Markup 30%: $42.51 × 1.30 = $55.26 USD

    DEBE coincidir con compute_price() de transform_mapper_new.py
    """
    # Leer configuración desde .env
    PRICE_MARKUP = float(os.getenv("PRICE_MARKUP", "30"))
    USE_TAX = os.getenv("USE_TAX", "true").lower() == "true"
    FULFILLMENT_FEE = float(os.getenv("FULFILLMENT_FEE", "4.0"))
    TAX_RATE = 0.07  # 7% Florida tax

    # Paso 1: Precio base de Amazon
    base_price = amazon_price_usd

    # Paso 2: Agregar tax si está habilitado
    tax_amount = round(base_price * TAX_RATE, 2) if USE_TAX else 0.0

    # Paso 3: Costo total = Amazon + Tax [opcional] + Fee
    total_cost = round(base_price + tax_amount + FULFILLMENT_FEE, 2)

    # Paso 4: Agregar markup
    final_price = round(total_cost * (1.0 + PRICE_MARKUP / 100.0), 2)

    return final_price


def sync_one_listing(listing, glow_cache, changes_log):
    """
    Sincroniza un solo listing con Amazon usando datos de Glow API.

    Args:
        listing: dict con item_id, asin, price_usd, amazon_price_last, title
        glow_cache: dict con {asin: glow_data} pre-cargado con Glow API
        changes_log: lista para registrar cambios

    Returns:
        dict con resultado de la sincronización
    """
    item_id = listing["item_id"]
    asin = listing["asin"]
    current_price = listing["price_usd"]
    amazon_price_last = listing.get("amazon_price_last")  # Último precio conocido de Amazon
    title = listing["title"]
    site_items = listing.get("site_items")  # Países donde está publicado

    print(f"\n{'='*80}")
    print(f"🔄 Sincronizando: {asin}")
    print(f"   ML Item ID: {item_id}")
    print(f"   Título: {title[:60]}...")
    print(f"   Precio actual ML: ${current_price} USD")
    if amazon_price_last:
        print(f"   Último precio Amazon conocido: ${amazon_price_last} USD")

    # Consultar estado en Amazon usando cache de Glow API
    print(f"   🌐 Verificando datos desde Glow API (precio + delivery real)...")
    amazon_status = check_amazon_product_status_from_cache(asin, glow_cache)

    result = {
        "item_id": item_id,
        "asin": asin,
        "action": "none",
        "success": False,
        "message": "",
        "amazon_status": amazon_status,
        "site_items": site_items  # Para detectar errores por cuenta diferente
    }

    # Caso 1: Producto NO disponible / No cumple requisitos → Pausar en ML
    if amazon_status["status"] in ["unavailable", "error"]:
        pause_reason = amazon_status.get('error', 'No cumple requisitos de fast delivery o sin precio')

        print(f"   ⚠️ PRODUCTO NO DISPONIBLE")
        print(f"   📋 Razón: {pause_reason}")
        print(f"   ⏸️ ACCIÓN: Pausar publicación en ML")

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

    # Caso 2: Producto ACTIVO (precio + delivery rápido) → Sincronizar precio
    elif amazon_status["status"] == "active" and amazon_status["price"]:
        amazon_price = amazon_status["price"]
        new_ml_price = calculate_new_ml_price(amazon_price)

        # Leer markup actual del .env para el log
        current_markup = float(os.getenv("PRICE_MARKUP", "30"))
        print(f"   ✅ Producto disponible en Amazon")
        print(f"   💰 Precio Amazon: ${amazon_price} USD")
        print(f"   💰 Precio ML calculado (con {current_markup}% markup): ${new_ml_price} USD")

        # REACTIVACIÓN: Si el producto estaba sin stock en ML, reactivarlo primero
        # Consultamos el stock actual en ML
        ml_item_data = ml_http_get(f"{ML_API}/items/{item_id}", params={})
        if ml_item_data:
            current_ml_stock = ml_item_data.get("available_quantity", 10)

            if current_ml_stock == 0:
                print(f"   ℹ️ Producto tiene stock=0 en ML, reactivando...")
                if reactivate_ml_listing(item_id, site_items=site_items, quantity=10):
                    result["action"] = "reactivated"
                    result["success"] = True
                    result["message"] = "Producto reactivado (stock: 0 → 10)"
                    print(f"   ✅ Producto reactivado exitosamente")

                    # Notificar por Telegram
                    if telegram_configured():
                        notify_listing_reactivated(asin, item_id)
                else:
                    print(f"   ❌ Error reactivando producto")


        # NUEVA LÓGICA: Comparar precio de Amazon actual vs último precio conocido
        # Esto previene que el sync sobreescriba los precios bajados por la función
        # de catálogo automático de MercadoLibre
        #
        # SYNC_FORCE_PRICE_UPDATE (en .env):
        #   - true:  Actualiza TODOS los precios siempre (ignora si cambió en Amazon)
        #   - false: Solo actualiza si el precio cambió en Amazon (comportamiento inteligente)

        PRICE_CHANGE_THRESHOLD = 2.0  # Umbral de cambio en Amazon (2%)
        FORCE_UPDATE = os.getenv("SYNC_FORCE_PRICE_UPDATE", "false").lower() == "true"
        should_update = False

        if FORCE_UPDATE:
            # Modo FORCE: Siempre actualizar, comparando precio ML actual vs precio calculado
            print(f"   🔄 MODO FORCE ACTIVADO: Actualizando precio independientemente de cambios en Amazon")
            should_update = True
        elif amazon_price_last is None:
            # Primera vez que sincronizamos este producto, siempre actualizar
            print(f"   ℹ️ Primera sincronización para este producto")
            print(f"   🔄 ACCIÓN: Actualizar precio y guardar precio Amazon de referencia")
            should_update = True
        else:
            # Comparar precio actual de Amazon vs último precio conocido
            amazon_price_diff = abs(amazon_price - amazon_price_last)
            amazon_price_diff_percent = (amazon_price_diff / amazon_price_last * 100) if amazon_price_last > 0 else 100

            if amazon_price_diff_percent > PRICE_CHANGE_THRESHOLD:
                print(f"   📊 Precio Amazon cambió: ${amazon_price_last} → ${amazon_price} ({amazon_price_diff_percent:.1f}%)")
                print(f"   🔄 ACCIÓN: Actualizar precio en ML")
                should_update = True
            else:
                print(f"   ℹ️ Precio Amazon sin cambios significativos: ${amazon_price} (diff: {amazon_price_diff_percent:.1f}%)")
                print(f"   ✅ No se actualiza (respeta ajustes de catálogo automático de ML)")
                result["action"] = "no_change"
                result["success"] = True
                result["message"] = f"Amazon sin cambios (${amazon_price})"

        # Actualizar precio si corresponde
        if should_update:
            success, failed_countries = update_ml_price(item_id, new_ml_price, site_items)

            if success:
                # Actualizar en BD el precio de ML Y el último precio de Amazon
                update_listing_price_in_db(item_id, new_ml_price, amazon_price)

                # Solo cambiar action a "price_updated" si NO fue reactivado antes
                if result["action"] != "reactivated":
                    result["action"] = "price_updated"
                else:
                    # Si fue reactivado, actualizar el mensaje para incluir el precio
                    result["message"] = f"Producto reactivado (stock: 0 → 10) y precio actualizado: ${current_price} → ${new_ml_price} USD"

                result["success"] = True
                result["old_price"] = current_price
                result["new_price"] = new_ml_price
                result["amazon_price"] = amazon_price
                print(f"   ✅ Precio ML actualizado: ${current_price} → ${new_ml_price}")
                print(f"   ✅ Precio Amazon guardado: ${amazon_price}")

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

    # Refrescar token de ML automáticamente si está expirado
    print("🔑 Verificando token de MercadoLibre...", flush=True)
    if refresh_ml_token():
        print("✅ Token de ML refrescado correctamente", flush=True)
    else:
        print("⚠️ Token de ML ya está vigente", flush=True)
    print(flush=True)

    # Recargar .env después de refresh (sin sobrescribir env vars ya seteadas por el loop)
    load_dotenv(override=False)
    global ML_TOKEN
    ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")

    # Leer configuración actual del .env
    current_markup = float(os.getenv("PRICE_MARKUP", "30"))
    use_tax = os.getenv("USE_TAX", "true").lower() == "true"
    fulfillment_fee = float(os.getenv("FULFILLMENT_FEE", "4.0"))
    max_delivery_days = int(os.getenv("MAX_DELIVERY_DAYS", "3"))

    print("=" * 80, flush=True)
    print("🔄 SINCRONIZACIÓN AMAZON → MERCADOLIBRE", flush=True)
    print("=" * 80, flush=True)
    print(f"📅 Fecha: {start_time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"💰 Markup configurado: {current_markup}%", flush=True)
    print(f"💵 Tax (7% Florida): {'ACTIVADO' if use_tax else 'DESACTIVADO'}", flush=True)
    print(f"📦 Fulfillment Fee: ${fulfillment_fee} USD", flush=True)
    print(f"🚚 Max Delivery Days: {max_delivery_days} días (productos con delivery >{max_delivery_days}d serán pausados)", flush=True)
    print(flush=True)

    # Verificar que existe la BD
    print(f"🔍 Verificando base de datos en: {DB_PATH}", flush=True)
    if not os.path.exists(DB_PATH):
        print(f"❌ No se encontró la base de datos: {DB_PATH}", flush=True)
        print("   Ejecuta primero save_listing_data.py para crear la BD", flush=True)
        sys.exit(1)
    print(f"✅ Base de datos encontrada", flush=True)
    print(flush=True)

    # Obtener todos los listings publicados
    print("📋 Cargando listings desde la base de datos...", flush=True)
    listings = get_all_published_listings()

    if not listings:
        print("⚠️ No se encontraron listings publicados en la BD", flush=True)
        print("   Asegúrate de que los listings tengan item_id asignado", flush=True)
        sys.exit(0)

    print(f"✅ Encontrados {len(listings)} listings para sincronizar\n", flush=True)

    # Notificar inicio de sync
    print("📲 Verificando notificación Telegram...", flush=True)
    if telegram_configured():
        print("   → Enviando notificación...", flush=True)
        notify_sync_start(len(listings))
        print("   → Notificación enviada", flush=True)
    else:
        print("   → Telegram no configurado, saltando", flush=True)

    # Extraer todos los ASINs
    print("📦 Extrayendo ASINs...", flush=True)
    asins = [listing["asin"] for listing in listings]
    print(f"   → {len(asins)} ASINs extraídos", flush=True)
    print()

    # Obtener precios + delivery REAL usando Glow API
    print(f"🌐 CONSULTANDO GLOW API", flush=True)
    print(f"{'='*80}", flush=True)
    print(f"Obteniendo precio y delivery real para {len(asins)} productos...", flush=True)
    print(f"Fuente: Amazon.com (HTML real con zipcode {os.getenv('BUYER_ZIPCODE', '33172')})", flush=True)
    print(f"{'='*80}", flush=True)
    print()

    glow_cache = get_glow_data_batch(asins, show_progress=True)

    print(f"{'='*80}", flush=True)
    passed = sum(1 for v in glow_cache.values() if v is not None)
    print(f"✅ Cache de Glow API listo: {passed}/{len(glow_cache)} productos aprobados")
    print(f"{'='*80}", flush=True)
    print()

    # Log de cambios
    changes_log = []

    # Estadísticas
    stats = {
        "total": len(listings),
        "paused": 0,
        "reactivated": 0,
        "price_updated": 0,
        "no_change": 0,
        "errors": 0,
        "errors_wrong_account": 0  # Errores por items de otra cuenta
    }

    # Sincronizar cada listing usando cache de Glow
    for i, listing in enumerate(listings, 1):
        print(f"\n[{i}/{len(listings)}]", end=" ")

        result = sync_one_listing(listing, glow_cache, changes_log)

        # Actualizar estadísticas
        if result["success"]:
            if result["action"] == "paused":
                stats["paused"] += 1
            elif result["action"] == "reactivated":
                stats["reactivated"] += 1
            elif result["action"] == "price_updated":
                stats["price_updated"] += 1
            elif result["action"] == "no_change":
                stats["no_change"] += 1
        else:
            # Incrementar errores totales
            stats["errors"] += 1

            # Detectar si el error es porque el item pertenece a otra cuenta
            if is_wrong_account_item(result.get("site_items")):
                stats["errors_wrong_account"] += 1

        # Los delays ya se manejaron en get_glow_data_batch()
        # No necesitamos delays adicionales aquí

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
    # Contar total de productos pausados en la DB
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM listings WHERE stock = 0")
        total_paused = cursor.fetchone()[0]
        conn.close()
    except Exception as e:
        print(f"⚠️ Error contando productos pausados: {e}")
        total_paused = None

    print("📊 RESUMEN DE SINCRONIZACIÓN")
    print("=" * 80)
    print(f"Total procesados:              {stats['total']}")
    print(f"Productos reactivados:         {stats['reactivated']}")
    print(f"Publicaciones pausadas ahora:  {stats['paused']}")
    if total_paused is not None:
        print(f"Total publicaciones pausadas:  {total_paused}")
    print(f"Precios actualizados:          {stats['price_updated']}")
    print(f"Sin cambios:                   {stats['no_change']}")
    print(f"Errores:                       {stats['errors']}")

    # Desglose de errores
    if stats['errors'] > 0:
        errors_other = stats['errors'] - stats['errors_wrong_account']
        print(f"   ├─ Cuenta diferente:  {stats['errors_wrong_account']}")
        print(f"   └─ Otros errores:     {errors_other}")

    print()
    print(f"📄 Log guardado en: {log_file}")
    print(f"⏱️ Duración: {duration:.1f} minutos")

    # Mostrar detalle de errores si los hay
    if stats['errors'] > 0:
        print("\n" + "=" * 80)
        print("❌ DETALLE DE ERRORES")
        print("=" * 80)

        error_changes = [c for c in changes_log if not c.get("success", True)]

        for i, change in enumerate(error_changes, 1):
            print(f"\n[{i}/{len(error_changes)}] ASIN: {change.get('asin', 'N/A')}")
            print(f"   ML Item ID: {change.get('item_id', 'N/A')}")
            print(f"   Acción intentada: {change.get('action', 'N/A')}")
            print(f"   Razón del error: {change.get('message', 'N/A')}")

            # Mostrar qué cambio se intentó aplicar
            if change.get('action') == 'pause_failed':
                print(f"   Cambio que falló: Intentó pausar el listing")
                amazon_status = change.get('amazon_status', {})
                print(f"   Por qué se quiso pausar: {amazon_status.get('error', 'N/A')}")

            elif change.get('action') in ['price_update_failed', 'reactivate_failed']:
                old_price = change.get('old_price')
                new_price = change.get('new_price')
                if old_price and new_price:
                    print(f"   Cambio que falló: Precio ${old_price} → ${new_price} USD")

                amazon_price = change.get('amazon_price')
                if amazon_price:
                    print(f"   Precio Amazon actual: ${amazon_price} USD")

    print("\n✅ Sincronización completada")

    # Notificar finalización de sync
    if telegram_configured():
        # Cargar stats del sync anterior para comparar
        prev_sync_stats = None
        try:
            # Buscar el log anterior más reciente
            prev_logs = sorted(LOG_DIR.glob("sync_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
            # Saltar el log actual (el primero) y tomar el segundo
            if len(prev_logs) >= 2:
                prev_log_file = prev_logs[1]
                with open(prev_log_file, 'r') as f:
                    prev_log_data = json.load(f)
                    prev_sync_stats = prev_log_data.get('statistics', {})
        except Exception as e:
            print(f"   ⚠️ No se pudo cargar sync anterior para comparación: {e}")

        notify_sync_complete(stats, duration, prev_sync_stats)

    # Limpiar JSONs viejos de storage/asins_json/ (evitar usar datos desactualizados)
    print("\n🧹 Limpiando JSONs viejos de ASINs...")
    asins_json_dir = Path("storage/asins_json")
    if asins_json_dir.exists():
        deleted_count = 0
        for json_file in asins_json_dir.glob("*.json"):
            try:
                json_file.unlink()
                deleted_count += 1
            except Exception as e:
                print(f"   ⚠️ Error eliminando {json_file.name}: {e}")
        print(f"   ✅ Eliminados {deleted_count} archivos JSON viejos")
    else:
        print(f"   ℹ️  Directorio {asins_json_dir} no existe")


if __name__ == "__main__":
    main()
