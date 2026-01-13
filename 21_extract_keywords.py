#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 21_extract_keywords.py - EXTRAER KEYWORDS DE CATEGORÍAS ML
# ═══════════════════════════════════════════════════════════════════════════════
#
# ¿Qué hace?
#   Lee el archivo html_categories.txt con categorías de MercadoLibre y genera keywords de Amazon.
#   Usa OpenAI API para analizar el texto y mantener contexto jerárquico.
#
#   IMPORTANTE: Mantiene el contexto de categoría padre + subcategoría
#   Ejemplo: Si ve "Bebés" → "Juguetes", genera "baby toys" (NO solo "toys")
#
# Input:
#   - html_categories.txt
#
# Output:
#   - keywords_from_ml_categories.txt (keywords únicos, ordenados alfabéticamente)
#
# Comando:
#   python3 21_extract_keywords.py
#
# ═══════════════════════════════════════════════════════════════════════════════
import os
import json
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# Inicializar cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_categories_from_text(text_content):
    """Extrae categorías del texto usando GPT-4"""
    print(f"📝 Procesando categorías del archivo...")

    # Llamar a OpenAI API
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": f"""Eres un experto en e-commerce que convierte categorías trending de MercadoLibre en keywords ESPECÍFICAS y COMPLETAS para buscar productos en Amazon.

TEXTO A ANALIZAR:
{text_content}

CONTEXTO IMPORTANTE:
Estas son categorías TRENDING de MercadoLibre. Tu trabajo es convertirlas en keywords ESPECÍFICAS que se puedan usar para BUSCAR productos similares en Amazon.

REGLA CRÍTICA #1: NUNCA generes keywords genéricas de 1 palabra
❌ MAL: "reptiles", "toys", "grooming", "food"
✅ BIEN: "reptile terrariums", "reptile tanks", "cat toys", "dog grooming brushes"

REGLA CRÍTICA #2: SIEMPRE incluye el contexto completo
- Si dice "Other categories of Reptiles & Amphibians" y luego "Terrariums, Tanks & Boxes"
  → Genera: "reptile terrariums", "reptile tanks", "reptile enclosures", "amphibian terrariums"

REGLA CRÍTICA #3: Piensa como un COMPRADOR de Amazon
- ¿Qué buscaría alguien que quiere comprar esto?
- Usa términos completos y específicos que se usan en Amazon
- Incluye variaciones comunes

EJEMPLOS REALES:

Input: "Other categories of Animals and Pets" → "Pet Treats"
Output:
dog treats
cat treats
pet training treats
healthy pet treats
natural pet treats
dental dog treats

Input: "Other categories of Reptiles & Amphibians" → "Terrariums, Tanks & Boxes"
Output:
reptile terrariums
reptile tanks
reptile enclosures
glass terrariums
amphibian tanks
snake terrariums
lizard tanks

Input: "Other categories of Cats" → "Grooming & Care"
Output:
cat grooming brushes
cat nail clippers
cat grooming gloves
cat deshedding tools
cat grooming kit
cat dental care

Input: "Other categories of Horses" → "Grooming & Care"
Output:
horse grooming brushes
horse curry combs
horse hoof picks
horse grooming kit
horse mane brush
horse tail brush

REGLAS DE EXPANSIÓN:
1. Si ves "Toys" bajo "Cats", genera múltiples keywords: "cat toys", "interactive cat toys", "cat toy balls", "cat feather toys", etc.
2. Si ves "Food", expande: "dog food", "cat food", "dry dog food", "wet cat food", "organic pet food"
3. Piensa en VARIACIONES que un comprador real buscaría
4. Incluye ADJETIVOS comunes: "natural", "organic", "premium", "training", "interactive", "automatic"
5. Incluye TIPOS específicos cuando sea relevante

FILTROS ESTRICTOS:
- IGNORA "Other" como categoría
- IGNORA porcentajes y números
- IGNORA "Sales in this category..."
- NO generes keywords de 1 sola palabra
- NO generes keywords genéricos sin contexto

FORMATO DE SALIDA:
- Un keyword por línea
- Sin numeración, sin viñetas
- Solo el keyword en inglés (minúsculas)
- Mínimo 2 palabras por keyword
- Máximo 4-5 palabras por keyword

