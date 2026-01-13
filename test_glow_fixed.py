#!/usr/bin/env python3
"""
TEST: Verificar que amazon_glow_api_v2_advanced.py funciona con curl_cffi

Testea la integración de curl_cffi en el módulo principal.
"""

import sys
from pathlib import Path

# Importar módulo con nueva integración
sys.path.insert(0, str(Path(__file__).parent))
from src.integrations.amazon_glow_api_v2_advanced import check_availability_v2_advanced

# ASINs de prueba (algunos que antes se bloqueaban)
TEST_ASINS = [
    "B07CTLNYVV",  # El que fallaba antes
    "B0BN94P3YW",
    "B0C1H26C46",
    "B08L5VFJ2R",
    "B0B7CPSN8B"
]

print("=" * 80)
print("TEST: Verificar integración curl_cffi en amazon_glow_api_v2_advanced.py")
print("=" * 80)
print()

zipcode = "33172"
print(f"📍 Zipcode: {zipcode}")
print(f"🧪 ASINs de prueba: {len(TEST_ASINS)}")
print()

successful = 0
blocked = 0
errors = 0

for i, asin in enumerate(TEST_ASINS, 1):
    print(f"\n{'='*80}")
    print(f"TEST {i}/{len(TEST_ASINS)}: {asin}")
    print(f"{'='*80}")

    try:
        result = check_availability_v2_advanced(asin, zipcode)

        if result.get("error"):
            if "bloqueado" in result["error"].lower() or "captcha" in result["error"].lower():
                print(f"❌ BLOQUEADO: {result['error']}")
                blocked += 1
            else:
                print(f"⚠️  ERROR: {result['error']}")
                errors += 1
        else:
            print(f"✅ ÉXITO!")
            print(f"   Available: {result['available']}")
            print(f"   Price: ${result['price']}" if result['price'] else "   Price: N/A")
            print(f"   Delivery: {result['delivery_date']}" if result['delivery_date'] else "   Delivery: N/A")
            print(f"   Days: {result['days_until_delivery']}" if result['days_until_delivery'] else "   Days: N/A")
            successful += 1

    except Exception as e:
        print(f"💥 EXCEPCIÓN: {e}")
        errors += 1
        import traceback
        traceback.print_exc()

print()
print("=" * 80)
print("📊 RESUMEN")
print("=" * 80)
print(f"✅ Exitosos:    {successful}/{len(TEST_ASINS)}")
print(f"❌ Bloqueados:  {blocked}/{len(TEST_ASINS)}")
print(f"⚠️  Errores:     {errors}/{len(TEST_ASINS)}")
print()

if blocked == 0:
    print("🎉 ¡ÉXITO! No hubo bloqueos - curl_cffi está funcionando!")
else:
    print("⚠️  Todavía hay bloqueos - revisar logs")

print("=" * 80)
