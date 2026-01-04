#!/usr/bin/env python3
"""
Script para exportar información esencial de items de MercadoLibre.
Solo: CBT ID, estado, precio, cantidad disponible, SELLER_SKU, marketplace items.
"""

import requests
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# Cargar variables de entorno
load_dotenv()

ML_ACCESS_TOKEN = os.getenv('ML_ACCESS_TOKEN')
ML_USER_ID = os.getenv('ML_USER_ID', '2560656533')

# Session global para reusar conexiones
session = requests.Session()

def get_all_item_ids():
    """
    Obtiene todos los IDs de items usando paginación tipo scan.
    Returns: lista de item IDs
    """
    all_items = []
    scroll_id = None
    page = 0

    print(f"🔍 Obteniendo lista de items del usuario {ML_USER_ID}...")

    while True:
        page += 1

        # Primera llamada sin scroll_id, siguientes con scroll_id
        if scroll_id is None:
            url = f"https://api.mercadolibre.com/users/{ML_USER_ID}/items/search?search_type=scan&limit=100"
        else:
            url = f"https://api.mercadolibre.com/users/{ML_USER_ID}/items/search?search_type=scan&scroll_id={scroll_id}&limit=100"

        headers = {
            'Authorization': f'Bearer {ML_ACCESS_TOKEN}'
        }

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(f"❌ Error obteniendo items (página {page}): {response.status_code}")
            print(f"   Respuesta: {response.text}")
            break

        data = response.json()
        results = data.get('results', [])

        if not results:
            print(f"✅ Fin de resultados en página {page}")
            break

        all_items.extend(results)
        print(f"   📄 Página {page}: {len(results)} items obtenidos (total acumulado: {len(all_items)})")

        # Obtener scroll_id para siguiente página
        scroll_id = data.get('scroll_id', '')

        # Si scroll_id está vacío, hemos llegado al final
        if not scroll_id:
            print(f"✅ Fin de resultados (scroll_id vacío)")
            break

    print(f"\n✅ Total de items obtenidos: {len(all_items)}")
    return all_items

def get_item_details(item_ids):
    """
    Obtiene TODOS los detalles de los items usando multiget.
    Ahora sin filtro de campos para obtener información completa.
    """
    all_details = []
    batch_size = 20
    total = len(item_ids)

    print(f"\n📦 Obteniendo detalles COMPLETOS de {total} items...")

    for i in range(0, total, batch_size):
        batch = item_ids[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total + batch_size - 1) // batch_size

        ids_param = ','.join(batch)
        # Sin attributes param = trae TODA la info
        url = f"https://api.mercadolibre.com/items?ids={ids_param}"

        headers = {
            'Authorization': f'Bearer {ML_ACCESS_TOKEN}'
        }

        response = session.get(url, headers=headers)

        if response.status_code != 200:
            print(f"❌ Error obteniendo detalles del batch {batch_num}: {response.status_code}")
            continue

        batch_results = response.json()

        for item_result in batch_results:
            if item_result.get('code') == 200:
                all_details.append(item_result['body'])
            else:
                print(f"   ⚠️  Item {item_result.get('body', {}).get('id', 'unknown')} no encontrado")

        print(f"   ✅ Batch {batch_num}/{total_batches} completado")

    print(f"\n✅ Total de items con detalles: {len(all_details)}")
    return all_details

