#!/usr/bin/env python3
"""
Prueba Category Matcher v2 con todos los ASINs
Compara categorías detectadas vs categorías actuales
"""

import json
import sys
from pathlib import Path
from typing import Dict, List
import time

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from category_matcher_v2 import CategoryMatcherV2


def load_asin_data(asin: str) -> Dict:
    """
    Carga datos del ASIN combinando JSON original de SP API + _mini_ml.json
    Prioriza el título ORIGINAL de SP API sobre el generado por IA
    """
    # Cargar JSON original de SP API (para título original)
    sp_api_file = Path(f"storage/asins_json/{asin}.json")
    sp_api_data = None

    if sp_api_file.exists():
        with open(sp_api_file, 'r', encoding='utf-8') as f:
            sp_api_data = json.load(f)

    # Cargar archivo procesado _mini_ml.json (para categoría actual y otros datos)
    mini_ml_file = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")
    mini_ml_data = None

    if mini_ml_file.exists():
        with open(mini_ml_file, 'r', encoding='utf-8') as f:
            mini_ml_data = json.load(f)

    # Si tenemos ambos, combinar con prioridad a SP API para el título
    if sp_api_data and mini_ml_data:
        # Extraer título original de SP API
        original_title = None
        if 'summaries' in sp_api_data and sp_api_data['summaries']:
            original_title = sp_api_data['summaries'][0].get('itemName', '')
        elif 'attributes' in sp_api_data and 'item_name' in sp_api_data['attributes']:
            item_names = sp_api_data['attributes']['item_name']
            if item_names and isinstance(item_names, list):
                original_title = item_names[0].get('value', '')

        # Extraer bullet points originales como features
        original_features = []
        if 'attributes' in sp_api_data and 'bullet_point' in sp_api_data['attributes']:
            bullets = sp_api_data['attributes']['bullet_point']
            original_features = [b.get('value', '') for b in bullets if 'value' in b]

        # Extraer productType de SP API
        product_type = None
        if 'productTypes' in sp_api_data and sp_api_data['productTypes']:
            product_type = sp_api_data['productTypes'][0].get('productType')

        # Extraer browseClassification
        browse_classification = None
        if 'summaries' in sp_api_data and sp_api_data['summaries']:
            browse_class = sp_api_data['summaries'][0].get('browseClassification', {})
            browse_classification = browse_class.get('displayName')

        # Extraer item_type_keyword
        item_type_keyword = None
        if 'attributes' in sp_api_data and 'item_type_keyword' in sp_api_data['attributes']:
            item_keywords = sp_api_data['attributes']['item_type_keyword']
            if item_keywords and isinstance(item_keywords, list):
                item_type_keyword = item_keywords[0].get('value')

        # Combinar: usar título original + marca de SP API + datos de mini_ml + hints
        combined = mini_ml_data.copy()
        combined['title_original'] = original_title or mini_ml_data.get('title_ai', '')
        combined['brand_original'] = sp_api_data.get('summaries', [{}])[0].get('brand', mini_ml_data.get('brand', ''))
        combined['features_original'] = original_features if original_features else mini_ml_data.get('main_characteristics', [])

        # Agregar hints de SP API
        combined['productType'] = product_type
        combined['browseClassification'] = browse_classification
        combined['item_type_keyword'] = item_type_keyword

        return combined

    # Solo tenemos uno de los dos archivos
    if mini_ml_data:
        return mini_ml_data

    if sp_api_data:
        return sp_api_data

    return None


def get_current_category(asin_data: Dict) -> Dict:
    """Obtiene la categoría actual del producto"""
    # El archivo _mini_ml.json ya tiene la estructura plana
    return {
        'category_id': asin_data.get('category_id'),
        'category_name': asin_data.get('category_name'),
        'category_path': asin_data.get('category_path')
    }


def build_product_summary(asin_data: Dict) -> str:
    """Construye resumen del producto para mostrar (usando título ORIGINAL)"""
    # Priorizar título original de SP API sobre el generado por IA
    title = asin_data.get('title_original', asin_data.get('title_ai', 'Sin título'))[:60]
    brand = asin_data.get('brand_original', asin_data.get('brand', 'N/A'))

    return f"{title}... | Brand: {brand}"


