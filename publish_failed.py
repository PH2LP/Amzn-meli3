#!/usr/bin/env python3
"""Publicar solo los ASINs que fallaron"""

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
from dotenv import load_dotenv
from src.mainglobal import publish_item

load_dotenv(override=True)

# ASINs que fallaron en la última ejecución
failed_asins = [
    "B0DRW69H11",
    "B0D3H3NKBN",
    "B0CHLBDJYP",
    "B081SRSNWW"
    # Omitimos B0CLC6NBBX (requiere GTIN que no tenemos)
]

results = {"success": [], "failed": []}

for asin in failed_asins:
    mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")

    if not mini_path.exists():
        print(f"❌ No existe mini_ml para {asin}")
        results["failed"].append(asin)
        continue

    print(f"\n{'='*60}")
    print(f"📦 Publicando {asin}...")
    print('='*60)

    try:
        with open(mini_path, "r", encoding="utf-8") as f:
            mini_ml = json.load(f)

        result = publish_item(mini_ml)

        if result and result.get("item_id"):
            print(f"✅ Publicado: {result.get('item_id')}")
            results["success"].append(asin)
        else:
            print(f"⚠️ Sin item_id en respuesta")
            results["failed"].append(asin)

    except Exception as e:
        print(f"❌ Error: {e}")
        results["failed"].append(asin)

    # Rate limiting
    if asin != failed_asins[-1]:
        print("⏱️  Esperando 3 segundos...")
        time.sleep(3)

print(f"\n{'='*60}")
print("📊 REPORTE FINAL")
print('='*60)
print(f"✅ Publicados: {len(results['success'])}/{len(failed_asins)}")
print(f"❌ Fallidos: {len(results['failed'])}/{len(failed_asins)}")

if results["success"]:
    print(f"\n✅ Exitosos: {', '.join(results['success'])}")
if results["failed"]:
    print(f"\n❌ Fallidos: {', '.join(results['failed'])}")
print('='*60)
