#!/usr/bin/env python3
"""Test manual transformation for B0FC5FJZ9Z"""

import sys
sys.path.insert(0, '.')
from src.unified_transformer import transform_amazon_to_ml_unified
from src.transform_mapper_new import load_json_file, save_json_file
from pathlib import Path

print('=' * 70)
print('TRANSFORMANDO B0FC5FJZ9Z MANUALMENTE')
print('=' * 70)

try:
    result = transform_amazon_to_ml_unified('B0FC5FJZ9Z')

    if result:
        print('✅ Transformación exitosa')
        print(f'Categoría: {result.get("category_id")} - {result.get("category_name")}')
        print(f'Confianza: {result.get("category_similarity", 0):.2f}')
        print(f'Precio base: ${result.get("price", {}).get("base_usd")}')
        print(f'Precio final: ${result.get("price", {}).get("net_proceeds_usd")}')
        print(f'Atributos mapeados: {len(result.get("attributes_mapped", {}))}')
        print(f'Imágenes: {len(result.get("images", []))}')
        print(f'GTINs: {result.get("gtins", [])}')
        print(f'Dimensiones: {result.get("package", {})}')

        # Guardar mini_ml
        output_path = Path('storage/logs/publish_ready/B0FC5FJZ9Z_mini_ml.json')
        save_json_file(result, str(output_path))
        print(f'\n✅ Mini_ML guardado en: {output_path}')
        print(f'Tamaño del archivo: {output_path.stat().st_size / 1024:.1f} KB')
    else:
        print('❌ Transformación retornó None o False')

except Exception as e:
    print(f'\n❌ ERROR DURANTE TRANSFORMACIÓN:')
    print(f'Tipo: {type(e).__name__}')
    print(f'Mensaje: {e}')
    print('\nTraceback completo:')
    import traceback
    traceback.print_exc()
