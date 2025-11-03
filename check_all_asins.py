#!/usr/bin/env python3
"""Verificar estado de todos los ASINs"""

import sys
from pathlib import Path

# Auto-activar venv
if sys.prefix == sys.base_prefix:
    vpy = Path(__file__).parent / "venv" / "bin" / "python"
    if vpy.exists():
        import os
        os.execv(str(vpy), [str(vpy)] + sys.argv)

import sqlite3

# Leer ASINs del archivo
with open("resources/asins.txt", "r") as f:
    asins = [line.strip().upper() for line in f if line.strip() and not line.startswith("#")]

print(f"\n{'='*70}")
print(f"📊 REPORTE FINAL DE PUBLICACIONES")
print(f"{'='*70}\n")

# Conectar a la base de datos
conn = sqlite3.connect("storage/listings_database.db")
cursor = conn.cursor()

published = []
failed = []

for i, asin in enumerate(asins, 1):
    cursor.execute("SELECT item_id, asin FROM listings WHERE asin = ? LIMIT 1", (asin,))
    result = cursor.fetchone()

    if result:
        item_id = result[0]
        print(f"{i:2}. ✅ {asin}: {item_id}")
        published.append(asin)
    else:
        print(f"{i:2}. ❌ {asin}: NO PUBLICADO")
        failed.append(asin)

conn.close()

print(f"\n{'='*70}")
print(f"📈 ESTADÍSTICAS")
print(f"{'='*70}")
print(f"Total ASINs: {len(asins)}")
print(f"✅ Publicados: {len(published)}/{len(asins)} ({len(published)*100//len(asins)}%)")
print(f"❌ Fallidos: {len(failed)}/{len(asins)} ({len(failed)*100//len(asins) if failed else 0}%)")

if failed:
    print(f"\n⚠️  ASINs que no se pudieron publicar:")
    for asin in failed:
        print(f"   - {asin}")
        # Verificar si existe el mini_ml
        mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")
        if mini_path.exists():
            print(f"     → mini_ml existe, ver errores específicos")
        else:
            print(f"     → mini_ml NO existe, revisar transformación")

print(f"{'='*70}\n")
