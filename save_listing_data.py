#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo para guardar datos de listings cuando se publican.
Crea una base de datos local con toda la info necesaria para responder preguntas.
"""

import os
import json
import sqlite3
from datetime import datetime

DB_PATH = "storage/listings_database.db"

def init_database():
    """Inicializa la base de datos SQLite"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tabla principal de listings
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
            images_urls TEXT,  -- JSON array
            attributes TEXT,   -- JSON object
            main_features TEXT,  -- JSON array (bullet points)

            -- Marketplaces donde está publicado
            marketplaces TEXT,  -- JSON array: ["MLM", "MLB", ...]

            -- Metadata
            date_published TIMESTAMP,
            date_updated TIMESTAMP,

            -- Data completa del mini_ml para fallback
            mini_ml_data TEXT  -- JSON completo
        )
    """)

    # Índices para búsqueda rápida
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_item_id ON listings(item_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_asin ON listings(asin)")

    # Tabla de preguntas frecuentes (para respuestas rápidas)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faq_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_pattern TEXT NOT NULL,
            answer_template TEXT NOT NULL,
            category TEXT,  -- shipping, dimensions, warranty, etc.
            priority INTEGER DEFAULT 0,
            uses_count INTEGER DEFAULT 0
        )
    """)

    # Tabla de respuestas generadas (caché)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS answer_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT,
            question_hash TEXT,  -- MD5 de la pregunta normalizada
            question TEXT,
            answer TEXT,
            created_at TIMESTAMP,
            used_count INTEGER DEFAULT 0
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_question_hash ON answer_cache(question_hash)")

    conn.commit()
    conn.close()

    print(f"✅ Base de datos inicializada en: {DB_PATH}")

def save_listing(item_id, mini_ml, marketplaces=None):
    """
    Guarda datos de un listing cuando se publica.

    Args:
        item_id: ID del item en MercadoLibre (puede ser None si aún no se publicó)
        mini_ml: Diccionario con datos del mini_ml
        marketplaces: Lista de marketplaces ["MLM", "MLB", ...]
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    asin = mini_ml.get("asin", "")
    pkg = mini_ml.get("package", {})
    price = mini_ml.get("price", {})

    # Extraer características principales (bullets)
    main_features = []
    if mini_ml.get("main_characteristics"):
        main_features = mini_ml["main_characteristics"]

    # Extraer URLs de imágenes
    images = mini_ml.get("images", [])
    if isinstance(images, list):
        image_urls = [img.get("url") if isinstance(img, dict) else img for img in images]
    else:
        image_urls = []

    # Preparar datos
    data = {
        "item_id": item_id,
        "asin": asin,
        "title": mini_ml.get("title_ai", ""),
        "description": mini_ml.get("description_ai", ""),
        "brand": mini_ml.get("brand", ""),
        "model": mini_ml.get("model", ""),
        "category_id": mini_ml.get("category", "").split("(")[-1].strip(")") if "(" in mini_ml.get("category", "") else mini_ml.get("category", ""),
        "category_name": mini_ml.get("category", "").split("(")[0].strip() if "(" in mini_ml.get("category", "") else "",
        "price_usd": price.get("net_proceeds_usd", 0),
        "length_cm": pkg.get("length_cm"),
        "width_cm": pkg.get("width_cm"),
        "height_cm": pkg.get("height_cm"),
        "weight_kg": pkg.get("weight_kg"),
        "images_urls": json.dumps(image_urls),
        "attributes": json.dumps(mini_ml.get("attributes", [])),
        "main_features": json.dumps(main_features),
        "marketplaces": json.dumps(marketplaces or ["MLM", "MLB", "MLC", "MCO", "MLA"]),
        "date_published": datetime.now().isoformat(),
        "date_updated": datetime.now().isoformat(),
        "mini_ml_data": json.dumps(mini_ml)
    }

    # Insertar o actualizar
    cursor.execute("""
        INSERT INTO listings (
            item_id, asin, title, description, brand, model,
            category_id, category_name, price_usd,
            length_cm, width_cm, height_cm, weight_kg,
            images_urls, attributes, main_features, marketplaces,
            date_published, date_updated, mini_ml_data
        ) VALUES (
            :item_id, :asin, :title, :description, :brand, :model,
            :category_id, :category_name, :price_usd,
            :length_cm, :width_cm, :height_cm, :weight_kg,
            :images_urls, :attributes, :main_features, :marketplaces,
            :date_published, :date_updated, :mini_ml_data
        )
        ON CONFLICT(item_id) DO UPDATE SET
            title = :title,
            description = :description,
            date_updated = :date_updated
    """, data)

    conn.commit()
    conn.close()

    print(f"✅ Listing guardado: {asin} (item_id: {item_id})")

def load_listing_by_item_id(item_id):
    """Carga datos de un listing por item_id"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM listings WHERE item_id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None

