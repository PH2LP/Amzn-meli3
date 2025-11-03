#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO DE SINCRONIZACIÓN AMAZON <-> MERCADOLIBRE
================================================
Este script sincroniza automáticamente los listings de MercadoLibre con Amazon:
- Detecta productos pausados/descontinuados en Amazon → Pausa en ML
- Detecta cambios de precio en Amazon → Actualiza precio en ML proporcionalmente
- Se ejecuta cada 3 días vía cron job

Configuración del cron job:
0 9 */3 * * cd /Users/felipemelucci/Desktop/revancha && ./venv/bin/python3 sync_amazon_ml.py >> logs/sync_amazon_ml.log 2>&1
"""

import os
import sys
import json
import sqlite3
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(override=True)

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
PRICE_MARKUP_PERCENT = float(os.getenv("PRICE_MARKUP_PERCENT", 40))

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


def check_amazon_product_status(asin, access_token):
    """
    Verifica el estado de un producto en Amazon.

    Returns:
        dict: {
            "available": bool,
            "price": float or None,
            "buyable": bool,
            "status": str  # "active", "unavailable", "not_found", "error"
        }
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-amz-access-token": access_token,
        "Content-Type": "application/json",
    }

    # Primero: Verificar Catalog Items (datos del producto)
    catalog_url = f"{SPAPI_BASE}/catalog/2022-04-01/items/{asin}"
    catalog_params = {
        "marketplaceIds": MARKETPLACE_ID,
        "includedData": "summaries,salesRanks,attributes"
    }

    result = {
        "available": False,
        "price": None,
        "buyable": False,
        "status": "unknown",
        "error": None
    }

    try:
        # Consultar catálogo
        r = requests.get(catalog_url, headers=headers, params=catalog_params, timeout=30)

        if r.status_code == 404:
            result["status"] = "not_found"
            result["error"] = "Producto no encontrado en Amazon"
            return result

        if r.status_code == 403:
            result["status"] = "error"
            result["error"] = "Sin permisos para consultar este ASIN"
            return result

        r.raise_for_status()
        catalog_data = r.json()

        # Verificar si el producto existe y está activo
        summaries = catalog_data.get("summaries", [])
        if not summaries:
            result["status"] = "unavailable"
            result["error"] = "Producto sin información en catálogo"
            return result

        summary = summaries[0]

        # Verificar si está disponible
        release_date = summary.get("releaseDate")
        if release_date:
            from dateutil import parser
            try:
                release = parser.parse(release_date)
                if release > datetime.now():
                    result["status"] = "unreleased"
                    result["error"] = f"Producto aún no lanzado (fecha: {release_date})"
                    return result
            except:
                pass

        # Ahora consultar precio via Product Pricing API
        pricing_url = f"{SPAPI_BASE}/products/pricing/v0/items/{asin}/offers"
        pricing_params = {
            "MarketplaceId": MARKETPLACE_ID,
            "ItemCondition": "New"
        }

        try:
            pr = requests.get(pricing_url, headers=headers, params=pricing_params, timeout=30)
            pr.raise_for_status()
            pricing_data = pr.json()

            # Extraer precio y disponibilidad
            payload = pricing_data.get("payload", {})
            offers = payload.get("Offers", [])

            if offers:
                # Tomar el primer offer
                offer = offers[0]
                listing_price = offer.get("ListingPrice", {})
                buybox_price = offer.get("BuyingPrice", {})

                # Intentar obtener precio del listing o buybox
                price_amount = listing_price.get("Amount") or buybox_price.get("Amount")

                if price_amount:
                    result["price"] = float(price_amount)

                # Verificar si es comprable
                is_buybox_winner = offer.get("IsBuyBoxWinner", False)
                is_fulfilled = offer.get("IsFulfilledByAmazon", False)

                result["buyable"] = is_buybox_winner or is_fulfilled
                result["available"] = True
                result["status"] = "active"
            else:
                # No hay offers = no está disponible para compra
                result["status"] = "unavailable"
                result["error"] = "Sin ofertas disponibles"

        except Exception as pricing_error:
            # Si falla el pricing, al menos tenemos info del catálogo
            result["available"] = True  # Existe en catálogo
            result["status"] = "active"
            result["error"] = f"No se pudo obtener precio: {pricing_error}"

        return result

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
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
            print(f"   Response: {e.response.text}")
        return None


def pause_ml_listing(item_id):
    """Pausa una publicación en MercadoLibre"""
    url = f"{ML_API}/items/{item_id}"
    body = {"status": "paused"}
    result = ml_http_put(url, body)
    return result is not None


def update_ml_price(item_id, new_price_usd):
    """
    Actualiza el precio de una publicación en ML.
    Usa global_net_proceeds para Global Selling.
    """
    url = f"{ML_API}/items/{item_id}"
    body = {
        "global_net_proceeds": {
            "amount": round(new_price_usd, 2),
            "currency_id": "USD"
        }
    }
    result = ml_http_put(url, body)
    return result is not None


