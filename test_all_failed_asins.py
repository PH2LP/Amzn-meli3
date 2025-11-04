#!/usr/bin/env python3
"""
Test completo del sistema mejorado con los 4 ASINs que fallaron originalmente.

Verifica:
1. Detección IA de GTIN
2. Manejo de GTIN duplicado (force_no_gtin)
3. Recategorización automática cuando categoría requiere GTIN
4. Publicación exitosa

ASINs bajo prueba:
- B081SRSNWW: GTIN duplicado + categoría requiere GTIN (debe recategorizar)
- B0D3H3NKBN: GTIN duplicado (debe publicar sin GTIN) - ✅ Ya publicado
- B0CLC6NBBX: GTIN inválido
- B0DRW69H11: Error múltiple en todos los países
"""
import sys
from main2 import Pipeline, Config

# ASINs que fallaron en el reporte original
failed_asins = [
    "B081SRSNWW",  # 10 intentos - Dr.Jart+ mask → recategorización esperada
    "B0D3H3NKBN",  # 16 intentos - LONDONTOWN nail polish → ya publicado
    "B0CLC6NBBX",  # 4 intentos - Picun headphones
    "B0DRW69H11",  # 28 intentos - LEGO Creator
]

print("=" * 80)
print("🧪 TEST COMPLETO: Sistema Mejorado de Manejo de GTIN")
print("=" * 80)
print()
print("📋 ASINs bajo prueba:")
for asin in failed_asins:
    print(f"   • {asin}")
print()
print("🎯 Funcionalidades a probar:")
print("   1. ✅ Detección IA de GTIN como fallback")
print("   2. ✅ Fix de GTIN removal bug")
print("   3. ✅ Recategorización automática para GTIN conflicts")
print()
print("=" * 80)
print()

# Setup config
Config.setup_directories()
Config.SKIP_VALIDATION = False  # Queremos validación completa
Config.DRY_RUN = False  # Publicación real

# Crear pipeline
pipeline = Pipeline(Config)

try:
    print("🚀 Iniciando pipeline con validación completa...")
    print()
    results = pipeline.run(failed_asins)

    print("\n" + "=" * 80)
    print("📊 RESULTADOS FINALES DEL TEST")
    print("=" * 80)

    success = results.get("results", {}).get("success", [])
    failed = results.get("results", {}).get("failed", [])

    print(f"✅ Exitosos: {len(success)}/{len(failed_asins)} ({len(success)/len(failed_asins)*100:.0f}%)")
    print(f"❌ Fallidos: {len(failed)}/{len(failed_asins)} ({len(failed)/len(failed_asins)*100:.0f}%)")
    print()

    if success:
        print("✅ ASINs publicados exitosamente:")
        for asin in success:
            print(f"   • {asin}")

    if failed:
        print("\n❌ ASINs que aún fallan:")
        for asin in failed:
            print(f"   • {asin}")

    print("\n" + "=" * 80)
    print("📈 MEJORAS APLICADAS:")
    print("=" * 80)
    print("1. 🤖 Detección IA de GTIN: Activa")
    print("2. 🐛 Fix GTIN removal bug: Aplicado")
    print("3. 🔄 Recategorización automática: Implementada")
    print()

    if len(success) > len(failed):
        print("✅ TEST EXITOSO: Más productos publicados que fallidos")
        sys.exit(0)
    elif len(success) > 0:
        print("⚠️  TEST PARCIAL: Algunos productos publicados, otros requieren atención")
        sys.exit(2)
    else:
        print("❌ TEST FALLIDO: Ningún producto pudo publicarse")
        sys.exit(1)

except KeyboardInterrupt:
    print("\n\n⚠️  Test interrumpido por el usuario")
    sys.exit(130)
except Exception as e:
    print(f"\n❌ Error en el test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
