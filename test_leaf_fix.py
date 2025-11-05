#!/usr/bin/env python3
"""
Test rápido para verificar que CategoryMatcherV2 solo selecciona categorías LEAF
"""
import json
from src.category_matcher_v2 import CategoryMatcherV2

# Inicializar CategoryMatcher
print("🚀 Inicializando CategoryMatcherV2...")
matcher = CategoryMatcherV2()

# Producto de prueba: LEGO Wicked (antes fallaba con CBT455425)
product = {
    'title': 'LEGO Wicked Emerald City Building Toy Set',
    'description': 'LEGO building set with 945 pieces, featuring Emerald City from Wicked musical',
    'brand': 'LEGO',
    'productType': 'TOY_BUILDING_BLOCK',
    'features': ['945 pieces', 'Building blocks', 'Wicked theme']
}

print("\n" + "="*70)
print("📦 PRODUCTO DE PRUEBA: LEGO Wicked")
print("="*70)
print(f"Título: {product['title']}")
print(f"ProductType: {product['productType']}")

# Buscar categoría
result = matcher.find_category(product, top_k=30, use_ai=True)

print("\n" + "="*70)
print("✅ RESULTADO:")
print("="*70)
print(f"Categoría ID: {result['category_id']}")
print(f"Nombre: {result['category_name']}")
print(f"Path: {result['category_path']}")
print(f"Confianza: {result['confidence']:.2f}")
print(f"Método: {result['method']}")

# Verificar que es LEAF
import requests
cat_id = result['category_id']
response = requests.get(f"https://api.mercadolibre.com/categories/{cat_id}")
if response.status_code == 200:
    data = response.json()
    children_count = len(data.get('children_categories', []))
    print(f"\n{'✅' if children_count == 0 else '❌'} Verificación LEAF: {children_count} subcategorías")
    if children_count == 0:
        print("   👍 Categoría seleccionada ES LEAF (puede publicar)")
    else:
        print("   ❌ ERROR: Categoría seleccionada NO es LEAF (tiene hijos)")
else:
    print(f"⚠️ Error verificando categoría: HTTP {response.status_code}")

print("="*70 + "\n")
