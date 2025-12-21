#!/usr/bin/env python3
"""
Script para obtener todos los items de un vendedor de MercadoLibre

Uso:
    python3 get_seller_items.py <seller_id> <site_code>

    seller_id: ID numérico del vendedor (ej: 1234567890)
    site_code: MLA (Argentina), MLB (Brasil), MLM (México), MLC (Chile), MCO (Colombia)

Ejemplo:
    python3 get_seller_items.py 1234567890 MLA
"""

import requests
import json
import sys
import time
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


def get_ml_headers():
    """Obtener headers básicos para las requests"""
    # El search API de ML NO requiere autenticación
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'es-AR,es;q=0.9'
    }
    return headers


def search_seller_by_nickname(nickname, site_code='MLA'):
    """Buscar seller_id a partir del nickname"""
    print(f"🔍 Buscando vendedor: {nickname} en {site_code}...")

    url = f"https://api.mercadolibre.com/sites/{site_code}/search"
    params = {'q': nickname, 'limit': 10}
    headers = get_ml_headers()

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)

        if response.status_code != 200:
            print(f"❌ Error HTTP {response.status_code}: {response.text[:200]}")
            return None, None

        data = response.json()

        for item in data.get('results', []):
            seller = item.get('seller', {})
            if nickname.lower() in seller.get('nickname', '').lower():
                return seller.get('id'), seller.get('nickname')

        return None, None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None


def get_all_seller_items(seller_id, site_code='MLA', show_details=False):
    """Obtener todos los items de un vendedor con paginación"""
    all_items = []
    offset = 0
    limit = 50
    headers = get_ml_headers()

    print(f"\n📊 Descargando items del seller {seller_id} en {site_code}...")
    print(f"=" * 80)

    while True:
        url = f"https://api.mercadolibre.com/sites/{site_code}/search"
        params = {
            'seller_id': seller_id,
            'limit': limit,
            'offset': offset
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)

            if response.status_code != 200:
                print(f"❌ Error HTTP {response.status_code}: {response.text[:200]}")
                break

            data = response.json()

            results = data.get('results', [])
            if not results:
                break

            all_items.extend(results)

            total = data.get('paging', {}).get('total', 0)
            progress = f"{len(all_items)}/{total}"
            print(f"✅ Descargados {progress} items...")

            # Mostrar detalles de los últimos items si se solicita
            if show_details:
                for item in results[:3]:  # Solo primeros 3 de este batch
                    print(f"   • {item['id']} - {item['title'][:50]} - ${item['price']:,.0f} - {item.get('sold_quantity', 0)} ventas")

            offset += limit

            if offset >= total:
                break

            time.sleep(1)  # Rate limit más conservador

        except requests.exceptions.Timeout:
            print(f"⏱️  Timeout en offset {offset}, reintentando...")
            time.sleep(3)
            continue
        except Exception as e:
            print(f"❌ Error en offset {offset}: {e}")
            time.sleep(2)
            continue

    return all_items


def get_seller_items_all_countries(seller_id):
    """Obtener items de un seller en todos los países"""
    sites = {
        'MLA': 'Argentina',
        'MLB': 'Brasil',
        'MLM': 'México',
        'MLC': 'Chile',
        'MCO': 'Colombia'
    }

    all_data = {}

    print(f"\n🌎 Descargando items de todos los países...")
    print(f"=" * 80)

    for site_code, country in sites.items():
        print(f"\n📍 {country} ({site_code}):")
        items = get_all_seller_items(seller_id, site_code)

        if items:
            all_data[site_code] = items
            print(f"✅ {len(items)} items descargados")
        else:
            print(f"ℹ️  No hay items en este país")

    return all_data


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n💡 CÓMO OBTENER EL SELLER_ID:")
        print("=" * 80)
        print("1. Buscar por nickname:")
        print("   python3 get_seller_items.py nickname:NOCNOC-USA MLA")
        print("\n2. Desde un item:")
        print("   curl https://api.mercadolibre.com/items/MLA123456789")
        print("   # Del JSON, obtener 'seller_id'")
        print("\n3. Con seller_id conocido:")
        print("   python3 get_seller_items.py 1234567890 MLA")
        return

    arg1 = sys.argv[1]
    site_code = sys.argv[2] if len(sys.argv) > 2 else 'MLA'

    # Si el argumento empieza con "nickname:", buscar primero
    if arg1.startswith('nickname:'):
        nickname = arg1.replace('nickname:', '')
        seller_id, real_nickname = search_seller_by_nickname(nickname, site_code)

        if not seller_id:
            print(f"❌ No se encontró el vendedor '{nickname}'")
            return

        print(f"✅ Vendedor encontrado: {real_nickname} (ID: {seller_id})")
    else:
        seller_id = arg1
        print(f"🔍 Usando seller_id: {seller_id}")

    # Opción: descargar solo un país o todos
    if len(sys.argv) > 2 and sys.argv[2] != 'all':
        # Un solo país
        items = get_all_seller_items(seller_id, site_code)

        if items:
            output_file = f"seller_{seller_id}_{site_code}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(items, f, indent=2, ensure_ascii=False)

            print(f"\n✅ {len(items)} items guardados en: {output_file}")
    else:
        # Todos los países
        all_data = get_seller_items_all_countries(seller_id)

        output_file = f"seller_{seller_id}_ALL.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)

        total_items = sum(len(items) for items in all_data.values())
        print(f"\n✅ {total_items} items totales guardados en: {output_file}")


if __name__ == "__main__":
    main()
