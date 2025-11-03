#!/usr/bin/env python3
"""Fix TODOS los 7 ASINs y publicar"""

import sys
from pathlib import Path

# Auto-activar venv
if sys.prefix == sys.base_prefix:
    vpy = Path(__file__).parent / "venv" / "bin" / "python"
    if vpy.exists():
        import os
        os.execv(str(vpy), [str(vpy)] + sys.argv)

import json
import re
import time
from dotenv import load_dotenv
from src.unified_transformer import transform_amazon_to_ml_unified
from src.mainglobal import publish_item

load_dotenv(override=True)

def extract_gtins_from_json(amazon_json):
    """Extraer TODOS los GTINs del JSON de Amazon"""
    text = json.dumps(amazon_json)
    gtins = re.findall(r'\b\d{12,14}\b', text)

    # Filtrar y validar
    valid_gtins = []
    for g in set(gtins):
        g = g.lstrip('0')  # Remover ceros iniciales
        if 12 <= len(g) <= 14:
            valid_gtins.append(g)

    return list(set(valid_gtins))

# ASINs a arreglar
asins_to_fix = [
    ('B0CYM126TT', 'CBT1157'),   # LEGO - con GTIN
    ('B0DRW8G3WK', 'CBT1157'),   # LEGO - con GTIN
    ('B092RCLKHN', None),         # Garmin - buscar categoría sin BRAND
    ('B0CLC6NBBX', None),         # Picun - buscar categoría sin BRAND
    ('B0BXSLRQH7', None),         # Golden Hour - buscar categoría sin BRAND
    ('B0CHLBDJYP', 'CBT413467'), # Leather care
    ('B0DRW69H11', 'CBT455425')  # Airfryer
]

print(f"\n{'='*70}")
print(f"🔧 REGENERANDO Y PUBLICANDO 7 ASINS")
print(f"{'='*70}\n")

results = {'published': [], 'failed': []}

for asin, force_category in asins_to_fix:
    print(f"\n{'='*70}")
    print(f"🔄 {asin}")
    print(f"{'='*70}\n")

    # Leer JSON de Amazon
    amazon_json_path = Path(f"storage/asins_json/{asin}.json")
    if not amazon_json_path.exists():
        print(f"❌ No existe {amazon_json_path}")
        results['failed'].append(asin)
        continue

    with open(amazon_json_path) as f:
        amazon_json = json.load(f)

    # Extraer GTINs
    gtins = extract_gtins_from_json(amazon_json)
    print(f"📋 GTINs extraídos: {gtins}")

    # Regenerar con unified transformer
    print(f"🤖 Regenerando...")
    try:
        unified_result = transform_amazon_to_ml_unified(
            amazon_json,
            target_category=force_category
        )

        if not unified_result:
            print(f"❌ Transformación falló")
            results['failed'].append(asin)
            continue

        # Construir mini_ml con GTINs
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
            "gtins": gtins,  # ← GTINs extraídos del JSON
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
        print(f"   GTINs: {len(gtins)}")

        # Publicar inmediatamente
        print(f"\n🚀 Publicando...")
        result = publish_item(mini_ml)

        if result:
            item_id = result.get("item_id") or result.get("id")
            if item_id:
                site_items = result.get("site_items", [])
                success = [s for s in site_items if s.get("item_id")]
                failed = [s for s in site_items if s.get("error")]
                print(f"✅ PUBLICADO: {item_id}")
                print(f"   → {len(success)} países OK, {len(failed)} errores")
                results['published'].append(asin)
            else:
                site_items = result.get("site_items", [])
                success = [s for s in site_items if s.get("item_id")]
                if success:
                    print(f"⚠️ Publicado parcialmente: {len(success)} países")
                    results['published'].append(asin)
                else:
                    print(f"❌ Sin item_id")
                    results['failed'].append(asin)
        else:
            print(f"❌ Validación bloqueó o error")
            results['failed'].append(asin)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        results['failed'].append(asin)

    time.sleep(3)

# REPORTE
print(f"\n{'='*70}")
print(f"📊 REPORTE FINAL")
print(f"{'='*70}")
print(f"✅ Publicados: {len(results['published'])}/7")
print(f"❌ Fallaron: {len(results['failed'])}/7")

if results['published']:
    print(f"\n✅ Exitosos: {', '.join(results['published'])}")
if results['failed']:
    print(f"\n❌ Fallidos: {', '.join(results['failed'])}")

# Total ahora
total_published = 7 + len(results['published'])  # 7 previos + nuevos
print(f"\n🎯 TOTAL PIPELINE: {total_published}/14 ASINs publicados")
print(f"{'='*70}\n")
