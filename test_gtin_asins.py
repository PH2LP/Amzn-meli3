#!/usr/bin/env python3
"""
Test GTIN fix con los ASINs que fallaron
"""
import sys
from main2 import Pipeline, Config

# ASINs que fallaron por GTIN duplicado
failed_asins = [
    "B081SRSNWW",  # 10 intentos fallidos - Dr.Jart+ mask
    "B0D3H3NKBN",  # 16 intentos fallidos - LONDONTOWN nail polish
]

print("🧪 Testing GTIN fix con ASINs que tenían force_no_gtin=True")
print("=" * 70)
print(f"ASINs a probar: {', '.join(failed_asins)}")
print("=" * 70)
print()

# Setup config
Config.setup_directories()

# Crear pipeline y ejecutar
pipeline = Pipeline(Config)
result = pipeline.run(failed_asins)

print("\n" + "=" * 70)
print("📊 RESULTADOS DEL TEST")
print("=" * 70)
print(f"✅ Exitosos: {len(result.get('results', {}).get('success', []))}")
print(f"❌ Fallidos: {len(result.get('results', {}).get('failed', []))}")
print()

if result.get('results', {}).get('success'):
    print("✅ ASINs publicados exitosamente:")
    for asin in result['results']['success']:
        print(f"   • {asin}")

if result.get('results', {}).get('failed'):
    print("\n❌ ASINs que aún fallan:")
    for asin in result['results']['failed']:
        print(f"   • {asin}")

print("\n💡 Si los ASINs se publicaron exitosamente, el fix de GTIN funcionó!")
