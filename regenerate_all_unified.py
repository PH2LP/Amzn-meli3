#!/usr/bin/env python3
"""Regenerar TODOS los mini_ml con sistema unificado de IA"""

import sys
from pathlib import Path

# Auto-activar venv
if sys.prefix == sys.base_prefix:
    vpy = Path(__file__).parent / "venv" / "bin" / "python"
    if vpy.exists():
        import os
        os.execv(str(vpy), [str(vpy)] + sys.argv)

import json
import time
from src.unified_transformer import transform_amazon_to_ml_unified

# Leer ASINs
with open("resources/asins.txt", "r") as f:
    asins = [line.strip().upper() for line in f if line.strip() and not line.startswith("#")]

print(f"\n{'='*70}")
print(f"🔄 REGENERANDO {len(asins)} PRODUCTOS CON SISTEMA UNIFICADO")
print(f"{'='*70}\n")

results = {"success": [], "failed": []}

for i, asin in enumerate(asins, 1):
    amazon_path = Path(f"storage/asins_json/{asin}.json")

    if not amazon_path.exists():
        print(f"{i}. ❌ {asin}: No tiene JSON de Amazon")
        results["failed"].append(asin)
        continue

    print(f"\n{i}/{len(asins)}. {asin}")
    print("="*60)

    try:
        with open(amazon_path, "r", encoding="utf-8") as f:
            amazon_json = json.load(f)

        # Transformar con sistema unificado
        ml_data = transform_amazon_to_ml_unified(amazon_json)

        if not ml_data:
            print(f"❌ No se pudo transformar {asin}")
            results["failed"].append(asin)
            continue

        # Extraer ASIN del JSON de Amazon
        amazon_asin = asin
        if "summaries" in amazon_json and amazon_json["summaries"]:
            amazon_asin = amazon_json["summaries"][0].get("asin", asin)

        # Construir mini_ml compatible con el pipeline existente
        mini_ml = {
            "asin": amazon_asin,
            "brand": next((a["value_name"] for a in ml_data.get("attributes", []) if a["id"] == "BRAND"), ""),
            "model": next((a["value_name"] for a in ml_data.get("attributes", []) if a["id"] == "MODEL"), ""),
            "category_id": ml_data.get("category_id"),
            "category_name": ml_data.get("category_name"),
            "title_ai": ml_data.get("title"),
            "description_ai": ml_data.get("description"),
            "package": ml_data.get("dimensions", {}),
            "price": {
                "base_usd": ml_data.get("price", {}).get("base_usd", 0),
                "tax_usd": ml_data.get("price", {}).get("tax_usd", 0),
                "cost_usd": ml_data.get("price", {}).get("base_usd", 0),
                "markup_pct": 35,
                "net_proceeds_usd": ml_data.get("price", {}).get("base_usd", 0) * 1.35
            },
            "gtins": [a["value_name"] for a in ml_data.get("attributes", []) if a["id"] in ["GTIN", "UPC", "EAN"]],
            "images": ml_data.get("images", []),
            "attributes_mapped": {
                attr["id"]: {"value_name": attr["value_name"]}
                for attr in ml_data.get("attributes", [])
            }
        }

        # Guardar mini_ml
        mini_ml_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")
        with open(mini_ml_path, "w", encoding="utf-8") as f:
            json.dump(mini_ml, f, indent=2, ensure_ascii=False)

        print(f"✅ Mini_ML generado: {mini_ml_path}")
        results["success"].append(asin)

        # Rate limiting para no exceder límites de OpenAI
        if i < len(asins):
            print("⏱️  Esperando 3 segundos...")
            time.sleep(3)

    except Exception as e:
        print(f"❌ Error procesando {asin}: {e}")
        import traceback
        traceback.print_exc()
        results["failed"].append(asin)

print(f"\n{'='*70}")
print("📊 RESUMEN FINAL")
print(f"{'='*70}")
print(f"✅ Exitosos: {len(results['success'])}/{len(asins)}")
print(f"❌ Fallidos: {len(results['failed'])}/{len(asins)}")

if results["failed"]:
    print(f"\n⚠️  Fallidos: {', '.join(results['failed'])}")

print(f"{'='*70}\n")
