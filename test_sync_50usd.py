#!/usr/bin/env python3
"""
Test de sincronización con precio Amazon simulado = $50 USD
"""

import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

sys.path.insert(0, str(Path(__file__).parent))

from scripts.tools.sync_amazon_ml import (
    sync_one_listing,
    calculate_new_ml_price
)

DB_PATH = "storage/listings_database.db"

def main():
    print("=" * 80)
    print("🧪 TEST: Precio Amazon = $50 USD")
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
    print(f"   Precio actual en BD: ${current_price_db} USD")

    # SIMULACIÓN: Precio Amazon = $50 USD
    simulated_amazon_price = 50.00

    print(f"\n{'='*80}")
    print("🔄 SIMULACIÓN: Amazon cambia precio a $50 USD")
    print("=" * 80)

    print(f"💰 Precio Amazon simulado: ${simulated_amazon_price} USD")

    # Calcular precio ML esperado con la fórmula correcta
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

    # Ejecutar sincronización
    print(f"\n{'='*80}")
    print("🔄 SINCRONIZANDO CON MERCADOLIBRE")
    print("=" * 80)

    changes_log = []
    result = sync_one_listing(listing, simulated_cache, changes_log)

    # Verificar resultado
    print(f"\n{'='*80}")
    print("✅ RESULTADO")
    print("=" * 80)

    print(f"\n📊 Acción: {result['action']}")
    print(f"   Exitoso: {result['success']}")
    print(f"   Mensaje: {result['message']}")

    if result['action'] == 'price_updated':
        print(f"\n✅ PRECIO ACTUALIZADO EN ML")
        print(f"   ${result.get('old_price', 'N/A')} → ${result.get('new_price', 'N/A')} USD")

        # Verificar en BD
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT price_usd FROM listings WHERE item_id = ?", (item_id,))
        saved_price = cursor.fetchone()[0]
        conn.close()

        print(f"\n💾 Base de datos actualizada:")
        print(f"   Precio guardado: ${saved_price} USD")

        if abs(saved_price - expected_ml_price) < 0.01:
            print(f"   ✅ Correcto - coincide con esperado (${expected_ml_price} USD)")
        else:
            print(f"   ⚠️ Discrepancia detectada")
            print(f"   Esperado: ${expected_ml_price} USD")
            print(f"   Guardado: ${saved_price} USD")

        print(f"\n{'='*80}")
        print("✅ SINCRONIZACIÓN EXITOSA")
        print("=" * 80)
        print(f"\nEl precio en MercadoLibre se actualizó automáticamente")
        print(f"cuando Amazon cambió de ${current_price_db} a ${simulated_amazon_price} USD")

    elif result['action'] == 'no_change':
        print(f"\n⚠️ No se actualizó (diferencia < 2%)")

    else:
        print(f"\n❌ Error: {result['action']}")
        print(f"   {result['message']}")

if __name__ == "__main__":
    main()
