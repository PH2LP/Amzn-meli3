#!/usr/bin/env python3
"""
Script para exportar TODA la información disponible de items de MercadoLibre.
Incluye: item data, descripción, visitas, health metrics, stock por almacén, y más.
"""

import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv
import time

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

def get_item_complete_data(item_id):
    """
    Obtiene TODA la información disponible de un item desde múltiples endpoints.
    Returns: dict con toda la data
    """
    headers = {
        'Authorization': f'Bearer {ML_ACCESS_TOKEN}'
    }

    complete_data = {
        'item_id': item_id,
        'item_data': None,
        'description': None,
        'visits': None,
        'health': None,
        'marketplace_items': None,
        'item_stock': None,
    }

    # 1. Datos básicos del item
    try:
        url = f"https://api.mercadolibre.com/items/{item_id}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            complete_data['item_data'] = response.json()
    except Exception as e:
        print(f"   ⚠️  Error obteniendo item data para {item_id}: {e}")

    # 2. Descripción del item
    try:
        url = f"https://api.mercadolibre.com/items/{item_id}/description"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            complete_data['description'] = response.json()
    except Exception as e:
        print(f"   ⚠️  Error obteniendo descripción para {item_id}: {e}")

    # 3. Visitas (métricas de tráfico)
    try:
        url = f"https://api.mercadolibre.com/items/{item_id}/visits?last=30&unit=day"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            complete_data['visits'] = response.json()
    except Exception as e:
        print(f"   ⚠️  Error obteniendo visitas para {item_id}: {e}")

    # 4. Health status (calidad y exposición)
    try:
        url = f"https://api.mercadolibre.com/items/{item_id}/health"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            complete_data['health'] = response.json()
    except Exception as e:
        # El endpoint de health puede no estar disponible para todos los items
        pass

    # 5. Marketplace items (si es CBT)
    if item_id.startswith('CBT'):
        try:
            url = f"https://api.mercadolibre.com/items/{item_id}/marketplace_items"
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                complete_data['marketplace_items'] = response.json()
        except Exception as e:
            print(f"   ⚠️  Error obteniendo marketplace items para {item_id}: {e}")

    # 6. Stock por almacén (inventario detallado)
    try:
        url = f"https://api.mercadolibre.com/items/{item_id}/inventories"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            complete_data['item_stock'] = response.json()
    except Exception as e:
        # No todos los items tienen inventarios
        pass

    return complete_data

def get_items_complete_details(item_ids):
    """
    Obtiene detalles completos de todos los items.
    Returns: lista de items con toda su información
    """
    all_details = []
    total = len(item_ids)

    print(f"\n📦 Obteniendo detalles COMPLETOS de {total} items...")
    print(f"⏰ Esto puede tomar varios minutos...")

    for i, item_id in enumerate(item_ids, 1):
        print(f"   [{i}/{total}] Procesando {item_id}...")

        complete_data = get_item_complete_data(item_id)
        all_details.append(complete_data)

        # Rate limiting: pequeña pausa cada 10 items
        if i % 10 == 0:
            time.sleep(0.5)

    print(f"\n✅ Total de items procesados: {len(all_details)}")
    return all_details

def format_value(value, default='N/A'):
    """Formatea un valor para mostrar, retorna default si es None o vacío."""
    if value is None or value == '':
        return default
    return str(value)