def get_marketplace_items(item_id):
    """
    Obtiene los marketplace items para un item CBT con retry en caso de rate limit.
    """
    if not item_id.startswith('CBT'):
        return None

    headers = {
        'Authorization': f'Bearer {ML_ACCESS_TOKEN}'
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            url = f"https://api.mercadolibre.com/items/{item_id}/marketplace_items"
            response = session.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:  # Rate limit
                wait_time = (attempt + 1) * 0.5
                time.sleep(wait_time)
                continue
            elif response.status_code == 404:
                return None  # Item no tiene marketplace_items
            else:
                return None
        except:
            if attempt < max_retries - 1:
                time.sleep(0.2)
                continue
            return None

    return None

def export_to_txt(items, output_file):
    """
    Exporta los items con información esencial a un archivo de texto.
    """
    print(f"\n📝 Exportando a {output_file}...")

    # Obtener marketplace items para items CBT (paralelo)
    print(f"\n🌍 Obteniendo marketplace items para items CBT...")
    cbt_items = [item for item in items if item.get('id', '').startswith('CBT')]
    print(f"   Items CBT encontrados: {len(cbt_items)}")

    marketplace_data = {}

    start_time = time.time()
    print(f"   ⚡ MODO PARALELO ACTIVADO - 15 workers simultáneos")

    # Paralelizar las requests de marketplace items
    with ThreadPoolExecutor(max_workers=15) as executor:
        # Crear futures para todos los items CBT
        future_to_item = {
            executor.submit(get_marketplace_items, item.get('id')): item.get('id')
            for item in cbt_items if item.get('id')
        }

        # Procesar resultados a medida que se completan
        completed = 0
        for future in as_completed(future_to_item):
            item_id = future_to_item[future]
            completed += 1

            try:
                mp_data = future.result()
                if mp_data:
                    marketplace_data[item_id] = mp_data
                    print(f"   ✅ [{completed}/{len(cbt_items)}] {item_id}")
                else:
                    print(f"   ⚠️  [{completed}/{len(cbt_items)}] {item_id} - sin datos")
            except Exception as e:
                print(f"   ❌ [{completed}/{len(cbt_items)}] {item_id} - error: {e}")

    elapsed = time.time() - start_time
    print(f"✅ Marketplace items obtenidos: {len(marketplace_data)}")
    print(f"   ⏱️  Tiempo total: {elapsed:.2f}s ({elapsed/60:.2f} min)")
    print(f"   📊 Promedio: {elapsed/len(cbt_items):.3f}s por item")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"EXPORTACIÓN SIMPLE DE ITEMS MERCADOLIBRE\n")
        f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total de items: {len(items)}\n")
        f.write(f"{'='*100}\n\n")

        for idx, item in enumerate(items, 1):
            item_id = item.get('id', 'N/A')

            f.write(f"[{idx}/{len(items)}] {item_id}\n")
            f.write(f"{'-'*100}\n")

            # Mostrar marketplace items primero si existen
            local_items_str = ""
            if item_id in marketplace_data:
                mp_data = marketplace_data[item_id]
                mp_items = mp_data.get('marketplace_items', [])
                if mp_items:
                    local_ids = [f"{mp['site_id']}:{mp['item_id']}" for mp in mp_items]
                    local_items_str = " | ".join(local_ids)
                    f.write(f"ITEMS LOCALES: {local_items_str}\n")

            # === INFORMACIÓN BÁSICA ===
            f.write(f"\n--- INFORMACIÓN BÁSICA ---\n")
            f.write(f"CBT ID: {item_id}\n")
            f.write(f"Site ID: {item.get('site_id', 'N/A')}\n")
            f.write(f"Estado: {item.get('status', 'N/A')}\n")
            f.write(f"Título: {item.get('title', 'N/A')}\n")
            f.write(f"Categoría ID: {item.get('category_id', 'N/A')}\n")
            f.write(f"Permalink: {item.get('permalink', 'N/A')}\n")

            # === PRECIO Y STOCK ===
            f.write(f"\n--- PRECIO Y STOCK ---\n")
            currency = item.get('currency_id', 'USD')
            price = item.get('price', 'N/A')
            f.write(f"Precio: {price} {currency}\n")
            f.write(f"Precio original: {item.get('original_price', 'N/A')} {currency}\n")
            f.write(f"Cantidad disponible: {item.get('available_quantity', 'N/A')}\n")
            f.write(f"Cantidad inicial: {item.get('initial_quantity', 'N/A')}\n")
            f.write(f"Cantidad vendida: {item.get('sold_quantity', 'N/A')}\n")

            # === SKUs ===
            f.write(f"\n--- SKUs ---\n")
            seller_custom_field = item.get('seller_custom_field')
            if seller_custom_field:
                f.write(f"seller_custom_field: {seller_custom_field}\n")

            # Buscar SELLER_SKU en atributos
            attributes = item.get('attributes', [])
            seller_sku = None
            for attr in attributes:
                if attr.get('id') == 'SELLER_SKU':
                    seller_sku = attr.get('value_name') or attr.get('value_id')
                    break
            if seller_sku:
                f.write(f"SELLER_SKU (atributo): {seller_sku}\n")

            # === FECHAS ===
            f.write(f"\n--- FECHAS ---\n")
            f.write(f"Creado: {item.get('date_created', 'N/A')}\n")
            f.write(f"Última actualización: {item.get('last_updated', 'N/A')}\n")
            f.write(f"Start time: {item.get('start_time', 'N/A')}\n")
            f.write(f"Stop time: {item.get('stop_time', 'N/A')}\n")

            # === LISTING ===
            f.write(f"\n--- LISTING ---\n")
            f.write(f"Tipo de listing: {item.get('listing_type_id', 'N/A')}\n")
            f.write(f"Tipo de compra: {item.get('buying_mode', 'N/A')}\n")
            f.write(f"Condición: {item.get('condition', 'N/A')}\n")
            f.write(f"Acepta mercadopago: {item.get('accepts_mercadopago', 'N/A')}\n")

            # === SHIPPING ===
            shipping = item.get('shipping', {})
            if shipping:
                f.write(f"\n--- SHIPPING ---\n")
                f.write(f"Modo: {shipping.get('mode', 'N/A')}\n")
                f.write(f"Envío gratis: {shipping.get('free_shipping', 'N/A')}\n")
                f.write(f"Logistic type: {shipping.get('logistic_type', 'N/A')}\n")
                f.write(f"Tags: {', '.join(shipping.get('tags', []))}\n")

            # === TAGS Y OTROS ===
            f.write(f"\n--- TAGS Y CATEGORIZACIÓN ---\n")
            f.write(f"Tags: {', '.join(item.get('tags', []))}\n")
            f.write(f"Catalog listing: {item.get('catalog_listing', 'N/A')}\n")
            f.write(f"Catalog product ID: {item.get('catalog_product_id', 'N/A')}\n")

            # === SALUD DEL LISTING ===
            health = item.get('health', None)
            if health:
                f.write(f"\n--- SALUD DEL LISTING ---\n")
                f.write(f"Health: {health}\n")

            # === ATRIBUTOS ===
            if attributes:
                f.write(f"\n--- ATRIBUTOS ({len(attributes)}) ---\n")
                for attr in attributes[:10]:  # Primeros 10 atributos
                    attr_id = attr.get('id', 'N/A')
                    attr_name = attr.get('name', 'N/A')
                    attr_value = attr.get('value_name') or attr.get('value_id', 'N/A')
                    f.write(f"  {attr_name} ({attr_id}): {attr_value}\n")
                if len(attributes) > 10:
                    f.write(f"  ... y {len(attributes) - 10} atributos más\n")

            # === IMÁGENES ===
            pictures = item.get('pictures', [])
            if pictures:
                f.write(f"\n--- IMÁGENES ({len(pictures)}) ---\n")
                for idx_pic, pic in enumerate(pictures[:3], 1):  # Primeras 3
                    f.write(f"  {idx_pic}. {pic.get('url', 'N/A')}\n")
                if len(pictures) > 3:
                    f.write(f"  ... y {len(pictures) - 3} imágenes más\n")

            # === MARKETPLACE ITEMS ===
            if item_id in marketplace_data:
                mp_data = marketplace_data[item_id]
                mp_items = mp_data.get('marketplace_items', [])

                if mp_items:
                    f.write(f"\n--- MARKETPLACE ITEMS ({len(mp_items)}) ---\n")
                    for mp_item in mp_items:
                        mp_id = mp_item.get('item_id', 'N/A')
                        mp_site = mp_item.get('site_id', 'N/A')
                        mp_user = mp_item.get('user_id', 'N/A')
                        mp_date = mp_item.get('date_created', 'N/A')
                        f.write(f"  • {mp_site}: {mp_id}\n")
                        f.write(f"    User ID: {mp_user}\n")
                        f.write(f"    Fecha: {mp_date}\n")

            # === JSON COMPLETO (opcional) ===
            f.write(f"\n--- JSON COMPLETO ---\n")
            f.write(json.dumps(item, indent=2, ensure_ascii=False))

            f.write(f"\n\n")

        f.write(f"\n{'='*100}\n")
        f.write(f"Fin del reporte\n")

    print(f"✅ Exportación completada: {output_file}")

def main():
    """
    Función principal del script.
    """
    if not ML_ACCESS_TOKEN:
        print("❌ Error: ML_ACCESS_TOKEN no encontrado en .env")
        return

    # Generar nombre de archivo con timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"ml_items_simple_export_{timestamp}.txt"

    try:
        # 1. Obtener todos los IDs de items
        item_ids = get_all_item_ids()

        if not item_ids:
            print("⚠️  No se encontraron items para exportar")
            return

        # 2. Obtener detalles esenciales
        items = get_item_details(item_ids)

        if not items:
            print("⚠️  No se pudieron obtener detalles de los items")
            return

        # 3. Exportar a archivo de texto
        export_to_txt(items, output_file)

        print(f"\n✅ Proceso completado exitosamente")
        print(f"📄 Archivo generado: {output_file}")

    except Exception as e:
        print(f"❌ Error durante la ejecución: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
