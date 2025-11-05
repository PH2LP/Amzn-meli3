#!/usr/bin/env python3
"""Test descenso recursivo LEAF"""
import sys
sys.path.insert(0, 'src')
from category_matcher_v2 import CategoryMatcherV2

# Inicializar matcher
matcher = CategoryMatcherV2()

# Test: Building Toys (CBT455425) - tiene 3 hijos LEAF
print("\n" + "="*70)
print("TEST: Verificando descenso a categorías LEAF")
print("="*70)

# Verificar CBT455425 y sus hijos
parent_id = "CBT455425"
print(f"\n1. Verificando {parent_id}:")
is_leaf = matcher._is_leaf_category(parent_id)
print(f"   ¿Es LEAF? {is_leaf}")

children = matcher._get_category_children(parent_id)
print(f"   Hijos: {len(children)}")

for child_id in children:
    child_leaf = matcher._is_leaf_category(child_id)
    print(f"      - {child_id}: LEAF={child_leaf}")
    
    # Si el hijo es PADRE, verificar sus hijos
    if not child_leaf:
        grandchildren = matcher._get_category_children(child_id)
        print(f"         └─ Tiene {len(grandchildren)} nietos")

print("\n✅ Test completado")
