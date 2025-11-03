#!/usr/bin/env python3
"""
Validar y publicar los mini_ml existentes.
Solo regenerar los que fallen validación.
"""

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

# Leer ASINs
asins_file = Path("resources/asins.txt")
asins = [line.strip() for line in asins_file.read_text().splitlines() if line.strip()]

print(f"\n{'='*70}")
print(f"🚀 VALIDAR Y PUBLICAR {len(asins)} ASINS")
print(f"{'='*70}\n")

results = {"validated": [], "published": [], "failed": [], "needs_regen": []}

for i, asin in enumerate(asins, 1):
    print(f"\n{'='*70}")
    print(f"{i}/{len(asins)}. {asin}")
    print(f"{'='*70}\n")

    mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")

    if not mini_path.exists():
        print(f"⚠️ No existe {mini_path} - NECESITA REGENERACIÓN")
        results["needs_regen"].append(asin)
        continue

    with open(mini_path, "r") as f:
        mini_ml = json.load(f)

    # Intentar publicar (tiene validación IA integrada)
    print(f"🚀 Publicando...")
    try:
        result = publish_item(mini_ml)

        if result is None:
            print(f"❌ Publicación abortada por validación")
            results["needs_regen"].append(asin)
            continue

        item_id = result.get("item_id") or result.get("id")
        if item_id:
            print(f"✅ Publicado: {item_id}")
            site_items = result.get("site_items", [])
            successful = [s for s in site_items if s.get("item_id")]
            failed_items = [s for s in site_items if s.get("error")]
            print(f"   → {len(successful)} países OK, {len(failed_items)} errores")
            results["published"].append(asin)
        else:
            print(f"⚠️ Sin item_id")
            site_items = result.get("site_items", [])
            successful = [s for s in site_items if s.get("item_id")]
            if successful:
                print(f"   → Parcial: {len(successful)} países")
                results["published"].append(asin)
            else:
                results["failed"].append(asin)

    except Exception as e:
        print(f"❌ Error: {e}")
        results["failed"].append(asin)

    if i < len(asins):
        print(f"\n⏱️  Esperando 3s...")
        time.sleep(3)

# REPORTE
print(f"\n{'='*70}")
print(f"📊 REPORTE FINAL")
print(f"{'='*70}")
print(f"✅ Publicados: {len(results['published'])}/{len(asins)}")
print(f"❌ Fallaron: {len(results['failed'])}/{len(asins)}")
print(f"🔄 Necesitan regeneración: {len(results['needs_regen'])}/{len(asins)}")

if results["published"]:
    print(f"\n✅ Publicados: {', '.join(results['published'])}")
if results["failed"]:
    print(f"\n❌ Fallidos: {', '.join(results['failed'])}")
if results["needs_regen"]:
    print(f"\n🔄 Necesitan regeneración: {', '.join(results['needs_regen'])}")

print(f"{'='*70}\n")

# Guardar reporte
with open("storage/publish_report.json", "w") as f:
    json.dump(results, f, indent=2)
print("💾 Reporte: storage/publish_report.json")
