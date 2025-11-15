#!/usr/bin/env python3
"""
Corrección manual de categorías según tipo de producto.
Usa solo categorías que sabemos que funcionan en TODOS los países.
"""

import json
from pathlib import Path

# Mapeo correcto de ASINs a categorías universales
CATEGORY_FIXES = {
    # Relojes → Cambiar a Toys & Games (más universal que Sports)
    'B092RCLKHN': {
        'category_id': 'CBT29890',
        'category_name': 'Toys & Games',
        'reason': 'Reloj GPS - CBT388015 no permitido en México/Argentina'
    },
    'B0BXSLRQH7': {
        'category_id': 'CBT29890',
        'category_name': 'Toys & Games',
        'reason': 'Reloj deportivo - CBT388015 no permitido en México/Argentina'
    },

    # LEGO → Debe estar en Building Blocks
    'B0DRW69H11': {
        'category_id': 'CBT1157',
        'category_name': 'Building Blocks & Figures',
        'reason': 'LEGO Set - debe estar en Building Blocks'
    },

    # Balón → Toys & Games (más universal que Sports)
    'B0DCYZJBYD': {
        'category_id': 'CBT29890',
        'category_name': 'Toys & Games',
        'reason': 'Balón baloncesto - Sports no siempre permitido'
    },

    # Audífonos → Toys & Games (CBT no tiene Electronics universal)
    'B0CLC6NBBX': {
        'category_id': 'CBT29890',
        'category_name': 'Toys & Games',
        'reason': 'Audífonos - No hay categoría Electronics universal en CBT'
    },

    # Kit pintura → Ya está en categoría correcta (CBT29890)
    'B0BRNY9HZB': {
        'category_id': 'CBT29890',
        'category_name': 'Toys & Games',
        'reason': 'Kit de arte - categoría correcta'
    }
}

def fix_categories():
    """Corrige categorías de los mini_ml"""

    print("🔧 CORRIGIENDO CATEGORÍAS MANUALMENTE")
    print("=" * 70)

    fixed_count = 0

    for asin, fix_data in CATEGORY_FIXES.items():
        mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")

        if not mini_path.exists():
            print(f"⚠️  {asin}: Mini ML no existe")
            continue

        with open(mini_path) as f:
            mini_ml = json.load(f)

        old_cat = mini_ml.get('category_id')
        new_cat = fix_data['category_id']

        if old_cat != new_cat:
            mini_ml['category_id'] = new_cat
            mini_ml['category_name'] = fix_data['category_name']

            with open(mini_path, 'w') as f:
                json.dump(mini_ml, f, indent=2, ensure_ascii=False)

            print(f"✅ {asin}:")
            print(f"   {old_cat} → {new_cat}")
            print(f"   Razón: {fix_data['reason']}")

            fixed_count += 1
        else:
            print(f"✓  {asin}: Ya tiene categoría correcta ({new_cat})")

    print("\n" + "=" * 70)
    print(f"📊 {fixed_count} ASINs corregidos")
    print("\nAhora ejecuta:")
    print("  python3 delete_and_republish.py")

if __name__ == "__main__":
    fix_categories()
