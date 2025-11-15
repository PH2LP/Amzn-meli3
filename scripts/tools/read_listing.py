#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script simple para leer datos de la BD de listings
"""

import sqlite3
import json
import sys

DB_PATH = "storage/listings_database.db"

def get_listing_by_asin(asin):
    """Obtiene un listing por ASIN"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Para acceder por nombre de columna
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM listings WHERE asin = ?", (asin,))
    row = cursor.fetchone()

    if row:
        # Convertir a dict
        listing = dict(row)

        # Parsear los campos JSON
        if listing.get('images_urls'):
            listing['images_urls'] = json.loads(listing['images_urls'])
        if listing.get('attributes'):
            listing['attributes'] = json.loads(listing['attributes'])
        if listing.get('main_features'):
            listing['main_features'] = json.loads(listing['main_features'])

        conn.close()
        return listing

    conn.close()
    return None

def list_all_asins():
    """Lista todos los ASINs con sus links"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT asin, item_id, amazon_url, permalink, title
        FROM listings
        ORDER BY date_published DESC
    """)

    results = cursor.fetchall()
    conn.close()
    return results

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asin = sys.argv[1]
        listing = get_listing_by_asin(asin)

        if listing:
            print(f"\n{'='*60}")
            print(f"ASIN: {listing['asin']}")
            print(f"Título: {listing['title']}")
            print(f"Amazon URL: {listing['amazon_url']}")
            print(f"MercadoLibre ID: {listing['item_id']}")
            print(f"MercadoLibre URL: {listing['permalink'] or 'N/A'}")
            print(f"Categoría: {listing['category_name']} ({listing['category_id']})")
            print(f"Precio USD: ${listing['price_usd']}")
            print(f"Marca: {listing['brand']}")
            print(f"Modelo: {listing['model']}")
            print(f"GTIN: {listing.get('gtin', 'N/A')}")
            print(f"Publicado: {listing['date_published']}")
            print(f"{'='*60}\n")
        else:
            print(f"❌ ASIN {asin} no encontrado en la BD")
    else:
        print("\n📦 Todos los productos en la BD:\n")
        listings = list_all_asins()

        for i, row in enumerate(listings, 1):
            asin, item_id, amazon_url, permalink, title = row
            print(f"{i}. {asin}")
            print(f"   📖 {title[:60]}...")
            print(f"   🔗 Amazon: {amazon_url}")
            print(f"   🔗 MercadoLibre: {permalink or item_id or 'N/A'}")
            print()
