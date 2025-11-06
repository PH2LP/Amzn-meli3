#!/usr/bin/env python3
"""Borrar las últimas publicaciones con HTML mal formateado."""
import requests
import os
from dotenv import load_dotenv

load_dotenv()
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")

# IDs reportados en los logs
item_ids = [
    "CBT2680957103",  # B0F52Z4CG7
    "CBT2680915911",  # B0F1Y81JH8
    "CBT2994396574",  # B0DY3X1MB8
    "CBT2994535762",  # B0DY31MCQW - primer intento
    "CBT2680402079",  # B0DY31MCQW - retry
    "CBT2994436142",  # B0DT39TCPT
    "CBT2994559626",  # B0DXKCL3DN
]

headers = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"}

print("🗑️  Eliminando publicaciones con HTML mal formateado...")
for item_id in item_ids:
    try:
        # Cerrar el listing
        r = requests.put(
            f"https://api.mercadolibre.com/items/{item_id}",
            headers=headers,
            json={"status": "closed"}
        )
        if r.status_code in (200, 201):
            print(f"✅ {item_id} → Cerrado")
        else:
            print(f"⚠️  {item_id} → {r.status_code} {r.text[:100]}")
    except Exception as e:
        print(f"❌ {item_id} → Error: {e}")

print("\n✓ Proceso completado")
