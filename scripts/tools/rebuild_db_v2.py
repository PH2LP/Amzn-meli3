#!/usr/bin/env python3
"""
Script para reconstruir listings_database.db desde ml_items_CON_marketplace_20260104.txt
Usa el esquema CORRECTO de la DB antigua, extrayendo site_items del export.
Campos como stock, costo_amazon, precio_actual se completarán automáticamente al correr sync.
"""

import sqlite3
import json
import re
from datetime import datetime
import os
import shutil

def parse_export_file(filename):
    """
    Parsea el archivo de export línea por línea extrayendo CBT ID, ASIN, site_items, etc.
    """
    items = []

    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    current_item = {}
    in_json_block = False
    json_buffer = []

    print(f"📋 Parseando {len(lines):,} líneas...")

    for i, line in enumerate(lines):
        # Detectar inicio de item
        if line.startswith('[') and 'CBT' in line:
            # Si había un item anterior, guardarlo
            if current_item.get('item_id') and current_item.get('asin') and current_item.get('site_items'):
                items.append(current_item.copy())

            # Nuevo item
            cbt_match = re.search(r'(CBT\d+)', line)
            current_item = {
                'item_id': cbt_match.group(1) if cbt_match else None,
                'site_items': [],
                'marketplaces': [],
                'asin': None,
                'title': None,
                'category_id': None,
                'price_usd': None,
                'status': None,
                'permalink': None,
                'mini_ml_data': None,
                'gtin': None,
            }

        # Extraer ITEMS LOCALES (site_items)
        elif line.startswith('ITEMS LOCALES:'):
            site_items_str = line.replace('ITEMS LOCALES:', '').strip()
            # Formato: "MCO:MCO1761802803 | MLM:MLM4512345018 | ..."
            for part in site_items_str.split('|'):
                part = part.strip()
                if ':' in part:
                    site_id, item_id = part.split(':', 1)
                    current_item['site_items'].append({
                        'site_id': site_id.strip(),
                        'item_id': item_id.strip(),
                        'logistic_type': None  # Se completará en sync
                    })
                    current_item['marketplaces'].append(site_id.strip())

        # Extraer ASIN (SELLER_SKU)
        elif 'SELLER_SKU' in line and 'atributo' in line:
            asin_match = re.search(r': ([A-Z0-9]+)$', line)
            if asin_match:
                current_item['asin'] = asin_match.group(1)

        # Extraer título
        elif line.startswith('Título:'):
            current_item['title'] = line.replace('Título:', '').strip()

        # Inicio de JSON completo
        elif line.strip() == '--- JSON COMPLETO ---':
            in_json_block = True
            json_buffer = []

        # Fin de JSON completo (línea vacía después de JSON)
        elif in_json_block and line.strip() == '' and json_buffer:
            try:
                item_data = json.loads(''.join(json_buffer))

                # Extraer campos del JSON
                current_item['category_id'] = item_data.get('category_id')
                current_item['price_usd'] = item_data.get('price')
                current_item['status'] = item_data.get('status')
                current_item['permalink'] = item_data.get('permalink')

                # Mini ML data completo (para fallback)
                current_item['mini_ml_data'] = json.dumps(item_data)

                # Atributos
                for attr in item_data.get('attributes', []):
                    if attr.get('id') == 'GTIN':
                        current_item['gtin'] = attr.get('value_name')
                    # También extraer SELLER_SKU del JSON por si no estaba en el texto
                    if attr.get('id') == 'SELLER_SKU' and not current_item['asin']:
                        current_item['asin'] = attr.get('value_name')

            except Exception as e:
                print(f"   ⚠️  Error parseando JSON en línea {i}: {e}")

            in_json_block = False
            json_buffer = []

        # Acumular líneas del JSON
        elif in_json_block:
            json_buffer.append(line)

        # Progreso
        if i % 10000 == 0 and i > 0:
            print(f"   Líneas procesadas: {i:,}/{len(lines):,} - Items encontrados: {len(items)}")

    # Guardar último item
    if current_item.get('item_id') and current_item.get('asin') and current_item.get('site_items'):
        items.append(current_item)

    print(f"\n✅ Items válidos encontrados: {len(items)}")
    return items

def create_new_database(items, output_db='storage/listings_database_NEW.db'):
    """
    Crea una nueva base de datos con el ESQUEMA CORRECTO de la DB antigua.
    """
    # Hacer backup de la DB actual si existe
    if os.path.exists('storage/listings_database.db'):
        backup_name = f'storage/listings_database_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        shutil.copy2('storage/listings_database.db', backup_name)
        print(f"✅ Backup creado: {backup_name}")

    # Crear nueva DB
    conn = sqlite3.connect(output_db)
    cursor = conn.cursor()

    # Crear tabla con el ESQUEMA EXACTO de la DB antigua
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
    ''')

    # Crear índices
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_item_id ON listings(item_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_asin ON listings(asin)')

    # Insertar items
    print(f"\n📝 Insertando {len(items)} items en la nueva DB...")

    for i, item in enumerate(items, 1):
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO listings (
                    item_id, asin, title, category_id, price_usd,
                    permalink, marketplaces, site_items,
                    mini_ml_data, gtin, stock
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 10)
            ''', (
                item['item_id'],
                item['asin'],
                item.get('title'),
                item.get('category_id'),
                item.get('price_usd'),
                item.get('permalink'),
                json.dumps(item['marketplaces']),
                json.dumps(item['site_items']),
                item.get('mini_ml_data'),
                item.get('gtin')
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

    # Verificar site_items
    cursor.execute("SELECT item_id, site_items FROM listings LIMIT 1")
    sample = cursor.fetchone()

    conn.close()

    print(f"\n✅ Base de datos creada: {output_db}")
    print(f"   Total items: {total}")
    print(f"   ASINs únicos: {unique_asins}")
    print(f"\n📋 Sample site_items:")
    print(f"   {sample[0]}: {sample[1][:100]}...")

    return output_db

def main():
    """
    Función principal.
    """
    print("="*80)
    print("RECONSTRUCCIÓN DE BASE DE DATOS DESDE EXPORT (v2 - ESQUEMA CORRECTO)")
    print("="*80)
    print()

    export_file = 'ml_items_CON_marketplace_20260104.txt'

    if not os.path.exists(export_file):
        print(f"❌ Archivo no encontrado: {export_file}")
        return

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
    print()
    print("NOTA: Los campos stock, costo_amazon, precio_actual se completarán al correr sync")

if __name__ == "__main__":
    main()
