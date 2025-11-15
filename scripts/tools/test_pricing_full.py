#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test completo del sistema de precios dinámicos
Simula TODO el flujo incluyendo la consulta de buybox
"""

import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "storage/listings_database.db"
PRICE_MARKUP = float(os.getenv("PRICE_MARKUP", 45)) / 100
TAX_FLORIDA = 0.07
MARGEN_MINIMO = 0.25


def calcular_precios(costo_amazon, price_markup=PRICE_MARKUP, tax=TAX_FLORIDA, margen_minimo=MARGEN_MINIMO):
    """Calcula precios según las fórmulas del sistema"""
    costo_real = costo_amazon * (1 + tax)
    precio_original = costo_real * (1 + price_markup)
    precio_minimo = costo_real * (1 + margen_minimo)

    return {
        "costo_real": round(costo_real, 2),
        "precio_original": round(precio_original, 2),
        "precio_minimo": round(precio_minimo, 2)
    }


def simular_buybox_para_test(asin):
    """
    Simula el buybox según el ASIN de test
    En un caso real, esto vendría de ML API
    """
    buybox_map = {
        "TEST001": 70.00,   # Competitivo
        "TEST002": 60.00,   # No rentable
        "TEST003": 66.88,   # Límite exacto
    }
    return buybox_map.get(asin, None)


def ajustar_precios_test():
    """
    Versión de test que simula el buybox en vez de consultarlo
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT asin, item_id, costo_amazon, precio_original, precio_actual
        FROM listings
        WHERE es_catalogo = 1 AND asin LIKE 'TEST%'
    """)

    productos = cursor.fetchall()

    if not productos:
        print("⚠️  No hay productos de test en la DB")
        print("   Ejecuta primero: python3 scripts/tools/test_dynamic_pricing.py")
        conn.close()
        return

    print(f"\n🧪 EJECUTANDO TEST COMPLETO DE AJUSTE DE PRECIOS")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    print(f"📊 Configuración:")
    print(f"   • Margen objetivo: {PRICE_MARKUP*100:.0f}%")
    print(f"   • Margen mínimo: {MARGEN_MINIMO*100:.0f}%")
    print(f"   • Tax Florida: {TAX_FLORIDA*100:.0f}%\n")

    resultados = {
        "actualizados": 0,
        "sin_cambios": 0,
        "no_rentable": 0,
        "errores": 0
    }

    for producto in productos:
        asin_prod, item_id, costo_amazon, precio_original, precio_actual = producto

        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"📦 ASIN: {asin_prod}")
        print(f"   Item ID: {item_id}")

        # Calcular precios
        if not costo_amazon and precio_original:
            costo_amazon = precio_original / (1 + PRICE_MARKUP) / (1 + TAX_FLORIDA)
            print(f"   ℹ️  Costo Amazon calculado: ${costo_amazon:.2f}")

        if not costo_amazon:
            print(f"   ⚠️  Sin datos de costo, saltando...")
            resultados["errores"] += 1
            continue

        precios = calcular_precios(costo_amazon)
        print(f"   💰 Costo real (+ tax): ${precios['costo_real']:.2f}")
        print(f"   📊 Precio original ({PRICE_MARKUP*100:.0f}%): ${precios['precio_original']:.2f}")
        print(f"   🚨 Precio mínimo ({MARGEN_MINIMO*100:.0f}%): ${precios['precio_minimo']:.2f}")

        # Simular buybox
        buybox_price = simular_buybox_para_test(asin_prod)

        if buybox_price is None:
            print(f"   ❌ No hay buybox simulado para {asin_prod}")
            resultados["errores"] += 1
            continue

        print(f"   🏆 Buybox simulado: ${buybox_price:.2f}")

        # LÓGICA DE DECISIÓN (igual que adjust_catalog_prices.py)
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
                margen = (nuevo_precio / precios["costo_real"]) - 1
                razon = f"Precio competitivo manteniendo margen ({margen*100:.1f}%)"
            else:
                nuevo_precio = precios["precio_minimo"]
                razon = "Precio mínimo (competidor muy bajo)"

            resultados["actualizados"] += 1

        print(f"   💡 Decisión: ${nuevo_precio:.2f}")
        print(f"      Razón: {razon}")

        # Actualizar en DB (solo precio_actual, sin tocar ML)
        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE listings
            SET precio_actual = ?,
                ultima_actualizacion_precio = ?
            WHERE asin = ?
        """, (nuevo_precio, now, asin_prod))

        print(f"   ✅ DB actualizada con nuevo precio")

    conn.commit()
    conn.close()

    # Resumen
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📊 RESUMEN:")
    print(f"   ✅ Actualizados: {resultados['actualizados']}")
    print(f"   ⏸️  Sin cambios: {resultados['sin_cambios']}")
    print(f"   🚨 No rentable: {resultados['no_rentable']}")
    print(f"   ❌ Errores: {resultados['errores']}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    # Mostrar estado final de la DB
    verificar_db()


def verificar_db():
    """Verifica el estado final de los productos test en la DB"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT asin, costo_amazon, precio_original, precio_actual,
               ultima_actualizacion_precio
        FROM listings
        WHERE asin LIKE 'TEST%'
        ORDER BY asin
    """)

    productos = cursor.fetchall()
    conn.close()

    if not productos:
        return

    print("🔍 VERIFICACIÓN EN DB:")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    for prod in productos:
        asin, costo, original, actual, ultima_act = prod
        cambio = ""
        if original and actual:
            if actual < original:
                diff = original - actual
                pct = (diff / original) * 100
                cambio = f"↓ ${diff:.2f} ({pct:.1f}%)"
            elif actual == original:
                cambio = "= Sin cambios"

        print(f"   {asin}:")
        print(f"      Precio Original: ${original:.2f}")
        print(f"      Precio Actual:   ${actual:.2f} {cambio}")
        print(f"      Última act:      {ultima_act}\n")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")


if __name__ == "__main__":
    ajustar_precios_test()
