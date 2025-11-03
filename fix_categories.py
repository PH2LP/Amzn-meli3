#!/usr/bin/env python3
"""Buscar y aplicar categorías correctas para cada producto"""

import sys
from pathlib import Path

# Auto-activar venv
if sys.prefix == sys.base_prefix:
    vpy = Path(__file__).parent / "venv" / "bin" / "python"
    if vpy.exists():
        import os
        os.execv(str(vpy), [str(vpy)] + sys.argv)

import json
import requests

# Leer ASINs
with open("resources/asins.txt", "r") as f:
    asins = [line.strip().upper() for line in f if line.strip() and not line.startswith("#")]

print(f"\n{'='*70}")
print("🔍 BUSCANDO CATEGORÍAS CORRECTAS PARA CADA PRODUCTO")
print(f"{'='*70}\n")

results = {}

for i, asin in enumerate(asins, 1):
    mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")

    if not mini_path.exists():
        print(f"{i}. ❌ {asin}: No tiene mini_ml")
        continue

    with open(mini_path, "r", encoding="utf-8") as f:
        mini = json.load(f)

    title = mini.get("title_ai", "")
    current_cat = f"{mini.get('category_id')} - {mini.get('category_name')}"

    print(f"{i}. {asin}")
    print(f"   Título: {title[:60]}...")
    print(f"   Categoría actual: {current_cat}")

    # Buscar categoría correcta usando el título completo
    try:
        # Buscar en CBT usando el título del producto
        search_query = title.replace(" ", "+")
        url = f"https://api.mercadolibre.com/sites/CBT/domain_discovery/search?limit=3&q={search_query}"

        response = requests.get(url, timeout=10)
        if response.ok:
            suggestions = response.json()

            if suggestions:
                best = suggestions[0]
                new_cat_id = best["category_id"]
                new_cat_name = best["category_name"]

                print(f"   ✅ Sugerida: {new_cat_id} - {new_cat_name}")

                # Guardar resultado
                results[asin] = {
                    "current": mini.get("category_id"),
                    "suggested": new_cat_id,
                    "suggested_name": new_cat_name,
                    "needs_update": mini.get("category_id") != new_cat_id
                }
            else:
                print(f"   ⚠️ Sin sugerencias de ML")
                results[asin] = {"current": mini.get("category_id"), "suggested": None, "needs_update": False}
        else:
            print(f"   ❌ Error API: {response.status_code}")
            results[asin] = {"current": mini.get("category_id"), "suggested": None, "needs_update": False}

    except Exception as e:
        print(f"   ❌ Error: {e}")
        results[asin] = {"current": mini.get("category_id"), "suggested": None, "needs_update": False}

    print()

# Resumen
print(f"\n{'='*70}")
print("📊 RESUMEN")
print(f"{'='*70}")

needs_update = [asin for asin, data in results.items() if data.get("needs_update")]
print(f"Total: {len(results)}")
print(f"Necesitan actualización: {len(needs_update)}")

if needs_update:
    print(f"\n📝 Productos que necesitan nueva categoría:")
    for asin in needs_update:
        data = results[asin]
        print(f"  - {asin}: {data['current']} → {data['suggested']} ({data['suggested_name']})")

# Guardar resultados
with open("storage/logs/category_fixes.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\n💾 Resultados guardados en: storage/logs/category_fixes.json")
print(f"{'='*70}\n")
