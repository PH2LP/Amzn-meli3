#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST DE INTEGRACIÓN: CATEGORIZACIÓN DE ERRORES EN SYNC
=======================================================
Verifica que el sistema categorice correctamente los errores durante el sync
"""

import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env
load_dotenv(override=True)

# Agregar paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'scripts' / 'tools'))

# Importar función de detección
from sync_amazon_ml_GLOW import is_wrong_account_item, ML_USER_ID

DB_PATH = "storage/listings_database.db"

def test_sync_error_categorization():
    """Test de categorización de errores con datos reales de la DB"""

    print("=" * 80)
    print("🧪 TEST DE INTEGRACIÓN: CATEGORIZACIÓN DE ERRORES")
    print("=" * 80)
    print(f"\n📋 ML_USER_ID configurado: {ML_USER_ID}")
    print(f"📂 Database: {DB_PATH}")
    print()

    # Conectar a la DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Obtener TODOS los listings (no usar LIMIT para test completo)
    cursor.execute("""
        SELECT item_id, asin, title, site_items
        FROM listings
    """)

    listings = cursor.fetchall()

    print(f"📊 Analizando {len(listings)} listings...")
    print()

    # Contadores
    nexo_count = 0
    oneworld_count = 0
    mixed_count = 0
    no_data_count = 0

    # Seller IDs de NEXO
    NEXO_SELLER_IDS = {
        "3047790551", "3047796173", "3048288440",
        "3048288454", "3048288470", "3048289672", "3048289692"
    }

    # Analizar cada listing
    for item_id, asin, title, site_items in listings:
        if is_wrong_account_item(site_items):
            oneworld_count += 1
        elif site_items:
            # Tiene datos pero no es cuenta diferente → es NEXO
            import json
            try:
                site_data = json.loads(site_items)
                has_nexo = any(
                    str(s.get("seller_id", "")) in NEXO_SELLER_IDS
                    for s in site_data if "error" not in s
                )
                if has_nexo:
                    nexo_count += 1
                else:
                    # Esto no debería pasar si is_wrong_account_item funciona bien
                    mixed_count += 1
            except:
                no_data_count += 1
        else:
            no_data_count += 1

    # Cerrar conexión
    conn.close()

    # Resumen
    print("=" * 80)
    print("📊 RESULTADOS DEL ANÁLISIS")
    print("=" * 80)
    print(f"Items de NEXO (cuenta actual):     {nexo_count}")
    print(f"Items de ONEWORLD (otra cuenta):   {oneworld_count}")
    print(f"Items mixtos (ambas cuentas):      {mixed_count}")
    print(f"Items sin datos de seller:         {no_data_count}")
    print()
    print(f"Total items:                        {len(listings)}")
    print()

    # Calcular porcentajes
    if oneworld_count > 0:
        oneworld_pct = (oneworld_count / len(listings)) * 100
        print(f"⚠️  Items de cuenta diferente: {oneworld_pct:.1f}%")
        print(f"   Estos {oneworld_count} items darán error 'cuenta diferente' en el sync")
        print()

    # Verificar si los números coinciden con lo esperado
    # Sabemos que hay ~107 items de ONEWORLD
    expected_oneworld = 107
    tolerance = 10  # Tolerancia de +/- 10 items

    print("=" * 80)
    print("✅ VALIDACIÓN")
    print("=" * 80)

    if abs(oneworld_count - expected_oneworld) <= tolerance:
        print(f"✅ PASS: Cantidad de items ONEWORLD coincide (~{expected_oneworld} esperados)")
        print(f"   Detectados: {oneworld_count}")
        success = True
    else:
        print(f"❌ FAIL: Cantidad de items ONEWORLD no coincide")
        print(f"   Esperados: ~{expected_oneworld}")
        print(f"   Detectados: {oneworld_count}")
        success = False

    print()
    print("=" * 80)
    if success:
        print("✅ TEST DE INTEGRACIÓN EXITOSO")
    else:
        print("❌ TEST DE INTEGRACIÓN FALLÓ")
    print("=" * 80)
    print()

    return success

if __name__ == "__main__":
    success = test_sync_error_categorization()
    sys.exit(0 if success else 1)
