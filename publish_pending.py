#!/usr/bin/env python3
"""Publicar los 5 ASINs pendientes"""

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

# ASINs pendientes por cuota OpenAI
pending_asins = [
    "B092RCLKHN",
    "B0DRW69H11",
    "B0D3H3NKBN",
    "B0CJQG4PMF",
    "B0CLC6NBBX"
]

print(f"\n{'='*70}")
print(f"🚀 PUBLICANDO {len(pending_asins)} ASINS PENDIENTES")
print(f"{'='*70}\n")

results = {"success": [], "failed": []}

for i, asin in enumerate(pending_asins, 1):
    mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")

    if not mini_path.exists():
        print(f"{i}. ❌ {asin}: No tiene mini_ml")
        results["failed"].append(asin)
        continue

    print(f"\n{'='*70}")
    print(f"{i}/{len(pending_asins)}. {asin}")
    print('='*70)

    try:
        with open(mini_path, "r", encoding="utf-8") as f:
            mini_ml = json.load(f)

        result = publish_item(mini_ml)

        if result:
            item_id = result.get("item_id") or result.get("id")
            if item_id:
                print(f"✅ Publicado: {item_id}")

                # Contar países exitosos
                site_items = result.get("site_items", [])
                successful = [s for s in site_items if s.get("item_id")]
                failed = [s for s in site_items if s.get("error")]
                print(f"   → {len(successful)} países exitosos, {len(failed)} con errores")

                results["success"].append(asin)
            else:
                print(f"⚠️ Sin item_id en respuesta")
                # Ver si hay publicaciones parciales
                site_items = result.get("site_items", [])
                successful = [s for s in site_items if s.get("item_id")]
                if successful:
                    print(f"   → Publicado parcialmente en {len(successful)} países")
                    results["success"].append(asin)
                else:
                    results["failed"].append(asin)
        else:
            print(f"❌ Respuesta vacía")
            results["failed"].append(asin)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        results["failed"].append(asin)

    # Rate limiting
    if i < len(pending_asins):
        print("\n⏱️  Esperando 3 segundos...")
        time.sleep(3)

print(f"\n{'='*70}")
print("📊 REPORTE FINAL")
print(f"{'='*70}")
print(f"✅ Publicados: {len(results['success'])}/{len(pending_asins)}")
print(f"❌ Fallidos: {len(results['failed'])}/{len(pending_asins)}")

if results["success"]:
    print(f"\n✅ Exitosos: {', '.join(results['success'])}")
if results["failed"]:
    print(f"\n❌ Fallidos: {', '.join(results['failed'])}")

print(f"{'='*70}\n")
