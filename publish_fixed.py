#!/usr/bin/env python3
"""Publicar los 5 ASINs arreglados"""

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

# ASINs arreglados
fixed_asins = [
    "B0D1Z99167",  # UNIT_VOLUME arreglado
    "B0CYM126TT",  # Regenerado
    "B0DRW8G3WK",  # Regenerado
    "B0CHLBDJYP",  # Regenerado
    "B0BXSLRQH7"   # Regenerado
]

print(f"\n{'='*70}")
print(f"🚀 PUBLICANDO {len(fixed_asins)} ASINS ARREGLADOS")
print(f"{'='*70}\n")

results = {"success": [], "failed": []}

for i, asin in enumerate(fixed_asins, 1):
    print(f"\n{'='*70}")
    print(f"{i}/{len(fixed_asins)}. {asin}")
    print(f"{'='*70}\n")

    mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")

    if not mini_path.exists():
        print(f"❌ No existe {mini_path}")
        results["failed"].append(asin)
        continue

    with open(mini_path) as f:
        mini_ml = json.load(f)

    try:
        result = publish_item(mini_ml)

        if result:
            item_id = result.get("item_id") or result.get("id")
            if item_id:
                print(f"✅ Publicado: {item_id}")
                site_items = result.get("site_items", [])
                successful = [s for s in site_items if s.get("item_id")]
                failed = [s for s in site_items if s.get("error")]
                print(f"   → {len(successful)} países OK, {len(failed)} errores")
                results["success"].append(asin)
            else:
                print(f"⚠️ Sin item_id")
                site_items = result.get("site_items", [])
                successful = [s for s in site_items if s.get("item_id")]
                if successful:
                    print(f"   → Parcial: {len(successful)} países")
                    results["success"].append(asin)
                else:
                    results["failed"].append(asin)
        else:
            print(f"❌ Validación bloqueó publicación")
            results["failed"].append(asin)

    except Exception as e:
        print(f"❌ Error: {e}")
        results["failed"].append(asin)

    if i < len(fixed_asins):
        print(f"\n⏱️  Esperando 3s...")
        time.sleep(3)

# REPORTE
print(f"\n{'='*70}")
print(f"📊 REPORTE")
print(f"{'='*70}")
print(f"✅ Publicados: {len(results['success'])}/{len(fixed_asins)}")
print(f"❌ Fallaron: {len(results['failed'])}/{len(fixed_asins)}")

if results["success"]:
    print(f"\n✅ Exitosos: {', '.join(results['success'])}")
if results["failed"]:
    print(f"\n❌ Fallidos: {', '.join(results['failed'])}")

print(f"{'='*70}\n")
