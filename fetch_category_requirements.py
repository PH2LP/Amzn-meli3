#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Descarga y cachea TODOS los atributos de una categoría ML (obligatorios + opcionales).
Guarda en cache/categories/<category_id>.json
"""

import os, sys, json, requests
from dotenv import load_dotenv

# --- Auto-activar venv ---
if sys.prefix == sys.base_prefix:
    vpy = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
    if os.path.exists(vpy):
        os.execv(vpy, [vpy] + sys.argv)

load_dotenv()

ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")
CACHE_DIR = os.path.join("cache", "categories")
os.makedirs(CACHE_DIR, exist_ok=True)

def fetch_category_attrs(category_id: str, token: str):
    url = f"https://api.mercadolibre.com/categories/{category_id}/attributes"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    return r.json()

def main():
    if len(sys.argv) < 2:
        print("Uso: python fetch_category_requirements.py <CATEGORY_ID>  (p.ej. CBT1157)")
        sys.exit(1)

    if not ML_ACCESS_TOKEN:
        print("❌ Falta ML_ACCESS_TOKEN en .env")
        sys.exit(1)

    category_id = sys.argv[1].strip()
    print(f"🔎 Descargando atributos de categoría {category_id}…")
    data = fetch_category_attrs(category_id, ML_ACCESS_TOKEN)
    out = os.path.join(CACHE_DIR, f"{category_id}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Guardado en {out}")

if __name__ == "__main__":
    main()