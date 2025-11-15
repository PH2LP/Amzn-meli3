#!/usr/bin/env python3
# ============================================================
# brand_filter.py
# ✅ Sistema de filtrado de marcas prohibidas
# ✅ Previene publicar productos de marcas con restricciones
# ============================================================

import json
import re
from pathlib import Path

CONFIG_FILE = Path(__file__).parent.parent.parent / "config" / "blocked_brands.json"


def load_blocked_brands():
    """
    Carga la lista de marcas prohibidas desde el archivo de configuración.

    Returns:
        list: Lista de marcas prohibidas (lowercase para comparación)
    """
    if not CONFIG_FILE.exists():
        print(f"⚠️  Archivo de marcas prohibidas no encontrado: {CONFIG_FILE}")
        return []

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            brands = config.get('blocked_brands', [])
            # Normalizar a lowercase para comparación insensible a mayúsculas
            return [brand.lower().strip() for brand in brands]
    except Exception as e:
        print(f"❌ Error cargando marcas prohibidas: {e}")
        return []


def is_brand_blocked(brand: str, verbose: bool = False) -> dict:
    """
    Verifica si una marca está en la lista de prohibidas.

    Args:
        brand: Nombre de la marca a verificar
        verbose: Si es True, imprime mensaje cuando detecta marca prohibida

    Returns:
        dict: {
            'is_blocked': bool,
            'brand': str (marca original),
            'matched_brand': str o None (marca prohibida que matcheó)
        }
    """
    if not brand:
        return {'is_blocked': False, 'brand': None, 'matched_brand': None}

    brand_clean = brand.lower().strip()
    blocked_brands = load_blocked_brands()

    # Verificar match exacto
    for blocked in blocked_brands:
        if blocked == brand_clean:
            if verbose:
                print(f"🚫 Marca prohibida detectada: {brand}")

            return {
                'is_blocked': True,
                'brand': brand,
                'matched_brand': blocked.title()
            }

        # Verificar si la marca bloqueada está contenida en el nombre
        # Ejemplo: "Nike Pro" contiene "Nike"
        if blocked in brand_clean or brand_clean in blocked:
            if verbose:
                print(f"🚫 Marca prohibida detectada: {brand} (match: {blocked.title()})")

            return {
                'is_blocked': True,
                'brand': brand,
                'matched_brand': blocked.title()
            }

    # No es marca prohibida
    return {'is_blocked': False, 'brand': brand, 'matched_brand': None}


def check_product_brand(product_data: dict, verbose: bool = False) -> dict:
    """
    Verifica si un producto tiene una marca prohibida.
    Busca en múltiples campos para máxima detección.

    Args:
        product_data: Dict con datos del producto (puede ser mini_ml, amazon_data, etc)
        verbose: Si es True, imprime detalles

    Returns:
        dict: {
            'is_blocked': bool,
            'brand': str o None,
            'matched_brand': str o None,
            'asin': str o None
        }
    """
    # Extraer marca de diferentes posibles campos
    brand = None
    asin = product_data.get('asin', 'N/A')

    # Intentar obtener brand de varios campos posibles
    if 'brand' in product_data:
        brand = product_data['brand']
    elif 'summaries' in product_data and len(product_data['summaries']) > 0:
        brand = product_data['summaries'][0].get('brand', '')
    elif 'attributes' in product_data:
        # Buscar en atributos
        attrs = product_data['attributes']
        if isinstance(attrs, dict) and 'brand' in attrs:
            brand = attrs['brand']

    if not brand:
        return {'is_blocked': False, 'brand': None, 'matched_brand': None, 'asin': asin}

    # Verificar si está prohibida
    check = is_brand_blocked(brand, verbose=verbose)

    return {
        'is_blocked': check['is_blocked'],
        'brand': brand,
        'matched_brand': check['matched_brand'],
        'asin': asin
    }


def filter_asins_by_brand(asins_data: list, verbose: bool = True) -> dict:
    """
    Filtra una lista de productos por marca prohibida.

    Args:
        asins_data: Lista de dicts con datos de productos
        verbose: Si es True, imprime resumen

    Returns:
        dict: {
            'allowed': list,  # Productos permitidos
            'blocked': list,  # Productos bloqueados
            'stats': {
                'total': int,
                'allowed': int,
                'blocked': int,
                'blocked_brands': dict  # {brand: count}
            }
        }
    """
    allowed = []
    blocked = []
    blocked_brands_count = {}

    if verbose:
        print(f"\n🔍 Verificando marcas prohibidas en {len(asins_data)} productos...\n")

    for product in asins_data:
        check = check_product_brand(product, verbose=False)

        if check['is_blocked']:
            blocked.append(product)
            brand = check['matched_brand']
            blocked_brands_count[brand] = blocked_brands_count.get(brand, 0) + 1

            if verbose:
                asin = product.get('asin', 'N/A')
                print(f"🚫 {asin}: {check['brand']} (marca prohibida)")
        else:
            allowed.append(product)
            if verbose:
                asin = product.get('asin', 'N/A')
                brand = check['brand'] or 'Sin marca'
                print(f"✅ {asin}: {brand}")

    stats = {
        'total': len(asins_data),
        'allowed': len(allowed),
        'blocked': len(blocked),
        'blocked_brands': blocked_brands_count
    }

    if verbose:
        print(f"\n" + "="*60)
        print(f"📊 RESUMEN DE FILTRADO DE MARCAS")
        print(f"="*60)
        print(f"  Total productos: {stats['total']}")
        print(f"  ✅ Permitidos: {stats['allowed']}")
        print(f"  🚫 Bloqueados: {stats['blocked']}")

        if blocked_brands_count:
            print(f"\n  Marcas bloqueadas detectadas:")
            for brand, count in sorted(blocked_brands_count.items()):
                print(f"    • {brand}: {count} producto(s)")

        print(f"="*60 + "\n")

    return {
        'allowed': allowed,
        'blocked': blocked,
        'stats': stats
    }


# -------------------------------------------------------------
# 🧪 Test directo
# -------------------------------------------------------------

if __name__ == "__main__":
    print("🧪 Test del sistema de filtrado de marcas\n")

    # Test 1: Marcas individuales
    print("Test 1: Verificación individual")
    print("-" * 40)

    test_brands = [
        "Nike",
        "Adidas",
        "Samsung",
        "Converse",
        "Apple",
        "Urban Decay"
    ]

    for brand in test_brands:
        result = is_brand_blocked(brand, verbose=True)
        if not result['is_blocked']:
            print(f"✅ {brand}: Permitida")

    # Test 2: Productos completos
    print("\n\nTest 2: Productos completos")
    print("-" * 40)

    test_products = [
        {'asin': 'B001', 'brand': 'Nike'},
        {'asin': 'B002', 'brand': 'Samsung'},
        {'asin': 'B003', 'brand': 'Ralph Lauren'},
        {'asin': 'B004', 'brand': 'LEGO'},
    ]

    result = filter_asins_by_brand(test_products, verbose=True)

    print(f"\n✅ Test completado")
