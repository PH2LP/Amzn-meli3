#!/usr/bin/env python3
"""
Script para reconstruir listings_database.db desde ml_items_CON_marketplace_20260104.txt
Crea una DB limpia solo con los items que tienen marketplace items.
"""

import sqlite3
import json
import re
from datetime import datetime

def parse_export_file(filename):
    """
    Parsea el archivo de export y extrae toda la info de cada item.
    """
    items = []

    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Separar por items (buscar el JSON completo de cada uno)
    json_blocks = re.findall(r'--- JSON COMPLETO ---\n(.*?)\n\n', content, re.DOTALL)

    print(f"📋 JSONs encontrados: {len(json_blocks)}")

    for i, json_str in enumerate(json_blocks, 1):
        try:
            item_data = json.loads(json_str)

            # Extraer info relevante
            item_id = item_data.get('id')
            asin = item_data.get('seller_custom_field') or item_data.get('attributes', [{}])[0].get('value_name')

            # Buscar SELLER_SKU en atributos
            for attr in item_data.get('attributes', []):
                if attr.get('id') == 'SELLER_SKU':
                    asin = attr.get('value_name') or attr.get('value_id')
                    break

            if not item_id or not asin:
                continue

            items.append({
                'item_id': item_id,
                'asin': asin,
                'title': item_data.get('title'),
                'category_id': item_data.get('category_id'),
                'price_usd': item_data.get('price'),
                'status': item_data.get('status'),
                'available_quantity': item_data.get('available_quantity', 0),
                'sold_quantity': item_data.get('sold_quantity', 0),
                'date_created': item_data.get('date_created'),
                'last_updated': item_data.get('last_updated'),
                'permalink': item_data.get('permalink'),
                'thumbnail': item_data.get('thumbnail'),
                'pictures': json.dumps([p.get('url') for p in item_data.get('pictures', [])]),
                'attributes': json.dumps(item_data.get('attributes', [])),
                'shipping': json.dumps(item_data.get('shipping', {})),
                'tags': json.dumps(item_data.get('tags', [])),
            })

            if i % 100 == 0:
                print(f"   Procesados: {i}/{len(json_blocks)}")

        except json.JSONDecodeError as e:
            print(f"   ⚠️  Error parseando JSON #{i}: {e}")
            continue
        except Exception as e:
            print(f"   ⚠️  Error procesando item #{i}: {e}")
            continue

    return items

def create_new_database(items, output_db='storage/listings_database_NEW.db'):
    """
    Crea una nueva base de datos con los items parseados.
    """
    # Hacer backup de la DB actual si existe
    import os
    import shutil

    if os.path.exists('storage/listings_database.db'):
        backup_name = f'storage/listings_database_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        shutil.copy2('storage/listings_database.db', backup_name)
        print(f"✅ Backup creado: {backup_name}")

    # Crear nueva DB
    conn = sqlite3.connect(output_db)
    cursor = conn.cursor()

    # Crear tabla con el mismo esquema que la actual
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS listings (
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
            attributes_json TEXT,
            shipping_json TEXT,
            tags_json TEXT,

            -- Status
            status TEXT,
            available_quantity INTEGER,
            sold_quantity INTEGER,

            -- Fechas
            date_created TEXT,
            last_updated TEXT,

            -- Otros
            permalink TEXT,
            thumbnail TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Insertar items
    print(f"\n📝 Insertando {len(items)} items en la nueva DB...")

    for i, item in enumerate(items, 1):
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO listings (
                    item_id, asin, title, category_id, price_usd,
                    status, available_quantity, sold_quantity,
                    date_created, last_updated, permalink, thumbnail,
                    images_urls, attributes_json, shipping_json, tags_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item['item_id'],
                item['asin'],
                item['title'],
                item['category_id'],
                item['price_usd'],
                item['status'],
                item['available_quantity'],
                item['sold_quantity'],
                item['date_created'],
                item['last_updated'],
                item['permalink'],
                item['thumbnail'],
                item['pictures'],
                item['attributes'],
                item['shipping'],
                item['tags']
            ))

            if i % 100 == 0:
                print(f"   Insertados: {i}/{len(items)}")

        except Exception as e:
            print(f"   ❌ Error insertando item {item['item_id']}: {e}")

    conn.commit()

    # Estadísticas
    cursor.execute("SELECT COUNT(*) FROM listings")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT asin) FROM listings")
    unique_asins = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'active'")
    active = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'paused'")
    paused = cursor.fetchone()[0]

    conn.close()

    print(f"\n✅ Base de datos creada: {output_db}")
    print(f"   Total items: {total}")
    print(f"   ASINs únicos: {unique_asins}")
    print(f"   Activos: {active}")
    print(f"   Pausados: {paused}")

    return output_db

def main():
    """
    Función principal.
    """
    print("="*80)
    print("RECONSTRUCCIÓN DE BASE DE DATOS DESDE EXPORT")
    print("="*80)
    print()

    export_file = 'ml_items_CON_marketplace_20260104.txt'

    # Parsear export
    print(f"📖 Leyendo {export_file}...")
    items = parse_export_file(export_file)

    if not items:
        print("❌ No se encontraron items para importar")
        return

    print(f"✅ Parseados {len(items)} items")
    print()

    # Crear nueva DB
    new_db = create_new_database(items)

    print()
    print("="*80)
    print("✅ PROCESO COMPLETADO")
    print("="*80)
    print()
    print(f"Nueva DB: {new_db}")
    print(f"Para reemplazar la actual, ejecuta:")
    print(f"  mv storage/listings_database.db storage/listings_database_OLD.db")
    print(f"  mv {new_db} storage/listings_database.db")

if __name__ == "__main__":
    main()
