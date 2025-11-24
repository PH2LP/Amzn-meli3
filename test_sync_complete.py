#!/usr/bin/env python3
"""
Test completo de sincronización Amazon -> ML
Con producto real publicado
"""

import os
import sys
import sqlite3
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

sys.path.insert(0, str(Path(__file__).parent))

from scripts.tools.sync_amazon_ml import (
    sync_one_listing,
    calculate_new_ml_price
)
from src.integrations.amazon_pricing import get_prime_offers_batch_optimized

DB_PATH = "storage/listings_database.db"
ML_API = "https://api.mercadolibre.com"
ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")

def get_current_ml_price(item_id):
    """Obtiene el precio actual desde la API de ML"""
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    # Intentar obtener item global
    url = f"{ML_API}/items/{item_id}"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()

        # El precio está en el campo price (precio local en la moneda del país)
        # Para CBT global, usamos net_proceeds
        price = data.get("price")

        # Si es CBT, intentar obtener net_proceeds
        if "CBT" in item_id:
            # Buscar site_listings para obtener un item local
            site_listings = data.get("variations", [{}])[0].get("attribute_combinations", []) if "variations" in data else []

            # Por ahora retornamos el price que tenemos
            return price

        return price
    except Exception as e:
        print(f"⚠️ Error obteniendo precio de ML: {e}")
        return None

def main():
    print("=" * 80)
    print("🧪 TEST COMPLETO DE SINCRONIZACIÓN DE PRECIOS")
    print("=" * 80)

    # Obtener el listing desde la BD
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT item_id, asin, price_usd, title, site_items
        FROM listings
        WHERE asin = 'B0C3W4MNN1'
    """)

    result = cursor.fetchone()
    if not result:
        print("❌ No se encontró el producto en la BD")
        return

    listing = dict(result)
    conn.close()

    asin = listing["asin"]
    item_id = listing["item_id"]
    current_price_db = listing["price_usd"]

    print(f"\n📦 Producto:")
    print(f"   ASIN: {asin}")
    print(f"   ML Item ID: {item_id}")
    print(f"   Precio en BD: ${current_price_db} USD")

    # PASO 1: Obtener precio REAL actual de Amazon
    print(f"\n{'='*80}")
    print("📊 PASO 1: Obtener precio real actual de Amazon")
    print("=" * 80)

    prime_offers = get_prime_offers_batch_optimized([asin], batch_size=1, show_progress=False)

    if asin not in prime_offers or not prime_offers[asin]:
        print(f"❌ No se pudo obtener precio de Amazon para {asin}")
        return

    real_amazon_price = prime_offers[asin]["price"]
    print(f"✅ Precio real en Amazon: ${real_amazon_price} USD")

    # PASO 2: Simular un cambio de precio significativo (>2%)
    print(f"\n{'='*80}")
    print("🔄 PASO 2: Simular cambio de precio en Amazon (+15%)")
    print("=" * 80)

    # Aumentar precio en 15% para asegurar que supere el umbral del 2%
    simulated_amazon_price = round(real_amazon_price * 1.15, 2)
    print(f"💰 Precio Amazon simulado: ${simulated_amazon_price} USD")

    expected_ml_price = calculate_new_ml_price(simulated_amazon_price)
    print(f"💰 Precio ML esperado: ${expected_ml_price} USD")
    print(f"💰 Precio ML actual (BD): ${current_price_db} USD")

    # Calcular diferencia
    diff_percent = abs((expected_ml_price - current_price_db) / current_price_db * 100)
    print(f"📊 Diferencia: {diff_percent:.1f}% (umbral: 2.0%)")

    # Crear cache simulado con el nuevo precio
    simulated_cache = {
        asin: {
            "price": simulated_amazon_price,
            "is_prime": True,
            "is_amazon": True,
            "condition": "New"
        }
    }

    # PASO 3: Ejecutar sincronización con precio simulado
    print(f"\n{'='*80}")
    print("🔄 PASO 3: Ejecutar sincronización con precio simulado")
    print("=" * 80)

    changes_log = []
    result = sync_one_listing(listing, simulated_cache, changes_log)

    # PASO 4: Verificar resultado
    print(f"\n{'='*80}")
    print("✅ PASO 4: Verificación de resultado")
    print("=" * 80)

    print(f"\n📊 Resultado de sincronización:")
    print(f"   Acción: {result['action']}")
    print(f"   Exitoso: {result['success']}")
    print(f"   Mensaje: {result['message']}")

    if result['action'] == 'price_updated':
        print(f"\n✅ ÉXITO - Precio actualizado en ML")
        print(f"   Precio anterior: ${result.get('old_price', 'N/A')} USD")
        print(f"   Precio nuevo: ${result.get('new_price', 'N/A')} USD")

        # Verificar en BD
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT price_usd FROM listings WHERE item_id = ?", (item_id,))
        saved_price = cursor.fetchone()[0]
        conn.close()

        print(f"\n💾 Verificación en BD:")
        print(f"   Precio guardado: ${saved_price} USD")

        if abs(saved_price - expected_ml_price) < 0.01:
            print(f"   ✅ Precio en BD coincide con esperado")
        else:
            print(f"   ⚠️ Precio en BD difiere")

    elif result['action'] == 'no_change':
        print(f"\n⚠️ No se actualizó (diferencia < 2%)")
        print(f"   El sistema funciona pero necesitamos mayor cambio para disparar actualización")

    else:
        print(f"\n❌ Acción inesperada: {result['action']}")
        print(f"   Mensaje: {result['message']}")

    print(f"\n{'='*80}")
    print("🏁 TEST COMPLETADO")
    print("=" * 80)

    # PASO 5: Restaurar precio original
    print(f"\n🔄 PASO 5: Restaurar precio original basado en precio real de Amazon")

    changes_log_restore = []
    result_restore = sync_one_listing(listing, prime_offers, changes_log_restore)

    print(f"\n📊 Resultado de restauración:")
    print(f"   Acción: {result_restore['action']}")
    print(f"   Exitoso: {result_restore['success']}")

    if result_restore['action'] == 'price_updated':
        print(f"   ✅ Precio restaurado a ${result_restore.get('new_price')} USD")
    elif result_restore['action'] == 'no_change':
        print(f"   ℹ️ No fue necesario restaurar (precio ya correcto)")
    else:
        print(f"   Acción: {result_restore['action']}")

    print(f"\n{'='*80}")
    print("✅ TEST DE SINCRONIZACIÓN COMPLETO")
    print("=" * 80)

if __name__ == "__main__":
    main()