def main():
    print("=" * 100)
    print("🔍 PRUEBA DE CATEGORY MATCHER V2 - TODOS LOS ASINS")
    print("=" * 100)

    # Cargar ASINs
    asins_file = Path("resources/asins.txt")
    with open(asins_file, 'r') as f:
        asins = [line.strip() for line in f if line.strip()]

    print(f"\n📦 {len(asins)} productos a analizar\n")

    # Inicializar Category Matcher v2
    print("🚀 Inicializando Category Matcher v2...")
    matcher = CategoryMatcherV2()
    print("✅ Listo\n")

    results = []
    errors = []

    for i, asin in enumerate(asins, 1):
        print(f"\n{'=' * 100}")
        print(f"[{i}/{len(asins)}] ASIN: {asin}")
        print("=" * 100)

        # Cargar datos del ASIN
        asin_data = load_asin_data(asin)
        if not asin_data:
            print(f"❌ No se encontró JSON para {asin}")
            errors.append({'asin': asin, 'error': 'JSON no encontrado'})
            continue

        # Mostrar info del producto
        product_summary = build_product_summary(asin_data)
        print(f"📦 Producto: {product_summary}")

        # Obtener categoría actual
        current_cat = get_current_category(asin_data)
        print(f"\n📂 CATEGORÍA ACTUAL:")
        print(f"   ID: {current_cat['category_id']}")
        print(f"   Nombre: {current_cat['category_name']}")
        print(f"   Path: {current_cat.get('category_path', 'N/A')}")

        # Detectar categoría con v2
        print(f"\n🤖 Detectando categoría con Category Matcher v2...")
        start = time.time()

        try:
            # Preparar datos del producto usando TÍTULO ORIGINAL de SP API + HINTS
            product_data = {
                'title': asin_data.get('title_original', asin_data.get('title_ai', '')),  # PRIORIDAD: título original
                'brand': asin_data.get('brand_original', asin_data.get('brand', '')),  # PRIORIDAD: marca original
                'features': asin_data.get('features_original', asin_data.get('main_characteristics', [])),  # PRIORIDAD: bullets originales
                'description': asin_data.get('description_ai', ''),  # Descripción generada está OK
                'characteristics': {
                    'main': asin_data.get('main_characteristics', []),
                    'second': asin_data.get('second_characteristics', [])
                },
                # HINTS DE SP API
                'productType': asin_data.get('productType'),
                'browseClassification': asin_data.get('browseClassification'),
                'item_type_keyword': asin_data.get('item_type_keyword')
            }

            # Detectar categoría
            detected = matcher.find_category(product_data, top_k=10, use_ai=True)
            elapsed = time.time() - start

            print(f"\n✅ CATEGORÍA DETECTADA (en {elapsed:.2f}s):")
            print(f"   ID: {detected['category_id']}")
            print(f"   Nombre: {detected['category_name']}")
            print(f"   Path: {detected.get('category_path', 'N/A')}")
            print(f"   Confianza: {detected['confidence']:.2f}")
            print(f"   Método: {detected['method']}")
            print(f"   Razonamiento: {detected.get('reasoning', 'N/A')[:200]}...")

            # Comparar
            match = current_cat['category_id'] == detected['category_id']
            match_symbol = "✅" if match else "⚠️"

            print(f"\n{match_symbol} COMPARACIÓN:")
            if match:
                print(f"   Las categorías COINCIDEN")
            else:
                print(f"   Las categorías son DIFERENTES")
                print(f"   Actual: {current_cat['category_id']} ({current_cat['category_name']})")
                print(f"   Detectada: {detected['category_id']} ({detected['category_name']})")

            results.append({
                'asin': asin,
                'product': product_summary,
                'current': current_cat,
                'detected': detected,
                'match': match,
                'time': elapsed
            })

        except Exception as e:
            print(f"\n❌ ERROR al detectar categoría: {e}")
            import traceback
            traceback.print_exc()
            errors.append({'asin': asin, 'error': str(e)})

    # Resumen final
    print("\n" + "=" * 100)
    print("📊 RESUMEN FINAL")
    print("=" * 100)

    total = len(results)
    matches = sum(1 for r in results if r['match'])
    different = total - matches

    print(f"\n✅ Productos analizados: {total}")
    if total > 0:
        print(f"✅ Categorías que coinciden: {matches} ({matches/total*100:.1f}%)")
        print(f"⚠️  Categorías diferentes: {different} ({different/total*100:.1f}%)")
    else:
        print(f"✅ Categorías que coinciden: {matches}")
        print(f"⚠️  Categorías diferentes: {different}")
    print(f"❌ Errores: {len(errors)}")

    if different > 0:
        print(f"\n{'=' * 100}")
        print("⚠️  PRODUCTOS CON CATEGORÍAS DIFERENTES:")
        print("=" * 100)

        for r in results:
            if not r['match']:
                print(f"\n🔸 {r['asin']} - {r['product']}")
                print(f"   Actual:    {r['current']['category_id']} - {r['current']['category_name']}")
                print(f"   Detectada: {r['detected']['category_id']} - {r['detected']['category_name']}")
                print(f"   Confianza: {r['detected']['confidence']:.2f}")
                print(f"   Razonamiento: {r['detected'].get('reasoning', 'N/A')[:150]}...")

    if errors:
        print(f"\n{'=' * 100}")
        print("❌ ERRORES:")
        print("=" * 100)
        for err in errors:
            print(f"   {err['asin']}: {err['error']}")

    # Guardar reporte
    report = {
        'total_products': len(asins),
        'analyzed': total,
        'matches': matches,
        'different': different,
        'errors': len(errors),
        'results': results,
        'errors_detail': errors
    }

    report_file = Path("storage/logs/category_matcher_v2_test_report.json")
    report_file.parent.mkdir(parents=True, exist_ok=True)

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Reporte guardado en: {report_file}")
    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