# ============================================================
# FUNCIONES DE BASE DE DATOS
# ============================================================

def get_all_published_listings():
    """
    Obtiene todos los listings publicados desde la base de datos.
    Retorna lista de dicts con: item_id, asin, price_usd
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT item_id, asin, price_usd, title
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


# ============================================================
# LÓGICA PRINCIPAL DE SINCRONIZACIÓN
# ============================================================

def calculate_new_ml_price(amazon_price_usd):
    """
    Calcula el nuevo precio de ML aplicando el markup configurado.
    """
    markup_multiplier = 1 + (PRICE_MARKUP_PERCENT / 100)
    return round(amazon_price_usd * markup_multiplier, 2)


def sync_one_listing(listing, amazon_token, changes_log):
    """
    Sincroniza un solo listing con Amazon.

    Args:
        listing: dict con item_id, asin, price_usd, title
        amazon_token: access token de Amazon
        changes_log: lista para registrar cambios

    Returns:
        dict con resultado de la sincronización
    """
    item_id = listing["item_id"]
    asin = listing["asin"]
    current_price = listing["price_usd"]
    title = listing["title"]

    print(f"\n{'='*80}")
    print(f"🔄 Sincronizando: {asin}")
    print(f"   ML Item ID: {item_id}")
    print(f"   Título: {title[:60]}...")
    print(f"   Precio actual ML: ${current_price} USD")

    # Consultar estado en Amazon
    print(f"   📡 Consultando Amazon...")
    amazon_status = check_amazon_product_status(asin, amazon_token)

    result = {
        "item_id": item_id,
        "asin": asin,
        "action": "none",
        "success": False,
        "message": "",
        "amazon_status": amazon_status
    }

    # Caso 1: Producto no disponible en Amazon → Pausar en ML
    if amazon_status["status"] in ["not_found", "unavailable", "unreleased"]:
        print(f"   ⚠️ Estado Amazon: {amazon_status['status']}")
        print(f"   ⚠️ Razón: {amazon_status.get('error', 'Desconocida')}")
        print(f"   ⏸️ ACCIÓN: Pausar publicación en ML")

        if pause_ml_listing(item_id):
            result["action"] = "paused"
            result["success"] = True
            result["message"] = f"Pausado: {amazon_status.get('error', 'No disponible en Amazon')}"
            print(f"   ✅ Publicación pausada exitosamente")
        else:
            result["action"] = "pause_failed"
            result["message"] = "Error al pausar publicación"
            print(f"   ❌ Error pausando publicación")

    # Caso 2: Producto activo pero sin precio
    elif amazon_status["status"] == "active" and not amazon_status["price"]:
        print(f"   ℹ️ Producto activo pero sin precio disponible")
        print(f"   ⏸️ ACCIÓN: Pausar publicación en ML por precaución")

        if pause_ml_listing(item_id):
            result["action"] = "paused"
            result["success"] = True
            result["message"] = "Pausado: Sin precio en Amazon"
            print(f"   ✅ Publicación pausada exitosamente")
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

            if update_ml_price(item_id, new_ml_price):
                # Actualizar también en BD
                update_listing_price_in_db(item_id, new_ml_price)

                result["action"] = "price_updated"
                result["success"] = True
                result["message"] = f"Precio actualizado: ${current_price} → ${new_ml_price} USD"
                result["old_price"] = current_price
                result["new_price"] = new_ml_price
                print(f"   ✅ Precio actualizado exitosamente")
            else:
                result["action"] = "price_update_failed"
                result["message"] = "Error al actualizar precio"
                print(f"   ❌ Error actualizando precio")
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
    print("=" * 80)
    print("🔄 SINCRONIZACIÓN AMAZON → MERCADOLIBRE")
    print("=" * 80)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Markup configurado: {PRICE_MARKUP_PERCENT}%")
    print()

    # Verificar que existe la BD
    if not os.path.exists(DB_PATH):
        print(f"❌ No se encontró la base de datos: {DB_PATH}")
        print("   Ejecuta primero save_listing_data.py para crear la BD")
        sys.exit(1)

    # Obtener token de Amazon
    print("🔐 Obteniendo access token de Amazon...")
    try:
        amazon_token = get_amazon_access_token()
        print("✅ Token obtenido exitosamente\n")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # Obtener todos los listings publicados
    print("📋 Cargando listings desde la base de datos...")
    listings = get_all_published_listings()

    if not listings:
        print("⚠️ No se encontraron listings publicados en la BD")
        print("   Asegúrate de que los listings tengan item_id asignado")
        sys.exit(0)

    print(f"✅ Encontrados {len(listings)} listings para sincronizar\n")

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

    # Sincronizar cada listing
    for i, listing in enumerate(listings, 1):
        print(f"\n[{i}/{len(listings)}]", end=" ")

        result = sync_one_listing(listing, amazon_token, changes_log)

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
    print("\n✅ Sincronización completada")


if __name__ == "__main__":
    main()