IMPORTANTE: Genera entre 3-8 variaciones de keywords por cada categoría, pensando en cómo buscaría un comprador REAL en Amazon."""
                }
            ],
            max_tokens=4000
        )

        # Extraer keywords de la respuesta
        keywords_text = response.choices[0].message.content

        # Limpiar keywords
        keywords = []
        for line in keywords_text.split('\n'):
            k = line.strip().lower()

            # Filtrar líneas vacías, comentarios, y respuestas de error de GPT
            if not k or k.startswith('#') or k.startswith('❌') or k.startswith('✅'):
                continue

            # Filtrar respuestas de error comunes de GPT
            if "sorry" in k or "can't assist" in k or "cannot" in k:
                continue

            # Filtrar keywords que terminen en "other"
            if k.endswith(" other") or k == "other":
                continue

            # Remover texto innecesario
            k = k.replace(" in baby safety", "")
            k = k.replace(" in baby", "")

            # Agregar si no quedó vacío
            if k:
                keywords.append(k)

        # Extraer usage de tokens
        usage = response.usage
        input_tokens = usage.prompt_tokens
        output_tokens = usage.completion_tokens
        total_tokens = usage.total_tokens

        # Calcular costo (GPT-4o pricing: $2.50 per 1M input tokens, $10.00 per 1M output tokens)
        cost_input = (input_tokens / 1_000_000) * 2.50
        cost_output = (output_tokens / 1_000_000) * 10.00
        total_cost = cost_input + cost_output

        print(f"   ✅ Extraídas {len(keywords)} keywords")
        print(f"   📊 Tokens: {total_tokens:,} (input: {input_tokens:,}, output: {output_tokens:,})")
        print(f"   💵 Costo: ${total_cost:.4f}")

        return keywords, {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens, "cost": total_cost}

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return [], {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost": 0.0}

def main():
    print("=" * 80)
    print("EXTRACCIÓN DE KEYWORDS DESDE html_categories.txt")
    print("=" * 80)
    print()

    # Leer archivo html_categories.txt
    input_file = Path(__file__).parent / "html_categories.txt"

    if not input_file.exists():
        print(f"❌ No se encontró el archivo: {input_file}")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        text_content = f.read()

    print(f"📂 Archivo encontrado: {input_file}")
    print(f"📄 Tamaño: {len(text_content)} caracteres")
    print()

    # Procesar el texto
    all_keywords, stats = extract_categories_from_text(text_content)

    total_stats = {
        "input_tokens": stats["input_tokens"],
        "output_tokens": stats["output_tokens"],
        "total_tokens": stats["total_tokens"],
        "cost": stats["cost"]
    }

    # Cargar keywords existentes si el archivo ya existe
    output_file = Path(__file__).parent / "keywords_from_ml_categories.txt"
    existing_keywords = set()

    if output_file.exists():
        with open(output_file, 'r', encoding='utf-8') as f:
            existing_keywords = set(line.strip() for line in f if line.strip())
        print(f"📝 Cargadas {len(existing_keywords)} keywords existentes del archivo")

    # Combinar keywords nuevas con existentes
    all_keywords_set = set(all_keywords)
    all_keywords_set.update(existing_keywords)

    # Ordenar alfabéticamente
    sorted_keywords = sorted(all_keywords_set, key=str.lower)

    # Guardar en archivo (sobrescribir con lista completa)
    with open(output_file, 'w', encoding='utf-8') as f:
        for keyword in sorted_keywords:
            f.write(f"{keyword}\n")

    new_keywords_count = len(all_keywords_set) - len(existing_keywords)

    # Resumen
    print("=" * 80)
    print("✅ PROCESAMIENTO COMPLETADO")
    print("=" * 80)
    print(f"Keywords extraídas:      {len(all_keywords)}")
    print(f"Keywords existentes:     {len(existing_keywords)}")
    print(f"Keywords nuevas:         {new_keywords_count}")
    print(f"Total keywords únicas:   {len(sorted_keywords)}")
    print(f"Archivo guardado:        {output_file}")
    print()
    print("📊 CONSUMO TOTAL:")
    print(f"   Tokens totales:       {total_stats['total_tokens']:,}")
    print(f"   - Input tokens:       {total_stats['input_tokens']:,}")
    print(f"   - Output tokens:      {total_stats['output_tokens']:,}")
    print(f"   💵 Costo total:       ${total_stats['cost']:.4f}")
    print()

    # Mostrar preview
    print("📋 Preview de keywords (primeras 20):")
    for i, keyword in enumerate(sorted_keywords[:20], 1):
        print(f"   {i:2d}. {keyword}")

    if len(sorted_keywords) > 20:
        print(f"   ... y {len(sorted_keywords) - 20} más")
    print()

if __name__ == "__main__":
    main()
