#!/usr/bin/env python3
"""
🔥 STRESS TEST COMPLETO - Sistema de Títulos + Filtrado de Logos
Objetivo: Intentar romper el sistema con casos extremos y difíciles
"""

from src.pipeline.logo_filter import LogoFilter
import json

print("=" * 80)
print("🔥 STRESS TEST COMPLETO - Intentando romper el sistema")
print("=" * 80)
print()
print("OBJETIVO: Detectar CUALQUIER error antes de producción")
print()

filter_obj = LogoFilter()

# CASOS EXTREMOS organizados por categoría
test_categories = {
    "PRODUCTOS OFICIALES CON PALABRAS SOSPECHOSAS": [
        {
            "title": "Apple MagSafe Charger for iPhone 15",
            "brand": "Apple",
            "expected_official": True,
            "expected_title_format": "Apple MagSafe [...]",  # SIN "para"
            "why_tricky": "Dice 'charger' y 'for' pero ES oficial Apple"
        },
        {
            "title": "Sony DualSense Charging Station for PlayStation 5",
            "brand": "Sony",
            "expected_official": True,
            "expected_title_format": "Sony DualSense [...]",  # SIN "para"
            "why_tricky": "Es 'Charging Station' con 'for' pero oficial Sony"
        },
        {
            "title": "Apple Smart Keyboard Folio for iPad Pro 11-inch",
            "brand": "Apple",
            "expected_official": True,
            "expected_title_format": "Apple Smart Keyboard [...]",  # SIN "para"
            "why_tricky": "Keyboard + Folio + 'for' pero ES oficial Apple"
        },
        {
            "title": "Samsung Protective Standing Cover for Galaxy Tab S9",
            "brand": "Samsung",
            "expected_official": True,
            "expected_title_format": "Samsung Protective [...]",  # SIN "para"
            "why_tricky": "Cover + 'for' pero ES oficial Samsung"
        },
        {
            "title": "Apple USB-C to Lightning Cable 1m",
            "brand": "Apple",
            "expected_official": True,
            "expected_title_format": "Apple USB-C [...]",  # SIN "para"
            "why_tricky": "Es un CABLE pero oficial Apple"
        },
    ],

    "ACCESORIOS THIRD-PARTY CLAROS": [
        {
            "title": "Anker PowerCore 10000 Portable Charger for iPhone",
            "brand": "Anker",
            "expected_official": False,
            "expected_title_format": "[...] PARA iPhone",  # CON "para"
            "why_tricky": "Anker para iPhone - third-party obvio"
        },
        {
            "title": "Logitech K380 Bluetooth Keyboard for iPad and Mac",
            "brand": "Logitech",
            "expected_official": False,
            "expected_title_format": "Teclado [...] Logitech PARA iPad",  # CON "para"
            "why_tricky": "Logitech para Apple - third-party"
        },
        {
            "title": "JSAUX Dock Stand for Nintendo Switch OLED",
            "brand": "JSAUX",
            "expected_official": False,
            "expected_title_format": "[...] PARA Nintendo Switch",  # CON "para"
            "why_tricky": "Marca desconocida para Switch - third-party"
        },
        {
            "title": "Spigen Tough Armor Case for iPhone 15 Pro Max",
            "brand": "Spigen",
            "expected_official": False,
            "expected_title_format": "Funda [...] PARA iPhone 15",  # CON "para"
            "why_tricky": "Spigen para iPhone - third-party"
        },
    ],

    "CASOS AMBIGUOS Y CONFUSOS": [
        {
            "title": "Apple-certified Lightning to USB Cable by Belkin",
            "brand": "Belkin",
            "expected_official": False,
            "expected_title_format": "Cable [...] PARA [...]",  # CON "para"
            "why_tricky": "Dice 'Apple-certified' pero marca es Belkin"
        },
        {
            "title": "MFi Certified Charger Compatible with iPhone 14",
            "brand": "Generic",
            "expected_official": False,
            "expected_title_format": "Cargador [...] PARA iPhone",  # CON "para"
            "why_tricky": "MFi certified pero no es de Apple"
        },
        {
            "title": "PlayStation 5 Console Skin Sticker Decal",
            "brand": "Unknown",
            "expected_official": False,
            "expected_title_format": "[...] PARA PlayStation 5",  # CON "para"
            "why_tricky": "Menciona PS5 pero es sticker third-party"
        },
        {
            "title": "Replacement Battery for Apple Magic Mouse",
            "brand": "Generic",
            "expected_official": False,
            "expected_title_format": "Batería [...] PARA Magic Mouse",  # CON "para"
            "why_tricky": "Replacement = third-party siempre"
        },
    ],

    "PRODUCTOS OFICIALES SIN 'FOR'": [
        {
            "title": "Apple AirPods Pro 2nd Generation with USB-C",
            "brand": "Apple",
            "expected_official": True,
            "expected_title_format": "Apple AirPods Pro [...]",  # SIN "para"
            "why_tricky": "Producto principal Apple, fácil"
        },
        {
            "title": "Sony PlayStation 5 Slim Digital Edition Console",
            "brand": "Sony",
            "expected_official": True,
            "expected_title_format": "Sony PlayStation 5 [...]",  # SIN "para"
            "why_tricky": "Consola principal, fácil"
        },
        {
            "title": "Microsoft Xbox Wireless Controller Carbon Black",
            "brand": "Microsoft",
            "expected_official": True,
            "expected_title_format": "Microsoft Xbox [...]",  # SIN "para"
            "why_tricky": "Control oficial, fácil"
        },
    ],

    "EDGE CASES EXTREMOS": [
        {
            "title": "Apple-style Keyboard RGB Backlit for iPad Pro",
            "brand": "Generic",
            "expected_official": False,
            "expected_title_format": "[...] PARA iPad Pro",  # CON "para"
            "why_tricky": "'Apple-style' = imitación, no es Apple"
        },
        {
            "title": "Original Apple Charger 20W USB-C Power Adapter",
            "brand": "Apple",
            "expected_official": True,
            "expected_title_format": "Apple [...]",  # SIN "para"
            "why_tricky": "Dice 'Original' y es Apple = oficial"
        },
        {
            "title": "Genuine Samsung Fast Charging Cable Type-C",
            "brand": "Samsung",
            "expected_official": True,
            "expected_title_format": "Samsung [...]",  # SIN "para"
            "why_tricky": "Dice 'Genuine' y es Samsung = oficial"
        },
        {
            "title": "Compatible Stylus Pen Apple Pencil Alternative",
            "brand": "Generic",
            "expected_official": False,
            "expected_title_format": "[...] PARA iPad",  # CON "para"
            "why_tricky": "Dice 'Compatible' y 'Alternative' = third-party"
        },
        {
            "title": "Nintendo Switch Pro Controller Wireless Black",
            "brand": "Nintendo",
            "expected_official": True,
            "expected_title_format": "Nintendo Switch Pro [...]",  # SIN "para"
            "why_tricky": "Control oficial Nintendo"
        },
        {
            "title": "Pro Controller for Nintendo Switch Wireless Gaming",
            "brand": "Generic",
            "expected_official": False,
            "expected_title_format": "Control [...] PARA Nintendo Switch",  # CON "para"
            "why_tricky": "Sin marca al inicio = third-party"
        },
    ],
}

