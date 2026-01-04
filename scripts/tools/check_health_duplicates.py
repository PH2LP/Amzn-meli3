#!/usr/bin/env python3
"""
Script para verificar el health de items locales duplicados.
Consulta la API de ML para obtener el estado real de salud de cada item.
"""

import requests
import os
import time
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

load_dotenv()

ML_ACCESS_TOKEN = os.getenv('ML_ACCESS_TOKEN')

def get_item_health(local_id):
    """
    Obtiene la info de salud de un item local (MLA, MLB, MLM, etc).
    """
    url = f"https://api.mercadolibre.com/items/{local_id}"
    headers = {'Authorization': f'Bearer {ML_ACCESS_TOKEN}'}

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return {
                'local_id': local_id,
                'status': data.get('status'),
                'health': data.get('health'),
                'sub_status': data.get('sub_status', []),
                'catalog_listing': data.get('catalog_listing'),
                'qty': data.get('available_quantity', 0),
                'success': True
            }
        else:
            return {'local_id': local_id, 'success': False, 'error': response.status_code}
    except Exception as e:
        return {'local_id': local_id, 'success': False, 'error': str(e)}

def main():
    """
    Lee los archivos de duplicados y consulta health de cada uno.
    """
    if not ML_ACCESS_TOKEN:
        print("❌ Error: ML_ACCESS_TOKEN no encontrado en .env")
        return

    countries = ['MLA', 'MLB', 'MLM', 'MCO', 'MLC']

    for country in countries:
        input_file = f'duplicados_{country}_con_estado.txt'
        output_file = f'duplicados_{country}_CON_HEALTH.txt'

        if not os.path.exists(input_file):
            continue

        print(f"\n{'='*80}")
        print(f"🔍 Procesando {country}...")
        print(f"{'='*80}")

        # Leer archivo de duplicados
        local_ids = []
        lines_data = []

        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    lines_data.append({'type': 'comment', 'line': line})
                    continue

                parts = line.strip().split('\t')
                if len(parts) >= 5:
                    local_id = parts[0]
                    local_ids.append(local_id)
                    lines_data.append({
                        'type': 'item',
                        'local_id': local_id,
                        'cbt_id': parts[1],
                        'asin': parts[2],
                        'status': parts[3],
                        'qty': parts[4],
                        'action': parts[5] if len(parts) > 5 else ''
                    })

        print(f"   📋 Items a verificar: {len(local_ids)}")

        # Consultar health en paralelo
        health_data = {}

        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = {executor.submit(get_item_health, local_id): local_id for local_id in local_ids}

            completed = 0
            for future in as_completed(futures):
                result = future.result()
                completed += 1

                if result['success']:
                    health_data[result['local_id']] = result
                    health_str = result.get('health') or 'null'
                    sub_status = result.get('sub_status', [])
                    sub_str = ', '.join(sub_status) if sub_status else ''
                    print(f"   ✅ [{completed}/{len(local_ids)}] {result['local_id']}: {result['status']}, health={health_str}, sub={sub_str}")
                else:
                    print(f"   ❌ [{completed}/{len(local_ids)}] {result['local_id']}: Error")

                # Delay cada 50 items
                if completed % 50 == 0:
                    time.sleep(1)

        # Generar archivo de salida con health
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f'# DUPLICADOS EN {country} CON HEALTH\n')
            f.write(f'# Formato: ITEM_LOCAL_ID | CBT_ID | ASIN | ESTADO | QTY | HEALTH | SUB_STATUS | ACCIÓN\n')
            f.write('#' + '='*120 + '\n\n')

            # Agrupar por ASIN
            by_asin = defaultdict(list)
            for item_data in lines_data:
                if item_data['type'] == 'item':
                    by_asin[item_data['asin']].append(item_data)

            for asin in sorted(by_asin.keys()):
                items = by_asin[asin]

                f.write(f'\n# ASIN {asin} - {len(items)} listings en {country}\n')

                # Ordenar por health/status
                items_with_health = []
                for item in items:
                    local_id = item['local_id']
                    health_info = health_data.get(local_id, {})

                    item['health'] = health_info.get('health')
                    item['sub_status_list'] = health_info.get('sub_status', [])
                    item['actual_status'] = health_info.get('status', item['status'])
                    items_with_health.append(item)

                # Ordenar: sin problemas primero
                items_sorted = sorted(items_with_health, key=lambda x: (
                    0 if x['health'] is None and x['actual_status'] == 'active' and int(x['qty']) > 0 else
                    1 if x['actual_status'] == 'active' and int(x['qty']) > 0 else
                    2 if len(x['sub_status_list']) > 0 else
                    3 if x['actual_status'] == 'paused' else
                    4
                ))

                for i, item in enumerate(items_sorted, 1):
                    health_str = item.get('health') or 'null'
                    sub_status_str = ', '.join(item['sub_status_list']) if item['sub_status_list'] else ''

                    # Decidir acción basado en health
                    if i == 1 and item['actual_status'] == 'active' and int(item['qty']) > 0 and not item['sub_status_list']:
                        action = '✅ MANTENER (activo, sin problemas)'
                    elif item['sub_status_list'] or item['health'] is not None:
                        action = f'❌ ELIMINAR (problemas: {sub_status_str or health_str})'
                    elif item['actual_status'] == 'paused' or int(item['qty']) == 0:
                        action = '❌ ELIMINAR (pausado/sin stock)'
                    elif item['actual_status'] == 'active' and int(item['qty']) > 0:
                        action = '⚠️  REVISAR (también activo sin problemas)'
                    else:
                        action = '❌ ELIMINAR'

                    f.write(f"{item['local_id']}\t{item['cbt_id']}\t{item['asin']}\t{item['actual_status']}\t{item['qty']}\t{health_str}\t{sub_status_str}\t{action}\n")

        print(f"\n✅ {country}: {output_file}")

if __name__ == "__main__":
    main()