def export_to_txt(items, output_file):
    """
    Exporta los items con TODA su información a un archivo de texto.
    """
    print(f"\n📝 Exportando a {output_file}...")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"EXPORTACIÓN COMPLETA DE ITEMS MERCADOLIBRE\n")
        f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total de items: {len(items)}\n")
        f.write(f"{'='*100}\n\n")

        for idx, complete_data in enumerate(items, 1):
            item_id = complete_data.get('item_id', 'N/A')
            item = complete_data.get('item_data', {})

            if not item:
                f.write(f"[{idx}/{len(items)}] {item_id}\n")
                f.write(f"{'-'*100}\n")
                f.write(f"⚠️  No se pudo obtener información de este item\n\n")
                continue

            f.write(f"[{idx}/{len(items)}] {item_id}\n")
            f.write(f"{'-'*100}\n")

            # ============ INFORMACIÓN BÁSICA ============
            f.write(f"\n### INFORMACIÓN BÁSICA ###\n")
            f.write(f"ID: {format_value(item.get('id'))}\n")
            f.write(f"Site ID: {format_value(item.get('site_id'))}\n")
            f.write(f"Título: {format_value(item.get('title'))}\n")
            f.write(f"Categoría: {format_value(item.get('category_id'))}\n")
            f.write(f"Estado: {format_value(item.get('status'))}\n")
            f.write(f"Sub-estado: {format_value(', '.join(item.get('sub_status', [])))}\n")

            # Seller info
            f.write(f"Seller ID: {format_value(item.get('seller_id'))}\n")

            # Fechas
            f.write(f"Fecha creación: {format_value(item.get('date_created'))}\n")
            f.write(f"Última actualización: {format_value(item.get('last_updated'))}\n")
            f.write(f"Fecha inicio: {format_value(item.get('start_time'))}\n")
            f.write(f"Fecha fin: {format_value(item.get('stop_time'))}\n")

            # ============ PRECIOS Y STOCK ============
            f.write(f"\n### PRECIOS Y STOCK ###\n")
            currency = item.get('currency_id', 'USD')
            f.write(f"Moneda: {currency}\n")
            f.write(f"Precio: {format_value(item.get('price'))} {currency}\n")

            base_price = item.get('base_price')
            if base_price and base_price != item.get('price'):
                f.write(f"Precio base: {base_price} {currency}\n")

            original_price = item.get('original_price')
            if original_price:
                f.write(f"Precio original: {original_price} {currency}\n")

            f.write(f"Cantidad inicial: {format_value(item.get('initial_quantity'))}\n")
            f.write(f"Cantidad disponible: {format_value(item.get('available_quantity'))}\n")
            f.write(f"Cantidad vendida: {format_value(item.get('sold_quantity'))}\n")

            # ============ IDENTIFICADORES Y SKUs ============
            f.write(f"\n### IDENTIFICADORES ###\n")

            catalog_product_id = item.get('catalog_product_id')
            if catalog_product_id:
                f.write(f"Catalog Product ID: {catalog_product_id}\n")

            seller_custom_field = item.get('seller_custom_field')
            if seller_custom_field:
                f.write(f"SKU (seller_custom_field): {seller_custom_field}\n")

            # Buscar identificadores en atributos
            attributes = item.get('attributes', [])

            for attr in attributes:
                attr_id = attr.get('id')
                if attr_id in ['GTIN', 'EAN', 'UPC', 'ISBN', 'SELLER_SKU', 'PART_NUMBER', 'MODEL', 'BRAND']:
                    value = attr.get('value_name') or attr.get('value_id', 'N/A')
                    f.write(f"{attr.get('name', attr_id)}: {value}\n")

            # ============ PUBLICACIÓN ============
            f.write(f"\n### TIPO DE PUBLICACIÓN ###\n")
            f.write(f"Tipo: {format_value(item.get('listing_type_id'))}\n")
            f.write(f"Método de compra: {format_value(item.get('buying_mode'))}\n")
            f.write(f"Condición: {format_value(item.get('condition'))}\n")

            warranty = item.get('warranty')
            if warranty:
                f.write(f"Garantía: {warranty}\n")

            # Tags
            tags = item.get('tags', [])
            if tags:
                f.write(f"Tags: {', '.join(tags)}\n")

            # ============ ENVÍO ============
            f.write(f"\n### ENVÍO ###\n")
            shipping = item.get('shipping', {})
            f.write(f"Modo de envío: {format_value(shipping.get('mode'))}\n")
            f.write(f"Envío gratis: {'Sí' if shipping.get('free_shipping') else 'No'}\n")
            f.write(f"Logística: {format_value(shipping.get('logistic_type'))}\n")

            free_methods = shipping.get('free_methods', [])
            if free_methods:
                f.write(f"Métodos de envío gratis: {', '.join([str(m.get('id')) for m in free_methods])}\n")

            dimensions = shipping.get('dimensions')
            if dimensions:
                f.write(f"Dimensiones paquete: {dimensions}\n")

            # ============ IMÁGENES ============
            pictures = item.get('pictures', [])
            if pictures:
                f.write(f"\n### IMÁGENES ({len(pictures)}) ###\n")
                for pic_idx, pic in enumerate(pictures[:5], 1):
                    pic_id = pic.get('id', 'N/A')
                    pic_url = pic.get('secure_url', pic.get('url', 'N/A'))
                    f.write(f"  {pic_idx}. ID: {pic_id}\n")
                    f.write(f"     URL: {pic_url}\n")
                if len(pictures) > 5:
                    f.write(f"  ... y {len(pictures) - 5} imágenes más\n")

            # ============ VARIACIONES ============
            variations = item.get('variations', [])
            if variations:
                f.write(f"\n### VARIACIONES ({len(variations)}) ###\n")
                for var_idx, variation in enumerate(variations, 1):
                    var_id = variation.get('id', 'N/A')
                    var_price = variation.get('price', 0)
                    var_available = variation.get('available_quantity', 0)
                    var_sold = variation.get('sold_quantity', 0)

                    var_attrs = variation.get('attribute_combinations', [])
                    var_desc = ' - '.join([f"{attr.get('name')}: {attr.get('value_name')}" for attr in var_attrs])

                    f.write(f"  Variación {var_idx}:\n")
                    f.write(f"    ID: {var_id}\n")
                    f.write(f"    Atributos: {var_desc}\n")
                    f.write(f"    Precio: {var_price} {currency}\n")
                    f.write(f"    Disponible: {var_available}\n")
                    f.write(f"    Vendido: {var_sold}\n")

                    var_seller_custom_field = variation.get('seller_custom_field')
                    if var_seller_custom_field:
                        f.write(f"    SKU: {var_seller_custom_field}\n")
                    f.write(f"\n")

            # ============ ATRIBUTOS COMPLETOS ============
            if attributes:
                f.write(f"\n### ATRIBUTOS ({len(attributes)}) ###\n")
                for attr in attributes:
                    attr_id = attr.get('id', 'N/A')
                    attr_name = attr.get('name', 'N/A')
                    attr_value = attr.get('value_name', attr.get('value_id', 'N/A'))
                    f.write(f"  • {attr_name} ({attr_id}): {attr_value}\n")

            # ============ DESCRIPCIÓN ============
            description_data = complete_data.get('description', {})
            if description_data:
                f.write(f"\n### DESCRIPCIÓN ###\n")
                desc_text = description_data.get('plain_text', '')
                if desc_text:
                    desc_preview = desc_text[:500] if len(desc_text) > 500 else desc_text
                    f.write(f"{desc_preview}")
                    if len(desc_text) > 500:
                        f.write(f"\n... (total {len(desc_text)} caracteres)")
                    f.write(f"\n")

            # ============ VISITAS Y MÉTRICAS ============
            visits_data = complete_data.get('visits')
            if visits_data:
                f.write(f"\n### VISITAS (últimos 30 días) ###\n")
                total_visits = visits_data.get('total', 0)
                f.write(f"Total de visitas: {total_visits}\n")

            # ============ HEALTH STATUS ============
            health_data = complete_data.get('health')
            if health_data:
                f.write(f"\n### HEALTH STATUS ###\n")
                health_level = health_data.get('health_level', 'N/A')
                f.write(f"Nivel de salud: {health_level}\n")

                problems = health_data.get('problems', [])
                if problems:
                    f.write(f"Problemas detectados:\n")
                    for problem in problems:
                        f.write(f"  • {problem}\n")

            # ============ MARKETPLACE ITEMS (CBT) ============
            marketplace_items_data = complete_data.get('marketplace_items')
            if marketplace_items_data:
                marketplace_items = marketplace_items_data.get('marketplace_items', [])
                if marketplace_items:
                    f.write(f"\n### MARKETPLACE ITEMS ({len(marketplace_items)}) ###\n")
                    for mp_item in marketplace_items:
                        mp_id = mp_item.get('item_id', 'N/A')
                        mp_site = mp_item.get('site_id', 'N/A')
                        mp_user = mp_item.get('user_id', 'N/A')
                        f.write(f"  • {mp_site}: {mp_id} (User: {mp_user})\n")

            # ============ STOCK DETALLADO ============
            stock_data = complete_data.get('item_stock')
            if stock_data:
                f.write(f"\n### INVENTARIO DETALLADO ###\n")
                inventories = stock_data.get('inventories', [])
                if inventories:
                    for inv in inventories:
                        inv_id = inv.get('id', 'N/A')
                        warehouse = inv.get('warehouse_id', 'N/A')
                        available = inv.get('available_quantity', 0)
                        f.write(f"  Almacén {warehouse} (ID: {inv_id}): {available} unidades\n")

            # ============ ENLACES ============
            f.write(f"\n### ENLACES ###\n")
            f.write(f"Permalink: {format_value(item.get('permalink'))}\n")
            f.write(f"Thumbnail: {format_value(item.get('thumbnail'))}\n")

            f.write(f"\n")

        f.write(f"\n{'='*100}\n")
        f.write(f"Fin del reporte completo\n")

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
    output_file = f"ml_items_complete_export_{timestamp}.txt"

    try:
        # 1. Obtener todos los IDs de items
        item_ids = get_all_item_ids()

        if not item_ids:
            print("⚠️  No se encontraron items para exportar")
            return

        # 2. Obtener TODOS los detalles de todos los items
        items = get_items_complete_details(item_ids)

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
