#!/usr/bin/env python3
"""
Sistema para extraer TODAS las características de productos usando IA (una sola vez)
y guardarlas en archivos de texto para respuestas rápidas sin tokens.
"""

import os
import json
import openai
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Directorios
STORAGE_DIR = Path("storage")
MINI_ML_DIR = STORAGE_DIR / "logs" / "publish_ready"
AMAZON_JSON_DIR = STORAGE_DIR / "asins_json"
CHARACTERISTICS_DIR = STORAGE_DIR / "product_characteristics"

# Crear directorio si no existe
CHARACTERISTICS_DIR.mkdir(parents=True, exist_ok=True)


def load_mini_ml(asin):
    """Cargar mini_ml JSON"""
    try:
        mini_ml_path = MINI_ML_DIR / f"{asin}_mini_ml.json"
        if mini_ml_path.exists():
            with open(mini_ml_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Error cargando mini_ml para {asin}: {e}")
    return None


def load_amazon_json(asin):
    """Cargar JSON de Amazon completo"""
    try:
        amazon_path = AMAZON_JSON_DIR / f"{asin}.json"
        if amazon_path.exists():
            with open(amazon_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Error cargando amazon_json para {asin}: {e}")
    return None


def extract_characteristics_with_ai(asin, mini_ml=None, amazon_json=None):
    """
    Usa GPT-4o-mini para extraer TODAS las características del producto
    y organizarlas en formato de texto estructurado.

    Solo se ejecuta UNA VEZ por producto.
    """

    # Construir contexto COMPLETO con TODA la información disponible
    context_parts = []

    context_parts.append(f"SKU/ASIN: {asin}")

    # ========================================
    # DATOS DE MINI_ML
    # ========================================
    if mini_ml:
        if mini_ml.get("title_ai"):
            context_parts.append(f"\nTÍTULO: {mini_ml['title_ai']}")

        if mini_ml.get("brand"):
            context_parts.append(f"MARCA: {mini_ml['brand']}")

        if mini_ml.get("model"):
            context_parts.append(f"MODELO: {mini_ml['model']}")

        # TODOS los atributos mapeados
        attrs = mini_ml.get("attributes_mapped", {})
        if attrs:
            context_parts.append("\n=== ATRIBUTOS DEL PRODUCTO ===")
            for attr_key, attr_data in attrs.items():
                attr_value = attr_data.get("value_name")
                if attr_value and attr_value not in ["centimeters", "ounces", "en_US"]:
                    context_parts.append(f"{attr_key}: {attr_value}")

        # Características principales
        main_chars = mini_ml.get("main_characteristics", [])
        if main_chars:
            context_parts.append("\n=== CARACTERÍSTICAS PRINCIPALES ===")
            for char in main_chars:
                if isinstance(char, dict):
                    name = char.get("name", "")
                    value = char.get("value_name", "")
                    if name and value and value not in ["centimeters", "ounces", "en_US"]:
                        context_parts.append(f"{name}: {value}")

        # Características secundarias
        second_chars = mini_ml.get("second_characteristics", [])
        if second_chars:
            context_parts.append("\n=== CARACTERÍSTICAS SECUNDARIAS ===")
            for char in second_chars:
                if isinstance(char, dict):
                    name = char.get("name", "")
                    value = char.get("value_name", "")
                    if name and value and value not in ["centimeters", "ounces", "en_US"]:
                        context_parts.append(f"{name}: {value}")

        # Dimensiones y peso
        pkg = mini_ml.get("package", {})
        if pkg:
            context_parts.append("\n=== DIMENSIONES Y PESO ===")
            context_parts.append(f"Largo: {pkg.get('length_cm')} cm")
            context_parts.append(f"Ancho: {pkg.get('width_cm')} cm")
            context_parts.append(f"Alto: {pkg.get('height_cm')} cm")
            context_parts.append(f"Peso: {pkg.get('weight_kg')} kg")

        # Descripción completa
        desc = mini_ml.get("description_ai", "")
        if desc:
            context_parts.append(f"\n=== DESCRIPCIÓN COMPLETA ===\n{desc}")

    # ========================================
    # DATOS DE AMAZON JSON (info adicional)
    # ========================================
    if amazon_json:
        # Features/Bullet points de Amazon
        features = amazon_json.get("features", [])
        if features:
            context_parts.append("\n=== FEATURES DE AMAZON ===")
            for i, feature in enumerate(features, 1):
                context_parts.append(f"{i}. {feature}")

        # Especificaciones técnicas de Amazon
        specs = amazon_json.get("specifications", {})
        if specs:
            context_parts.append("\n=== ESPECIFICACIONES TÉCNICAS ===")
            for key, value in specs.items():
                context_parts.append(f"{key}: {value}")

        # Descripción de Amazon (si es diferente)
        amazon_desc = amazon_json.get("description", "")
        if amazon_desc and (not mini_ml or amazon_desc != mini_ml.get("description_ai", "")):
            context_parts.append(f"\n=== DESCRIPCIÓN DE AMAZON ===\n{amazon_desc}")

    context = "\n".join(context_parts)

    # ========================================
    # PROMPT PARA LA IA
    # ========================================
    system_prompt = """Eres un experto en extraer y organizar información de productos para e-commerce.

Tu tarea es EXTRAER Y ORGANIZAR TODAS las características del producto en un formato estructurado de texto plano.

FORMATO DE SALIDA (usar este formato exacto):

SKU: [valor]
TITULO: [valor]
MARCA: [valor]
MODELO: [valor si existe]

=== INFORMACIÓN BÁSICA ===
CATEGORIA: [valor si se puede inferir]
TIPO_PRODUCTO: [valor]
[cualquier otra info básica relevante]

=== QUÉ INCLUYE / CANTIDAD ===
CANTIDAD: [número de piezas/unidades]
INCLUYE: [descripción detallada de qué incluye]
CONTENIDO: [lista específica de items]

=== CARACTERÍSTICAS FÍSICAS ===
COLOR: [valor]
MATERIAL: [valor]
DIMENSIONES: [valor en formato claro]
PESO: [valor con unidad]
TAMAÑO: [valor si aplica]
[cualquier otra característica física]

=== ESPECIFICACIONES TÉCNICAS ===
[Listar TODAS las specs técnicas relevantes]
[Para electrónica: voltaje, potencia, conectividad, etc.]
[Para ropa: tallas, tela, cuidado, etc.]
[Para cualquier categoría: extraer TODO lo relevante]

=== CARACTERÍSTICAS ESPECIALES ===
[Todo lo que hace especial al producto]
[Certificaciones, features únicos, tecnologías, etc.]

=== DESCRIPCIÓN DETALLADA ===
[Resumen completo del producto en 2-4 párrafos]
[Incluir beneficios, usos, y detalles importantes]

=== INFORMACIÓN ADICIONAL ===
[Advertencias, instrucciones de uso, garantía, etc.]

INSTRUCCIONES IMPORTANTES:
1. Extraer TODA la información disponible, no omitir nada
2. Si un campo no aplica o no existe, escribir "No especificado"
3. Ser específico y detallado
4. Mantener el formato con === para secciones
5. El objetivo es que con SOLO este archivo se puedan responder TODAS las preguntas sobre el producto
6. Si hay información duplicada en diferentes fuentes, unificar en la versión más completa
7. Para categorías específicas (electrónica, ropa, juguetes, etc.) adaptar las secciones según relevancia"""

    try:
        print(f"  🤖 Extrayendo características con IA...")

        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extrae TODAS las características de este producto:\n\n{context}"}
            ],
            max_tokens=2000,  # Más tokens para extraer TODO
            temperature=0.3   # Más conservador para mantener precisión
        )

        characteristics_text = response.choices[0].message.content.strip()
        tokens_used = response.usage.total_tokens

        return characteristics_text, tokens_used

    except Exception as e:
        print(f"  ❌ Error con IA: {e}")
        return None, 0


