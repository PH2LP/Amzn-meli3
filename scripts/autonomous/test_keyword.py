#!/usr/bin/env python3
"""
Test de Keyword - Modo Seguro
NO publica nada, solo muestra resultados
"""

import sys
import json
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from scripts.autonomous.autonomous_search_and_publish import AutonomousSystem

def test_keyword(keyword, pages=50, top_n=100, only_prime=True, output_file=None):
    """
    Prueba una keyword SIN publicar

    Args:
        keyword: Keyword a probar
        pages: Páginas a buscar en Amazon
        top_n: Cantidad de ASINs a retornar (TÚ decides)
        only_prime: Filtrar solo Prime
        output_file: Archivo JSON para guardar resultados
    """

    print(f"\n{'='*60}")
    print(f"🧪 TEST MODE - Keyword: {keyword}")
    print(f"{'='*60}\n")
    print(f"📊 Configuración:")
    print(f"   Páginas a buscar: {pages}")
    print(f"   Top N a retornar: {top_n}")
    print(f"   Solo Prime: {only_prime}")
    print(f"\n⚠️  MODO SEGURO: NO publicará nada\n")

    # Crear sistema autónomo
    system = AutonomousSystem()

    # 1. Buscar ASINs en Amazon
    print(f"[1/4] 🔍 Buscando ASINs en Amazon...")

    keyword_data = {
        "keyword": keyword,
        "initial_search_pages": pages,
        "genericity": "specific"
    }

    # Buscar ASINs (incluye filtros de marcas y Prime)
    asins = system.search_asins_for_keyword(keyword_data)

    print(f"   ✅ {len(asins)} ASINs encontrados después de filtros")

    if not asins:
        print(f"\n❌ No se encontraron ASINs para '{keyword}'")
        return {
            'success': False,
            'message': 'No se encontraron ASINs',
            'total_found': 0,
            'after_filters': 0,
            'final_count': 0,
            'top_asins': [],
            'rejected': []
        }

    # 2. Ordenar por BSR si hay más de top_n
    print(f"\n[2/4] 📊 Ordenando por BSR...")

    if len(asins) > top_n:
        print(f"   Procesando {len(asins)} ASINs para ordenar por BSR...")
        final_asins = system.rank_asins_by_bsr(asins, top_n=top_n)
    else:
        print(f"   Solo hay {len(asins)} ASINs, tomando todos")
        final_asins = asins[:top_n]

    print(f"   ✅ Top {len(final_asins)} ASINs seleccionados")

    # 3. Obtener detalles de los top ASINs
    print(f"\n[3/4] 📦 Obteniendo detalles de ASINs...")

    from integrations.amazon_api import get_product_data_from_asin, get_product_bsr_only

    top_asins_details = []

    for i, asin in enumerate(final_asins[:20], 1):  # Limitar a 20 para detalles completos
        try:
            print(f"   {i}/20: {asin}...", end="")

            # Obtener datos básicos
            data = get_product_data_from_asin(asin)

            if data:
                bsr = get_product_bsr_only(asin)

                top_asins_details.append({
                    'asin': asin,
                    'title': data.get('title', 'N/A'),
                    'price': data.get('price', 'N/A'),
                    'bsr': bsr,
                    'brand': data.get('brand', 'N/A'),
                    'category': data.get('category', 'N/A')
                })

                print(f" ✅")
            else:
                print(f" ⚠️ Sin datos")

        except Exception as e:
            print(f" ❌ Error: {e}")
            continue

    # 4. Preparar resultados
    print(f"\n[4/4] 📋 Preparando resultados...\n")

    results = {
        'success': True,
        'keyword': keyword,
        'total_found': len(asins),
        'after_filters': len(asins),
        'final_count': len(final_asins),
        'top_asins': top_asins_details,
        'all_asins': final_asins,  # Todos los ASINs (solo IDs)
        'config': {
            'pages': pages,
            'top_n': top_n,
            'only_prime': only_prime
        }
    }

    # Guardar en archivo si se especificó
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"💾 Resultados guardados en: {output_file}\n")

    # Mostrar resumen
    print(f"{'='*60}")
    print(f"✅ TEST COMPLETADO")
    print(f"{'='*60}")
    print(f"\n📊 Resumen:")
    print(f"   ASINs encontrados: {results['total_found']}")
    print(f"   Después de filtros: {results['after_filters']}")
    print(f"   Top N seleccionados: {results['final_count']}")
    print(f"\n🏆 Top 10 ASINs por BSR:")

    for i, asin_data in enumerate(results['top_asins'][:10], 1):
        bsr = asin_data.get('bsr', 'N/A')
        title = asin_data.get('title', 'N/A')[:50]
        print(f"   {i}. {asin_data['asin']} - BSR #{bsr} - {title}...")

    print(f"\n⚠️  RECUERDA: Esto es solo un TEST, NO se publicó nada\n")

    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test de keyword sin publicar')
    parser.add_argument('--keyword', required=True, help='Keyword a probar')
    parser.add_argument('--pages', type=int, default=50, help='Páginas a buscar')
    parser.add_argument('--top-n', type=int, default=100, help='Top N ASINs a retornar')
    parser.add_argument('--only-prime', action='store_true', default=True, help='Solo Prime')
    parser.add_argument('--no-prime', action='store_false', dest='only_prime', help='Incluir no-Prime')
    parser.add_argument('--output', help='Archivo JSON para guardar resultados')

    args = parser.parse_args()

    try:
        results = test_keyword(
            keyword=args.keyword,
            pages=args.pages,
            top_n=args.top_n,
            only_prime=args.only_prime,
            output_file=args.output
        )

        sys.exit(0 if results['success'] else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrumpido por usuario\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}\n")
        sys.exit(1)
