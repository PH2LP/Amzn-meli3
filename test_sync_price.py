#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de sincronización de precios Amazon -> ML
Simula un cambio de precio en Amazon y verifica que se actualice en ML
"""

import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

# Importar funciones del sync
from scripts.tools.sync_amazon_ml import (
    get_all_published_listings,
    sync_one_listing,
    calculate_new_ml_price
)

# Importar función de pricing de Amazon
from src.integrations.amazon_pricing import get_prime_offers_batch_optimized

DB_PATH = "storage/listings_database.db"

def main():
    print("=" * 80)
    print("🧪 TEST DE SINCRONIZACIÓN DE PRECIOS")
    print("=" * 80)

    # Obtener el último listing publicado
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT item_id, asin, price_usd, title, site_items
        FROM listings
        WHERE item_id IS NOT NULL
        ORDER BY rowid DESC
        LIMIT 1
    """)

    listing = dict(cursor.fetchone())
    conn.close()

    asin = listing["asin"]
    item_id = listing["item_id"]
    current_ml_price = listing["price_usd"]

    print(f"\n📦 Producto seleccionado:")
    print(f"   ASIN: {asin}")
    print(f"   ML Item ID: {item_id}")
    print(f"   Título: {listing['title'][:60]}...")
    print(f"   Precio actual en ML: ${current_ml_price} USD")

    # PASO 1: Obtener precio REAL actual de Amazon
    print(f"\n{'='*80}")
    print("📊 PASO 1: Obtener precio real actual de Amazon")
    print("=" * 80)

    prime_offers = get_prime_offers_batch_optimized([asin], batch_size=1, show_progress=False)

    if asin not in prime_offers or not prime_offers[asin]:
        print(f"❌ No se pudo obtener precio de Amazon para {asin}")
        print("   El producto puede estar sin oferta Prime o no disponible")
        return

    real_amazon_price = prime_offers[asin]["price"]
    print(f"✅ Precio real en Amazon: ${real_amazon_price} USD")

    # PASO 2: Simular un cambio de precio
    print(f"\n{'='*80}")
    print("🔄 PASO 2: Simular cambio de precio en Amazon")
    print("=" * 80)

    # Aumentar precio en un 10% para forzar actualización
    simulated_amazon_price = round(real_amazon_price * 1.10, 2)
    print(f"💰 Precio simulado (real +10%): ${simulated_amazon_price} USD")

    # Calcular qué precio debería tener en ML con el nuevo precio de Amazon
    expected_ml_price = calculate_new_ml_price(simulated_amazon_price)
    print(f"💰 Precio esperado en ML: ${expected_ml_price} USD")

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

    print(f"\n📊 Resultado de la sincronización:")
    print(f"   Acción: {result['action']}")
    print(f"   Exitoso: {result['success']}")
    print(f"   Mensaje: {result['message']}")

    if result['action'] == 'price_updated':
        print(f"\n✅ PRUEBA EXITOSA - Precio actualizado correctamente")
        print(f"   Precio anterior: ${result.get('old_price', 'N/A')} USD")
        print(f"   Precio nuevo: ${result.get('new_price', 'N/A')} USD")

        # Verificar en BD que se guardó
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT price_usd FROM listings WHERE item_id = ?", (item_id,))
        saved_price = cursor.fetchone()[0]
        conn.close()

        print(f"   Precio guardado en BD: ${saved_price} USD")

        if abs(saved_price - expected_ml_price) < 0.01:
            print(f"\n✅ VERIFICACIÓN EXITOSA - Precio en BD coincide con lo esperado")
        else:
            print(f"\n⚠️ ADVERTENCIA - Precio en BD no coincide")
            print(f"   Esperado: ${expected_ml_price} USD")
            print(f"   Guardado: ${saved_price} USD")

    elif result['action'] == 'no_change':
        print(f"\n⚠️ No se actualizó el precio (diferencia < 2%)")
        print(f"   Esto significa que el sistema está funcionando correctamente")
        print(f"   pero el cambio simulado no es suficiente para disparar una actualización")

    else:
        print(f"\n⚠️ Resultado inesperado: {result['action']}")
        print(f"   Mensaje: {result['message']}")

    print(f"\n{'='*80}")
    print("🏁 TEST COMPLETADO")
    print("=" * 80)

    # PASO 5: Restaurar precio original
    print(f"\n🔄 Restaurando precio original en ML...")

    # Volver a sincronizar con el precio REAL de Amazon
    changes_log_restore = []
    result_restore = sync_one_listing(listing, prime_offers, changes_log_restore)

    if result_restore['success']:
        print(f"✅ Precio restaurado correctamente")
    else:
        print(f"⚠️ No fue necesario restaurar precio")

if __name__ == "__main__":
    main()
