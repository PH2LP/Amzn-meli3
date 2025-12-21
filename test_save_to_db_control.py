#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST: CONTROL DE GUARDADO EN DB
================================
Verifica que SAVE_TO_DB controle correctamente si se guarda o no en la DB
"""

import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

# Setup
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'scripts' / 'tools'))

def test_save_to_db_control():
    """Test del control SAVE_TO_DB"""

    print("=" * 80)
    print("🧪 TEST: CONTROL DE GUARDADO EN DB")
    print("=" * 80)
    print()

    # Test 1: SAVE_TO_DB=true (debería guardar)
    print("📋 Test 1: SAVE_TO_DB=true (debería guardar)")
    os.environ["SAVE_TO_DB"] = "true"

    # Importar función
    from scripts.tools.save_listing_data import is_save_to_db_enabled, save_listing
    print(f"   SAVE_TO_DB = {is_save_to_db_enabled()}")

    # Crear mini_ml de prueba
    mini_ml_test = {
        "asin": "B0TEST123",
        "title_ai": "Producto de prueba",
        "brand": "TestBrand",
        "price": {"net_proceeds_usd": 10.0},
        "package": {},
        "images": [],
        "attributes_mapped": {},
        "main_characteristics": []
    }

    # Verificar que la función se ejecute sin error
    try:
        save_listing("TEST_ITEM_ID", mini_ml_test)

        # Verificar que se guardó en la DB
        conn = sqlite3.connect("storage/listings_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT asin FROM listings WHERE asin = ?", ("B0TEST123",))
        result = cursor.fetchone()
        conn.close()

        if result:
            print(f"   ✅ PASS: Producto guardado en DB")
            # Limpiar
            conn = sqlite3.connect("storage/listings_database.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM listings WHERE asin = ?", ("B0TEST123",))
            conn.commit()
            conn.close()
            test1_pass = True
        else:
            print(f"   ❌ FAIL: Producto NO se guardó en DB")
            test1_pass = False
    except Exception as e:
        print(f"   ❌ FAIL: Error al guardar: {e}")
        test1_pass = False

    print()

    # Test 2: SAVE_TO_DB=false (NO debería guardar)
    print("📋 Test 2: SAVE_TO_DB=false (NO debería guardar)")
    os.environ["SAVE_TO_DB"] = "false"

    # La función is_save_to_db_enabled() leerá el nuevo valor automáticamente
    print(f"   SAVE_TO_DB = {is_save_to_db_enabled()}")

    mini_ml_test2 = {
        "asin": "B0TEST456",
        "title_ai": "Producto de prueba 2",
        "brand": "TestBrand",
        "price": {"net_proceeds_usd": 10.0},
        "package": {},
        "images": [],
        "attributes_mapped": {},
        "main_characteristics": []
    }

    try:
        # Capturar output
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            save_listing("TEST_ITEM_ID_2", mini_ml_test2)
        output = f.getvalue()

        # Verificar que NO se guardó en la DB
        conn = sqlite3.connect("storage/listings_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT asin FROM listings WHERE asin = ?", ("B0TEST456",))
        result = cursor.fetchone()
        conn.close()

        if not result and "SAVE_TO_DB=false" in output:
            print(f"   ✅ PASS: Producto NO se guardó en DB (como esperado)")
            test2_pass = True
        else:
            print(f"   ❌ FAIL: Producto se guardó cuando NO debería")
            # Limpiar si se guardó
            if result:
                conn = sqlite3.connect("storage/listings_database.db")
                cursor = conn.cursor()
                cursor.execute("DELETE FROM listings WHERE asin = ?", ("B0TEST456",))
                conn.commit()
                conn.close()
            test2_pass = False
    except Exception as e:
        print(f"   ❌ FAIL: Error inesperado: {e}")
        test2_pass = False

    print()

    # Restaurar valor original
    load_dotenv(override=True)

    # Resumen
    print("=" * 80)
    if test1_pass and test2_pass:
        print("✅ TODOS LOS TESTS PASARON")
        print("=" * 80)
        return True
    else:
        print("❌ ALGUNOS TESTS FALLARON")
        print("=" * 80)
        return False

if __name__ == "__main__":
    success = test_save_to_db_control()
    sys.exit(0 if success else 1)
