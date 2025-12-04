#!/usr/bin/env python3
"""
Test de lógica de whitelist basada en título
"""

from src.pipeline.logo_filter import LogoFilter

print("=" * 80)
print("🧪 TEST: Whitelist de logos basada en título del producto")
print("=" * 80)
print()

filter_obj = LogoFilter()

# Test cases
test_cases = [
    {
        "title": "Apple Silicone Case for iPad Pro 13-inch",
        "description": "❌ THIRD-PARTY (tiene 'case for') - Logo Apple PROHIBIDO",
        "expected": []
    },
    {
        "title": "Apple iPad Pro 13-inch M4 Chip",
        "description": "✅ OFICIAL Apple (sin 'for/para') - Logo Apple PERMITIDO",
        "expected": ["apple"]
    },
    {
        "title": "Funda genérica para iPad Pro 13 pulgadas",
        "description": "❌ THIRD-PARTY (tiene 'funda para') - Logo Apple PROHIBIDO",
        "expected": []
    },
    {
        "title": "Sony PlayStation 5 DualSense Wireless Controller",
        "description": "✅ OFICIAL Sony - Logos PlayStation/Sony PERMITIDOS",
        "expected": ["sony"]
    },
    {
        "title": "Base de carga para control PS5",
        "description": "❌ THIRD-PARTY (tiene 'base para') - Logo PlayStation PROHIBIDO",
        "expected": []
    },
    {
        "title": "Teclado mecánico RGB para gaming",
        "description": "❌ Genérico (tiene 'para') - Todos los logos PROHIBIDOS",
        "expected": []
    },
    {
        "title": "Razer DeathAdder V3 Gaming Mouse",
        "description": "✅ OFICIAL Razer - Logo Razer PERMITIDO",
        "expected": ["razer"]
    },
    {
        "title": "Cable USB-C compatible con MacBook",
        "description": "❌ THIRD-PARTY (tiene 'compatible') - Logo Apple PROHIBIDO",
        "expected": []
    },
    {
        "title": "Microsoft Xbox Series X Console",
        "description": "✅ OFICIAL Microsoft - Logo Xbox PERMITIDO",
        "expected": ["microsoft"]
    },
    {
        "title": "Dock charging station for Nintendo Switch",
        "description": "❌ THIRD-PARTY (tiene 'dock for') - Logo Nintendo PROHIBIDO",
        "expected": []
    }
]

passed = 0
failed = 0

for i, test in enumerate(test_cases, 1):
    title = test["title"]
    desc = test["description"]
    expected = test["expected"]

    allowed_brands = filter_obj._extract_allowed_brands(title)

    # Verificar si coincide con lo esperado
    is_correct = allowed_brands == expected
    status = "✅" if is_correct else "❌ FAILED"

    if is_correct:
        passed += 1
    else:
        failed += 1

    print(f"{i}. {title}")
    print(f"   📝 {desc}")
    print(f"   {status} Resultado: {', '.join(allowed_brands) if allowed_brands else 'Ninguna'}")
    if not is_correct:
        print(f"      (Esperado: {', '.join(expected) if expected else 'Ninguna'})")
    print()

print("=" * 80)
print("📊 RESUMEN DE RESULTADOS")
print("=" * 80)
print()
print(f"✅ Tests pasados: {passed}/{len(test_cases)}")
print(f"❌ Tests fallidos: {failed}/{len(test_cases)}")
print()

if failed == 0:
    print("🎉 TODOS LOS TESTS PASARON - Lógica correcta!")
else:
    print("⚠️  Hay tests fallidos - revisar lógica")

print()
print("=" * 80)
print("📋 REGLAS DE NEGOCIO")
print("=" * 80)
print()
print("✅ PERMITE logos si:")
print("   - Producto OFICIAL de la marca (ej: 'Sony PlayStation 5')")
print("   - NO tiene palabras de compatibilidad (for, para, compatible, case, dock, etc.)")
print()
print("❌ PROHIBE logos si:")
print("   - Producto third-party (tiene 'for', 'para', 'compatible', etc.)")
print("   - Es accesorio (case, funda, cable, dock, stand, adapter, etc.)")
print()
print("Ejemplos correctos:")
print("   ✅ 'Apple iPad Pro' → Logo Apple PERMITIDO")
print("   ❌ 'Case for iPad Pro' → Logo Apple PROHIBIDO")
print("   ✅ 'Sony PlayStation 5 Console' → Logo Sony PERMITIDO")
print("   ❌ 'Base para PS5' → Logo PlayStation PROHIBIDO")
print()
print("=" * 80)
