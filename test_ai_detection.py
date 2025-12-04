#!/usr/bin/env python3
"""
Test de detección con IA: Producto oficial vs third-party
"""

from src.pipeline.logo_filter import LogoFilter

print("=" * 80)
print("🤖 TEST: Detección con IA - Producto Oficial vs Third-Party")
print("=" * 80)
print()

filter_obj = LogoFilter()

# Test cases con ejemplos complejos que keywords no manejarían bien
test_cases = [
    {
        "title": "Apple MagSafe Charger for iPhone 15 Pro",
        "description": "OFICIAL Apple (MagSafe es marca de Apple)",
        "expected_official": True,
        "expected_brand": "apple"
    },
    {
        "title": "Generic MagSafe-style charger compatible with iPhone",
        "description": "THIRD-PARTY (dice 'generic' y 'compatible')",
        "expected_official": False,
        "expected_brand": None
    },
    {
        "title": "Sony PlayStation 5 Console Digital Edition",
        "description": "OFICIAL Sony",
        "expected_official": True,
        "expected_brand": "sony"
    },
    {
        "title": "Base de carga para controles PS5",
        "description": "THIRD-PARTY (accesorio genérico)",
        "expected_official": False,
        "expected_brand": None
    },
    {
        "title": "Apple iPad Pro 13-inch M4",
        "description": "OFICIAL Apple",
        "expected_official": True,
        "expected_brand": "apple"
    },
    {
        "title": "Funda estilo Apple para iPad Pro",
        "description": "THIRD-PARTY ('estilo Apple', no es de Apple)",
        "expected_official": False,
        "expected_brand": None
    },
    {
        "title": "Razer BlackWidow V4 Mechanical Gaming Keyboard",
        "description": "OFICIAL Razer",
        "expected_official": True,
        "expected_brand": "razer"
    },
    {
        "title": "RGB Gaming Keyboard compatible with Razer software",
        "description": "THIRD-PARTY (compatible con, no es Razer)",
        "expected_official": False,
        "expected_brand": None
    }
]

passed = 0
failed = 0

print("Analizando productos con IA...\n")

for i, test in enumerate(test_cases, 1):
    title = test["title"]
    desc = test["description"]
    expected_official = test["expected_official"]
    expected_brand = test["expected_brand"]

    # Detectar con IA
    ai_result = filter_obj._is_official_product_ai(title)

    is_official = ai_result["is_official"]
    detected_brand = ai_result["brand"]
    reasoning = ai_result["reasoning"]

    # Verificar si es correcto
    brand_match = (detected_brand == expected_brand if expected_brand else detected_brand is None)
    is_correct = (is_official == expected_official) and brand_match

    status = "✅" if is_correct else "❌ FAILED"

    if is_correct:
        passed += 1
    else:
        failed += 1

    print(f"{i}. {title}")
    print(f"   📝 {desc}")
    print(f"   {status} IA dice: {'OFICIAL' if is_official else 'THIRD-PARTY'} - {detected_brand or 'N/A'}")
    print(f"      Razonamiento: {reasoning}")
    if not is_correct:
        print(f"      (Esperado: {'OFICIAL' if expected_official else 'THIRD-PARTY'} - {expected_brand or 'N/A'})")
    print()

print("=" * 80)
print("📊 RESUMEN")
print("=" * 80)
print()
print(f"✅ Tests pasados: {passed}/{len(test_cases)}")
print(f"❌ Tests fallidos: {failed}/{len(test_cases)}")
print()

if failed == 0:
    print("🎉 TODOS LOS TESTS PASARON - IA funciona perfectamente!")
else:
    print(f"⚠️  {failed} tests fallidos - revisar prompt de IA")

print()
print("=" * 80)
