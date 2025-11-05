#!/usr/bin/env python3
"""Test build_mini_ml for Nintendo Switch 2"""

import sys
sys.path.insert(0, '.')
from src.transform_mapper_new import build_mini_ml, load_json_file, save_json_file
from pathlib import Path

print('=' * 70)
print('EJECUTANDO build_mini_ml PARA NINTENDO SWITCH 2')
print('=' * 70)

try:
    # Cargar JSON de Amazon
    amazon_json = load_json_file('storage/asins_json/B0FC5FJZ9Z.json')

    print(f'\n📦 Producto:')
    print(f'  ASIN: {amazon_json.get("asin")}')
    print(f'  Título: {amazon_json.get("attributes", {}).get("item_name", [{}])[0].get("value", "N/A")}')
    print(f'  Marca: {amazon_json.get("summaries", [{}])[0].get("brand", "N/A")}')
    print(f'  Precio: ${amazon_json.get("attributes", {}).get("list_price", [{}])[0].get("value", 0)}')

    # Ejecutar build_mini_ml
    print(f'\n🔧 Ejecutando build_mini_ml...')
    mini_ml = build_mini_ml(amazon_json)

    if mini_ml:
        print(f'\n✅ Mini ML generado exitosamente')
        print(f'  Categoría: {mini_ml.get("category_id")} - {mini_ml.get("category_name")}')
        print(f'  Confianza: {mini_ml.get("category_similarity", 0):.2f}')
        print(f'  Título: {mini_ml.get("title_ai", "N/A")[:60]}...')
        print(f'  Precio base: ${mini_ml.get("price", {}).get("base_usd")}')
        print(f'  Precio net proceeds: ${mini_ml.get("price", {}).get("net_proceeds_usd")}')
        print(f'  Atributos mapeados: {len(mini_ml.get("attributes_mapped", {}))}')
        print(f'  Imágenes: {len(mini_ml.get("images", []))}')
        print(f'  GTINs: {mini_ml.get("gtins", [])}')

        # Dimensiones
        pkg = mini_ml.get("package", {})
        print(f'  Dimensiones: {pkg.get("length_cm")} x {pkg.get("width_cm")} x {pkg.get("height_cm")} cm')
        print(f'  Peso: {pkg.get("weight_kg")} kg')

        # Guardar
        output_path = Path('storage/logs/publish_ready/B0FC5FJZ9Z_mini_ml_TEST.json')
        save_json_file(str(output_path), mini_ml)
        print(f'\n💾 Mini ML guardado en: {output_path}')
        print(f'   Tamaño: {output_path.stat().st_size / 1024:.1f} KB')

    else:
        print(f'\n❌ build_mini_ml retornó None')

except Exception as e:
    print(f'\n❌ ERROR:')
    print(f'  Tipo: {type(e).__name__}')
    print(f'  Mensaje: {e}')
    print(f'\nTraceback:')
    import traceback
    traceback.print_exc()
