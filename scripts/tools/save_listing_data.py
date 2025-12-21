#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo para guardar datos de listings en la base de datos
Usado por main2 para almacenar item_ids después de publicar
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(override=True)

DB_PATH = "storage/listings_database.db"

def is_save_to_db_enabled():
    """Lee la variable SAVE_TO_DB del .env cada vez que se llama"""
    return os.getenv("SAVE_TO_DB", "true").lower() == "true"

def init_database():
    """Inicializa la base de datos si no existe"""
    Path("storage").mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # La tabla ya existe, solo verificar que tenga la estructura correcta
    # No hacemos nada si ya existe
    cursor.execute("""
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

            -- Sistema de precios dinámicos
            costo_amazon REAL,
            tax_florida REAL,
            precio_original REAL,
            precio_actual REAL,
            es_catalogo INTEGER DEFAULT 0,
            ultima_actualizacion_precio TIMESTAMP
        )
    """)

    # Agregar columnas si la tabla ya existe pero no tiene estas columnas
    cursor.execute("PRAGMA table_info(listings)")
    existing_columns = [col[1] for col in cursor.fetchall()]

    new_columns = {
        'costo_amazon': 'REAL',
        'tax_florida': 'REAL',
        'precio_original': 'REAL',
        'precio_actual': 'REAL',
        'es_catalogo': 'INTEGER DEFAULT 0',
        'ultima_actualizacion_precio': 'TIMESTAMP',
        'amazon_url': 'TEXT',
        'gtin': 'TEXT'
    }

    for col_name, col_type in new_columns.items():
        if col_name not in existing_columns:
            cursor.execute(f"ALTER TABLE listings ADD COLUMN {col_name} {col_type}")


    conn.commit()
    conn.close()


def save_listing(item_id, mini_ml, marketplaces=None, site_items=None):
    """
    Guarda o actualiza un listing en la base de datos

    Args:
        item_id: ID del item en MercadoLibre
        mini_ml: Dict con los datos del mini_ml
        marketplaces: Lista de marketplaces donde está publicado
        site_items: Lista de dicts con info por país (site_id, item_id, price, status)
    """
    # Verificar si el guardado en DB está habilitado
    if not is_save_to_db_enabled():
        print(f"   ⚠️  SAVE_TO_DB=false → No se guardará {mini_ml.get('asin', 'N/A')} en la DB")
        return

    if marketplaces is None:
        marketplaces = ["MLM", "MLB", "MLC", "MCO", "MLA"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Extraer datos del mini_ml
    asin = mini_ml.get("asin", "")
    title = mini_ml.get("title_ai", "")
    brand = mini_ml.get("brand", "")
    model = mini_ml.get("model", "")
    category_id = mini_ml.get("category_id", "")
    category_name = mini_ml.get("category_name", "")

    # Construir URL de Amazon
    amazon_url = f"https://www.amazon.com/dp/{asin}" if asin else None
    gtin = mini_ml.get("gtin", "")

    # Precio
    price_info = mini_ml.get("price", {})
    price_usd = price_info.get("net_proceeds_usd", 0.0)

    # Dimensiones del paquete
    package = mini_ml.get("package", {})
    length_cm = package.get("length_cm", 0.0)
    width_cm = package.get("width_cm", 0.0)
    height_cm = package.get("height_cm", 0.0)
    weight_kg = package.get("weight_kg", 0.0)

    # Convertir listas/dicts a JSON string
    import json
    # ✅ Filtrar solo elementos dict válidos antes de acceder con .get()
    images_urls = json.dumps([img.get("url") for img in mini_ml.get("images", []) if isinstance(img, dict)])
    attributes = json.dumps(mini_ml.get("attributes_mapped", {}))
    main_features = json.dumps(mini_ml.get("main_characteristics", []))
    marketplaces_str = json.dumps(marketplaces)
    mini_ml_data = json.dumps(mini_ml)
    site_items_str = json.dumps(site_items) if site_items else None

    now = datetime.now().isoformat()

    # Verificar si ya existe este ASIN
    cursor.execute("SELECT id FROM listings WHERE asin = ?", (asin,))
    existing = cursor.fetchone()

    if existing:
        # Actualizar registro existente
        cursor.execute("""
            UPDATE listings
            SET item_id = ?,
                title = ?,
                brand = ?,
                model = ?,
                category_id = ?,
                category_name = ?,
                price_usd = ?,
                length_cm = ?,
                width_cm = ?,
                height_cm = ?,
                weight_kg = ?,
                images_urls = ?,
                attributes = ?,
                main_features = ?,
                marketplaces = ?,
                site_items = ?,
                date_updated = ?,
                mini_ml_data = ?,
                amazon_url = ?,
                gtin = ?
            WHERE asin = ?
        """, (
            item_id, title, brand, model, category_id, category_name,
            price_usd, length_cm, width_cm, height_cm, weight_kg,
            images_urls, attributes, main_features, marketplaces_str,
            site_items_str, now, mini_ml_data, amazon_url, gtin, asin
        ))
    else:
        # Insertar nuevo registro
        cursor.execute("""
            INSERT INTO listings (
                item_id, asin, title, brand, model, category_id, category_name,
                price_usd, length_cm, width_cm, height_cm, weight_kg,
                images_urls, attributes, main_features, marketplaces,
                site_items, date_published, date_updated, mini_ml_data,
                amazon_url, gtin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_id, asin, title, brand, model, category_id, category_name,
            price_usd, length_cm, width_cm, height_cm, weight_kg,
            images_urls, attributes, main_features, marketplaces_str,
            site_items_str, now, now, mini_ml_data, amazon_url, gtin
        ))

    conn.commit()
    conn.close()


def check_asin_exists(asin: str) -> dict:
    """
    Verifica si un ASIN ya fue publicado en la BD

    Returns:
        dict: {
            'exists': bool,
            'item_id': str o None,
            'title': str o None,
            'date_published': str o None
        }
    """
    init_database()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT item_id, title, date_published
        FROM listings
        WHERE asin = ?
        LIMIT 1
    """, (asin,))

    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            'exists': True,
            'item_id': result[0],
            'title': result[1],
            'date_published': result[2]
        }
    else:
        return {
            'exists': False,
            'item_id': None,
            'title': None,
            'date_published': None
        }


def check_gtin_exists(gtin: str) -> dict:
    """
    Verifica si un GTIN ya fue publicado en la BD

    Returns:
        dict: {
            'exists': bool,
            'asin': str o None,
            'item_id': str o None,
            'title': str o None,
            'date_published': str o None
        }
    """
    init_database()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT asin, item_id, title, date_published
        FROM listings
        WHERE gtin = ?
        LIMIT 1
    """, (gtin,))

    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            'exists': True,
            'asin': result[0],
            'item_id': result[1],
            'title': result[2],
            'date_published': result[3]
        }
    else:
        return {
            'exists': False,
            'asin': None,
            'item_id': None,
            'title': None,
            'date_published': None
        }
