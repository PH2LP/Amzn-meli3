#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para el sistema de precios dinámicos

Simula productos de catálogo en la DB y prueba la lógica
de ajuste de precios sin tocar MercadoLibre.
"""

import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "storage/listings_database.db"

# Datos de prueba simulados
PRODUCTOS_TEST = [
    {
        "asin": "TEST001",
        "item_id": "MLM999999991",  # ID fake
        "title": "Producto Test 1 - Competitivo",
        "costo_amazon": 50.00,  # $50 en Amazon
        "precio_original": None,  # Se calculará
        "precio_actual": None,
        "es_catalogo": 1,
        "buybox_simulado": 70.00,  # Buybox competitivo
        "descripcion": "Caso donde SÍ conviene competir"
    },
    {
        "asin": "TEST002",
        "item_id": "MLM999999992",
        "title": "Producto Test 2 - No Rentable",
        "costo_amazon": 50.00,
        "precio_original": None,
        "precio_actual": None,
        "es_catalogo": 1,
        "buybox_simulado": 60.00,  # Buybox muy bajo, no rentable
        "descripcion": "Caso donde NO conviene competir"
    },
    {
        "asin": "TEST003",
        "item_id": "MLM999999993",
        "title": "Producto Test 3 - Justo en el límite",
        "costo_amazon": 50.00,
        "precio_original": None,
        "precio_actual": None,
        "es_catalogo": 1,
        "buybox_simulado": 66.88,  # Justo en el precio mínimo (25%)
        "descripcion": "Caso límite: buybox = precio_mínimo"
    },
]


def calcular_precios(costo_amazon):
    """Calcula precios según las fórmulas del sistema"""
    TAX_FLORIDA = 0.07
    PRICE_MARKUP = 0.45

    costo_real = costo_amazon * (1 + TAX_FLORIDA)
    precio_original = costo_real * (1 + PRICE_MARKUP)
    precio_minimo = costo_real * 1.25  # 25% margen mínimo

    return {
        "costo_real": round(costo_real, 2),
        "precio_original": round(precio_original, 2),
        "precio_minimo": round(precio_minimo, 2)
    }


def insertar_productos_test():
    """Inserta productos de prueba en la DB"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n🧪 INSERTANDO PRODUCTOS DE PRUEBA EN LA DB...\n")

    for producto in PRODUCTOS_TEST:
        # Calcular precios
        precios = calcular_precios(producto["costo_amazon"])

        # Eliminar si ya existe (para poder re-ejecutar el test)
        cursor.execute("DELETE FROM listings WHERE asin = ?", (producto["asin"],))

        # Insertar
        cursor.execute("""
            INSERT INTO listings (
                asin, item_id, title, costo_amazon, tax_florida,
                precio_original, precio_actual, es_catalogo,
                date_published, date_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            producto["asin"],
            producto["item_id"],
            producto["title"],
            producto["costo_amazon"],
            0.07,
            precios["precio_original"],
            precios["precio_original"],  # Inicialmente = precio_original
            producto["es_catalogo"],
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))

        print(f"✅ {producto['asin']}: {producto['title']}")
        print(f"   📊 Costo Amazon: ${producto['costo_amazon']:.2f}")
        print(f"   💰 Costo Real (+tax): ${precios['costo_real']:.2f}")
        print(f"   🎯 Precio Original (45%): ${precios['precio_original']:.2f}")
        print(f"   🚨 Precio Mínimo (25%): ${precios['precio_minimo']:.2f}")
        print(f"   🏆 Buybox simulado: ${producto['buybox_simulado']:.2f}")
        print(f"   💡 {producto['descripcion']}\n")

    conn.commit()
    conn.close()

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")


def simular_ajuste_precios():
    """Simula el ajuste de precios SIN tocar ML"""
    print("🔍 SIMULANDO AJUSTE DE PRECIOS...\n")

    MARGEN_MINIMO = 0.25

    for producto in PRODUCTOS_TEST:
        precios = calcular_precios(producto["costo_amazon"])
        buybox = producto["buybox_simulado"]

        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"📦 {producto['asin']}: {producto['title']}")
        print(f"   💰 Precio Original: ${precios['precio_original']:.2f}")
        print(f"   🚨 Precio Mínimo: ${precios['precio_minimo']:.2f}")
        print(f"   🏆 Buybox ML: ${buybox:.2f}")

        # Lógica de decisión
        if buybox < precios["precio_minimo"]:
            nuevo_precio = precios["precio_original"]
            razon = "❌ No rentable competir (buybox < precio mínimo)"
            margen_final = 0.45
        else:
            precio_competitivo = buybox - 1

            if precio_competitivo >= precios["precio_minimo"]:
                nuevo_precio = precio_competitivo
                margen_final = (nuevo_precio / precios["costo_real"]) - 1
                razon = f"✅ Precio competitivo (margen {margen_final*100:.1f}%)"
            else:
                nuevo_precio = precios["precio_minimo"]
                razon = "⚠️  Precio mínimo (competidor muy bajo)"
                margen_final = 0.25

        print(f"   💡 Decisión: ${nuevo_precio:.2f}")
        print(f"   📝 Razón: {razon}")
        print(f"   📊 Margen final: {margen_final*100:.1f}%\n")


def limpiar_productos_test():
    """Elimina los productos de prueba de la DB"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("🧹 LIMPIANDO PRODUCTOS DE PRUEBA...\n")

    for producto in PRODUCTOS_TEST:
        cursor.execute("DELETE FROM listings WHERE asin = ?", (producto["asin"],))
        print(f"🗑️  Eliminado: {producto['asin']}")

    conn.commit()
    conn.close()

    print("\n✅ Productos de prueba eliminados\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--clean":
        limpiar_productos_test()
    else:
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("🧪 TEST DE SISTEMA DE PRECIOS DINÁMICOS")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        insertar_productos_test()
        simular_ajuste_precios()

        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("📋 RESUMEN DEL TEST:")
        print("   ✅ TEST001: Debería bajar a $69 (competir)")
        print("   ❌ TEST002: Debería mantener $77.58 (no rentable)")
        print("   ⚠️  TEST003: Debería bajar a $65.88 (límite)")
        print("\n💡 Para limpiar la DB ejecuta:")
        print("   python3 scripts/tools/test_dynamic_pricing.py --clean")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
