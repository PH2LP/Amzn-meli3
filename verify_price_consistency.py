#!/usr/bin/env python3
"""
Verificar que sync y transform usan la misma lógica de precios
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

sys.path.insert(0, str(Path(__file__).parent))

from scripts.tools.sync_amazon_ml import calculate_new_ml_price
from src.pipeline.transform_mapper_new import compute_price

def test_consistency():
    print("=" * 80)
    print("🧪 VERIFICACIÓN DE CONSISTENCIA DE PRECIOS")
    print("=" * 80)
    print("\nComparando:")
    print("  1. sync_amazon_ml.calculate_new_ml_price()")
    print("  2. transform_mapper_new.compute_price()")

    # Test con varios precios
    test_prices = [35.99, 50.00, 100.00, 20.00]

    all_consistent = True

    for amazon_price in test_prices:
        # Calcular con sync
        sync_price = calculate_new_ml_price(amazon_price)

        # Calcular con transform
        transform_result = compute_price(amazon_price)
        transform_price = transform_result["net_proceeds_usd"]

        print(f"\n📊 Amazon = ${amazon_price} USD")
        print(f"   Sync:      ${sync_price} USD")
        print(f"   Transform: ${transform_price} USD")

        if abs(sync_price - transform_price) < 0.01:
            print(f"   ✅ CONSISTENTE")
        else:
            print(f"   ❌ INCONSISTENTE")
            all_consistent = False

    print(f"\n{'=' * 80}")

    # Verificar configuración
    print("\n📋 Configuración actual:")
    print(f"   PRICE_MARKUP (env): {os.getenv('PRICE_MARKUP', 'NO DEFINIDO')}")
    print(f"   Tax 7% (hardcoded en sync)")
    print(f"   3PL Fee $4 (hardcoded en sync)")
    print(f"   Markup 30% (hardcoded en sync)")

    print(f"\n{'=' * 80}")

    if all_consistent:
        print("✅ AMBOS SISTEMAS USAN LA MISMA LÓGICA DE PRECIOS")
        print("\nFórmula aplicada:")
        print("  (Amazon + Tax 7% + $4 USD) × (1 + Markup 30%)")
        print("\n✅ Los productos publicados tendrán precios consistentes")
        print("✅ La sincronización calculará los mismos precios")
    else:
        print("❌ INCONSISTENCIA DETECTADA")
        print("\nLos sistemas calculan precios diferentes!")

    print("=" * 80)

    return all_consistent

if __name__ == "__main__":
    success = test_consistency()
    sys.exit(0 if success else 1)
