#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_blacklisted_keywords.py
═══════════════════════════════════════════════════════════════════════════════
Limpia master_keywords.json removiendo keywords que son marcas blacklisteadas.

Uso:
    python3 scripts/tools/clean_blacklisted_keywords.py

Esto removerá keywords como:
- nike (marca blacklisteada)
- adidas (marca blacklisteada)
- apple, ipad, etc. (marcas Apple)
═══════════════════════════════════════════════════════════════════════════════
"""

import json
import sys
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
MASTER_KW_FILE = PROJECT_ROOT / "config" / "master_keywords.json"
BLACKLIST_FILE = PROJECT_ROOT / "config" / "brand_blacklist.json"

# Marcas adicionales conocidas (Apple, etc.)
ADDITIONAL_BRANDS = [
    "apple",
    "iphone",
    "ipad",
    "macbook",
    "airpods",
    "samsung",
    "yeti",
    "gucci",
    "prada",
    "louis vuitton",
    "chanel"
]

def load_blacklist():
    """Carga la blacklist de marcas"""
    if not BLACKLIST_FILE.exists():
        print(f"⚠️ No se encontró {BLACKLIST_FILE}")
        return []

    with open(BLACKLIST_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    brands = [b.lower() for b in data.get("blacklisted_brands", [])]
    brands.extend(ADDITIONAL_BRANDS)

    return brands

def clean_keywords():
    """Limpia master_keywords.json removiendo marcas blacklisteadas"""

    print("═══════════════════════════════════════════════════════════")
    print("🧹 LIMPIEZA DE KEYWORDS BLACKLISTEADAS")
    print("═══════════════════════════════════════════════════════════\n")

    # 1. Cargar blacklist
    blacklisted_brands = load_blacklist()
    print(f"📋 Marcas blacklisteadas: {len(blacklisted_brands)}")
    print(f"   {', '.join(blacklisted_brands[:10])}...\n")

    # 2. Cargar master keywords
    if not MASTER_KW_FILE.exists():
        print(f"❌ No se encontró {MASTER_KW_FILE}")
        return

    with open(MASTER_KW_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    original_count = len(data["keywords"])
    print(f"📊 Keywords originales: {original_count:,}\n")

    # 3. Filtrar keywords
    removed_keywords = []
    clean_keywords_list = []

    for kw in data["keywords"]:
        keyword_text = kw["keyword"].lower()

        # Verificar si la keyword es exactamente una marca blacklisteada
        if keyword_text in blacklisted_brands:
            removed_keywords.append(kw)
        else:
            clean_keywords_list.append(kw)

    # 4. Actualizar data
    data["keywords"] = clean_keywords_list
    data["total_keywords"] = len(clean_keywords_list)

    # 5. Guardar
    backup_file = MASTER_KW_FILE.with_suffix('.json.backup')

    # Backup
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"💾 Backup guardado: {backup_file.name}")

    # Guardar limpio
    with open(MASTER_KW_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # 6. Reporte
    print(f"\n✅ Archivo limpio guardado: {MASTER_KW_FILE.name}")
    print(f"\n📊 RESULTADOS:")
    print(f"   • Keywords originales:   {original_count:,}")
    print(f"   • Keywords removidas:    {len(removed_keywords):,}")
    print(f"   • Keywords finales:      {len(clean_keywords_list):,}")

    if removed_keywords:
        print(f"\n🗑️  Keywords removidas:")
        for kw in removed_keywords:
            print(f"   • {kw['keyword']} ({kw['search_volume']:,} searches)")

    print("\n" + "═"*60)
    print("✅ LIMPIEZA COMPLETADA")
    print("═"*60)

if __name__ == "__main__":
    clean_keywords()
