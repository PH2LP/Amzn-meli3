#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# python3 00_extract_keywords.py - EXTRAER KEYWORDS DE TEXTO DE CATEGORÍAS ML
# ═══════════════════════════════════════════════════════════════════════════════
#
# ¿Qué hace?
#   Lee texto de categorías de MercadoLibre y genera keywords de Amazon.
#   Usa OpenAI GPT para procesar el texto y mantener contexto jerárquico.
#
# Input:
#   - Archivo: ml_categories_text.txt (texto copiado de las screenshots)
#   - Formato esperado: Una categoría por línea, con indentación para jerarquía
#
# Output:
#   - keywords_from_ml_categories.txt (keywords únicos, ordenados alfabéticamente)
#
# Comando:
#   python3 22_extract_keywords_from_text.py
#
# ═══════════════════════════════════════════════════════════════════════════════
import os
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# Inicializar cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_keywords_from_text(text):
    """Extrae keywords usando GPT-4"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": f"""Convierte estas categorías de MercadoLibre a keywords de búsqueda de Amazon en inglés.

REGLAS CRÍTICAS:
1. Mantén el contexto JERÁRQUICO - si ves una categoría padre (ej: Bebés) y subcategorías debajo, combínalas
2. Ejemplo: "Bebés > Baño > Termómetros" = "baby bath thermometers"
3. NO incluyas "other" como keyword
4. NO repitas el nombre de la categoría dentro del keyword
5. Genera keywords prácticos para buscar en Amazon

CATEGORÍAS DE MERCADOLIBRE:
{text}

FORMATO DE SALIDA:
- Un keyword por línea
- Solo el keyword en inglés
- Sin numeración, sin guiones
- Sin explicaciones
- Siempre con contexto de categoría padre cuando aplique"""
            }
        ],
        max_tokens=4000
    )

    # Extraer keywords
    keywords_text = response.choices[0].message.content

    # Limpiar keywords
    keywords = []
    for line in keywords_text.split('\n'):
        k = line.strip()
        # Filtrar líneas vacías, comentarios, y respuestas de error
        if not k or k.startswith('#') or k.startswith('❌') or k.startswith('✅'):
            continue

        # Filtrar mensajes de error completos de GPT (en inglés y español)
        error_phrases = [
            "sorry", "can't assist", "cannot", "unable to",
            "no puedo", "lo siento", "por favor proporciona"
        ]
        if any(phrase in k.lower() for phrase in error_phrases):
            continue

        # Filtrar "other"
        if k.lower().endswith(' other') or k.lower() == 'other':
            continue

        # Remover texto redundante
        k = k.replace(' in baby safety', '')
        k = k.replace(' in baby', '')

        # Limpiar duplicados de palabras consecutivas (ej: "baby bath baby bathtubs" -> "baby bath bathtubs")
        words = k.split()
        cleaned_words = []
        prev_word = None
        for word in words:
            if word.lower() != prev_word:
                cleaned_words.append(word)
            prev_word = word.lower()
        k = ' '.join(cleaned_words)

        if k:
            keywords.append(k)

    # Extraer usage
    usage = response.usage
    cost = (usage.prompt_tokens / 1_000_000 * 2.50) + (usage.completion_tokens / 1_000_000 * 10.00)

    return keywords, {
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "cost": cost
    }

def main():
    print("=" * 80)
    print("EXTRACCIÓN DE KEYWORDS DESDE TEXTO DE CATEGORÍAS ML")
    print("=" * 80)
    print()

    # Leer archivo de texto
    input_file = Path(__file__).parent / "html_categories.txt"

    if not input_file.exists():
        print(f"❌ No se encontró el archivo: {input_file}")
        print()
        print("Creá el archivo html_categories.txt y pegá el HTML/texto de la página ahí.")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()

    if not text.strip():
        print(f"❌ El archivo {input_file} está vacío")
        return

    print(f"📄 Leyendo categorías desde: {input_file}")
    lines = len([l for l in text.split('\n') if l.strip()])
    print(f"   Líneas de texto: {lines}")
    print()

    # Procesar con GPT
    print("🤖 Procesando con GPT-4...")
    keywords, stats = extract_keywords_from_text(text)
    print(f"   ✅ Extraídas {len(keywords)} keywords")
    print(f"   📊 Tokens: {stats['total_tokens']:,} (input: {stats['input_tokens']:,}, output: {stats['output_tokens']:,})")
    print(f"   💵 Costo: ${stats['cost']:.4f}")
    print()

    # Cargar keywords existentes
    output_file = Path(__file__).parent / "keywords_from_ml_categories.txt"
    existing_keywords = set()

    if output_file.exists():
        with open(output_file, 'r', encoding='utf-8') as f:
            existing_keywords = set(line.strip() for line in f if line.strip())
        print(f"📝 Cargadas {len(existing_keywords)} keywords existentes")

    # Combinar y ordenar
    all_keywords = set(keywords)
    all_keywords.update(existing_keywords)
    sorted_keywords = sorted(all_keywords, key=str.lower)

    # Guardar
    with open(output_file, 'w', encoding='utf-8') as f:
        for keyword in sorted_keywords:
            f.write(f"{keyword}\n")

    new_keywords_count = len(all_keywords) - len(existing_keywords)

    # Resumen
    print()
    print("=" * 80)
    print("✅ PROCESAMIENTO COMPLETADO")
    print("=" * 80)
    print(f"Keywords existentes:     {len(existing_keywords)}")
    print(f"Keywords nuevas:         {new_keywords_count}")
    print(f"Total keywords únicas:   {len(sorted_keywords)}")
    print(f"Archivo guardado:        {output_file}")
    print()

    # Preview
    print("📋 Preview de keywords (primeras 30):")
    for i, keyword in enumerate(sorted_keywords[:30], 1):
        print(f"   {i:2d}. {keyword}")

    if len(sorted_keywords) > 30:
        print(f"   ... y {len(sorted_keywords) - 30} más")
    print()

if __name__ == "__main__":
    main()
