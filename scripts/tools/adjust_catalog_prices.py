#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para ajustar precios automáticamente en productos de catálogo

Funcionalidad:
1. Obtiene todos los productos marcados como catálogo en la DB
2. Consulta el buybox (precio más bajo) en MercadoLibre
3. Calcula si puede competir manteniendo margen mínimo del 20%
4. Ajusta el precio si es rentable, sino mantiene precio original
5. Actualiza en ML y guarda en DB

Uso:
    python3 scripts/tools/adjust_catalog_prices.py [--asin ASIN] [--dry-run]

Opciones:
    --asin ASIN    Procesar solo un ASIN específico
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
PRICE_MARKUP = float(os.getenv("PRICE_MARKUP", 45)) / 100  # 45% -> 0.45
TAX_FLORIDA = 0.07  # 7% tax
MARGEN_MINIMO = 0.25  # 25% margen mínimo


def get_ml_buybox_price(item_id):
    """
    Obtiene el precio del buybox (competidor más barato) de ML

    Returns:
        float: Precio del buybox, o None si hay error
    """
    try:
        url = f"https://api.mercadolibre.com/items/{item_id}"
        headers = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"  ⚠️  Error al obtener item {item_id}: {response.status_code}")
            return None

        data = response.json()

        # Si es catálogo, buscar el precio del buybox
        if data.get("catalog_product_id"):
            catalog_id = data["catalog_product_id"]
            catalog_url = f"https://api.mercadolibre.com/products/{catalog_id}"

            catalog_response = requests.get(catalog_url, headers=headers, timeout=10)

            if catalog_response.status_code == 200:
                catalog_data = catalog_response.json()

                # Obtener el buybox price
                buybox = catalog_data.get("buy_box_winner", {})
                if buybox and "price" in buybox:
                    return float(buybox["price"])

        # Si no hay buybox, devolver el precio actual del item
        return float(data.get("price", 0))

    except Exception as e:
        print(f"  ❌ Error obteniendo buybox de {item_id}: {e}")
        return None


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


def calculate_prices(costo_amazon, price_markup=PRICE_MARKUP, tax=TAX_FLORIDA, margen_minimo=MARGEN_MINIMO):
    """
    Calcula precio original y precio mínimo permitido

    Returns:
        dict: {costo_real, precio_original, precio_minimo}
    """
    costo_real = costo_amazon * (1 + tax)
    precio_original = costo_real * (1 + price_markup)
    precio_minimo = costo_real * (1 + margen_minimo)

    return {
        "costo_real": round(costo_real, 2),
        "precio_original": round(precio_original, 2),
        "precio_minimo": round(precio_minimo, 2)
    }


