#!/usr/bin/env python3
"""
STRESS TEST: Casos extremos para intentar romper la detección de IA
Objetivo: Evitar FALSOS POSITIVOS (productos oficiales marcados como third-party)
"""

from src.pipeline.logo_filter import LogoFilter

print("=" * 80)
print("⚠️  STRESS TEST: Intentando romper la detección de IA")
print("=" * 80)
print()
print("OBJETIVO: Evitar FALSOS POSITIVOS (crítico para no perder imágenes buenas)")
print()

filter_obj = LogoFilter()

# Casos EXTREMOS que podrían confundir a la IA
stress_cases = [
    {
        "title": "Apple AirPods Pro (2nd Generation) USB-C",
        "expected_official": True,
        "expected_brand": "apple",
        "why_tricky": "Tiene USB-C (tipo de conector), podría confundir"
    },
    {
        "title": "Apple Pencil (2nd Generation) for iPad Pro",
        "expected_official": True,
        "expected_brand": "apple",
        "why_tricky": "Dice 'for iPad Pro' pero Apple Pencil ES de Apple"
    },
    {
        "title": "Apple USB-C to Lightning Cable (1m)",
        "expected_official": True,
        "expected_brand": "apple",
        "why_tricky": "Es un CABLE (keyword de accesorio) pero oficial Apple"
    },
    {
        "title": "Sony DualSense Charging Station for PS5",
        "expected_official": True,
        "expected_brand": "sony",
        "why_tricky": "Dice 'Charging Station' y 'for PS5' pero ES oficial Sony"
    },
    {
        "title": "Microsoft Xbox Wireless Controller for Xbox Series X|S",
        "expected_official": True,
        "expected_brand": "microsoft",
        "why_tricky": "Tiene 'for Xbox' pero ES producto oficial Microsoft"
    },
    {
        "title": "Samsung Galaxy SmartTag2 for Android devices",
        "expected_official": True,
        "expected_brand": "samsung",
        "why_tricky": "Dice 'for Android' pero es producto oficial Samsung"
    },
    {
        "title": "Stylus pen compatible with iPad Pro and Air",
        "expected_official": False,
        "expected_brand": None,
        "why_tricky": "No tiene marca al inicio, debería ser third-party"
    },
    {
        "title": "Wireless controller for PS5 console gaming",
        "expected_official": False,
        "expected_brand": None,
        "why_tricky": "No menciona Sony, debería ser third-party"
    },
    {
        "title": "USB-C cable for MacBook Pro and iPad",
        "expected_official": False,
        "expected_brand": None,
        "why_tricky": "No menciona Apple, debería ser third-party"
    },
    {
        "title": "Apple MagSafe Battery Pack",
        "expected_official": True,
        "expected_brand": "apple",
        "why_tricky": "Es una 'Battery Pack' (accesorio) pero oficial Apple"
    },
    {
        "title": "Meta Quest 3 Elite Strap with Battery",
        "expected_official": True,
        "expected_brand": "meta",
        "why_tricky": "Tiene 'Strap' y 'Battery' (accesorios) pero es oficial Meta"
    },
    {
        "title": "Logitech MX Master 3S Wireless Mouse for Mac and iPad",
        "expected_official": True,
        "expected_brand": "logitech",
        "why_tricky": "Dice 'for Mac and iPad' pero ES producto oficial Logitech"
    },
    {
        "title": "Protective case designed for Apple iPhone 15 Pro Max",
        "expected_official": False,
        "expected_brand": None,
        "why_tricky": "Tiene 'Apple' pero NO al inicio, es third-party"
    },
    {
        "title": "Premium charging dock compatible with Sony PS5 DualSense",
        "expected_official": False,
        "expected_brand": None,
        "why_tricky": "Menciona Sony pero NO al inicio, es third-party"
    },
    {
        "title": "Apple Smart Folio for iPad Pro 13-inch",
        "expected_official": True,
        "expected_brand": "apple",
        "why_tricky": "Es una 'Folio' (case) con 'for' pero oficial Apple"
    }
]

print(f"📝 Ejecutando {len(stress_cases)} tests de estrés...\n")

passed = 0
failed = 0
false_positives = []  # CRÍTICO: productos oficiales marcados como third-party
false_negatives = []  # Third-party marcados como oficiales (menos crítico)

for i, test in enumerate(stress_cases, 1):
    title = test["title"]
    expected_official = test["expected_official"]
    expected_brand = test["expected_brand"]
    why_tricky = test["why_tricky"]

    # Detectar con IA
    ai_result = filter_obj._is_official_product_ai(title)

    is_official = ai_result["is_official"]
    detected_brand = ai_result["brand"]
    reasoning = ai_result["reasoning"]

    # Verificar resultado
    brand_match = (detected_brand == expected_brand if expected_brand else detected_brand is None)
    is_correct = (is_official == expected_official) and brand_match

    # Identificar tipo de error
    error_type = ""
    if not is_correct:
        if expected_official and not is_official:
            error_type = "🚨 FALSO POSITIVO (CRÍTICO)"
            false_positives.append(title)
        elif not expected_official and is_official:
            error_type = "⚠️  FALSO NEGATIVO"
            false_negatives.append(title)

    status = "✅" if is_correct else f"❌ {error_type}"

    if is_correct:
        passed += 1
    else:
        failed += 1

    print(f"{i}. {title}")
    print(f"   🎯 Caso difícil: {why_tricky}")
    print(f"   {status} IA: {'OFICIAL' if is_official else 'THIRD-PARTY'} - {detected_brand or 'N/A'}")
    if not is_correct:
        print(f"      Esperado: {'OFICIAL' if expected_official else 'THIRD-PARTY'} - {expected_brand or 'N/A'}")
        print(f"      Razón IA: {reasoning}")
    print()

print("=" * 80)
print("📊 RESUMEN DEL STRESS TEST")
print("=" * 80)
print()
print(f"✅ Tests pasados: {passed}/{len(stress_cases)}")
print(f"❌ Tests fallidos: {failed}/{len(stress_cases)}")
print()

if len(false_positives) > 0:
    print(f"🚨 FALSOS POSITIVOS (CRÍTICO): {len(false_positives)}")
    print("   Estos productos oficiales fueron marcados como third-party:")
    for fp in false_positives:
        print(f"   • {fp}")
    print()

if len(false_negatives) > 0:
    print(f"⚠️  FALSOS NEGATIVOS: {len(false_negatives)}")
    print("   Estos third-party fueron marcados como oficiales (menos crítico):")
    for fn in false_negatives:
        print(f"   • {fn}")
    print()

if failed == 0:
    print("🎉 PERFECTO! La IA pasó todos los casos extremos!")
    print("   Sistema listo para producción sin riesgo de perder imágenes buenas.")
else:
    print(f"⚠️  {failed} casos fallidos - REVISAR antes de usar en producción")
    if len(false_positives) > 0:
        print("   🚨 HAY FALSOS POSITIVOS - Esto podría eliminar fotos buenas!")

print()
print("=" * 80)
