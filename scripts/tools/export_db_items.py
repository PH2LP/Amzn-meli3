#!/usr/bin/env python3
"""
Script para exportar todos los items de la base de datos SQLite a un archivo de texto.
Formato similar al export de MercadoLibre para facilitar comparaciones.
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = 'storage/listings_database.db'

def get_all_items_from_db():
    """
    Obtiene todos los items de la base de datos.
    Returns: lista de items (dicts)
    """
    print(f"🔍 Conectando a la base de datos: {DB_PATH}...")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Para acceder a columnas por nombre
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM listings")
    total = cursor.fetchone()['total']
    print(f"📦 Total de items en DB: {total}")

    cursor.execute("SELECT * FROM listings ORDER BY asin")
    rows = cursor.fetchall()

    items = [dict(row) for row in rows]

    conn.close()

    print(f"✅ Items obtenidos: {len(items)}")
    return items

def parse_json_field(value):
    """
    Parsea un campo JSON de forma segura.
    """
    if not value:
        return None
    try:
        return json.loads(value)
    except:
        return None

def export_to_txt(items, output_file):
    """
    Exporta los items a un archivo de texto con formato legible.
    """
    print(f"\n📝 Exportando a {output_file}...")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"EXPORTACIÓN DE ITEMS - BASE DE DATOS LOCAL\n")
        f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total de items: {len(items)}\n")
        f.write(f"{'='*100}\n\n")

        for idx, item in enumerate(items, 1):
            f.write(f"[{idx}/{len(items)}] {item.get('item_id', 'N/A')}\n")
            f.write(f"{'-'*100}\n")

            # Información básica
            f.write(f"ASIN: {item.get('asin', 'N/A')}\n")
            f.write(f"Item ID ML: {item.get('item_id', 'N/A')}\n")
            f.write(f"Título: {item.get('title', 'N/A')}\n")
            f.write(f"Marca: {item.get('brand', 'N/A')}\n")
            f.write(f"Modelo: {item.get('model', 'N/A')}\n")

            # Categoría
            f.write(f"Categoría ID: {item.get('category_id', 'N/A')}\n")
            category_name = item.get('category_name')
            if category_name:
                f.write(f"Categoría nombre: {category_name}\n")

            # Precios y costos
            price_usd = item.get('price_usd')
            if price_usd:
                f.write(f"Precio USD: ${price_usd}\n")

            costo_amazon = item.get('costo_amazon')
            if costo_amazon:
                f.write(f"Costo Amazon: ${costo_amazon}\n")

            tax_florida = item.get('tax_florida')
            if tax_florida:
                f.write(f"Tax Florida: ${tax_florida}\n")

            precio_original = item.get('precio_original')
            if precio_original:
                f.write(f"Precio original: ${precio_original}\n")

            precio_actual = item.get('precio_actual')
            if precio_actual:
                f.write(f"Precio actual: ${precio_actual}\n")

            amazon_price_last = item.get('amazon_price_last')
            if amazon_price_last:
                f.write(f"Último precio Amazon conocido: ${amazon_price_last}\n")

            # Stock
            stock = item.get('stock')
            if stock is not None:
                f.write(f"Stock: {stock}\n")

            # Dimensiones y peso
            length_cm = item.get('length_cm')
            width_cm = item.get('width_cm')
            height_cm = item.get('height_cm')
            weight_kg = item.get('weight_kg')

            if any([length_cm, width_cm, height_cm, weight_kg]):
                f.write(f"Dimensiones: ")
                dims = []
                if length_cm:
                    dims.append(f"L:{length_cm}cm")
                if width_cm:
                    dims.append(f"W:{width_cm}cm")
                if height_cm:
                    dims.append(f"H:{height_cm}cm")
                if weight_kg:
                    dims.append(f"Peso:{weight_kg}kg")
                f.write(' x '.join(dims) + '\n')

            # GTIN
            gtin = item.get('gtin')
            if gtin:
                f.write(f"GTIN: {gtin}\n")

            # URLs
            amazon_url = item.get('amazon_url')
            if amazon_url:
                f.write(f"URL Amazon: {amazon_url}\n")

            permalink = item.get('permalink')
            if permalink:
                f.write(f"URL ML: {permalink}\n")

            # Marketplaces
            marketplaces = parse_json_field(item.get('marketplaces'))
            if marketplaces:
                f.write(f"Marketplaces: {', '.join(marketplaces)}\n")

            # Site items (publicaciones por país)
            site_items = parse_json_field(item.get('site_items'))
            if site_items:
                f.write(f"Publicaciones por país ({len(site_items)}):\n")
                for site_item in site_items:
                    site_id = site_item.get('site_id', 'N/A')
                    item_id = site_item.get('item_id', 'N/A')
                    logistic = site_item.get('logistic_type', 'N/A')
                    f.write(f"  - {site_id}: {item_id} (Logística: {logistic})\n")

            # Country
            country = item.get('country')
            if country:
                f.write(f"País: {country}\n")

            # Es catálogo
            es_catalogo = item.get('es_catalogo', 0)
            if es_catalogo:
                f.write(f"Es catálogo: Sí\n")

            # Skip publisher
            skip_publisher = item.get('skip_publisher', 0)
            if skip_publisher:
                f.write(f"Skip publisher: Sí\n")

            # Notas
            notes = item.get('notes')
            if notes:
                f.write(f"Notas: {notes}\n")

            # Fechas
            date_published = item.get('date_published')
            if date_published:
                f.write(f"Fecha publicación: {date_published}\n")

            date_updated = item.get('date_updated')
            if date_updated:
                f.write(f"Fecha actualización: {date_updated}\n")

            ultima_actualizacion_precio = item.get('ultima_actualizacion_precio')
            if ultima_actualizacion_precio:
                f.write(f"Última actualización precio: {ultima_actualizacion_precio}\n")

            # Imágenes
            images_urls = parse_json_field(item.get('images_urls'))
            if images_urls:
                f.write(f"Imágenes: {len(images_urls)} imagen(es)\n")
                for img_idx, img_url in enumerate(images_urls[:3], 1):  # Mostrar solo las primeras 3
                    f.write(f"  {img_idx}. {img_url}\n")
                if len(images_urls) > 3:
                    f.write(f"  ... y {len(images_urls) - 3} más\n")

            # Características principales
            main_features = parse_json_field(item.get('main_features'))
            if main_features:
                f.write(f"Características principales ({len(main_features)}):\n")
                for feature in main_features[:5]:  # Mostrar solo las primeras 5
                    f.write(f"  • {feature}\n")
                if len(main_features) > 5:
                    f.write(f"  ... y {len(main_features) - 5} más\n")

            # Atributos
            attributes = parse_json_field(item.get('attributes'))
            if attributes and isinstance(attributes, list):
                f.write(f"Atributos ({len(attributes)}):\n")
                for attr in attributes[:10]:  # Mostrar solo los primeros 10
                    if isinstance(attr, dict):
                        attr_id = attr.get('id', 'N/A')
                        attr_name = attr.get('name', 'N/A')
                        attr_value = attr.get('value_name', attr.get('value_id', 'N/A'))
                        f.write(f"  • {attr_name} ({attr_id}): {attr_value}\n")
                if len(attributes) > 10:
                    f.write(f"  ... y {len(attributes) - 10} más\n")

            # Descripción (truncada si es muy larga)
            description = item.get('description')
            if description:
                desc_preview = description[:200] if len(description) > 200 else description
                f.write(f"Descripción: {desc_preview}")
                if len(description) > 200:
                    f.write(f"... (total {len(description)} caracteres)")
                f.write(f"\n")

            f.write(f"\n")

        f.write(f"\n{'='*100}\n")
        f.write(f"Fin del reporte\n")

    print(f"✅ Exportación completada: {output_file}")

def main():
    """
    Función principal del script.
    """
    # Generar nombre de archivo con timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"db_items_export_{timestamp}.txt"

    try:
        # 1. Obtener todos los items de la DB
        items = get_all_items_from_db()

        if not items:
            print("⚠️  No se encontraron items en la base de datos")
            return

        # 2. Exportar a archivo de texto
        export_to_txt(items, output_file)

        print(f"\n✅ Proceso completado exitosamente")
        print(f"📄 Archivo generado: {output_file}")

    except Exception as e:
        print(f"❌ Error durante la ejecución: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
