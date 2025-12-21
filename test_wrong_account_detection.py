#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST: DETECCIÓN DE ERRORES POR CUENTA DIFERENTE
================================================
Verifica que el sistema detecte correctamente items de otra cuenta
"""

import os
import sys
import json
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

def test_wrong_account_detection():
    """Test la función de detección de cuenta diferente"""

    print("=" * 80)
    print("🧪 TEST: DETECCIÓN DE ITEMS DE CUENTA DIFERENTE")
    print("=" * 80)
    print(f"\n📋 ML_USER_ID configurado: {ML_USER_ID}")
    print()

    # Test 1: Item de NEXO (cuenta actual) - NO debería detectarse como cuenta diferente
    site_items_nexo = json.dumps([
        {"item_id": "MLM123", "site_id": "MLM", "seller_id": 3047790551},
        {"item_id": "MLA456", "site_id": "MLA", "seller_id": 3048288440}
    ])

    result1 = is_wrong_account_item(site_items_nexo)
    print(f"✅ Test 1: Item de NEXO (sellers 3047790551, 3048288440)")
    print(f"   Esperado: False (es de nuestra cuenta)")
    print(f"   Resultado: {result1}")
    print(f"   {'✅ PASS' if result1 == False else '❌ FAIL'}")
    print()

    # Test 2: Item de ONEWORLD (cuenta diferente) - SÍ debería detectarse
    site_items_oneworld = json.dumps([
        {"item_id": "MLM789", "site_id": "MLM", "seller_id": 2629800952},
        {"item_id": "MLA012", "site_id": "MLA", "seller_id": 2629798326}
    ])

    result2 = is_wrong_account_item(site_items_oneworld)
    print(f"✅ Test 2: Item de ONEWORLD (sellers 2629800952, 2629798326)")
    print(f"   Esperado: True (es de otra cuenta)")
    print(f"   Resultado: {result2}")
    print(f"   {'✅ PASS' if result2 == True else '❌ FAIL'}")
    print()

    # Test 3: Item mixto (NEXO + ONEWORLD) - NO debería detectarse como cuenta diferente
    site_items_mixto = json.dumps([
        {"item_id": "MLM345", "site_id": "MLM", "seller_id": 3047790551},  # NEXO
        {"item_id": "MLA678", "site_id": "MLA", "seller_id": 2629798326}   # ONEWORLD
    ])

    result3 = is_wrong_account_item(site_items_mixto)
    print(f"✅ Test 3: Item mixto (NEXO + ONEWORLD)")
    print(f"   Esperado: False (al menos un seller es de nuestra cuenta)")
    print(f"   Resultado: {result3}")
    print(f"   {'✅ PASS' if result3 == False else '❌ FAIL'}")
    print()

    # Test 4: JSON vacío o None
    result4a = is_wrong_account_item(None)
    result4b = is_wrong_account_item("")
    result4c = is_wrong_account_item("[]")  # Array vacío

    print(f"✅ Test 4: Casos edge (None, vacío, etc)")
    print(f"   None: {result4a} (esperado: False) - {'✅ PASS' if result4a == False else '❌ FAIL'}")
    print(f"   String vacío: {result4b} (esperado: False) - {'✅ PASS' if result4b == False else '❌ FAIL'}")
    print(f"   JSON vacío: {result4c} (esperado: False) - {'✅ PASS' if result4c == False else '❌ FAIL'}")
    print()

    # Resumen
    all_pass = (
        result1 == False and
        result2 == True and
        result3 == False and
        result4a == False and
        result4b == False and
        result4c == False
    )

    print("=" * 80)
    if all_pass:
        print("✅ TODOS LOS TESTS PASARON")
    else:
        print("❌ ALGUNOS TESTS FALLARON")
    print("=" * 80)
    print()

    return all_pass

if __name__ == "__main__":
    success = test_wrong_account_detection()
    sys.exit(0 if success else 1)
