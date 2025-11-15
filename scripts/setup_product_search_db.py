#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SETUP DE BASE DE DATOS PARA BÚSQUEDA INTELIGENTE DE PRODUCTOS
============================================================
Crea las tablas necesarias para el sistema de búsqueda con embeddings
"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "storage" / "listings_database.db"

def setup_database():
    """Crea tablas para embeddings y product requests"""

    print("🔧 Configurando base de datos para búsqueda inteligente...")
    print(f"📁 DB: {DB_PATH}")

    if not DB_PATH.exists():
        print(f"❌ Error: Base de datos no existe en {DB_PATH}")
        return False

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Tabla de embeddings de listings
    print("\n1️⃣ Creando tabla listing_embeddings...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listing_embeddings (
            item_id TEXT PRIMARY KEY,
            asin TEXT,
            title TEXT NOT NULL,
            embedding BLOB NOT NULL,
            embedding_model TEXT DEFAULT 'text-embedding-3-small',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES listings(item_id)
        )
    """)

    # Índice para búsquedas rápidas por ASIN
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_embeddings_asin
        ON listing_embeddings(asin)
    """)

    print("   ✅ Tabla listing_embeddings creada")

    # Tabla de solicitudes de productos no encontrados
    print("\n2️⃣ Creando tabla product_requests...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id TEXT UNIQUE NOT NULL,
            item_id TEXT,
            customer_nickname TEXT,
            question_text TEXT NOT NULL,
            extracted_keywords TEXT,
            best_match_item_id TEXT,
            best_match_title TEXT,
            best_match_similarity REAL,
            status TEXT DEFAULT 'pending',
            notified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME NULL,
            resolved_with_item_id TEXT NULL
        )
    """)

    # Índices para consultas rápidas
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_requests_status
        ON product_requests(status)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_requests_question_id
        ON product_requests(question_id)
    """)

    print("   ✅ Tabla product_requests creada")

    conn.commit()
    conn.close()

    print("\n✅ Base de datos configurada exitosamente!")
    print("\n📊 Tablas creadas:")
    print("   • listing_embeddings - Para almacenar embeddings de OpenAI")
    print("   • product_requests - Para trackear solicitudes no encontradas")

    return True


if __name__ == "__main__":
    success = setup_database()
    exit(0 if success else 1)
