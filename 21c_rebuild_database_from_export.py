#!/usr/bin/env python3
"""
Script para reconstruir listings_database.db desde ml_items_simple_export.txt
Mantiene la estructura exacta de la DB actual
"""

import sqlite3
import json
import re
from datetime import datetime
from pathlib import Path

def parse_export_file(export_file):
    """
    Parsea el archivo de export y extrae todos los items
    """
    print(f"📖 Parseando: {export_file}")

    with open(export_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Dividir por items - separar por el marcador [N/total] CBT...
    # Primero, dividir por los marcadores pero mantener el CBT ID
    parts = re.split(r'\[(\d+)/\d+\] (CBT\d+)', content)

    items = []

    # parts[0] es el header, luego viene: [num, cbt_id, content, num, cbt_id, content, ...]
    for i in range(1, len(parts), 3):
        if i+2 < len(parts):
            item_num = parts[i]
            cbt_id = parts[i+1]
            item_content = parts[i+2]

            # Extraer JSON completo
            json_match = re.search(r'--- JSON COMPLETO ---\n(\{.*?\n\})\n*$', item_content, re.DOTALL)
            if not json_match:
                print(f"⚠️  Sin JSON para {cbt_id} (#{item_num}), saltando...")
                continue

            try:
                item_json = json.loads(json_match.group(1))
            except json.JSONDecodeError as e:
                print(f"⚠️  Error JSON en {cbt_id}: {e}")
                continue

            # Extraer ITEMS LOCALES
            locales_match = re.search(r'^ITEMS LOCALES: (.+)$', item_content, re.MULTILINE)
            local_items = {}
            if locales_match:
                # Parsear: "MLM:MLM123 | MLA:MLA456 | ..."
                locales_str = locales_match.group(1)
                for pair in locales_str.split('|'):
                    pair = pair.strip()
                    if ':' in pair:
                        site, item_id = pair.split(':', 1)
                        local_items[site.strip()] = item_id.strip()

            # Extraer ASIN del atributo SELLER_SKU
            asin = None
            for attr in item_json.get('attributes', []):
                if attr.get('id') == 'SELLER_SKU':
                    asin = attr.get('value_name')
                    break

            if not asin:
                print(f"⚠️  Sin ASIN para {cbt_id}, saltando...")
                continue

            items.append({
                'json': item_json,
                'local_items': local_items,
                'asin': asin,
                'cbt_id': cbt_id
            })

    print(f"✓ Parseados {len(items)} items")
    return items

def create_database(items, output_db):
    """
    Crea la base de datos con estructura idéntica a la actual
    """
    print(f"\n🔨 Creando base de datos: {output_db}")

    # Eliminar DB anterior si existe
    if Path(output_db).exists():
        Path(output_db).unlink()

    conn = sqlite3.connect(output_db)
    cursor = conn.cursor()

    # Crear tabla con estructura EXACTA
    cursor.execute("""
        CREATE TABLE listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT UNIQUE,
            asin TEXT NOT NULL,
            title TEXT,
            description TEXT,
            brand TEXT,
            model TEXT,
            category_id TEXT,
            category_name TEXT,
            price_usd REAL,

            -- Dimensiones
            length_cm REAL,
            width_cm REAL,
            height_cm REAL,
            weight_kg REAL,

            -- Datos adicionales
            images_urls TEXT,
            attributes TEXT,
            main_features TEXT,

            -- Marketplaces donde está publicado
            marketplaces TEXT,

            -- Site items por país (JSON array con {site_id, item_id, logistic_type})
            site_items TEXT,

            -- Metadata
            date_published TIMESTAMP,
            date_updated TIMESTAMP,

            -- Data completa del mini_ml para fallback
            mini_ml_data TEXT,
            permalink TEXT,
            country TEXT,

            -- Campos que se completarán en sync
            stock INTEGER DEFAULT 10,
            costo_amazon REAL,
            tax_florida REAL,
            precio_original REAL,
            precio_actual REAL,
            es_catalogo INTEGER DEFAULT 0,
            ultima_actualizacion_precio TIMESTAMP,
            gtin TEXT,
            amazon_url TEXT,
            amazon_price_last REAL DEFAULT NULL,
            notes TEXT,
            skip_publisher INTEGER DEFAULT 0
        )
    """)

    # Crear índices
    cursor.execute("CREATE INDEX idx_item_id ON listings(item_id)")
    cursor.execute("CREATE INDEX idx_asin ON listings(asin)")

    print(f"✓ Estructura de tabla creada")

    # Insertar items
    inserted = 0
    skipped = 0

    for item in items:
        try:
            json_data = item['json']
            asin = item['asin']
            cbt_id = item['cbt_id']
            local_items = item['local_items']

            # Extraer campos básicos
            title = json_data.get('title')
            category_id = json_data.get('category_id')
            price_usd = json_data.get('price')

            # Extraer atributos
            brand = None
            model = None
            gtin = None
            length_cm = None
            width_cm = None
            height_cm = None
            weight_kg = None

            for attr in json_data.get('attributes', []):
                attr_id = attr.get('id')
                value_name = attr.get('value_name')

                if attr_id == 'BRAND':
                    brand = value_name
                elif attr_id == 'MODEL':
                    model = value_name
                elif attr_id == 'GTIN':
                    gtin = value_name
                elif attr_id == 'LENGTH':
                    try:
                        length_cm = float(str(value_name).split()[0])
                    except:
                        pass
                elif attr_id == 'WIDTH':
                    try:
                        width_cm = float(str(value_name).split()[0])
                    except:
                        pass
                elif attr_id == 'HEIGHT':
                    try:
                        height_cm = float(str(value_name).split()[0])
                    except:
                        pass
                elif attr_id == 'WEIGHT':
                    try:
                        weight_kg = float(str(value_name).split()[0])
                    except:
                        pass

            # Imágenes
            images = [pic.get('secure_url') for pic in json_data.get('pictures', [])]
            images_urls = json.dumps(images) if images else None

            # Atributos completos
            attributes = json.dumps(json_data.get('attributes', []))

            # Marketplaces (países donde está publicado)
            marketplaces = json.dumps(list(local_items.keys())) if local_items else json.dumps([])

            # Site items - formato: [{site_id, item_id, logistic_type}]
            site_items_list = []
            for site, item_id in local_items.items():
                site_items_list.append({
                    'site_id': site,
                    'item_id': item_id,
                    'logistic_type': 'remote'  # Default para mantener compatibilidad con DB anterior
                })
            site_items = json.dumps(site_items_list) if site_items_list else None

            # Fechas
            date_published = json_data.get('date_created') or json_data.get('start_time')
            date_updated = json_data.get('last_updated') or json_data.get('date_created')

            # Permalink
            permalink = json_data.get('permalink', '')

            # Stock
            stock = json_data.get('available_quantity', 10)

            # Mini ML data (JSON completo para fallback)
            mini_ml_data = json.dumps(json_data)

            # Insertar
            cursor.execute("""
                INSERT INTO listings (
                    item_id, asin, title, brand, model, category_id, price_usd,
                    length_cm, width_cm, height_cm, weight_kg,
                    images_urls, attributes, marketplaces, site_items,
                    date_published, date_updated, mini_ml_data, permalink,
                    stock, gtin, es_catalogo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cbt_id, asin, title, brand, model, category_id, price_usd,
                length_cm, width_cm, height_cm, weight_kg,
                images_urls, attributes, marketplaces, site_items,
                date_published, date_updated, mini_ml_data, permalink,
                stock, gtin, 1  # es_catalogo=1 porque todos son CBT
            ))

            inserted += 1

        except Exception as e:
            print(f"⚠️  Error insertando {cbt_id}: {e}")
            skipped += 1
            continue

    conn.commit()
    conn.close()

    print(f"✓ Items insertados: {inserted}")
    if skipped > 0:
        print(f"⚠️  Items saltados: {skipped}")

    return inserted

def main():
    # Archivos
    export_file = 'ml_items_simple_export_20260114_021305.txt'
    temp_db = 'storage/listings_database_new.db'
    final_db = 'storage/listings_database.db'

    # Verificar que existe el export
    if not Path(export_file).exists():
        print(f"❌ Error: No se encontró {export_file}")
        return

    # Parsear export
    items = parse_export_file(export_file)

    if not items:
        print("❌ No se encontraron items válidos")
        return

    # Crear nueva DB
    inserted = create_database(items, temp_db)

    if inserted == 0:
        print("❌ No se insertó ningún item")
        return

    # Reemplazar DB actual
    print(f"\n🔄 Reemplazando DB actual...")
    Path(final_db).unlink()
    Path(temp_db).rename(final_db)

    print(f"\n✅ ¡DB reconstruida exitosamente!")
    print(f"   Archivo: {final_db}")
    print(f"   Items: {inserted}")

    # Verificar
    conn = sqlite3.connect(final_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM listings")
    count = cursor.fetchone()[0]
    conn.close()

    print(f"   Verificación: {count} items en DB")

if __name__ == "__main__":
    main()
