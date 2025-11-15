#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SISTEMA INTELIGENTE DE BÚSQUEDA DE PRODUCTOS
============================================
Busca productos en el catálogo usando AI + embeddings de OpenAI

FLUJO:
1. Analiza pregunta con Claude AI
2. Genera embedding de la búsqueda (OpenAI)
3. Compara con embeddings de listings
4. Devuelve mejor match si similarity > threshold
"""

import os
import sqlite3
import json
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

# Configuración
DB_PATH = Path(__file__).parent.parent.parent / "storage" / "listings_database.db"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SIMILARITY_THRESHOLD = float(os.getenv("PRODUCT_SEARCH_THRESHOLD", "0.8"))
EMBEDDING_MODEL = os.getenv("PRODUCT_SEARCH_MODEL", "text-embedding-3-small")

# Cliente API
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def cosine_similarity(vec1, vec2):
    """Calcula similitud coseno entre dos vectores"""
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)

    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def analyze_question_with_ai(question_text, item_context_title=None):
    """
    Analiza pregunta con OpenAI para determinar si es búsqueda de producto

    Args:
        question_text: Texto de la pregunta
        item_context_title: Título del producto donde preguntaron (opcional)

    Returns:
        dict: {
            "is_product_search": bool,
            "keywords": str,
            "category": str
        }
    """
    if not openai_client:
        print("⚠️  OpenAI no configurado")
        return None

    # Si hay contexto del item, incluirlo en el prompt
    context_info = ""
    if item_context_title:
        context_info = f"""
CONTEXTO IMPORTANTE:
El cliente preguntó esto en la publicación: "{item_context_title}"

Usa este contexto para interpretar la pregunta:
- Si pregunta "Tenés el Pro?" y el contexto es "iPhone 15", busca "iPhone 15 Pro"
- Si pregunta "Tenés AirPods?" y el contexto es "iPhone 15", busca "AirPods" (producto diferente)
- Si pregunta "Tenés en negro?" refiere al mismo producto del contexto pero en color negro
- Si pregunta "Tenés de 256GB?" refiere al mismo producto del contexto pero con esa capacidad
- Si pregunta "Tenés el Plus?" y el contexto es "Samsung Galaxy S24", busca "Samsung Galaxy S24 Plus"
- Si pregunta "Tenés el Max?" combina con el contexto (ej: "Tenés el Max?" en "iPhone 15 Pro" → "iPhone 15 Pro Max")
- Si pregunta "Tenés el modelo 2024?" combina con el contexto (ej: en "MacBook Air" → "MacBook Air 2024")
- Si pregunta sobre accesorios (funda, cargador, cable) pero está en producto principal, busca el accesorio solo
- Si pregunta "Tenés sin cable?" refiere a versión inalámbrica del mismo producto del contexto
"""

    prompt = f"""Analiza esta pregunta de un cliente en MercadoLibre y determina:

1. ¿Es una búsqueda de producto específico? (true/false)
2. Si es búsqueda, extrae palabras clave del producto (usa el CONTEXTO si está disponible)
3. Categoría general del producto

{context_info}

Pregunta: "{question_text}"

Responde SOLO con JSON en este formato:
{{
    "is_product_search": true/false,
    "keywords": "palabras clave del producto",
    "category": "categoría general"
}}

Ejemplos SIN contexto:
- "Tenes el filtro Waterdrop G3?" → {{"is_product_search": true, "keywords": "filtro Waterdrop G3", "category": "water filters"}}
- "Cuánto demora el envío?" → {{"is_product_search": false, "keywords": "", "category": ""}}

Ejemplos CON contexto:
- Contexto: "iPhone 15 128GB" + Pregunta: "Tenés el Pro?" → {{"is_product_search": true, "keywords": "iPhone 15 Pro", "category": "smartphones"}}
- Contexto: "iPhone 15" + Pregunta: "Tenés los AirPods Max?" → {{"is_product_search": true, "keywords": "AirPods Max", "category": "headphones"}}
- Contexto: "Parlante JBL Charge 5" + Pregunta: "Tenés el Pro?" → {{"is_product_search": true, "keywords": "Parlante JBL Charge 5 Pro", "category": "speakers"}}
"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.choices[0].message.content.strip()

        # Extraer JSON de la respuesta
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        result = json.loads(content)
        return result

    except Exception as e:
        print(f"❌ Error analizando pregunta con AI: {e}")
        return None


def generate_embedding(text):
    """
    Genera embedding de texto usando OpenAI

    Args:
        text: Texto para generar embedding

    Returns:
        list: Vector de embedding (1536 dimensiones)
    """
    if not openai_client:
        print("⚠️  OpenAI no configurado")
        return None

    try:
        response = openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )

        embedding = response.data[0].embedding
        return embedding

    except Exception as e:
        print(f"❌ Error generando embedding: {e}")
        return None


