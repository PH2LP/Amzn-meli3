#!/usr/bin/env python3
"""Test script para probar la publicación de un solo ASIN"""

import sys
from pathlib import Path

# Auto-activar venv
if sys.prefix == sys.base_prefix:
    vpy = Path(__file__).parent / "venv" / "bin" / "python"
    if vpy.exists():
        print(f"⚙️  Activando entorno virtual: {vpy}")
        import os
        os.execv(str(vpy), [str(vpy)] + sys.argv)

import json
from dotenv import load_dotenv
from src.mainglobal import publish_item

load_dotenv(override=True)

# Test con B0BXSLRQH7 (tenía problemas de atributos)
asin = "B0BXSLRQH7"
mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")

if not mini_path.exists():
    print(f"❌ No existe mini_ml para {asin}")
    sys.exit(1)

print(f"🧪 Probando publicación de {asin}...")
with open(mini_path, "r", encoding="utf-8") as f:
    mini_ml = json.load(f)

try:
    result = publish_item(mini_ml)
    print(f"\n✅ Resultado: {result}")
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
