#!/usr/bin/env python3
"""Regenerar mini_ml para los 3 ASINs fallidos"""

import sys
sys.path.insert(0, '.')
from src.transform_mapper_new import build_mini_ml, load_json_file, save_json_file
from pathlib import Path

ASINS = ['B0DRW6GDXN', 'B0CMQ85FPB', 'B0FC5FJZ9Z']

def regenerate_asin(asin: str):
    print('=' * 70)
    print(f'REGENERANDO: {asin}')
    print('=' * 70)

    try:
        # Cargar JSON de Amazon
        amazon_path = Path(f'storage/asins_json/{asin}.json')
        if not amazon_path.exists():
            print(f'❌ No existe {amazon_path}')
            return None

        amazon_json = load_json_file(str(amazon_path))

        # Info básica
        title = amazon_json.get('attributes', {}).get('item_name', [{}])[0].get('value', 'N/A')
        brand = amazon_json.get('summaries', [{}])[0].get('brand', 'N/A')
        price_info = amazon_json.get('attributes', {}).get('list_price', [{}])[0]
        price = price_info.get('value', 0) if price_info else 0

        print(f'\n📦 Producto:')
        print(f'   Título: {title[:60]}...')
        print(f'   Marca: {brand}')
        print(f'   Precio: ${price}')

        # Generar mini_ml
        print(f'\n🔧 Generando mini_ml...')
        mini_ml = build_mini_ml(amazon_json)

        if not mini_ml:
            print(f'❌ build_mini_ml retornó None')
            return None

        # Validar campos críticos
        category_id = mini_ml.get('category_id')
        category_name = mini_ml.get('category_name')
        confidence = mini_ml.get('category_similarity', 0)
        title_ai = mini_ml.get('title_ai', '')
        price_final = mini_ml.get('price', {}).get('net_proceeds_usd')
        attrs = len(mini_ml.get('attributes_mapped', {}))
        images = len(mini_ml.get('images', []))
        gtins = mini_ml.get('gtins', [])

        print(f'\n✅ Mini ML generado:')
        print(f'   Categoría: {category_id} - {category_name}')
        print(f'   Confianza: {confidence:.2f}')
        print(f'   Título: {title_ai[:60]}...')
        print(f'   Precio final: ${price_final}')
        print(f'   Atributos: {attrs}')
        print(f'   Imágenes: {images}')
        print(f'   GTINs: {gtins}')

        # Validaciones
        issues = []
        if not category_id or category_id == 'CBT1157':
            issues.append(f'❌ Categoría incorrecta o genérica: {category_id}')
        if confidence < 0.7:
            issues.append(f'⚠️  Confianza baja: {confidence:.2f}')
        if not title_ai:
            issues.append('❌ Sin título')
        if not price_final or price_final < 1:
            issues.append(f'❌ Precio inválido: ${price_final}')
        if attrs < 5:
            issues.append(f'⚠️  Pocos atributos: {attrs}')
        if images < 1:
            issues.append(f'❌ Sin imágenes: {images}')
        if not gtins:
            issues.append('⚠️  Sin GTIN (puede fallar en algunos países)')

        if issues:
            print(f'\n⚠️  PROBLEMAS DETECTADOS:')
            for issue in issues:
                print(f'   {issue}')
        else:
            print(f'\n✅ VALIDACIÓN COMPLETA: Sin problemas críticos')

        # Guardar
        output_path = Path(f'storage/logs/publish_ready/{asin}_mini_ml.json')
        save_json_file(str(output_path), mini_ml)
        print(f'\n💾 Guardado en: {output_path}')
        print(f'   Tamaño: {output_path.stat().st_size / 1024:.1f} KB')

        return {
            'asin': asin,
            'success': True,
            'category': f'{category_id} - {category_name}',
            'confidence': confidence,
            'issues': issues
        }

    except Exception as e:
        print(f'\n❌ ERROR: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        return {
            'asin': asin,
            'success': False,
            'error': str(e)
        }

if __name__ == '__main__':
    print('=' * 70)
    print('REGENERACIÓN DE MINI_ML PARA 3 ASINs FALLIDOS')
    print('=' * 70)

    results = []
    for asin in ASINS:
        result = regenerate_asin(asin)
        if result:
            results.append(result)
        print('\n')

    # Resumen final
    print('=' * 70)
    print('RESUMEN FINAL')
    print('=' * 70)

    for r in results:
        status = '✅' if r['success'] else '❌'
        print(f'\n{status} {r["asin"]}')
        if r['success']:
            print(f'   Categoría: {r["category"]}')
            print(f'   Confianza: {r["confidence"]:.2f}')
            if r['issues']:
                print(f'   Issues: {len(r["issues"])}')
                for issue in r['issues']:
                    print(f'     {issue}')
        else:
            print(f'   Error: {r.get("error", "Unknown")}')

    success_count = sum(1 for r in results if r['success'])
    print(f'\n📊 Total: {success_count}/{len(results)} exitosos')
