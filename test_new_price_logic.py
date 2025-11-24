#!/usr/bin/env python3
"""
Test de la nueva lógica de cálculo de precios
Verifica que la fórmula sea: (Amazon + Tax 7% + $4) × (1 + Markup 30%)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scripts.tools.sync_amazon_ml import calculate_new_ml_price

def test_price_calculation():
    print("=" * 80)
    print("🧪 TEST DE LÓGICA DE CÁLCULO DE PRECIOS")
    print("=" * 80)
    print("\nFórmula: (Amazon + Tax 7% + $4 USD) × (1 + Markup 30%)")

    # Test cases
    test_cases = [
        {"amazon": 35.99, "expected": 55.26},
        {"amazon": 50.00, "expected": 74.75},
        {"amazon": 100.00, "expected": 144.30},  # (100 + 7 + 4) × 1.30 = 144.30
        {"amazon": 20.00, "expected": 33.02},
    ]

    all_passed = True

    for i, test in enumerate(test_cases, 1):
        amazon_price = test["amazon"]
        expected = test["expected"]

        # Calcular precio ML
        calculated = calculate_new_ml_price(amazon_price)

        # Verificar paso a paso
        tax = round(amazon_price * 0.07, 2)
        cost = round(amazon_price + tax + 4.0, 2)
        final = round(cost * 1.30, 2)

        print(f"\n📊 Test {i}: Amazon = ${amazon_price} USD")
        print(f"   Paso 1: Precio base = ${amazon_price}")
        print(f"   Paso 2: Tax 7% = ${tax}")
        print(f"   Paso 3: 3PL Fee = $4.00")
        print(f"   Paso 4: Costo total = ${cost}")
        print(f"   Paso 5: Markup 30% = ${final}")
        print(f"   Resultado: ${calculated} USD")

        if abs(calculated - expected) < 0.01:
            print(f"   ✅ CORRECTO (esperado: ${expected})")
        else:
            print(f"   ❌ ERROR (esperado: ${expected}, obtenido: ${calculated})")
            all_passed = False

    print(f"\n{'=' * 80}")
    if all_passed:
        print("✅ TODOS LOS TESTS PASARON")
        print("La lógica de cálculo es correcta:")
        print("  (Amazon + Tax 7% + $4) × (1 + Markup 30%)")
    else:
        print("❌ ALGUNOS TESTS FALLARON")
    print("=" * 80)

    return all_passed

if __name__ == "__main__":
    success = test_price_calculation()
    sys.exit(0 if success else 1)
