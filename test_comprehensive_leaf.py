#!/usr/bin/env python3
"""
Test comprehensivo del fix de categorías LEAF
"""
import json
import requests
from src.category_matcher_v2 import CategoryMatcherV2

def verify_is_leaf(cat_id):
    """Verifica que una categoría sea LEAF"""
    response = requests.get(f"https://api.mercadolibre.com/categories/{cat_id}")
    if response.status_code == 200:
        data = response.json()
        children_count = len(data.get('children_categories', []))
        return children_count == 0, children_count
    return None, None

# Test cases
test_products = [
    {
        'name': 'LEGO Building Set',
        'product': {
            'title': 'LEGO Wicked Emerald City Building Toy Set',
            'productType': 'TOY_BUILDING_BLOCK',
            'brand': 'LEGO'
        },
        'expected_category_type': 'Building'
    },
    {
        'name': 'Slippers',
        'product': {
            'title': 'Comfortable Indoor Slippers',
            'productType': 'FOOTWEAR',
            'brand': 'Comfort'
        },
        'expected_category_type': 'Footwear'
    },
    {
        'name': 'Nintendo Switch Game',
        'product': {
            'title': 'Super Mario Bros Wonder Nintendo Switch',
            'productType': 'VIDEO_GAME',
            'brand': 'Nintendo'
        },
        'expected_category_type': 'Games'
    }
]

print("="*70)
print("🧪 TEST COMPREHENSIVO - CATEGORÍAS LEAF")
print("="*70)

# Inicializar matcher una vez
print("\n🚀 Inicializando CategoryMatcherV2...")
matcher = CategoryMatcherV2()

results = []
all_passed = True

for i, test in enumerate(test_products, 1):
    print(f"\n{'='*70}")
    print(f"TEST {i}/3: {test['name']}")
    print(f"{'='*70}")
    print(f"Título: {test['product']['title']}")
    
    # Buscar categoría
    result = matcher.find_category(test['product'], top_k=30, use_ai=True)
    
    # Verificar que es LEAF
    is_leaf, children_count = verify_is_leaf(result['category_id'])
    
    # Resultado
    test_result = {
        'test_name': test['name'],
        'category_id': result['category_id'],
        'category_name': result['category_name'],
        'is_leaf': is_leaf,
        'children_count': children_count,
        'confidence': result['confidence']
    }
    
    results.append(test_result)
    
    print(f"\n📊 Resultado:")
    print(f"   Categoría: {result['category_id']} - {result['category_name']}")
    print(f"   Confianza: {result['confidence']:.2f}")
    
    if is_leaf:
        print(f"   ✅ LEAF: Sí (0 subcategorías) → PUEDE PUBLICAR")
    else:
        print(f"   ❌ LEAF: No ({children_count} subcategorías) → NO PUEDE PUBLICAR")
        all_passed = False

# Resumen final
print(f"\n{'='*70}")
print("📋 RESUMEN DE TESTS")
print(f"{'='*70}")

for r in results:
    status = "✅ PASS" if r['is_leaf'] else "❌ FAIL"
    print(f"{status} - {r['test_name']:20s} → {r['category_id']} ({r['children_count']} hijos)")

print(f"\n{'='*70}")
if all_passed:
    print("✅ TODOS LOS TESTS PASARON - Sistema listo para producción!")
    print("="*70)
    exit(0)
else:
    print("❌ ALGUNOS TESTS FALLARON - Revisar implementación")
    print("="*70)
    exit(1)