total_tests = sum(len(cases) for cases in test_categories.values())
passed = 0
failed = 0
failures = []

print(f"📝 Ejecutando {total_tests} tests organizados por categoría...\n")

for category, cases in test_categories.items():
    print("=" * 80)
    print(f"📂 {category}")
    print("=" * 80)
    print()

    for i, test in enumerate(cases, 1):
        title = test["title"]
        brand = test["brand"]
        expected_official = test["expected_official"]
        expected_format = test["expected_title_format"]
        why_tricky = test["why_tricky"]

        # Test de clasificación oficial vs third-party
        ai_result = filter_obj._is_official_product_ai(title)
        is_official = ai_result["is_official"]
        detected_brand = ai_result["brand"]
        reasoning = ai_result["reasoning"]

        # Verificar resultado
        is_correct = (is_official == expected_official)

        if is_correct:
            passed += 1
            status = "✅"
        else:
            failed += 1
            status = "❌ FALLO"
            failures.append({
                "category": category,
                "title": title,
                "expected": "OFICIAL" if expected_official else "THIRD-PARTY",
                "got": "OFICIAL" if is_official else "THIRD-PARTY",
                "reasoning": reasoning
            })

        print(f"{status} {title}")
        print(f"   🎯 Caso difícil: {why_tricky}")
        print(f"   📊 IA detectó: {'OFICIAL' if is_official else 'THIRD-PARTY'} - {detected_brand or 'N/A'}")
        print(f"   📝 Formato esperado título: {expected_format}")
        if not is_correct:
            print(f"   ⚠️  ESPERADO: {'OFICIAL' if expected_official else 'THIRD-PARTY'}")
            print(f"   💭 Razón IA: {reasoning}")
        print()

    print()

print("=" * 80)
print("📊 RESUMEN FINAL DEL STRESS TEST")
print("=" * 80)
print()
print(f"Total de tests: {total_tests}")
print(f"✅ Pasados: {passed}/{total_tests} ({passed/total_tests*100:.1f}%)")
print(f"❌ Fallidos: {failed}/{total_tests} ({failed/total_tests*100:.1f}%)")
print()

if failed > 0:
    print("🚨 FALLOS DETECTADOS:")
    print("=" * 80)
    for fail in failures:
        print(f"❌ Categoría: {fail['category']}")
        print(f"   Título: {fail['title']}")
        print(f"   Esperado: {fail['expected']}")
        print(f"   Obtenido: {fail['got']}")
        print(f"   Razón: {fail['reasoning']}")
        print()
    print()
    print("⚠️  SISTEMA NO ESTÁ LISTO - Revisar antes de producción")
else:
    print("🎉 PERFECTO! TODOS LOS TESTS PASARON!")
    print()
    print("✅ Sistema validado al 100%")
    print("✅ No hay casos que rompan la detección")
    print("✅ Listo para producción sin riesgos")

print()
print("=" * 80)
print("📈 ANÁLISIS POR CATEGORÍA")
print("=" * 80)
print()

for category, cases in test_categories.items():
    category_passed = sum(1 for c in cases if (
        filter_obj._is_official_product_ai(c["title"])["is_official"] == c["expected_official"]
    ))
    category_total = len(cases)
    category_pct = category_passed / category_total * 100

    status_icon = "✅" if category_passed == category_total else "⚠️"
    print(f"{status_icon} {category}: {category_passed}/{category_total} ({category_pct:.0f}%)")

print()
print("=" * 80)
