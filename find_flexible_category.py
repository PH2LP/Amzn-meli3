#!/usr/bin/env python3
"""Encontrar categoría flexible para Picun headphones"""

import sys
from pathlib import Path

# Auto-activar venv
if sys.prefix == sys.base_prefix:
    vpy = Path(__file__).parent / "venv" / "bin" / "python"
    if vpy.exists():
        import os
        os.execv(str(vpy), [str(vpy)] + sys.argv)

import requests
from openai import OpenAI
from dotenv import load_dotenv
import json

load_dotenv(override=True)

client = OpenAI()

def search_ml_categories(query: str, limit: int = 10):
    """Buscar categorías en ML"""
    url = "https://api.mercadolibre.com/sites/CBT/domain_discovery/search"
    params = {"q": query, "limit": limit}

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        categories = []
        for item in data:
            cat_id = item.get("category_id")
            cat_name = item.get("category_name")
            if cat_id and cat_name:
                categories.append({"category_id": cat_id, "category_name": cat_name})

        return categories
    except Exception as e:
        print(f"Error searching categories: {e}")
        return []

def check_brand_flexibility(category_id: str):
    """Verificar si la categoría acepta BRAND libre o tiene muchos valores"""
    try:
        resp = requests.get(f"https://api.mercadolibre.com/categories/{category_id}/attributes", timeout=10)
        resp.raise_for_status()
        attrs = resp.json()

        brand_attr = next((a for a in attrs if a.get("id") == "BRAND"), None)

        if not brand_attr:
            return {"has_brand": False, "required": False, "catalog_required": False, "value_count": 0, "accepts_freetext": True}

        tags = brand_attr.get("tags", {})
        values = brand_attr.get("values", [])
        value_type = brand_attr.get("value_type", "")

        # Buscar "Picun" en los valores
        has_picun = any("picun" in v.get("name", "").lower() for v in values)

        return {
            "has_brand": True,
            "required": tags.get("required", False),
            "catalog_required": tags.get("catalog_required", False),
            "value_count": len(values),
            "value_type": value_type,
            "has_picun": has_picun,
            "accepts_freetext": not tags.get("catalog_required", False)
        }
    except Exception as e:
        print(f"Error checking {category_id}: {e}")
        return None

# Buscar categorías alternativas usando IA
print("🔍 Buscando categorías alternativas para Picun B8 Bluetooth Headphones...")
print()

# Queries múltiples
queries = [
    "bluetooth headphones wireless",
    "wireless earphones headset",
    "audio accessories bluetooth",
    "portable headphones over-ear"
]

all_categories = []
for query in queries:
    print(f"Searching: {query}")
    cats = search_ml_categories(query, limit=5)
    all_categories.extend(cats)

# Deduplicar
unique_cats = {c["category_id"]: c for c in all_categories}.values()

print(f"\n✅ Encontradas {len(unique_cats)} categorías únicas")
print()

# Verificar flexibilidad de cada una
results = []
for cat in unique_cats:
    cid = cat["category_id"]
    name = cat["category_name"]

    print(f"Checking {cid} ({name})...")
    flex = check_brand_flexibility(cid)

    if flex:
        cat["brand_info"] = flex
        results.append(cat)

        status = "✅ PICUN FOUND!" if flex.get("has_picun") else \
                 "✅ FREE TEXT" if flex.get("accepts_freetext") else \
                 f"⚠️ {flex.get('value_count', 0)} brands only"

        print(f"   → {status}")
        print(f"   → Required: {flex.get('required')}, Catalog: {flex.get('catalog_required')}")

print(f"\n{'='*70}")
print("📊 MEJORES OPCIONES:")
print(f"{'='*70}\n")

# Ordenar por mejor opción
def category_score(cat):
    info = cat.get("brand_info", {})
    if info.get("has_picun"):
        return 100  # Perfecto!
    if info.get("accepts_freetext"):
        return 50  # Acepta texto libre
    if not info.get("required"):
        return 25  # BRAND no es requerido
    return -info.get("value_count", 0)  # Menos marcas = peor

results.sort(key=category_score, reverse=True)

for i, cat in enumerate(results[:5], 1):
    info = cat.get("brand_info", {})
    print(f"{i}. {cat['category_id']} - {cat['category_name']}")
    print(f"   Picun: {'✅ YES' if info.get('has_picun') else '❌ NO'}")
    print(f"   Free text: {'✅ YES' if info.get('accepts_freetext') else '❌ NO'}")
    print(f"   Required: {info.get('required')}")
    print(f"   Values: {info.get('value_count')}")
    print()

# Guardar resultado
best = results[0] if results else None
if best:
    output = {
        "recommended_category": best["category_id"],
        "category_name": best["category_name"],
        "reason": "Accepts Picun brand" if best["brand_info"].get("has_picun") else
                  "Accepts free text brand" if best["brand_info"].get("accepts_freetext") else
                  "BRAND not required",
        "all_options": [
            {
                "id": c["category_id"],
                "name": c["category_name"],
                "accepts_picun": c["brand_info"].get("has_picun", False),
                "accepts_freetext": c["brand_info"].get("accepts_freetext", False)
            }
            for c in results[:5]
        ]
    }

    with open("storage/B0CLC6NBBX_category_recommendation.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"💾 Recomendación guardada en storage/B0CLC6NBBX_category_recommendation.json")
    print(f"\n✅ USAR: {best['category_id']} - {best['category_name']}")
