#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para restaurar todos los precios a sus valores originales

Funcionalidad:
1. Lee de la DB todos los productos con precio_original
2. Restaura en MercadoLibre el precio original
3. Actualiza precio_actual en la DB

Uso:
    python3 scripts/tools/restore_original_prices.py [--asin ASIN] [--dry-run]

Opciones:
    --asin ASIN    Restaurar solo un ASIN específico
    --dry-run      Simular sin actualizar precios realmente
"""

import os
import sys
import json
import sqlite3
import requests
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

DB_PATH = "storage/listings_database.db"
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")


def update_ml_price(item_id, new_price):
    """
    Actualiza el precio de un item en MercadoLibre

    Returns:
        bool: True si se actualizó correctamente
    """
    try:
        url = f"https://api.mercadolibre.com/items/{item_id}"
        headers = {
            "Authorization": f"Bearer {ML_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {"price": new_price}

        response = requests.put(url, headers=headers, json=payload, timeout=10)

        if response.status_code == 200:
            return True
        else:
            print(f"  ⚠️  Error actualizando precio de {item_id}: {response.status_code}")
            print(f"      Response: {response.text}")
            return False

    except Exception as e:
        print(f"  ❌ Error actualizando precio de {item_id}: {e}")
        return False


def restore_original_prices(asin=None, dry_run=False):
    """
    Restaura precios originales de productos

    Args:
        asin: Si se especifica, solo procesa ese ASIN
        dry_run: Si es True, no actualiza precios, solo simula
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Obtener productos con precio_original
    if asin:
        cursor.execute("""
            SELECT asin, item_id, precio_original, precio_actual, es_catalogo
            FROM listings
            WHERE asin = ? AND precio_original IS NOT NULL
        """, (asin,))
    else:
        cursor.execute("""
            SELECT asin, item_id, precio_original, precio_actual, es_catalogo
            FROM listings
            WHERE precio_original IS NOT NULL
        """)

    productos = cursor.fetchall()

    if not productos:
        print("ℹ️  No hay productos con precio_original para restaurar")
        conn.close()
        return

    print(f"\n🔄 Restaurando precios originales de {len(productos)} producto(s)...\n")

    resultados = {
        "restaurados": 0,
        "sin_cambios": 0,
        "errores": 0
    }

    for producto in productos:
        asin_prod, item_id, precio_original, precio_actual, es_catalogo = producto

        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"📦 ASIN: {asin_prod}")
        print(f"   Item ID: {item_id}")
        print(f"   {'🏷️  Catálogo' if es_catalogo else '📋 No catálogo'}")
        print(f"   💰 Precio original: ${precio_original:.2f}")

        if precio_actual:
            print(f"   💵 Precio actual: ${precio_actual:.2f}")
        else:
            print(f"   ℹ️  Precio actual no registrado")

        # Verificar si ya está en precio original
        if precio_actual and abs(precio_original - precio_actual) < 1:
            print(f"   ✓ Ya está en precio original, sin cambios")
            resultados["sin_cambios"] += 1
            continue

        # Actualizar en ML si no es dry-run
        if not dry_run:
            success = update_ml_price(item_id, precio_original)

            if success:
                # Actualizar DB
                now = datetime.now().isoformat()
                cursor.execute("""
                    UPDATE listings
                    SET precio_actual = ?,
                        ultima_actualizacion_precio = ?
                    WHERE asin = ?
                """, (precio_original, now, asin_prod))

                print(f"   ✅ Precio restaurado a ${precio_original:.2f}")
                resultados["restaurados"] += 1
            else:
                print(f"   ❌ Error al restaurar precio")
                resultados["errores"] += 1
        else:
            print(f"   🔵 DRY-RUN: Restauraría a ${precio_original:.2f}")
            resultados["restaurados"] += 1

    conn.commit()
    conn.close()

    # Resumen
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📊 RESUMEN:")
    print(f"   ✅ Restaurados: {resultados['restaurados']}")
    print(f"   ⏸️  Sin cambios: {resultados['sin_cambios']}")
    print(f"   ❌ Errores: {resultados['errores']}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restaurar precios originales")
    parser.add_argument("--asin", help="Restaurar solo este ASIN")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin actualizar")

    args = parser.parse_args()

    restore_original_prices(asin=args.asin, dry_run=args.dry_run)
