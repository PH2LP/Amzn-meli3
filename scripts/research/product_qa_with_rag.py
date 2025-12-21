#!/usr/bin/env python3
"""
product_qa_with_rag.py
═══════════════════════════════════════════════════════════════════════════════
SISTEMA DE Q&A SOBRE PRODUCTOS USANDO RAG (Inspirado en Amazon Rufus)
═══════════════════════════════════════════════════════════════════════════════

Alternativa al endpoint de Amazon Rufus usando RAG con Claude.

FLUJO:
1. Obtener datos del producto de Amazon SP-API
2. Scrapear reviews (o usar API de terceros)
3. Usar Claude con RAG para responder preguntas

USO:
    python3 product_qa_with_rag.py --asin B0CYM126TT --question "Is it waterproof?"
"""

import os
import sys
import json
from pathlib import Path
from anthropic import Anthropic

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv(override=True)


def get_product_data(asin):
    """Obtiene datos del producto desde JSON local"""
    try:
        # Buscar en diferentes ubicaciones
        possible_paths = [
            Path(f"storage/asins_json/{asin}.json"),
            Path(__file__).parent.parent.parent / f"storage/asins_json/{asin}.json"
        ]

        for json_file in possible_paths:
            if json_file.exists():
                with open(json_file, 'r') as f:
                    return json.load(f)

        # Si no existe, retornar datos mock mínimos
        print(f"⚠️  JSON no encontrado para {asin}, usando datos mock")
        return {
            "asin": asin,
            "title": f"Product {asin}",
            "brand": "Example Brand",
            "description": "Example product description"
        }

    except Exception as e:
        print(f"⚠️  Error obteniendo datos: {e}")
        return None


def get_product_reviews(asin, limit=30):
    """
    Obtiene reviews del producto.

    OPCIONES:
    1. Scraping directo (puede violar ToS)
    2. API de terceros (Oxylabs, ScrapeIN, etc.)
    3. Usar reviews ya guardadas

    Para este ejemplo, usaremos datos mock.
    """
    # TODO: Implementar con API real de scraping
    # Por ahora, retornamos reviews mock
    mock_reviews = [
        {
            "rating": 5,
            "title": "Great product!",
            "text": "This LEGO set is amazing. Very durable and waterproof.",
            "verified": True
        },
        {
            "rating": 4,
            "title": "Good quality",
            "text": "Nice construction, my kids love it. A bit pricey though.",
            "verified": True
        },
        {
            "rating": 5,
            "title": "Excellent!",
            "text": "Perfect for outdoor play. Resists water really well.",
            "verified": True
        }
    ]

    print(f"📚 Reviews obtenidas: {len(mock_reviews)} (mock data)")
    return mock_reviews


def ask_product_question(asin, question):
    """
    Hace una pregunta sobre el producto usando RAG con Claude.

    Similar a Amazon Rufus pero usando Claude + datos públicos.
    """
    print(f"\n{'='*80}")
    print(f"🤖 PRODUCT Q&A WITH RAG")
    print(f"{'='*80}\n")
    print(f"ASIN: {asin}")
    print(f"Pregunta: {question}\n")

    # 1. Obtener datos del producto
    print("📦 Obteniendo datos del producto...")
    product_data = get_product_data(asin)

    if not product_data:
        print("❌ No se pudieron obtener datos del producto")
        return None

    # 2. Obtener reviews
    print("⭐ Obteniendo reviews...")
    reviews = get_product_reviews(asin)

    # 3. Preparar contexto para Claude
    context = f"""
DATOS DEL PRODUCTO:
{json.dumps(product_data, indent=2)}

REVIEWS DE CLIENTES ({len(reviews)} reviews):
{json.dumps(reviews, indent=2)}
"""

    # 4. Hacer pregunta a Claude con RAG
    print("🧠 Procesando con Claude...")

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""Eres un asistente de compras experto. Basándote en los datos del producto y las reviews de clientes, responde la siguiente pregunta de manera precisa y útil.

{context}

PREGUNTA DEL USUARIO: {question}

Instrucciones:
1. Responde basándote SOLO en la información proporcionada
2. Si la información no está disponible, dilo claramente
3. Cita reviews específicas cuando sea relevante
4. Sé conciso pero completo
5. Responde en español
"""

    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        answer = response.content[0].text

        print(f"\n{'='*80}")
        print("✅ RESPUESTA:")
        print(f"{'='*80}\n")
        print(answer)
        print(f"\n{'='*80}\n")

        return {
            "question": question,
            "answer": answer,
            "asin": asin,
            "reviews_analyzed": len(reviews)
        }

    except Exception as e:
        print(f"❌ Error con Claude: {e}")
        return None


def generate_product_summary(asin):
    """Genera un resumen del producto basado en reviews (como Rufus)"""
    print(f"\n{'='*80}")
    print(f"📝 GENERANDO RESUMEN DEL PRODUCTO")
    print(f"{'='*80}\n")

    product_data = get_product_data(asin)
    reviews = get_product_reviews(asin)

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""Basándote en estos datos del producto y las reviews de clientes, genera un resumen profesional del producto que ayude a los compradores a tomar una decisión informada.

PRODUCTO:
{json.dumps(product_data, indent=2)}

REVIEWS:
{json.dumps(reviews, indent=2)}

Genera un resumen que incluya:
1. Características principales
2. Pros y contras según reviews
3. Para quién es ideal este producto
4. Rating promedio y consenso general

Formato: Máximo 150 palabras, en español.
"""

    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        summary = response.content[0].text

        print("✅ RESUMEN GENERADO:")
        print(f"\n{summary}\n")

        return summary

    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def suggest_questions(asin):
    """Sugiere preguntas relevantes sobre el producto (como Rufus)"""
    product_data = get_product_data(asin)

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""Basándote en este producto, sugiere 5 preguntas que un comprador típicamente haría antes de comprar.

PRODUCTO:
{json.dumps(product_data, indent=2)}

Formato: Lista simple de preguntas, en español.
"""

    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        questions = response.content[0].text

        print("\n💭 PREGUNTAS SUGERIDAS:")
        print(questions)

        return questions

    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Product Q&A con RAG")
    parser.add_argument("--asin", default="B0CYM126TT", help="ASIN del producto")
    parser.add_argument("--question", help="Pregunta sobre el producto")
    parser.add_argument("--summary", action="store_true", help="Generar resumen")
    parser.add_argument("--suggest", action="store_true", help="Sugerir preguntas")

    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY no configurada en .env")
        sys.exit(1)

    if args.summary:
        generate_product_summary(args.asin)
    elif args.suggest:
        suggest_questions(args.asin)
    elif args.question:
        ask_product_question(args.asin, args.question)
    else:
        print(__doc__)
        print("\nEjemplos:")
        print("  python3 product_qa_with_rag.py --asin B0CYM126TT --summary")
        print("  python3 product_qa_with_rag.py --asin B0CYM126TT --suggest")
        print('  python3 product_qa_with_rag.py --asin B0CYM126TT --question "¿Es resistente al agua?"')


if __name__ == "__main__":
    main()
