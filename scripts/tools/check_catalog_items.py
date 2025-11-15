#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar cuáles productos publicados son de catálogo
y marcarlos automáticamente en la DB
"""

import os
import sqlite3
import requests
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "storage/listings_database.db"
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")


def check_if_catalog(item_id):
    """
    Consulta ML para verificar si un item es de catálogo

    Returns:
        dict: {is_catalog: bool, catalog_id: str, price: float}
    """
    try:
        url = f"https://api.mercadolibre.com/items/{item_id}"
        headers = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return {"is_catalog": False, "error": response.status_code}

        data = response.json()

        catalog_id = data.get("catalog_product_id")
        is_catalog = catalog_id is not None
        price = float(data.get("price", 0))

        return {
            "is_catalog": is_catalog,
            "catalog_id": catalog_id,
            "price": price,
            "title": data.get("title", "")
        }

    except Exception as e:
        return {"is_catalog": False, "error": str(e)}


def check_all_items():
    """Verifica todos los items publicados y actualiza es_catalogo en DB"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Obtener todos los productos publicados (excepto TEST)
    cursor.execute("""
        SELECT asin, item_id, title, es_catalogo, precio_actual
        FROM listings
        WHERE item_id IS NOT NULL AND asin NOT LIKE 'TEST%'
    """)

    productos = cursor.fetchall()

    if not productos:
        print("ℹ️  No hay productos publicados en la DB")
        conn.close()
        return

    print(f"\n🔍 Verificando {len(productos)} producto(s)...\n")

    catalogos_encontrados = 0
    actualizados = 0

    for producto in productos:
        asin, item_id, title, es_catalogo_actual, precio_actual = producto

        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"📦 ASIN: {asin}")
        print(f"   Item ID: {item_id}")
        print(f"   Título: {title[:60]}...")

        # Consultar ML
        result = check_if_catalog(item_id)

        if "error" in result:
            print(f"   ⚠️  Error al consultar: {result['error']}")
            continue

        if result["is_catalog"]:
            print(f"   ✅ ES CATÁLOGO")
            print(f"   🏷️  Catalog ID: {result['catalog_id']}")
            print(f"   💰 Precio actual en ML: ${result['price']:.2f}")

            catalogos_encontrados += 1

            # Actualizar en DB si no estaba marcado
            if es_catalogo_actual == 0:
                cursor.execute("""
                    UPDATE listings
                    SET es_catalogo = 1,
                        precio_actual = ?
                    WHERE asin = ?
                """, (result['price'], asin))
                print(f"   🔄 Actualizado en DB: es_catalogo = 1")
                actualizados += 1
            else:
                print(f"   ℹ️  Ya estaba marcado como catálogo")
        else:
            print(f"   📋 No es catálogo")

            # Si estaba marcado como catálogo, corregir
            if es_catalogo_actual == 1:
                cursor.execute("UPDATE listings SET es_catalogo = 0 WHERE asin = ?", (asin,))
                print(f"   🔄 Corregido en DB: es_catalogo = 0")

    conn.commit()
    conn.close()

    # Resumen
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📊 RESUMEN:")
    print(f"   🏷️  Productos de catálogo: {catalogos_encontrados}")
    print(f"   🔄 Actualizados en DB: {actualizados}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    if catalogos_encontrados > 0:
        print("💡 Ahora puedes ejecutar:")
        print("   python3 scripts/tools/adjust_catalog_prices.py --dry-run")
        print("   para ver cómo ajustaría los precios.\n")


if __name__ == "__main__":
    check_all_items()
