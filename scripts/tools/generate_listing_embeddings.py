#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GENERADOR DE EMBEDDINGS PARA LISTINGS
=====================================
Genera embeddings de OpenAI para todos los listings en el catálogo

MODOS:
- Inicial: Genera embeddings para todos los listings (primera vez)
- Incremental: Solo genera para listings nuevos sin embedding
"""

import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

# Configuración
DB_PATH = Path(__file__).parent.parent.parent / "storage" / "listings_database.db"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("PRODUCT_SEARCH_MODEL", "text-embedding-3-small")

# Cliente OpenAI
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def generate_embedding_batch(texts, batch_size=100):
    """
    Genera embeddings en batch para mejor performance

    Args:
        texts: Lista de textos
        batch_size: Tamaño del batch

    Returns:
        list: Lista de embeddings
    """
    if not openai_client:
        raise Exception("OpenAI no configurado. Agregá OPENAI_API_KEY al .env")

    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]

        try:
            response = openai_client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch
            )

            embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(embeddings)

            print(f"   ✅ Batch {i//batch_size + 1}: {len(batch)} embeddings generados")

        except Exception as e:
            print(f"   ❌ Error en batch {i//batch_size + 1}: {e}")
            # En caso de error, generar None para este batch
            all_embeddings.extend([None] * len(batch))

    return all_embeddings


def generate_all_embeddings(incremental=True):
    """
    Genera embeddings para todos los listings

    Args:
        incremental: Si True, solo procesa listings sin embedding
    """

    print("🔄 Generando embeddings de listings...")
    print(f"📁 DB: {DB_PATH}")
    print(f"🤖 Modelo: {EMBEDDING_MODEL}")
    print(f"📊 Modo: {'Incremental' if incremental else 'Completo'}")
    print()

    if not DB_PATH.exists():
        print(f"❌ Error: Base de datos no existe en {DB_PATH}")
        return False

    if not openai_client:
        print("❌ Error: OpenAI no configurado")
        print("   Agregá OPENAI_API_KEY al archivo .env")
        return False

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # Obtener listings que necesitan embedding
        if incremental:
            # Solo listings sin embedding
            query = """
                SELECT l.item_id, l.asin, l.title
                FROM listings l
                LEFT JOIN listing_embeddings e ON l.item_id = e.item_id
                WHERE e.item_id IS NULL
                  AND (l.country = '' OR l.country IS NULL)
                ORDER BY l.item_id
            """
        else:
            # Todos los listings
            query = """
                SELECT item_id, asin, title
                FROM listings
                WHERE country = '' OR country IS NULL
                ORDER BY item_id
            """

        cursor.execute(query)
        listings = cursor.fetchall()

        if not listings:
            print("✅ No hay listings nuevos para procesar")
            conn.close()
            return True

        print(f"📦 Encontrados: {len(listings)} listings para procesar\n")

        # Preparar textos para embeddings
        texts = []
        for item_id, asin, title in listings:
            # Usar título como texto para embedding
            texts.append(title)

        # Generar embeddings en batch
        print("🤖 Generando embeddings con OpenAI...")
        embeddings = generate_embedding_batch(texts, batch_size=100)

        # Guardar embeddings en DB
        print("\n💾 Guardando embeddings en base de datos...")

        saved_count = 0
        error_count = 0

        for (item_id, asin, title), embedding in zip(listings, embeddings):
            if embedding is None:
                error_count += 1
                continue

            try:
                # Serializar embedding a JSON
                embedding_json = json.dumps(embedding)

                # Insertar o actualizar
                cursor.execute("""
                    INSERT OR REPLACE INTO listing_embeddings
                    (item_id, asin, title, embedding, embedding_model, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    item_id,
                    asin,
                    title,
                    embedding_json.encode('utf-8'),
                    EMBEDDING_MODEL,
                    datetime.now().isoformat()
                ))

                saved_count += 1

                if saved_count % 50 == 0:
                    print(f"   💾 Guardados: {saved_count}/{len(listings)}")

            except Exception as e:
                print(f"   ❌ Error guardando {item_id}: {e}")
                error_count += 1

        conn.commit()
        conn.close()

        print(f"\n✅ Proceso completado!")
        print(f"   • Guardados: {saved_count}")
        if error_count > 0:
            print(f"   • Errores: {error_count}")

        # Calcular costo aproximado
        total_tokens = sum(len(text.split()) for text in texts) * 1.3  # Aproximación
        cost = (total_tokens / 1000) * 0.00002  # Precio de text-embedding-3-small
        print(f"\n💰 Costo aproximado: ${cost:.4f} USD")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_stats():
    """Muestra estadísticas de embeddings"""

    print("📊 Estadísticas de Embeddings\n")

    if not DB_PATH.exists():
        print(f"❌ Base de datos no existe")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Total de listings
    cursor.execute("SELECT COUNT(*) FROM listings WHERE country = '' OR country IS NULL")
    total_listings = cursor.fetchone()[0]

    # Listings con embedding
    cursor.execute("SELECT COUNT(*) FROM listing_embeddings")
    total_embeddings = cursor.fetchone()[0]

    # Listings sin embedding
    cursor.execute("""
        SELECT COUNT(*)
        FROM listings l
        LEFT JOIN listing_embeddings e ON l.item_id = e.item_id
        WHERE e.item_id IS NULL AND (l.country = '' OR l.country IS NULL)
    """)
    pending = cursor.fetchone()[0]

    conn.close()

    print(f"📦 Total de listings: {total_listings}")
    print(f"✅ Con embedding: {total_embeddings}")
    print(f"⏳ Pendientes: {pending}")

    if total_listings > 0:
        coverage = (total_embeddings / total_listings) * 100
        print(f"📈 Cobertura: {coverage:.1f}%")


if __name__ == "__main__":
    import sys

    # Verificar argumentos
    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        get_stats()
    elif len(sys.argv) > 1 and sys.argv[1] == "--full":
        # Modo completo (regenerar todos)
        generate_all_embeddings(incremental=False)
    else:
        # Modo incremental por defecto
        print("💡 Tip: Usá --stats para ver estadísticas")
        print("💡 Tip: Usá --full para regenerar todos los embeddings\n")
        generate_all_embeddings(incremental=True)