def load_listing_by_asin(asin):
    """Carga datos de un listing por ASIN"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM listings WHERE asin = ?", (asin,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None

def populate_faq_templates():
    """Llena la tabla de FAQs con respuestas template comunes"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    templates = [
        # Envío
        ("envio|shipping|envía|demora|tarda|llega|entrega",
         "Este producto se envía desde Estados Unidos a través de MercadoLibre Global. El tiempo de entrega estimado es de 15-25 días hábiles. El envío está incluido en el precio y puedes hacer seguimiento desde tu cuenta de MercadoLibre.",
         "shipping", 10),

        # Stock/disponibilidad
        ("stock|disponible|hay|tienen|queda",
         "Sí, el producto está disponible. Puedes realizar tu compra con confianza.",
         "stock", 9),

        # Garantía
        ("garantia|garantía|defecto|falla|problema|devol",
         "Todos nuestros productos cuentan con la garantía de MercadoLibre. Si hay algún problema con tu producto, puedes iniciar una devolución desde tu cuenta dentro de los 30 días posteriores a la recepción.",
         "warranty", 8),

        # Colores/variantes
        ("color|modelo|variante|opcion|version|tamaño",
         "La publicación muestra el producto exacto que recibirás. Si necesitas confirmar alguna característica específica, por favor menciona cuál en tu pregunta.",
         "variants", 7),

        # Factura
        ("factura|invoice|recibo|comprobante",
         "Recibirás tu comprobante de compra automáticamente a través de MercadoLibre. Este sirve como factura válida para tu compra.",
         "invoice", 6),

        # Autenticidad
        ("original|autentico|authentico|falso|trucho|legitimo",
         "Todos nuestros productos son 100% originales y nuevos. Trabajamos directamente con distribuidores autorizados en Estados Unidos.",
         "authenticity", 9),
    ]

    for pattern, answer, category, priority in templates:
        cursor.execute("""
            INSERT OR IGNORE INTO faq_templates (question_pattern, answer_template, category, priority)
            VALUES (?, ?, ?, ?)
        """, (pattern, answer, category, priority))

    conn.commit()
    conn.close()
    print("✅ Templates FAQ actualizados")

if __name__ == "__main__":
    # Inicializar base de datos
    init_database()
    populate_faq_templates()

    # Ejemplo: Guardar un listing de prueba
    print("\n📝 Guardando listings desde mini_ml existentes...")
    import glob

    mini_ml_files = glob.glob("storage/logs/publish_ready/*_mini_ml.json")
    for path in mini_ml_files[:3]:  # Solo los primeros 3 como ejemplo
        try:
            with open(path, "r", encoding="utf-8") as f:
                mini_ml = json.load(f)

            save_listing(
                item_id=None,  # No tenemos item_id aún
                mini_ml=mini_ml,
                marketplaces=["MLM", "MLB", "MLC", "MCO", "MLA"]
            )
        except Exception as e:
            print(f"⚠️ Error: {e}")

    print("\n✅ Base de datos creada y poblada")
