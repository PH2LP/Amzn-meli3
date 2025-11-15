#!/usr/bin/env python3
# ============================================================
# duplicate_checker.py
# ✅ Sistema de detección de duplicados antes de procesar
# ✅ Verifica por ASIN y por GTIN/UPC para evitar reprocesar
# ✅ Filtra marcas prohibidas automáticamente
# ============================================================

import sys
import json
from pathlib import Path

# Agregar scripts/tools al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'scripts' / 'tools'))
from save_listing_data import check_asin_exists, check_gtin_exists, init_database

# Agregar src al path para imports locales
sys.path.insert(0, str(Path(__file__).parent.parent))
from filters.brand_filter import is_brand_blocked


def check_product_duplicate(asin: str, gtin: str = None, verbose: bool = True) -> dict:
    """
    Verifica si un producto ya fue publicado, usando ASIN y GTIN.

    Args:
        asin: ASIN del producto
        gtin: GTIN/UPC/EAN del producto (opcional)
        verbose: Si es True, imprime mensajes detallados

    Returns:
        dict: {
            'is_duplicate': bool,
            'reason': str,  # 'asin' o 'gtin' o None
            'existing_asin': str o None,
            'existing_item_id': str o None,
            'existing_title': str o None,
            'date_published': str o None
        }
    """

    # Inicializar BD si no existe
    init_database()

    # 1. Verificar por ASIN (mismo producto exacto)
    asin_check = check_asin_exists(asin)
    if asin_check['exists']:
        if verbose:
            print(f"⚠️  ASIN {asin} ya publicado:")
            print(f"   Item ID: {asin_check['item_id']}")
            print(f"   Título: {asin_check['title'][:60]}...")
            print(f"   Fecha: {asin_check['date_published']}")

        return {
            'is_duplicate': True,
            'reason': 'asin',
            'existing_asin': asin,
            'existing_item_id': asin_check['item_id'],
            'existing_title': asin_check['title'],
            'date_published': asin_check['date_published']
        }

    # 2. Verificar por GTIN (mismo producto físico, diferente ASIN)
    if gtin:
        gtin_check = check_gtin_exists(gtin)
        if gtin_check['exists']:
            if verbose:
                print(f"⚠️  Producto con GTIN {gtin} ya publicado (ASIN diferente):")
                print(f"   ASIN existente: {gtin_check['asin']}")
                print(f"   ASIN nuevo: {asin}")
                print(f"   Item ID: {gtin_check['item_id']}")
                print(f"   Título: {gtin_check['title'][:60]}...")
                print(f"   → Es el mismo producto físico, ASIN diferente (variante/distribuidor)")

            return {
                'is_duplicate': True,
                'reason': 'gtin',
                'existing_asin': gtin_check['asin'],
                'existing_item_id': gtin_check['item_id'],
                'existing_title': gtin_check['title'],
                'date_published': gtin_check['date_published']
            }

    # No es duplicado
    return {
        'is_duplicate': False,
        'reason': None,
        'existing_asin': None,
        'existing_item_id': None,
        'existing_title': None,
        'date_published': None
    }


def check_brand_from_mini_ml(asin: str, verbose: bool = False) -> dict:
    """
    Verifica si un producto tiene marca prohibida leyendo desde el mini_ml.

    Args:
        asin: ASIN del producto
        verbose: Si es True, imprime detalles

    Returns:
        dict: {
            'is_blocked': bool,
            'brand': str o None,
            'matched_brand': str o None
        }
    """
    # Buscar el mini_ml del ASIN
    mini_ml_path = Path("storage/logs/publish_ready") / f"{asin}_mini_ml.json"

    if not mini_ml_path.exists():
        # Si no hay mini_ml, no podemos verificar marca aún
        return {'is_blocked': False, 'brand': None, 'matched_brand': None}

    try:
        with open(mini_ml_path, 'r', encoding='utf-8') as f:
            mini_ml = json.load(f)

        brand = mini_ml.get('brand', '')
        if not brand:
            return {'is_blocked': False, 'brand': None, 'matched_brand': None}

        check = is_brand_blocked(brand, verbose=verbose)
        return {
            'is_blocked': check['is_blocked'],
            'brand': brand,
            'matched_brand': check['matched_brand']
        }

    except Exception as e:
        if verbose:
            print(f"⚠️  Error verificando marca para {asin}: {e}")
        return {'is_blocked': False, 'brand': None, 'matched_brand': None}


def filter_asins_batch(asins: list, verbose: bool = True) -> dict:
    """
    Filtra una lista de ASINs, separando nuevos de duplicados.

    Args:
        asins: Lista de ASINs a verificar
        verbose: Si es True, imprime resumen

    Returns:
        dict: {
            'new_asins': list,  # ASINs que no están en la BD
            'duplicate_asins': list,  # ASINs que ya fueron publicados
            'stats': {
                'total': int,
                'new': int,
                'duplicate_by_asin': int,
                'duplicate_by_gtin': int
            }
        }
    """

    init_database()

    new_asins = []
    duplicate_asins = []
    dup_by_asin = 0
    dup_by_gtin = 0

    if verbose:
        print(f"\n🔍 Verificando {len(asins)} ASINs contra la base de datos...\n")

    for asin in asins:
        asin = asin.strip().upper()
        if not asin:
            continue

        # Por ahora solo verificamos por ASIN (GTIN lo verificaremos durante el procesamiento)
        check = check_asin_exists(asin)

        if check['exists']:
            duplicate_asins.append(asin)
            dup_by_asin += 1
            if verbose:
                print(f"⏭️  {asin}: Ya publicado → {check['item_id']}")
        else:
            new_asins.append(asin)
            if verbose:
                print(f"✅ {asin}: Nuevo producto")

    stats = {
        'total': len(asins),
        'new': len(new_asins),
        'duplicate_by_asin': dup_by_asin,
        'duplicate_by_gtin': dup_by_gtin
    }

    if verbose:
        print(f"\n" + "="*60)
        print(f"📊 RESUMEN DE VERIFICACIÓN")
        print(f"="*60)
        print(f"  Total ASINs: {stats['total']}")
        print(f"  ✅ Nuevos: {stats['new']}")
        print(f"  ⏭️  Duplicados (mismo ASIN): {stats['duplicate_by_asin']}")
        print(f"="*60 + "\n")

    return {
        'new_asins': new_asins,
        'duplicate_asins': duplicate_asins,
        'stats': stats
    }


# -------------------------------------------------------------
# 🧪 Test directo
# -------------------------------------------------------------

if __name__ == "__main__":
    # Test básico
    print("🧪 Test del sistema de detección de duplicados\n")

    # Leer algunos ASINs del archivo asins.txt
    asins_file = Path("asins.txt")
    if asins_file.exists():
        with open(asins_file, 'r') as f:
            test_asins = [line.strip() for line in f.readlines()[:10]]

        result = filter_asins_batch(test_asins, verbose=True)

        print(f"\n✅ Test completado")
        print(f"   Nuevos: {len(result['new_asins'])}")
        print(f"   Duplicados: {len(result['duplicate_asins'])}")
    else:
        print("⚠️  No se encontró asins.txt para testing")
