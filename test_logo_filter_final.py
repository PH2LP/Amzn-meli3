#!/usr/bin/env python3
"""
Test final del sistema de filtrado de logos integrado
Solo transforma el producto sin publicar
"""

import sys
import json
from pathlib import Path

# Importar módulo de transformación
from src.pipeline.transform_mapper_new import build_mini_ml, load_json_file

# ASIN de prueba: Teclado iPad (accesorio)
ASIN = "B0D9WB36MF"

print("=" * 80)
print("🧪 TEST: Sistema de Filtrado de Logos (Integrado)")
print("=" * 80)
print(f"\n📦 ASIN: {ASIN}")
print()

# Cargar JSON de Amazon
amazon_path = Path(f"storage/asins_json/{ASIN}.json")
if not amazon_path.exists():
    print(f"❌ No existe {amazon_path}")
    sys.exit(1)

print(f"✓ Cargando datos de Amazon...")
amazon_json = load_json_file(str(amazon_path))

# Ejecutar transformación (incluye filtrado de logos)
print(f"🔄 Ejecutando transformación con filtrado de logos...")
print()

mini_ml = build_mini_ml(amazon_json)

if not mini_ml:
    print("❌ Error en transformación")
    sys.exit(1)

# Analizar resultado
title = mini_ml.get('title_ai', '')
images = mini_ml.get('images', [])

print("=" * 80)
print("📊 RESULTADO")
print("=" * 80)
print(f"\n📝 Título: {title}")
print(f"\n🖼️  Imágenes:")
print(f"   Total: {len(images)}")

if images:
    for i, img in enumerate(images, 1):
        url = img.get('url', '')
        print(f"   {i}. {url[:70]}...")

print()

# Verificar si es accesorio
title_lower = title.lower()
accessory_keywords = ["para ", "compatible", "case", "funda", "cover", "cable", "charger", "dock", "adapter", "stand", "mount", "holder", "protector"]
is_accessory = any(kw in title_lower for kw in accessory_keywords)

print(f"🏷️  Tipo de producto:")
if is_accessory:
    print(f"   ✓ Accesorio detectado (aplicó filtro de logos)")
    for kw in accessory_keywords:
        if kw in title_lower:
            print(f"      Keyword: '{kw.strip()}'")
            break
else:
    print(f"   • Producto original (sin filtro de logos)")

print()
print("=" * 80)

# Guardar resultado
output_path = Path(f"storage/logs/publish_ready/{ASIN}_mini_ml.json")
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(mini_ml, f, ensure_ascii=False, indent=2)

print(f"\n✅ Resultado guardado en: {output_path}")
print()
