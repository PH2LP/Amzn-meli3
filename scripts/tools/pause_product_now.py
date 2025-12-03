#!/usr/bin/env python3
"""
Pausar producto simulando que demora >25 horas en Amazon
Dejar pausado para verificación manual en ML
"""

import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

sys.path.insert(0, str(Path(__file__).parent))

from scripts.tools.sync_amazon_ml import sync_one_listing

DB_PATH = "storage/listings_database.db"

def main():
    print("=" * 80)
    print("🧪 PAUSAR PRODUCTO POR TIEMPO DE DESPACHO >25 HORAS")
    print("=" * 80)

    # Obtener listing de la BD
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

    print(f"\n📦 Producto:")
    print(f"   ASIN: {asin}")
    print(f"   ML Item ID: {item_id}")
    print(f"   Título: {listing['title'][:60]}...")

    # Simular que Amazon rechaza el producto por Fast Fulfillment
    # (tiempo de despacho >25 horas = no cumple criterio de <24hs)
    print(f"\n⚠️ SIMULACIÓN:")
    print(f"   Tiempo de despacho en Amazon: >25 horas")
    print(f"   No cumple Fast Fulfillment (<24hs)")
    print(f"   Sistema debe pausar automáticamente en ML")

    # Cache con None = producto rechazado por filtros
    cache_no_prime = {
        asin: None  # None = No pasa filtros de Fast Fulfillment
    }

    # Ejecutar sincronización
    print(f"\n{'='*80}")
    print("🔄 EJECUTANDO SINCRONIZACIÓN...")
    print("=" * 80)

    changes_log = []
    result = sync_one_listing(listing, cache_no_prime, changes_log)

    # Mostrar resultado
    print(f"\n{'='*80}")
    print("✅ RESULTADO")
    print("=" * 80)

    print(f"\n📊 Acción ejecutada: {result['action']}")
    print(f"   Exitoso: {result['success']}")
    print(f"   Mensaje: {result['message']}")

    if result['action'] == 'paused' and result['success']:
        print(f"\n✅ PRODUCTO PAUSADO EXITOSAMENTE")
        print(f"\n📋 Detalles:")
        print(f"   Stock en ML: 0 (sin disponibilidad)")
        print(f"   Razón: {result['message']}")

        print(f"\n🔍 VERIFICA MANUALMENTE EN MERCADOLIBRE:")
        print(f"   Item ID Global: {item_id}")
        print(f"\n   URLs para verificar:")

        # Mostrar URLs de los países
        import json
        site_items = json.loads(listing['site_items'])
        for site_item in site_items:
            if site_item.get('item_id') and not site_item.get('error'):
                site_id = site_item['site_id']
                local_item_id = site_item['item_id']

                # Construir URL del país
                domain_map = {
                    'MLA': 'mercadolibre.com.ar',
                    'MLB': 'mercadolibre.com.br',
                    'MLC': 'mercadolibre.cl',
                    'MCO': 'mercadolibre.com.co',
                    'MLM': 'mercadolibre.com.mx'
                }
                domain = domain_map.get(site_id, 'mercadolibre.com')
                url = f"https://www.{domain}/p/{local_item_id}"

                print(f"   • {site_id}: {url}")

        print(f"\n💡 NOTA:")
        print(f"   El producto debe aparecer como 'Sin stock' o 'No disponible'")
        print(f"   NO debe permitir comprarse")

        print(f"\n⏸️ PRODUCTO DEJADO EN PAUSA")
        print(f"   No ejecutamos reactivación automática")
        print(f"   Verificá manualmente que esté pausado")

    else:
        print(f"\n⚠️ No se pausó como esperado")
        print(f"   Acción: {result['action']}")
        print(f"   Mensaje: {result['message']}")

    print(f"\n{'='*80}")

if __name__ == "__main__":
    main()
