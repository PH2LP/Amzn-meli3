#!/usr/bin/env python3
"""
Actualiza los pesos de paquete en Mercado Libre para las publicaciones
que fueron corregidas en la base de datos.
"""

import sqlite3
import json
import os
import sys
import requests
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Importar funciones de mainglobal
from src.integrations.mainglobal import http_put, API

def get_corrected_listings():
    """
    Obtiene las publicaciones que necesitan actualizar peso en ML.
    Por simplicidad, vamos a actualizar las 12 que sabemos que se corrigieron.
    """
    asins = [
        'B09SVHP9X8', 'B0BLJ3RRHD', 'B07T5SY43L', 'B0CTMHHJJC',
        'B0F1XHP6JL', 'B009S750LA', 'B0BNWDV6R7', 'B0F9FH8RYG',
        'B0D91CCYPX', 'B07HC9RM8N', 'B084NY52HF', 'B002FXS4BM'
    ]

    db_path = "storage/listings_database.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    listings = []
    for asin in asins:
        cursor.execute("""
            SELECT asin, item_id, length_cm, width_cm, height_cm, weight_kg
            FROM listings
            WHERE asin = ?
        """, (asin,))

        result = cursor.fetchone()
        if result:
            listings.append({
                'asin': result[0],
                'item_id': result[1],
                'length_cm': result[2],
                'width_cm': result[3],
                'height_cm': result[4],
                'weight_kg': result[5]
            })

    conn.close()
    return listings

def update_ml_dimensions(item_id, dimensions):
    """
    Actualiza las dimensiones del paquete en una publicación de ML.
    """
    # Convertir kg a gramos para ML
    weight_grams = int(dimensions['weight_kg'] * 1000)

    # Preparar el payload
    payload = {
        "shipping": {
            "dimensions": f"{dimensions['width_cm']}x{dimensions['height_cm']}x{dimensions['length_cm']},{weight_grams}"
        }
    }

    try:
        url = f"{API}/items/{item_id}"
        response = http_put(url, payload)
        return True, "Actualizado correctamente"

    except Exception as e:
        return False, f"Excepción: {str(e)}"

def main():
    print("=" * 80)
    print("ACTUALIZACIÓN DE PESOS EN MERCADO LIBRE")
    print("=" * 80)
    print()

    # Obtener publicaciones a actualizar
    listings = get_corrected_listings()
    print(f"Se van a actualizar {len(listings)} publicaciones\n")

    # Actualizar cada publicación
    updated = 0
    failed = 0

    for listing in listings:
        print(f"Actualizando {listing['item_id']} (ASIN: {listing['asin']})...")
        print(f"  Dimensiones: {listing['width_cm']}x{listing['height_cm']}x{listing['length_cm']}, {listing['weight_kg']*1000}g")

        success, message = update_ml_dimensions(listing['item_id'], listing)

        if success:
            print(f"  ✅ {message}")
            updated += 1
        else:
            print(f"  ❌ {message}")
            failed += 1

        print()

    print("=" * 80)
    print(f"✅ Actualizadas: {updated}")
    print(f"❌ Fallidas: {failed}")
    print(f"📊 Total: {len(listings)}")
    print("=" * 80)

if __name__ == "__main__":
    main()
