#!/usr/bin/env python3
"""
Sincroniza site_items en la BD con la realidad en MercadoLibre

Este script:
1. Lee todos los CBT de la BD
2. Busca cada CBT en todos los marketplaces vía API de ML
3. Actualiza site_items con los países donde realmente está publicado

IMPORTANTE: Para CBT, el item_id es EL MISMO en todos los países.
No hay item_ids locales diferentes. Lo que cambia es el site_id.
"""

import os
import sys
import sqlite3
import requests
import json
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "storage/listings_database.db"
ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
ML_USER_ID = os.getenv("ML_USER_ID")

def get_cbt_countries(item_id):
    """
    Consulta la API de ML para obtener en qué países está publicado un CBT.

    Para CBT, el item_id es el mismo en todos los países. Solo cambia el site_id.

    Returns:
        list: [{"site_id": "MLM", "item_id": "CBT...", "logistic_type": "remote"}]
    """
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    # Buscar el CBT en cada marketplace
    sites = ["MLM", "MLB", "MLC", "MCO", "MLA"]
    published_in = []

    for site_id in sites:
        # Buscar en items del usuario para ese marketplace
        url = f"https://api.mercadolibre.com/users/{ML_USER_ID}/items/search"
        params = {
            "site_id": site_id,
            "limit": 100
        }

        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
            if r.status_code != 200:
                continue

            results = r.json().get("results", [])

            # Si el CBT está en los resultados, está publicado en ese país
            if item_id in results:
                # Obtener logistic_type consultando el item
                item_url = f"https://api.mercadolibre.com/items/{item_id}"
                r2 = requests.get(item_url, headers=headers, timeout=30)

                logistic_type = "remote"  # default
                if r2.status_code == 200:
                    shipping = r2.json().get("shipping", {})
                    logistic_type = shipping.get("logistic_type", "remote")

                published_in.append({
                    "site_id": site_id,
                    "item_id": item_id,  # Para CBT, es el mismo ID
                    "logistic_type": logistic_type
                })

        except Exception as e:
            print(f"  Error consultando {site_id}: {e}")
            continue

    return published_in


def sync_database():
    """Sincroniza todos los site_items de la BD"""

    print("=" * 70)
    print("SINCRONIZACIÓN DE SITE_ITEMS DESDE MERCADOLIBRE")
    print("=" * 70)
    print()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Obtener todos los CBT
    cursor.execute("""
        SELECT item_id, asin, title
        FROM listings
        WHERE item_id IS NOT NULL
        ORDER BY date_updated DESC
    """)

    listings = cursor.fetchall()

    print(f"Total listings en BD: {len(listings)}")
    print()

    updated = 0
    errors = 0

    for item_id, asin, title in listings:
        print(f"CBT: {item_id}")
        print(f"  ASIN: {asin}")
        print(f"  Título: {title[:60] if title else 'N/A'}")
        print(f"  Consultando API de ML...")

        # Obtener países reales desde ML
        real_site_items = get_cbt_countries(item_id)

        if real_site_items:
            print(f"  ✅ Publicado en {len(real_site_items)} países:")
            for site in real_site_items:
                print(f"     - {site['site_id']}")

            # Actualizar BD
            site_items_json = json.dumps(real_site_items)
            cursor.execute("""
                UPDATE listings
                SET site_items = ?
                WHERE item_id = ?
            """, (site_items_json, item_id))

            updated += 1
        else:
            print(f"  ⚠️  No encontrado en ningún país")
            errors += 1

        print()

    # Commit
    conn.commit()
    conn.close()

    print("=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"Total procesados: {len(listings)}")
    print(f"Actualizados: {updated}")
    print(f"Errores: {errors}")
    print()


if __name__ == "__main__":
    sync_database()
