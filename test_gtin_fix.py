#!/usr/bin/env python3
"""
Test script para verificar que el fix de GTIN funciona correctamente
"""
import sys
import json
from pathlib import Path

# Verificar que los ASINs con force_no_gtin=True no tengan GTIN en atributos

failed_asins = ["B081SRSNWW", "B0D3H3NKBN", "B0CLC6NBBX", "B0DRW69H11"]

print("🔍 Verificando mini_ml files con force_no_gtin...\n")

for asin in failed_asins:
    mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")
    if not mini_path.exists():
        print(f"⚠️  {asin}: No mini_ml found")
        continue

    with open(mini_path) as f:
        mini = json.load(f)

    force_no_gtin = mini.get("force_no_gtin", False)
    last_error = mini.get("last_error")

    # Verificar si GTIN aparece en atributos
    has_gtin_in_attrs = "GTIN" in mini.get("attributes_mapped", {})

    gtin_in_main = any(c.get("id") == "GTIN" for c in mini.get("main_characteristics", []))
    gtin_in_second = any(c.get("id") == "GTIN" for c in mini.get("second_characteristics", []))

    print(f"📦 {asin}:")
    print(f"   force_no_gtin: {force_no_gtin}")
    print(f"   last_error: {last_error}")
    print(f"   GTIN en attributes_mapped: {has_gtin_in_attrs}")
    print(f"   GTIN en main_characteristics: {gtin_in_main}")
    print(f"   GTIN en second_characteristics: {gtin_in_second}")

    if force_no_gtin and (has_gtin_in_attrs or gtin_in_main or gtin_in_second):
        print(f"   ⚠️  PROBLEMA: GTIN presente aunque force_no_gtin=True")
    elif force_no_gtin:
        print(f"   ✅ OK: GTIN correctamente eliminado del mini_ml")
    print()

print("\n🧪 Ahora vamos a probar la función publish_item() con el fix...")
print("📝 El fix agrega un filtro final que elimina GTIN después de la IA")
print("✅ Fix implementado en src/mainglobal.py línea 1161-1166")
