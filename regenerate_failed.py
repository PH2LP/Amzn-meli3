#!/usr/bin/env python3
"""Regenerar ASINs que necesitan categorías/imágenes correctas"""

import sys
from pathlib import Path

# Auto-activar venv
if sys.prefix == sys.base_prefix:
    vpy = Path(__file__).parent / "venv" / "bin" / "python"
    if vpy.exists():
        import os
        os.execv(str(vpy), [str(vpy)] + sys.argv)

import json
from dotenv import load_dotenv
from src.unified_transformer import transform_amazon_to_ml_unified

load_dotenv(override=True)

# ASINs que necesitan regeneración
asins_to_regen = [
    "B0CYM126TT",  # Collage + promotional overlay
    "B0DRW8G3WK",  # Collage
    "B0CHLBDJYP",  # Categoría incorrecta
    "B0BXSLRQH7"   # Categoría CBT12345 inválida
]

print(f"\n{'='*70}")
print(f"🔄 REGENERANDO {len(asins_to_regen)} ASINS")
print(f"{'='*70}\n")

for asin in asins_to_regen:
    print(f"\n{'='*70}")
    print(f"🔄 {asin}")
    print(f"{'='*70}\n")

    # Leer JSON de Amazon
    amazon_json_path = Path(f"storage/asins_json/{asin}.json")

    if not amazon_json_path.exists():
        print(f"❌ No existe {amazon_json_path}")
        continue

    with open(amazon_json_path, "r") as f:
        amazon_json = json.load(f)

    # Regenerar con unified transformer
    print(f"🤖 Regenerando con IA...")
    try:
        unified_result = transform_amazon_to_ml_unified(amazon_json)

        if not unified_result:
            print(f"❌ Failed")
            continue

        # Construir mini_ml
        mini_ml = {
            "asin": asin,
            "brand": unified_result.get("brand", ""),
            "model": unified_result.get("model", ""),
            "category_id": unified_result["category_id"],
            "category_name": unified_result["category_name"],
            "title_ai": unified_result["title"],
            "description_ai": unified_result["description"],
            "package": unified_result["dimensions"],
            "price": unified_result["price"],
            "gtins": unified_result.get("gtins", []),
            "images": unified_result["images"],
            "attributes_mapped": {
                attr["id"]: {"value_name": attr["value_name"]}
                for attr in unified_result.get("attributes", [])
            }
        }

        # Guardar
        mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")
        with open(mini_path, "w") as f:
            json.dump(mini_ml, f, indent=2, ensure_ascii=False)

        print(f"✅ Regenerado: {unified_result['category_name']}")
        print(f"   Categoría: {unified_result['category_id']}")
        print(f"   Título: {unified_result['title'][:60]}")
        print(f"💾 Guardado: {mini_path}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

print(f"\n{'='*70}")
print(f"✅ REGENERACIÓN COMPLETA")
print(f"{'='*70}\n")
