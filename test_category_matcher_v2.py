#!/usr/bin/env python3
"""
Test Category Matcher v2 con ASINs reales del proyecto
Genera reporte de resultados para cada producto
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from category_matcher_v2 import CategoryMatcherV2


def load_asin_data(asin: str) -> Dict:
    """Carga datos de un ASIN desde el JSON"""
    json_path = Path(f"storage/asins_json/{asin}.json")

    if not json_path.exists():
        print(f"⚠️  Archivo no encontrado: {json_path}")
        return None

    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def transform_to_product_data(asin_data: Dict) -> Dict:
    """
    Transforma el JSON de Amazon SP API al formato que espera category_matcher_v2
    """
    product = {
        'asin': asin_data.get('asin', ''),
        'title': '',
        'description': '',
        'brand': '',
        'features': [],
        'productType': None,
        'browseClassification': None,
        'item_type_keyword': None
    }

    # Extraer título
    if 'attributes' in asin_data and 'item_name' in asin_data['attributes']:
        item_names = asin_data['attributes']['item_name']
        if item_names and len(item_names) > 0:
            product['title'] = item_names[0].get('value', '')

    # Fallback a summaries
    if not product['title'] and 'summaries' in asin_data:
        summaries = asin_data['summaries']
        if summaries and len(summaries) > 0:
            product['title'] = summaries[0].get('itemName', '')

    # Extraer marca
    if 'attributes' in asin_data and 'brand' in asin_data['attributes']:
        brands = asin_data['attributes']['brand']
        if brands and len(brands) > 0:
            product['brand'] = brands[0].get('value', '')

    # Fallback a summaries
    if not product['brand'] and 'summaries' in asin_data:
        summaries = asin_data['summaries']
        if summaries and len(summaries) > 0:
            product['brand'] = summaries[0].get('brand', '')

    # Extraer bullet points (características)
    if 'attributes' in asin_data and 'bullet_point' in asin_data['attributes']:
        bullet_points = asin_data['attributes']['bullet_point']
        product['features'] = [bp.get('value', '') for bp in bullet_points if bp.get('value')]

    # Extraer productType
    if 'productTypes' in asin_data:
        product_types = asin_data['productTypes']
        if product_types and len(product_types) > 0:
            product['productType'] = product_types[0].get('productType', '')

    # Extraer browseClassification
    if 'summaries' in asin_data:
        summaries = asin_data['summaries']
        if summaries and len(summaries) > 0:
            browse_class = summaries[0].get('browseClassification', {})
            if browse_class:
                product['browseClassification'] = browse_class.get('displayName', '')

    # Extraer item_type_keyword
    if 'attributes' in asin_data and 'item_type_keyword' in asin_data['attributes']:
        item_type = asin_data['attributes']['item_type_keyword']
        if item_type and len(item_type) > 0:
            product['item_type_keyword'] = item_type[0].get('value', '')

    # Construir descripción desde features
    if product['features']:
        product['description'] = ' '.join(product['features'][:3])  # Primeras 3 features

    return product


def test_all_asins():
    """Prueba category_matcher_v2 con todos los ASINs disponibles"""

    print("\n" + "="*80)
    print("🧪 TEST CATEGORY MATCHER V2 - ASINs Reales")
    print("="*80 + "\n")

    # Obtener lista de ASINs
    asins_dir = Path("storage/asins_json")
    asin_files = sorted(asins_dir.glob("*.json"))
    asins = [f.stem for f in asin_files]

    print(f"📦 {len(asins)} ASINs encontrados: {', '.join(asins)}\n")

    # Inicializar matcher
    print("🚀 Inicializando Category Matcher v2...\n")
    matcher = CategoryMatcherV2()

    # Resultados
    results = []

    # Procesar cada ASIN
    for i, asin in enumerate(asins, 1):
        print("\n" + "─"*80)
        print(f"[{i}/{len(asins)}] Procesando ASIN: {asin}")
        print("─"*80)

        # Cargar datos
        asin_data = load_asin_data(asin)
        if not asin_data:
            continue

        # Transformar a formato de producto
        product = transform_to_product_data(asin_data)

        print(f"📝 Título: {product['title'][:80]}...")
        print(f"🏷️  Marca: {product['brand']}")
        if product['productType']:
            print(f"📦 ProductType: {product['productType']}")
        if product['browseClassification']:
            print(f"🌳 Browse: {product['browseClassification']}")

        # Ejecutar matcher
        try:
            result = matcher.find_category(product, top_k=30, use_ai=True)

            # Agregar ASIN al resultado
            result['asin'] = asin
            result['product_title'] = product['title']
            result['product_brand'] = product['brand']
            result['productType'] = product['productType']
            result['browseClassification'] = product['browseClassification']

            results.append(result)

        except Exception as e:
            print(f"❌ Error procesando {asin}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Generar reporte
    print("\n\n" + "="*80)
    print("📊 REPORTE DE RESULTADOS")
    print("="*80 + "\n")

    # Tabla resumen
    print(f"{'ASIN':<15} {'Categoría':<10} {'Nombre Categoría':<35} {'Conf':<6} {'Método':<15}")
    print("─"*90)

    for r in results:
        cat_name = r['category_name'][:33] if r['category_name'] else 'N/A'
        conf = f"{r['confidence']:.2f}" if r['confidence'] else 'N/A'
        print(f"{r['asin']:<15} {r['category_id']:<10} {cat_name:<35} {conf:<6} {r['method']:<15}")

    print("\n")

    # Detalles de cada resultado
    print("="*80)
    print("📋 DETALLES POR PRODUCTO")
    print("="*80 + "\n")

    for r in results:
        print(f"\n{'─'*80}")
        print(f"ASIN: {r['asin']}")
        print(f"Título: {r['product_title'][:70]}...")
        print(f"Marca: {r['product_brand']}")
        if r.get('productType'):
            print(f"ProductType (Amazon): {r['productType']}")
        if r.get('browseClassification'):
            print(f"Browse (Amazon): {r['browseClassification']}")
        print(f"\n✅ RESULTADO:")
        print(f"   Categoría: {r['category_id']} - {r['category_name']}")
        print(f"   Path: {r['category_path']}")
        print(f"   Confianza: {r['confidence']:.2f}")
        print(f"   Método: {r['method']}")
        if r.get('reasoning'):
            print(f"   Razonamiento: {r['reasoning'][:200]}...")
        print(f"   Tiempo: {r['processing_time_ms']:.0f}ms")
        if r.get('embedding_similarity_top1'):
            print(f"   Similitud embedding: {r['embedding_similarity_top1']:.3f}")

    # Guardar reporte JSON
    report_path = Path("storage/reports/category_matcher_v2_test_results.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        'timestamp': datetime.now().isoformat(),
        'total_asins': len(asins),
        'successful': len(results),
        'failed': len(asins) - len(results),
        'results': results
    }

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n\n💾 Reporte guardado en: {report_path}")

    # Estadísticas
    print("\n" + "="*80)
    print("📈 ESTADÍSTICAS")
    print("="*80)
    print(f"Total ASINs procesados: {len(results)}/{len(asins)}")

    methods = {}
    for r in results:
        method = r['method']
        methods[method] = methods.get(method, 0) + 1

    print(f"\nMétodos utilizados:")
    for method, count in methods.items():
        print(f"  {method}: {count}")

    avg_confidence = sum(r['confidence'] for r in results) / len(results) if results else 0
    avg_time = sum(r['processing_time_ms'] for r in results) / len(results) if results else 0

    print(f"\nConfianza promedio: {avg_confidence:.2f}")
    print(f"Tiempo promedio: {avg_time:.0f}ms")

    print("\n" + "="*80)
    print("✅ TEST COMPLETADO")
    print("="*80 + "\n")

    return results


if __name__ == "__main__":
    test_all_asins()