def search_product(question_text, item_id_context=None, item_title_context=None, verbose=False):
    """
    Busca producto en el catálogo basado en pregunta del cliente

    Args:
        question_text: Pregunta del cliente
        item_id_context: ID del item donde preguntaron (opcional)
        item_title_context: Título del item donde preguntaron (opcional, para contexto)
        verbose: Mostrar información de debug

    Returns:
        dict: {
            "found": bool,
            "similarity": float,
            "item_id": str,
            "asin": str,
            "title": str,
            "url": str,
            "keywords": str,
            "is_product_search": bool
        }
    """

    if verbose:
        print(f"\n🔍 Analizando pregunta: '{question_text}'")
        if item_title_context:
            print(f"   Contexto: Item '{item_title_context}'")

    # Paso 1: Analizar con AI (con contexto del item si está disponible)
    analysis = analyze_question_with_ai(question_text, item_context_title=item_title_context)

    if not analysis:
        return {
            "found": False,
            "error": "No se pudo analizar la pregunta"
        }

    if verbose:
        print(f"   AI Analysis: {analysis}")

    # Si no es búsqueda de producto, retornar
    if not analysis.get("is_product_search"):
        return {
            "found": False,
            "is_product_search": False,
            "reason": "No es búsqueda de producto específico"
        }

    keywords = analysis.get("keywords", "")

    if not keywords:
        return {
            "found": False,
            "is_product_search": True,
            "reason": "No se pudieron extraer keywords"
        }

    # Paso 2: Generar embedding de la búsqueda
    if verbose:
        print(f"   Keywords: {keywords}")
        print(f"   Generando embedding...")

    search_embedding = generate_embedding(keywords)

    if not search_embedding:
        return {
            "found": False,
            "is_product_search": True,
            "keywords": keywords,
            "error": "No se pudo generar embedding"
        }

    # Paso 3: Buscar en base de datos
    if verbose:
        print(f"   Buscando en catálogo...")

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # Obtener todos los embeddings
        cursor.execute("""
            SELECT e.item_id, e.asin, e.title, e.embedding
            FROM listing_embeddings e
            INNER JOIN listings l ON e.item_id = l.item_id
            WHERE l.country = '' OR l.country IS NULL
        """)

        results = cursor.fetchall()
        conn.close()

        if not results:
            return {
                "found": False,
                "is_product_search": True,
                "keywords": keywords,
                "reason": "No hay embeddings en la base de datos"
            }

        if verbose:
            print(f"   Comparando con {len(results)} productos...")

        # Calcular similitudes
        best_match = None
        best_similarity = 0.0

        for item_id, asin, title, embedding_blob in results:
            # Deserializar embedding
            listing_embedding = json.loads(embedding_blob.decode('utf-8'))

            # Calcular similitud
            similarity = cosine_similarity(search_embedding, listing_embedding)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = {
                    "item_id": item_id,
                    "asin": asin,
                    "title": title,
                    "similarity": similarity
                }

        if verbose:
            if best_match:
                print(f"   Mejor match: {best_match['title'][:50]}... (similarity: {best_similarity:.3f})")

        # Verificar threshold
        if best_similarity >= SIMILARITY_THRESHOLD:
            # Encontrado!
            # Construir URL de MercadoLibre
            country_domain_map = {
                "MLA": "mercadolibre.com.ar",
                "MLB": "mercadolibre.com.br",
                "MLM": "mercadolibre.com.mx",
                "MLC": "mercadolibre.cl",
                "MCO": "mercadolibre.com.co"
            }

            # Extraer país del item_id (ej: MLA-123 → MLA)
            country_code = best_match["item_id"].split("-")[0]
            domain = country_domain_map.get(country_code, "mercadolibre.com")

            url = f"https://articulo.{domain}/{best_match['item_id']}"

            return {
                "found": True,
                "is_product_search": True,
                "similarity": best_similarity,
                "item_id": best_match["item_id"],
                "asin": best_match["asin"],
                "title": best_match["title"],
                "url": url,
                "keywords": keywords
            }
        else:
            # No encontrado con suficiente confianza
            return {
                "found": False,
                "is_product_search": True,
                "keywords": keywords,
                "best_match": best_match,
                "reason": f"Mejor match: {best_similarity:.2f} < threshold {SIMILARITY_THRESHOLD}"
            }

    except Exception as e:
        print(f"❌ Error buscando en BD: {e}")
        import traceback
        traceback.print_exc()
        return {
            "found": False,
            "is_product_search": True,
            "keywords": keywords,
            "error": str(e)
        }


def test_search():
    """Función de prueba"""
    print("🧪 Probando búsqueda inteligente de productos\n")
    print("=" * 60)

    test_questions = [
        "Hola, tenes el filtro Waterdrop WD-G3-W?",
        "Vendés auriculares Sony WH-1000XM5 en negro?",
        "Cuánto demora el envío?",
        "Tienen stock del Samsung DA29-00020B?",
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"\n{i}. Pregunta: '{question}'")
        print("-" * 60)

        result = search_product(question, verbose=True)

        print(f"\n   Resultado:")
        print(f"   • Encontrado: {result.get('found')}")

        if result.get("found"):
            print(f"   • Producto: {result.get('title')[:60]}...")
            print(f"   • Similarity: {result.get('similarity'):.3f}")
            print(f"   • URL: {result.get('url')}")
        elif result.get("is_product_search"):
            print(f"   • Es búsqueda: Sí")
            print(f"   • Keywords: {result.get('keywords')}")
            if result.get("best_match"):
                bm = result["best_match"]
                print(f"   • Mejor match: {bm.get('title')[:50]}... ({bm.get('similarity'):.2f})")
        else:
            print(f"   • Es búsqueda: No")
            print(f"   • Razón: {result.get('reason')}")

        print()


if __name__ == "__main__":
    test_search()
