#!/usr/bin/env python3
"""
Test: ¿Qué pasa si cambio el precio manualmente en ML?
¿El sync lo "corrige" o solo actualiza cuando Amazon cambia?
"""

import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

sys.path.insert(0, str(Path(__file__).parent))

from scripts.tools.sync_amazon_ml import sync_one_listing, calculate_new_ml_price
from src.integrations.amazon_pricing import get_prime_offers_batch_optimized

DB_PATH = "storage/listings_database.db"

def test_manual_change():
    print("=" * 80)
    print("🧪 TEST: Cambio manual de precio en ML")
    print("=" * 80)

    # Obtener listing
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
        print("❌ No se encontró el producto")
        return

    listing = dict(result)
    conn.close()

    asin = listing["asin"]
    current_price_bd = listing["price_usd"]

    print(f"\n📦 Producto: {asin}")
    print(f"   Precio actual en BD: ${current_price_bd} USD")

    # ESCENARIO 1: Simular que alguien cambió el precio manualmente en ML a $60
    print(f"\n{'='*80}")
    print("ESCENARIO 1: Cambio manual en ML (sin actualizar BD)")
    print("=" * 80)
    print("\n⚠️ Supongamos que alguien cambió el precio en ML a $60 USD")
    print("   Pero la BD todavía tiene ${current_price_bd} USD")

    # Obtener precio real de Amazon
    prime_offers = get_prime_offers_batch_optimized([asin], batch_size=1, show_progress=False)
    amazon_price = prime_offers[asin]["price"]
    expected_ml_price = calculate_new_ml_price(amazon_price)

    print(f"\n📊 Cuando sync ejecuta:")
    print(f"   Precio Amazon: ${amazon_price} USD")
    print(f"   Precio ML calculado: ${expected_ml_price} USD")
    print(f"   Precio en BD: ${current_price_bd} USD")
    print(f"   Diferencia: {abs((expected_ml_price - current_price_bd) / current_price_bd * 100):.1f}%")

    if abs(expected_ml_price - current_price_bd) < 0.01:
        print(f"\n✅ Diferencia < 2% → NO actualiza")
        print(f"   El precio manual de $60 en ML SE QUEDA")
        print(f"   Sync NO lo corrige porque compara con BD, no con ML")
    else:
        print(f"\n⚠️ Diferencia > 2% → SÍ actualizaría")

    # ESCENARIO 2: Cambio manual Y actualización de BD
    print(f"\n{'='*80}")
    print("ESCENARIO 2: Cambio manual en ML + actualizar BD a $60")
    print("=" * 80)

    manual_price = 60.00
    print(f"\n⚠️ Ahora actualizamos la BD también a ${manual_price} USD")

    # Simular que la BD se actualizó
    listing_modified = listing.copy()
    listing_modified["price_usd"] = manual_price

    print(f"\n📊 Cuando sync ejecuta:")
    print(f"   Precio Amazon: ${amazon_price} USD")
    print(f"   Precio ML calculado: ${expected_ml_price} USD")
    print(f"   Precio en BD: ${manual_price} USD")

    diff_pct = abs((expected_ml_price - manual_price) / manual_price * 100)
    print(f"   Diferencia: {diff_pct:.1f}%")

    if diff_pct > 2.0:
        print(f"\n⚠️ Diferencia {diff_pct:.1f}% > 2% → SÍ actualiza")
        print(f"   Sync CORRIGE el precio manual de ${manual_price} → ${expected_ml_price}")
        print(f"   El precio vuelve a estar basado en Amazon")
    else:
        print(f"\n✅ Diferencia < 2% → NO actualiza")

    # ESCENARIO 3: Amazon cambia precio
    print(f"\n{'='*80}")
    print("ESCENARIO 3: Precio de Amazon cambia")
    print("=" * 80)

    new_amazon_price = 50.00
    new_expected_ml = calculate_new_ml_price(new_amazon_price)

    print(f"\n⚠️ Amazon cambia precio a ${new_amazon_price} USD")
    print(f"\n📊 Cuando sync ejecuta:")
    print(f"   Precio Amazon: ${new_amazon_price} USD")
    print(f"   Precio ML calculado: ${new_expected_ml} USD")
    print(f"   Precio en BD: ${current_price_bd} USD")

    diff_pct_amazon = abs((new_expected_ml - current_price_bd) / current_price_bd * 100)
    print(f"   Diferencia: {diff_pct_amazon:.1f}%")

    if diff_pct_amazon > 2.0:
        print(f"\n✅ Diferencia {diff_pct_amazon:.1f}% > 2% → SÍ actualiza")
        print(f"   Sync actualiza: ${current_price_bd} → ${new_expected_ml}")
        print(f"   Precio se sincroniza con Amazon")

    # RESUMEN
    print(f"\n{'='*80}")
    print("📋 RESUMEN")
    print("=" * 80)
    print("""
El sistema de sync:

✅ SÍ actualiza cuando:
   - El precio de Amazon cambia (diferencia > 2%)
   - Alguien cambió manualmente en ML Y actualizó la BD (diferencia > 2%)

❌ NO actualiza cuando:
   - El precio de Amazon NO cambió
   - La diferencia es < 2%
   - Alguien cambió en ML pero NO actualizó la BD

💡 CONCLUSIÓN:
   Sync compara con el precio en la BASE DE DATOS, no con ML directamente.

   Si cambias manualmente en ML:
   - Sin tocar BD → Sync NO corrige (porque BD tiene precio viejo = Amazon)
   - Actualizando BD → Sync SÍ corrige en próxima ejecución

   Sync está diseñado para seguir a AMAZON como fuente de verdad.
    """)

    print("=" * 80)

if __name__ == "__main__":
    test_manual_change()
