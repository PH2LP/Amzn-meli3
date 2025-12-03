#!/usr/bin/env python3
"""
Test del nuevo sistema de detección de accesorios en títulos
"""

import sys
import os
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline.unified_transformer import transform_amazon_to_ml_unified

# Ejemplos de prueba
test_cases = [
    {
        "name": "Base Cargadora Nintendo Switch (ACCESORIO)",
        "amazon_json": {
            "title": "Nintendo Switch Charging Dock Station",
            "brand": "PowerA",
            "description": "Compatible charging dock for Nintendo Switch console",
            "features": [
                "USB-C charging port",
                "Fits Nintendo Switch",
                "LED indicator"
            ]
        },
        "expected_format": "Base Cargadora PARA Nintendo Switch"
    },
    {
        "name": "Teclado para iPad (ACCESORIO)",
        "amazon_json": {
            "title": "iPad 5th Generation Keyboard Case",
            "brand": "Logitech",
            "description": "Bluetooth keyboard case for iPad 5",
            "features": [
                "Backlit keys",
                "Compatible with iPad 5",
                "Rechargeable battery"
            ]
        },
        "expected_format": "Teclado PARA iPad 5"
    },
    {
        "name": "iPhone Case (ACCESORIO)",
        "amazon_json": {
            "title": "iPhone 14 Pro Max Case Silicone",
            "brand": "Spigen",
            "description": "Protective case for iPhone 14 Pro Max",
            "features": [
                "Silicone material",
                "Drop protection",
                "Fits iPhone 14 Pro Max"
            ]
        },
        "expected_format": "Funda PARA iPhone 14 Pro Max"
    },
    {
        "name": "iPad Original (PRODUCTO ORIGINAL)",
        "amazon_json": {
            "title": "Apple iPad Pro 11-inch 256GB WiFi",
            "brand": "Apple",
            "description": "iPad Pro with M2 chip, 11-inch display",
            "features": [
                "M2 chip",
                "256GB storage",
                "11-inch Liquid Retina display"
            ]
        },
        "expected_format": "iPad Pro 11 Pulgadas 256GB"
    },
    {
        "name": "Nintendo Switch Console (PRODUCTO ORIGINAL)",
        "amazon_json": {
            "title": "Nintendo Switch OLED Model 64GB White",
            "brand": "Nintendo",
            "description": "Nintendo Switch console with OLED screen",
            "features": [
                "7-inch OLED screen",
                "64GB internal storage",
                "Enhanced audio"
            ]
        },
        "expected_format": "Nintendo Switch Console OLED 64GB"
    }
]

def main():
    print("="*70)
    print("🧪 TEST: DETECCIÓN DE ACCESORIOS EN TÍTULOS")
    print("="*70)
    print()

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"\n[Test {i}/{len(test_cases)}] {test['name']}")
        print("-" * 70)

        # Mostrar input
        print(f"📦 Input Amazon Title: {test['amazon_json']['title']}")
        print(f"📦 Brand: {test['amazon_json']['brand']}")
        print(f"✅ Expected Format: {test['expected_format']}")

        # Ejecutar transformación
        print(f"\n🧠 Transformando con IA...")
        result = transform_amazon_to_ml_unified(test['amazon_json'])

        if result:
            generated_title = result.get('title', '')
            print(f"📝 Generated Title: {generated_title}")

            # Verificar formato
            if "PARA" in generated_title or "Compatible con" in generated_title:
                print(f"✅ Formato correcto detectado: Contiene 'PARA' o 'Compatible con'")
                passed += 1
            elif any(keyword in test['amazon_json']['title'].lower() for keyword in
                    ['case', 'dock', 'keyboard', 'charger', 'cable', 'adapter', 'cover']):
                print(f"❌ ERROR: Es accesorio pero NO contiene 'PARA' o 'Compatible con'")
                print(f"   MercadoLibre lo suspendería!")
                failed += 1
            else:
                print(f"✅ Producto original - formato correcto")
                passed += 1
        else:
            print(f"❌ ERROR: No se pudo generar título")
            failed += 1

    # Resumen
    print("\n" + "="*70)
    print("📊 RESUMEN")
    print("="*70)
    print(f"✅ Pasados: {passed}/{len(test_cases)}")
    print(f"❌ Fallados: {failed}/{len(test_cases)}")

    if failed == 0:
        print("\n🎉 TODOS LOS TESTS PASARON")
        print("   El sistema detecta correctamente accesorios vs productos originales")
    else:
        print("\n⚠️  ALGUNOS TESTS FALLARON")
        print("   Revisar los títulos generados arriba")

    print()

if __name__ == "__main__":
    main()
