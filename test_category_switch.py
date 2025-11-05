#!/usr/bin/env python3
"""Test category detection for Nintendo Switch 2"""

import sys
sys.path.insert(0, '.')
from src.category_matcher_v2 import CategoryMatcherV2
from src.transform_mapper_new import load_json_file

print('=' * 70)
print('DETECTANDO CATEGORÍA PARA NINTENDO SWITCH 2')
print('=' * 70)

# Cargar JSON de Amazon
amz = load_json_file('storage/asins_json/B0FC5FJZ9Z.json')

# Extraer datos relevantes
product_type = amz.get('productTypes', [{}])[0].get('productType', 'VIDEO_GAME_CONSOLE')
title = amz.get('attributes', {}).get('item_name', [{}])[0].get('value', 'Nintendo Switch 2')
brand = amz.get('summaries', [{}])[0].get('brand', 'Nintendo')

print(f'\n📦 Datos del producto:')
print(f'  Product Type: {product_type}')
print(f'  Título: {title}')
print(f'  Marca: {brand}')

# Inicializar CategoryMatcher
matcher = CategoryMatcherV2()

# Preparar product_data
product_data = {
    'title': title,
    'brand': brand,
    'product_type': product_type,
    'description': amz.get('attributes', {}).get('bullet_point', [{}])[0].get('value', ''),
}

# Detectar categoría
print(f'\n🔍 Iniciando detección de categoría...')
category_info = matcher.find_category(
    product_data=product_data,
    use_ai=True
)

print(f'\n📊 RESULTADO:')
print(f'  Categoría ID: {category_info.get("category_id")}')
print(f'  Categoría Nombre: {category_info.get("category_name")}')
print(f'  Confianza: {category_info.get("confidence", 0):.2f}')
print(f'  Método: {category_info.get("method")}')

# Buscar categorías de gaming manualmente
print(f'\n🎮 Buscando categorías de gaming en la base...')
all_cats = matcher.categories_df
gaming_cats = all_cats[
    all_cats['name'].str.contains('Console|Gaming|Video Game|PlayStation|Xbox|Nintendo',
                                   case=False, na=False)
]

print(f'\n📋 Categorías de consolas/gaming encontradas:')
for idx, row in gaming_cats.head(15).iterrows():
    print(f'  {row["id"]} - {row["name"]}')