def save_characteristics(asin, characteristics_text):
    """Guardar características en archivo de texto"""
    try:
        output_path = CHARACTERISTICS_DIR / f"{asin}.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(characteristics_text)
        print(f"  ✅ Guardado en: {output_path}")
        return True
    except Exception as e:
        print(f"  ❌ Error guardando: {e}")
        return False


def generate_for_asin(asin):
    """Generar archivo de características para un ASIN"""
    print(f"\n{'='*80}")
    print(f"📦 Procesando: {asin}")
    print(f"{'='*80}")

    # Verificar si ya existe
    output_path = CHARACTERISTICS_DIR / f"{asin}.txt"
    if output_path.exists():
        print(f"  ⏭️  Ya existe archivo de características, saltando...")
        return True, 0

    # Cargar datos
    print(f"  📥 Cargando datos...")
    mini_ml = load_mini_ml(asin)
    amazon_json = load_amazon_json(asin)

    if not mini_ml and not amazon_json:
        print(f"  ❌ No se encontraron datos para {asin}")
        return False, 0

    # Extraer características con IA
    characteristics_text, tokens = extract_characteristics_with_ai(asin, mini_ml, amazon_json)

    if not characteristics_text:
        return False, 0

    # Guardar
    success = save_characteristics(asin, characteristics_text)

    if success:
        print(f"  💰 Tokens usados: {tokens}")
        print(f"  💵 Costo aproximado: ${tokens * 0.00000015:.6f} USD")

    return success, tokens


def generate_all_products():
    """Generar archivos de características para TODOS los productos"""
    print("\n" + "="*80)
    print("🚀 GENERANDO CARACTERÍSTICAS PARA TODOS LOS PRODUCTOS")
    print("="*80)

    # Buscar todos los ASINs en mini_ml
    asins = []
    if MINI_ML_DIR.exists():
        for file in MINI_ML_DIR.glob("*_mini_ml.json"):
            asin = file.stem.replace("_mini_ml", "")
            asins.append(asin)

    if not asins:
        print("❌ No se encontraron productos")
        return

    print(f"\n📊 Encontrados {len(asins)} productos")
    print(f"📁 Guardando en: {CHARACTERISTICS_DIR}")

    total_tokens = 0
    success_count = 0
    skipped_count = 0

    for i, asin in enumerate(asins, 1):
        print(f"\n[{i}/{len(asins)}]", end=" ")

        success, tokens = generate_for_asin(asin)

        if success:
            if tokens > 0:
                success_count += 1
                total_tokens += tokens
            else:
                skipped_count += 1

    # Resumen final
    print("\n" + "="*80)
    print("📊 RESUMEN FINAL")
    print("="*80)
    print(f"✅ Archivos generados: {success_count}")
    print(f"⏭️  Archivos saltados (ya existían): {skipped_count}")
    print(f"💰 Tokens totales usados: {total_tokens:,}")
    print(f"💵 Costo total aproximado: ${total_tokens * 0.00000015:.6f} USD")
    print(f"📁 Archivos guardados en: {CHARACTERISTICS_DIR}")
    print("="*80)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Generar para ASIN específico
        asin = sys.argv[1]
        generate_for_asin(asin)
    else:
        # Generar para todos los productos
        generate_all_products()
