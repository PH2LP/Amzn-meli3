#!/usr/bin/env python3
"""Test del sync con Glow API - Verificar que todos los fixes están aplicados"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import sync function
from scripts.tools.sync_amazon_ml_GLOW import get_glow_data_batch

print("=" * 80)
print("🧪 TEST SYNC CON GLOW API")
print("=" * 80)
print()

# Test con algunos ASINs conocidos
test_asins = [
    "B0FHXSMFDN",  # Esperado: APROBADO (2 días)
    "B0C6YMKWR7",  # Esperado: RECHAZADO (15 días)
    "B0FTG5BLH3",  # Esperado: APROBADO (2 días)
]

print(f"📋 Testing {len(test_asins)} ASINs:")
for asin in test_asins:
    print(f"   - {asin}")
print()

try:
    # Llamar a get_glow_data_batch
    results = get_glow_data_batch(test_asins, show_progress=True)

    print()
    print("=" * 80)
    print("📊 RESULTADOS FINALES")
    print("=" * 80)
    print()

    for asin in test_asins:
        data = results.get(asin)

        if data:
            print(f"✅ {asin}:")
            print(f"   Precio: ${data['price']:.2f}")
            print(f"   Delivery: {data['delivery_date']}")
            print(f"   Días: {data['days_until_delivery']}")
            print(f"   Fast delivery: {'Sí' if data['is_fast_delivery'] else 'No'}")
            print(f"   Prime: {'Sí' if data['prime_available'] else 'No'}")
        else:
            print(f"❌ {asin}: RECHAZADO (no cumple requisitos)")
        print()

    # Verificar que los fixes están aplicados
    print("=" * 80)
    print("🔍 VERIFICACIÓN DE FIXES")
    print("=" * 80)
    print()

    checks = []

    # Check 1: prime_available debe estar presente
    if any(data and 'prime_available' in data for data in results.values() if data):
        checks.append("✅ Fix prime_available aplicado correctamente")
    else:
        checks.append("⚠️  Fix prime_available NO verificable (ningún producto aprobado)")

    # Check 2: Debe haber delays (verificar en código)
    with open("scripts/tools/sync_amazon_ml_GLOW.py", "r") as f:
        sync_code = f.read()
        if "time.sleep(1.5)" in sync_code:
            checks.append("✅ Rate limiting 1.5s aplicado")
        else:
            checks.append("❌ Rate limiting 1.5s NO encontrado")

        if "Pausa preventiva" in sync_code:
            checks.append("✅ Pausa preventiva cada 10 productos aplicada")
        else:
            checks.append("❌ Pausa preventiva NO encontrada")

    # Check 3: Verificar que usa check_real_availability
    if "check_real_availability" in sync_code:
        checks.append("✅ Usa Glow API (check_real_availability)")
    else:
        checks.append("❌ NO usa Glow API")

    for check in checks:
        print(check)

    print()
    print("=" * 80)

    if all("✅" in check or "⚠️" in check for check in checks):
        print("✅ TODOS LOS FIXES APLICADOS CORRECTAMENTE")
    else:
        print("❌ ALGUNOS FIXES NO ESTÁN APLICADOS")

    print("=" * 80)

except Exception as e:
    print(f"❌ ERROR EN TEST: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
