#!/usr/bin/env python3
"""Test AI validation on B092RCLKHN"""

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
from src.mainglobal import publish_item

load_dotenv(override=True)

# Test con B092RCLKHN (Garmin GPS con categoría incorrecta)
mini_path = Path("storage/logs/publish_ready/B092RCLKHN_mini_ml.json")

if not mini_path.exists():
    print(f"❌ {mini_path} not found")
    sys.exit(1)

with open(mini_path, "r") as f:
    mini_ml = json.load(f)

print(f"\n{'='*70}")
print(f"🧪 TESTING VALIDATION WITH B092RCLKHN")
print(f"Category: {mini_ml.get('category_id')} - {mini_ml.get('category_name')}")
print(f"Title: {mini_ml.get('title_ai')}")
print(f"{'='*70}\n")

# Intentar publicar - debería fallar validación
result = publish_item(mini_ml)

if result is None:
    print(f"\n✅ VALIDACIÓN FUNCIONÓ: Publicación fue abortada")
    print(f"Este listing necesita ser regenerado con la categoría correcta")
else:
    print(f"\n⚠️ VALIDACIÓN NO FUNCIONÓ: Publicación continuó a pesar de categoría incorrecta")
    print(f"Item ID: {result.get('item_id') or result.get('id')}")