def adjust_catalog_prices(asin=None, dry_run=False):
    """
    Ajusta precios de productos de catálogo

    Args:
        asin: Si se especifica, solo procesa ese ASIN
        dry_run: Si es True, no actualiza precios, solo simula
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Obtener productos de catálogo
    if asin:
        cursor.execute("""
            SELECT asin, item_id, costo_amazon, precio_original, precio_actual, es_catalogo
            FROM listings
            WHERE asin = ? AND es_catalogo = 1
        """, (asin,))
    else:
        cursor.execute("""
            SELECT asin, item_id, costo_amazon, precio_original, precio_actual, es_catalogo
            FROM listings
            WHERE es_catalogo = 1
        """)

    productos = cursor.fetchall()

    if not productos:
        print("ℹ️  No hay productos de catálogo para procesar")
        conn.close()
        return

    print(f"\n🔍 Procesando {len(productos)} producto(s) de catálogo...")
    print(f"   Margen mínimo: {MARGEN_MINIMO*100:.0f}%")
    print(f"   Margen objetivo: {PRICE_MARKUP*100:.0f}%\n")

    resultados = {
        "actualizados": 0,
        "sin_cambios": 0,
        "no_rentable": 0,
        "errores": 0
    }

    for producto in productos:
        asin_prod, item_id, costo_amazon, precio_original, precio_actual, es_catalogo = producto

        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"📦 ASIN: {asin_prod}")
        print(f"   Item ID: {item_id}")

        # Si no tiene costo_amazon, calcular desde precio_original
        if not costo_amazon and precio_original:
            costo_amazon = precio_original / (1 + PRICE_MARKUP) / (1 + TAX_FLORIDA)
            print(f"   ℹ️  Costo Amazon calculado: ${costo_amazon:.2f}")

        if not costo_amazon:
            print(f"   ⚠️  Sin datos de costo, saltando...")
            resultados["errores"] += 1
            continue

        # Calcular precios
        precios = calculate_prices(costo_amazon)
        print(f"   💰 Costo real (+ tax): ${precios['costo_real']:.2f}")
        print(f"   📊 Precio original ({PRICE_MARKUP*100:.0f}%): ${precios['precio_original']:.2f}")
        print(f"   🚨 Precio mínimo ({MARGEN_MINIMO*100:.0f}%): ${precios['precio_minimo']:.2f}")

        # Obtener buybox de ML
        buybox_price = get_ml_buybox_price(item_id)

        if buybox_price is None:
            print(f"   ❌ No se pudo obtener buybox")
            resultados["errores"] += 1
            continue

        print(f"   🏆 Buybox actual: ${buybox_price:.2f}")

        # Decidir nuevo precio
        nuevo_precio = None
        razon = ""

        if buybox_price < precios["precio_minimo"]:
            # No es rentable competir
            nuevo_precio = precios["precio_original"]
            razon = "No rentable competir (buybox < precio mínimo)"
            resultados["no_rentable"] += 1
        else:
            # Puedo competir
            precio_competitivo = buybox_price - 1

            if precio_competitivo >= precios["precio_minimo"]:
                nuevo_precio = precio_competitivo
                razon = "Precio competitivo manteniendo margen"
            else:
                nuevo_precio = precios["precio_minimo"]
                razon = "Precio mínimo (competidor muy bajo)"

            resultados["actualizados"] += 1

        print(f"   💡 Decisión: ${nuevo_precio:.2f}")
        print(f"      Razón: {razon}")

        # Actualizar en ML si no es dry-run
        if not dry_run:
            if precio_actual and abs(nuevo_precio - precio_actual) < 1:
                print(f"   ✓ Sin cambios necesarios")
                resultados["sin_cambios"] += 1
                resultados["actualizados"] -= 1
            else:
                success = update_ml_price(item_id, nuevo_precio)

                if success:
                    # Actualizar DB
                    now = datetime.now().isoformat()
                    cursor.execute("""
                        UPDATE listings
                        SET precio_actual = ?,
                            precio_original = ?,
                            costo_amazon = ?,
                            tax_florida = ?,
                            ultima_actualizacion_precio = ?
                        WHERE asin = ?
                    """, (nuevo_precio, precios["precio_original"], costo_amazon,
                          TAX_FLORIDA, now, asin_prod))

                    print(f"   ✅ Precio actualizado en ML y DB")
                else:
                    print(f"   ❌ Error al actualizar en ML")
                    resultados["errores"] += 1
                    resultados["actualizados"] -= 1
        else:
            print(f"   🔵 DRY-RUN: No se actualizó")

    conn.commit()
    conn.close()

    # Resumen
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📊 RESUMEN:")
    print(f"   ✅ Actualizados: {resultados['actualizados']}")
    print(f"   ⏸️  Sin cambios: {resultados['sin_cambios']}")
    print(f"   🚨 No rentable: {resultados['no_rentable']}")
    print(f"   ❌ Errores: {resultados['errores']}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ajustar precios de productos de catálogo")
    parser.add_argument("--asin", help="Procesar solo este ASIN")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin actualizar")

    args = parser.parse_args()

    adjust_catalog_prices(asin=args.asin, dry_run=args.dry_run)
