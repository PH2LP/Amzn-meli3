#!/usr/bin/env python3
"""
SCRIPT DE EMERGENCIA: Arreglar site_items en la BD

PROBLEMA:
Cuando se publican productos CBT, los site_items (item_id locales por país)
no se están guardando correctamente en la BD. Esto hace que el sync no
actualice todos los países.

SOLUCIÓN:
Este script recorre todos los CBT en la BD, consulta la API de ML para
obtener los site_items REALES, y actualiza la BD.
"""

import os
import sys
import sqlite3
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env
load_dotenv()

DB_PATH = "storage/listings_database.db"
ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
ML_USER_ID = os.getenv("ML_USER_ID")

def get_real_site_items_from_ml(item_id):
    """
    Obtiene los site_items REALES de un CBT desde la API de ML.

    Como /global/items/{id} no soporta GET, tenemos que buscar el CBT
    en los listings del usuario en cada país.

    Returns:
        list: Lista de {site_id, item_id, logistic_type} por país
    """
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    # Obtener detalles del item para extraer ASIN
    item_url = f"https://api.mercadolibre.com/items/{item_id}"
    r = requests.get(item_url, headers=headers, timeout=30)

    if r.status_code != 200:
        print(f"  ❌ Error consultando item: {r.status_code}")
        return None

    item_data = r.json()
    asin = item_data.get("seller_custom_field", "")

    if not asin:
        print(f"  ⚠️  No tiene ASIN (seller_custom_field)")
        return None

    print(f"  ASIN: {asin}")

    # Buscar el CBT en todos los marketplaces
    sites = ["MLM", "MLB", "MLC", "MCO", "MLA"]
    site_items = []

    for site_id in sites:
        print(f"    Buscando en {site_id}...", end=" ")

        # Buscar en listings del usuario
        search_url = f"https://api.mercadolibre.com/users/{ML_USER_ID}/items/search"
        params = {
            "site_id": site_id,
            "limit": 100
        }

        try:
            r = requests.get(search_url, headers=headers, params=params, timeout=30)
            if r.status_code != 200:
                print(f"Error {r.status_code}")
                continue

            results = r.json().get("results", [])

            # Buscar el CBT en los resultados
            if item_id in results:
                # Obtener detalles para confirmar logistic_type
                r2 = requests.get(item_url, headers=headers, timeout=30)
                if r2.status_code == 200:
                    details = r2.json()

                    site_items.append({
                        "site_id": site_id,
                        "item_id": item_id,  # Para CBT es el mismo ID global
                        "logistic_type": details.get("shipping", {}).get("logistic_type", "remote")
                    })

                    print(f"✅ Encontrado")
                else:
                    print(f"No encontrado")
            else:
                print(f"No encontrado")

        except Exception as e:
            print(f"Error: {e}")

    return site_items if site_items else None


def fix_database():
    """Recorre todos los CBT en la BD y actualiza site_items"""

    if not os.path.exists(DB_PATH):
        print(f"❌ BD no encontrada: {DB_PATH}")
        return

    print("=" * 70)
    print("SCRIPT DE EMERGENCIA: Arreglar site_items en la BD")
    print("=" * 70)
    print()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Obtener todos los CBT
    cursor.execute("""
        SELECT item_id, asin, title, site_items
        FROM listings
        WHERE item_id IS NOT NULL
        ORDER BY date_updated DESC
    """)

    listings = cursor.fetchall()

    print(f"Total listings en BD: {len(listings)}")
    print()

    updated_count = 0
    error_count = 0

    for item_id, asin, title, current_site_items in listings:
        print(f"CBT: {item_id}")
        print(f"  ASIN: {asin}")
        print(f"  Título: {title[:60]}")

        # Parsear site_items actual
        try:
            current = json.loads(current_site_items) if current_site_items else []
            print(f"  site_items actual: {len(current)} países")
        except:
            current = []
            print(f"  site_items actual: ERROR parseando")

        # Obtener site_items REAL desde ML
        print(f"  Consultando API de ML...")
        real_site_items = get_real_site_items_from_ml(item_id)

        if real_site_items:
            print(f"  ✅ site_items real: {len(real_site_items)} países")

            # Comparar
            if len(real_site_items) != len(current):
                print(f"  ⚠️  DIFERENCIA DETECTADA!")
                print(f"     BD: {len(current)} países")
                print(f"     ML: {len(real_site_items)} países")

                # Actualizar BD
                site_items_json = json.dumps(real_site_items)
                cursor.execute("""
                    UPDATE listings
                    SET site_items = ?
                    WHERE item_id = ?
                """, (site_items_json, item_id))

                print(f"  ✅ BD actualizada")
                updated_count += 1
            else:
                print(f"  ✅ BD correcta")
        else:
            print(f"  ❌ No se pudieron obtener site_items reales")
            error_count += 1

        print()

    # Commit changes
    conn.commit()
    conn.close()

    print("=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"Total procesados: {len(listings)}")
    print(f"Actualizados: {updated_count}")
    print(f"Errores: {error_count}")
    print(f"Sin cambios: {len(listings) - updated_count - error_count}")
    print()


if __name__ == "__main__":
    fix_database()
