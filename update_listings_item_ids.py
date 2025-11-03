#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para actualizar la base de datos con los item_ids de MercadoLibre
de publicaciones ya existentes.

Este script consulta todas las publicaciones del vendedor en ML y actualiza
la BD local con los item_ids correspondientes a cada ASIN.
"""

import os
import sys
import sqlite3
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
API = "https://api.mercadolibre.com"
HEADERS = {"Authorization": f"Bearer {ML_TOKEN}"}
DB_PATH = "storage/listings_database.db"


def http_get(url, params=None):
    """GET request con manejo de errores"""
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"⚠️ Error GET {url}: {e}")
        return None


def get_user_id():
    """Obtiene el user ID del seller"""
    user = http_get(f"{API}/users/me")
    if user:
        return user.get("id")
    return None


def get_all_ml_listings():
    """
    Obtiene TODOS los listings del vendedor desde ML.
    Retorna lista de dicts: [{item_id, asin, title}, ...]
    """
    listings = []

    print("📡 Obteniendo listings desde MercadoLibre...")

    # Método 1: /users/me/items/search
    print("   Intentando método 1: /users/me/items/search...")
    try:
        url = f"{API}/users/me/items/search"
        params = {"search_type": "scan", "limit": 50, "offset": 0}

        while True:
            data = http_get(url, params)
            if not data or "results" not in data:
                break

            results = data.get("results", [])
            if not results:
                break

            # Para cada resultado, obtener detalles para extraer ASIN
            for item_id_or_dict in results:
                if isinstance(item_id_or_dict, dict):
                    item_id = item_id_or_dict.get("id")
                else:
                    item_id = item_id_or_dict

                if not item_id:
                    continue

                # Obtener detalles del item
                item_details = http_get(f"{API}/items/{item_id}")
                if not item_details:
                    continue

                # Extraer ASIN del seller_custom_field
                asin = item_details.get("seller_custom_field", "").strip()
                title = item_details.get("title", "")

                if asin:
                    listings.append({
                        "item_id": item_id,
                        "asin": asin,
                        "title": title
                    })
                    print(f"   ✅ {item_id} → {asin}")

            # Paginación
            paging = data.get("paging", {})
            if paging.get("offset", 0) + paging.get("limit", 0) >= paging.get("total", 0):
                break

            params["offset"] += params["limit"]

        if listings:
            print(f"   ✅ Método 1 exitoso: {len(listings)} listings encontrados")
            return listings

    except Exception as e:
        print(f"   ⚠️ Método 1 falló: {e}")

    # Método 2: Buscar por seller_id en el sitio CBT
    print("\n   Intentando método 2: Búsqueda por seller_id en CBT...")
    try:
        user_id = get_user_id()
        if not user_id:
            print("   ⚠️ No se pudo obtener user_id")
            return []

        url = f"{API}/sites/CBT/search"
        params = {"seller_id": user_id, "limit": 50}
        data = http_get(url, params)

        if data and "results" in data:
            results = data["results"]

            # Procesar cada resultado
            for item_summary in results:
                item_id = item_summary.get("id")
                if not item_id:
                    continue

                # Obtener detalles completos
                item_details = http_get(f"{API}/items/{item_id}")
                if not item_details:
                    continue

                # Extraer ASIN del seller_custom_field
                asin = item_details.get("seller_custom_field", "").strip()
                title = item_details.get("title", "")

                if asin:
                    listings.append({
                        "item_id": item_id,
                        "asin": asin,
                        "title": title
                    })
                    print(f"   ✅ {item_id} → {asin}")

            if listings:
                print(f"   ✅ Método 2 exitoso: {len(listings)} listings encontrados")
                return listings

    except Exception as e:
        print(f"   ⚠️ Método 2 falló: {e}")

    return listings


def update_item_ids_in_db(listings):
    """
    Actualiza la BD con los item_ids encontrados.

    Args:
        listings: Lista de dicts con item_id, asin, title
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    updated = 0
    not_found = 0

    for listing in listings:
        item_id = listing["item_id"]
        asin = listing["asin"]

        # Verificar si existe el ASIN en la BD
        cursor.execute("SELECT id FROM listings WHERE asin = ?", (asin,))
        row = cursor.fetchone()

        if row:
            # Actualizar el item_id
            cursor.execute("""
                UPDATE listings
                SET item_id = ?
                WHERE asin = ?
            """, (item_id, asin))
            updated += 1
            print(f"   ✅ Actualizado: {asin} → {item_id}")
        else:
            not_found += 1
            print(f"   ⚠️ ASIN no encontrado en BD: {asin}")

    conn.commit()
    conn.close()

    return updated, not_found


def main():
    print("=" * 80)
    print("🔄 ACTUALIZACIÓN DE ITEM_IDS EN BASE DE DATOS")
    print("=" * 80)
    print()

    # Verificar que existe la BD
    if not os.path.exists(DB_PATH):
        print(f"❌ No se encontró la base de datos: {DB_PATH}")
        print("   Ejecuta primero: python3 save_listing_data.py")
        sys.exit(1)

    # Verificar estado actual
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM listings")
    total_in_db = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM listings WHERE item_id IS NOT NULL")
    with_item_id = cursor.fetchone()[0]
    conn.close()

    print(f"📊 Estado actual de la BD:")
    print(f"   Total de listings: {total_in_db}")
    print(f"   Con item_id: {with_item_id}")
    print(f"   Sin item_id: {total_in_db - with_item_id}")
    print()

    if with_item_id == total_in_db:
        print("✅ Todos los listings ya tienen item_id asignado")
        return

    # Obtener listings desde ML
    print("📋 PASO 1: Obtener listings desde MercadoLibre...")
    ml_listings = get_all_ml_listings()

    if not ml_listings:
        print("⚠️ No se encontraron listings en MercadoLibre")
        print("   Verifica que:")
        print("   1. El token ML_ACCESS_TOKEN sea válido")
        print("   2. Hayas publicado productos en ML")
        return

    print(f"\n✅ Encontrados {len(ml_listings)} listings en ML\n")

    # Actualizar BD
    print("📋 PASO 2: Actualizar base de datos...")
    updated, not_found = update_item_ids_in_db(ml_listings)

    # Resumen
    print("\n" + "=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)
    print(f"Listings en ML: {len(ml_listings)}")
    print(f"Actualizados en BD: {updated}")
    print(f"No encontrados en BD: {not_found}")
    print()

    if updated > 0:
        print("✅ Base de datos actualizada exitosamente")
        print()
        print("📝 Próximos pasos:")
        print("   1. Ejecutar sincronización: python3 sync_amazon_ml.py")
        print("   2. Instalar cron job: ./setup_sync_cron.sh")
    else:
        print("⚠️ No se actualizó ningún registro")
        print("   Verifica que los ASINs en ML coincidan con los de la BD")

    if not_found > 0:
        print()
        print(f"⚠️ {not_found} ASINs de ML no están en la BD")
        print("   Esto puede pasar si publicaste ASINs que no procesaste con el pipeline")


if __name__ == "__main__":
    main()
