#!/usr/bin/env python3
"""
Script para exportar todos los items de MercadoLibre a un archivo de texto.
Usa el endpoint /users/{USER_ID}/items/search con paginación tipo scan para obtener más de 1000 items.
"""

import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

ML_ACCESS_TOKEN = os.getenv('ML_ACCESS_TOKEN')
ML_USER_ID = os.getenv('ML_USER_ID', '2560656533')

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
    Obtiene los detalles de los items usando multiget (máximo 20 por request).
    Returns: lista de detalles de items
    """
    all_details = []
    batch_size = 20
    total = len(item_ids)

    print(f"\n📦 Obteniendo detalles de {total} items...")

    for i in range(0, total, batch_size):
        batch = item_ids[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total + batch_size - 1) // batch_size

        ids_param = ','.join(batch)
        url = f"https://api.mercadolibre.com/items?ids={ids_param}"

        headers = {
            'Authorization': f'Bearer {ML_ACCESS_TOKEN}'
        }

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(f"❌ Error obteniendo detalles del batch {batch_num}: {response.status_code}")
            continue

        batch_results = response.json()

        for item_result in batch_results:
            if item_result.get('code') == 200:
                all_details.append(item_result['body'])
            else:
                print(f"   ⚠️  Item {item_result.get('body', {}).get('id', 'unknown')} no encontrado (code: {item_result.get('code')})")

        print(f"   ✅ Batch {batch_num}/{total_batches} completado ({len(batch)} items)")

    print(f"\n✅ Total de items con detalles: {len(all_details)}")
    return all_details

def export_to_txt(items, output_file):
    """
    Exporta los items a un archivo de texto con formato legible.
    """
    print(f"\n📝 Exportando a {output_file}...")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"EXPORTACIÓN DE ITEMS MERCADOLIBRE\n")
        f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total de items: {len(items)}\n")
        f.write(f"{'='*100}\n\n")

        for idx, item in enumerate(items, 1):
            f.write(f"[{idx}/{len(items)}] {item.get('id', 'N/A')}\n")
            f.write(f"{'-'*100}\n")

            # Información básica
            f.write(f"Título: {item.get('title', 'N/A')}\n")
            f.write(f"Site ID: {item.get('site_id', 'N/A')}\n")
            f.write(f"Categoría: {item.get('category_id', 'N/A')}\n")
            f.write(f"Estado: {item.get('status', 'N/A')}\n")

            # Precio y stock
            currency = item.get('currency_id', 'USD')
            price = item.get('price', 0)
            base_price = item.get('base_price', 0)
            f.write(f"Precio: {price} {currency}\n")
            if base_price and base_price != price:
                f.write(f"Precio base: {base_price} {currency}\n")

            f.write(f"Cantidad disponible: {item.get('available_quantity', 0)}\n")
            f.write(f"Cantidad vendida: {item.get('sold_quantity', 0)}\n")

            # SKUs y identificadores
            seller_custom_field = item.get('seller_custom_field')
            if seller_custom_field:
                f.write(f"SKU (seller_custom_field): {seller_custom_field}\n")

            # Buscar SELLER_SKU en atributos
            attributes = item.get('attributes', [])
            seller_sku = next((attr.get('value_name') for attr in attributes if attr.get('id') == 'SELLER_SKU'), None)
            if seller_sku:
                f.write(f"SELLER_SKU: {seller_sku}\n")

            # Listing type
            listing_type = item.get('listing_type_id', 'N/A')
            f.write(f"Tipo de publicación: {listing_type}\n")

            # Fechas
            date_created = item.get('date_created', 'N/A')
            last_updated = item.get('last_updated', 'N/A')
            f.write(f"Fecha creación: {date_created}\n")
            f.write(f"Última actualización: {last_updated}\n")

            # Permalink
            permalink = item.get('permalink', 'N/A')
            f.write(f"URL: {permalink}\n")

            # Variaciones si existen
            variations = item.get('variations', [])
            if variations:
                f.write(f"Variaciones: {len(variations)}\n")
                for var_idx, variation in enumerate(variations, 1):
                    var_price = variation.get('price', 0)
                    var_available = variation.get('available_quantity', 0)
                    var_sold = variation.get('sold_quantity', 0)
                    var_id = variation.get('id', 'N/A')
                    var_attrs = variation.get('attribute_combinations', [])
                    var_desc = ' - '.join([f"{attr.get('name')}: {attr.get('value_name')}" for attr in var_attrs])
                    f.write(f"  Variación {var_idx} (ID: {var_id}): {var_desc}\n")
                    f.write(f"    Precio: {var_price} {currency}, Disponible: {var_available}, Vendido: {var_sold}\n")

            # Shipping info
            shipping = item.get('shipping', {})
            free_shipping = shipping.get('free_shipping', False)
            if free_shipping:
                f.write(f"Envío gratis: Sí\n")

            f.write(f"\n")

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
    output_file = f"ml_items_export_{timestamp}.txt"

    try:
        # 1. Obtener todos los IDs de items
        item_ids = get_all_item_ids()

        if not item_ids:
            print("⚠️  No se encontraron items para exportar")
            return

        # 2. Obtener detalles de todos los items
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
