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
        "description": "Producto OFICIAL de Apple - Logo Apple PERMITIDO"
    },
    {
        "title": "Funda genérica para iPad Pro 13 pulgadas",
        "description": "Accesorio genérico - Logo Apple PROHIBIDO"
    },
    {
        "title": "Sony PlayStation 5 DualSense Wireless Controller",
        "description": "Control oficial Sony - Logos PlayStation/Sony PERMITIDOS"
    },
    {
        "title": "Base de carga para control PS5",
        "description": "Accesorio third-party - Logo PlayStation PERMITIDO (menciona PS5)"
    },
    {
        "title": "Teclado mecánico RGB para gaming",
        "description": "Genérico sin marca - Todos los logos PROHIBIDOS"
    },
    {
        "title": "Razer DeathAdder V3 Gaming Mouse",
        "description": "Mouse oficial Razer - Logo Razer PERMITIDO"
    },
    {
        "title": "Cable USB-C compatible con MacBook",
        "description": "Cable genérico - Logo Apple PROHIBIDO"
    }
]

for i, test in enumerate(test_cases, 1):
    title = test["title"]
    desc = test["description"]

    allowed_brands = filter_obj._extract_allowed_brands(title)

    print(f"{i}. {title}")
    print(f"   📝 {desc}")
    print(f"   ✅ Marcas permitidas: {', '.join(allowed_brands) if allowed_brands else 'Ninguna'}")
    print()

print("=" * 80)
print("📊 RESUMEN DE LÓGICA")
print("=" * 80)
print()
print("✅ Si el título menciona 'Apple' → Logo Apple PERMITIDO en fotos")
print("✅ Si el título menciona 'PS5' → Logo PlayStation PERMITIDO en fotos")
print("✅ Si el título menciona 'Xbox' → Logo Microsoft/Xbox PERMITIDO en fotos")
print()
print("❌ Si el título dice 'para iPad' (genérico) → Logo Apple PROHIBIDO")
print("❌ Si el título dice 'compatible con' → Logos de esa marca PROHIBIDOS")
print()
print("=" * 80)
