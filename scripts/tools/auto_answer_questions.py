#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema INTELIGENTE de respuestas automáticas para MercadoLibre.
Nueva arquitectura con:
1. Saludo y despedida personalizados
2. Preguntas genéricas (GRATIS - 0 tokens)
3. Respuestas específicas con IA usando mini_ml (mínimos tokens)
4. Fallback a amazon_json solo si es necesario
"""

import os
import re
import json
import requests
import sqlite3
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import openai

# Importar módulos de búsqueda inteligente
try:
    from smart_product_search import search_product
    from telegram_product_notifier import notify_product_request
    SMART_SEARCH_ENABLED = True
except ImportError:
    print("⚠️  Módulos de búsqueda inteligente no disponibles")
    SMART_SEARCH_ENABLED = False

load_dotenv(override=True)

ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

API = "https://api.mercadolibre.com"
HEADERS = {"Authorization": f"Bearer {ML_TOKEN}"}

# Paths
QUESTIONS_FILE = "docs/questions/preguntas_custom"
SALUDO_FILE = "docs/questions/saludo"
CHARACTERISTICS_DIR = "storage/product_characteristics"

# ========================================
# CARGAR SALUDO Y DESPEDIDA
# ========================================

def load_greeting_and_farewell():
    """Carga saludo y despedida del archivo"""
    try:
        with open(SALUDO_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        # Parsear el archivo
        saludo = ""
        despedida = ""

        lines = content.split('\n')
        current_section = None

        for line in lines:
            if line.startswith("Saludo"):
                current_section = "saludo"
                continue
            elif line.startswith("Despedida"):
                current_section = "despedida"
                continue

            if current_section == "saludo" and line.strip():
                saludo = line.strip()
            elif current_section == "despedida" and line.strip():
                despedida = line.strip()

        return saludo, despedida

    except Exception as e:
        print(f"⚠️ Error cargando saludo/despedida: {e}")
        return "¡Hola!", "Saludos!"

SALUDO, DESPEDIDA = load_greeting_and_farewell()

# ========================================
# CARGAR PREGUNTAS GENÉRICAS
# ========================================

def load_generic_questions():
    """
    Carga preguntas genéricas del archivo.
    Retorna lista de dicts: [{keywords: [...], answer: "..."}]
    """
    questions = []

    try:
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        # Parsear el archivo
        current_question = {}

        for line in content.split('\n'):
            line = line.strip()

            # Skip comentarios y líneas vacías
            if not line or line.startswith('#'):
                continue

            if line.startswith("PREGUNTA:"):
                # Guardar pregunta anterior si existe
                if current_question and 'keywords' in current_question:
                    questions.append(current_question)
                current_question = {}

            elif line.startswith("KEYWORDS:"):
                keywords_str = line.replace("KEYWORDS:", "").strip()
                current_question['keywords'] = keywords_str.split('|')

            elif line.startswith("RESPUESTA:"):
                answer = line.replace("RESPUESTA:", "").strip()
                current_question['answer'] = answer

        # Agregar última pregunta
        if current_question and 'keywords' in current_question:
            questions.append(current_question)

        print(f"✅ Cargadas {len(questions)} preguntas genéricas")
        return questions

    except Exception as e:
        print(f"⚠️ Error cargando preguntas genéricas: {e}")
        return []

GENERIC_QUESTIONS = load_generic_questions()

# ========================================
# BÚSQUEDA EN PREGUNTAS GENÉRICAS
# ========================================

def find_generic_answer(question, question_translated=None):
    """
    Busca respuesta en preguntas genéricas usando regex.
    Busca tanto en la pregunta original como en la traducida (si existe).

    Args:
        question: Pregunta original (español)
        question_translated: Pregunta traducida por ML (inglés), opcional

    Retorna: respuesta o None
    """
    # Buscar en pregunta original
    question_lower = question.lower()

    # También buscar en traducción si existe
    texts_to_search = [question_lower]
    if question_translated:
        texts_to_search.append(question_translated.lower())

    # 🔍 FILTRO: Si la pregunta es sobre CANTIDAD/NÚMERO, NO usar respuestas genéricas
    # Estas preguntas necesitan respuesta específica del JSON
    cantidad_keywords = [
        r'\bcuant[oa]s?\b',  # cuanto, cuanta, cuantos, cuantas
        r'\bhow\s+many\b',    # how many
        r'\bhow\s+much\b',    # how much
        r'\bcantidad\b',      # cantidad
        r'\bnumber\b',        # number
        r'\bpieza(s)?\b',     # pieza, piezas
        r'\bunidad(es)?\b',   # unidad, unidades
        r'\bpcs?\b',          # pc, pcs
        r'\bqty\b'            # qty
    ]

    for text in texts_to_search:
        for cantidad_kw in cantidad_keywords:
            if re.search(cantidad_kw, text, re.IGNORECASE):
                print(f"⚠️ Pregunta de CANTIDAD detectada, saltando respuestas genéricas → IA")
                return None  # Forzar uso de IA

    for q in GENERIC_QUESTIONS:
        keywords = q.get('keywords', [])

        for keyword in keywords:
            keyword = keyword.strip()
            try:
                # Buscar en todas las versiones del texto
                for text in texts_to_search:
                    if re.search(keyword, text):
                        return q.get('answer')
            except re.error:
                # Si el regex es inválido, intentar match literal
                for text in texts_to_search:
                    if keyword in text:
                        return q.get('answer')

    return None

# ========================================
# CARGAR DATOS DEL PRODUCTO
# ========================================

def load_mini_ml(asin):
    """Carga mini_ml (preferido - más corto)"""
    path = f"storage/logs/publish_ready/{asin}_mini_ml.json"
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Error cargando mini_ml: {e}")
        return None

def load_amazon_json(asin):
    """
    Carga amazon_json (fallback - más largo).
    Si no existe, lo descarga temporalmente de Amazon, responde, y lo elimina.
    """
    path = f"storage/asins_json/{asin}.json"
    downloaded_temp = False

    # 1. Verificar si ya existe
    if not os.path.exists(path):
        print(f"📥 JSON no existe para {asin}, descargando temporalmente...")

        try:
            # 2. Descargar de Amazon SP-API
            import sys
            sys.path.insert(0, 'src')
            from integrations.amazon_api import get_product_data_from_asin

            # Descargar y guardar
            data = get_product_data_from_asin(asin, save_path=path)
            downloaded_temp = True
            print(f"✅ JSON descargado temporalmente para responder pregunta")

        except Exception as e:
            print(f"❌ Error descargando JSON de Amazon: {e}")
            return None

    # 3. Cargar el JSON
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 4. Si lo descargamos temporalmente, eliminarlo después de cargarlo
        if downloaded_temp:
            os.remove(path)
            print(f"🗑️  JSON temporal eliminado (respuesta completada)")

        return data

    except Exception as e:
        print(f"⚠️ Error cargando amazon_json: {e}")
        # Limpiar archivo corrupto si existe
        if downloaded_temp and os.path.exists(path):
            os.remove(path)
        return None

# ========================================
# RESPUESTAS CON IA (OPTIMIZADAS)
# ========================================

def generate_ai_answer_from_mini_ml(question, mini_ml):
    """
    Genera respuesta con IA usando SOLO mini_ml (más corto, menos tokens).
    """
    # Construir contexto COMPLETO con TODOS los atributos del JSON
    context_parts = []

    # Información básica
    if mini_ml.get("title_ai"):
        context_parts.append(f"PRODUCTO: {mini_ml['title_ai']}")

    if mini_ml.get("brand"):
        context_parts.append(f"MARCA: {mini_ml['brand']}")

    # TODOS los atributos mapeados (no filtrar, pasar todo)
    attrs = mini_ml.get("attributes_mapped", {})
    if attrs:
        context_parts.append("\n=== ATRIBUTOS DEL PRODUCTO ===")
        for attr_key, attr_data in attrs.items():
            attr_value = attr_data.get("value_name")
            if attr_value and attr_value not in ["centimeters", "ounces", "en_US"]:  # Skip valores inútiles
                context_parts.append(f"• {attr_key}: {attr_value}")

    # Características principales
    main_chars = mini_ml.get("main_characteristics", [])
    if main_chars:
        context_parts.append("\n=== CARACTERÍSTICAS PRINCIPALES ===")
        for char in main_chars[:10]:  # Primeras 10
            if isinstance(char, dict):
                name = char.get("name", "")
                value = char.get("value_name", "")
                if name and value and value not in ["centimeters", "ounces", "en_US"]:
                    context_parts.append(f"• {name}: {value}")

    # Dimensiones
    pkg = mini_ml.get("package", {})
    if pkg:
        context_parts.append(f"\nDIMENSIONES: {pkg.get('length_cm')}×{pkg.get('width_cm')}×{pkg.get('height_cm')}cm")
        context_parts.append(f"PESO: {pkg.get('weight_kg')}kg")

    # Descripción completa
    desc = mini_ml.get("description_ai", "")
    if desc:
        # Pasar más descripción (500 caracteres)
        context_parts.append(f"\n=== DESCRIPCIÓN DETALLADA ===\n{desc[:500]}")

    context = "\n".join(context_parts)

    # Prompt ULTRA ESTRICTO y profesional
    system_prompt = """Eres un experto en ventas de US ONE WORLD. Tienes acceso COMPLETO a la información del producto en formato JSON.

🔍 INFORMACIÓN DISPONIBLE:
Te estoy dando TODO sobre el producto: ATRIBUTOS, CARACTERÍSTICAS, DESCRIPCIÓN, DIMENSIONES, etc.
La información está organizada en secciones. BUSCA en TODAS las secciones antes de responder.

🚫 PROHIBIDO TERMINANTEMENTE:
- NUNCA digas: "no especifica", "no menciona", "no dice", "la descripción no indica", "no tengo", "no aplica"
- NO invites a "revisar la descripción/publicación" - ESA es tu fuente de datos
- NO seas vago, evasivo o negativo
- NO uses frases técnicas como "N/A", "No aplica", "Sin especificar"
- NO ignores los ATRIBUTOS del producto (ahí está info como COLOR, FRAGANCIA, MATERIAL, etc.)
- Sé NATURAL y CONVERSACIONAL, como si hablaras con un amigo

✅ CÓMO RESPONDER:
1. BUSCA la respuesta en ATRIBUTOS primero (FRAGANCIA, COLOR, MATERIAL, VOLUMEN_LIQUIDO, etc.)
2. Si no está en atributos, busca en CARACTERÍSTICAS PRINCIPALES
3. Si no está ahí, busca en DESCRIPCIÓN DETALLADA
4. Si realmente NO existe el dato en NINGUNA parte: "Con gusto te confirmo esa información específica. ¿Podrías darme más detalles?"
5. Máximo 2-3 líneas, directo y útil
6. NO uses emojis

📝 EJEMPLOS OBLIGATORIOS:

P: "¿Qué aroma tiene?"
Buscar: ATRIBUTOS → FRAGANCIA
❌ MAL: "En la descripción no dice el aroma"
✅ BIEN: "La fragancia es Pure Peace, con notas de agua de rosas y peonías."

P: "¿De qué color es?"
Buscar: ATRIBUTOS → COLOR
Si no tiene color específico: ✅ "Este producto no tiene un color particular, puedes ver el diseño en las fotos."
Si tiene color: ✅ "Viene en color [COLOR]."

P: "¿Qué incluye?"
Buscar: ATRIBUTOS → ENVASE, CANTIDAD, DESCRIPCIÓN
✅ "Incluye 3 botellas de 3.4oz: gel de baño, champú y acondicionador."

P: "¿Cuántos vienen en el paquete?"
Buscar: ATRIBUTOS → CANTIDAD, ITEM_PACKAGE_QUANTITY, NUMBER_OF_ITEMS
Si viene 1: ✅ "Viene 1 unidad por paquete."
Si vienen varios: ✅ "Vienen [X] unidades en el paquete."

P: "¿De qué material es?"
Buscar: ATRIBUTOS → MATERIAL
Si no tiene material específico: ✅ "Los materiales específicos puedes verlos en las fotos del producto."
Si tiene material: ✅ "Está hecho de [MATERIAL]."

RESPONDE USANDO LA INFO DEL JSON. SÉ DIRECTO, PROFESIONAL Y NATURAL."""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Contexto del producto:\n{context}\n\nPregunta del cliente: {question}"}
            ],
            max_tokens=120,
            temperature=0.7
        )

        answer = response.choices[0].message.content.strip()
        return answer, 120  # Retornar respuesta y tokens aproximados

    except Exception as e:
        print(f"⚠️ Error con IA: {e}")
        return None, 0

def generate_ai_answer_from_amazon(question, amazon_json):
    """
    Genera respuesta con IA usando amazon_json completo (más tokens).
    Solo se usa si mini_ml no tiene suficiente info.
    """
    # Extraer info clave del amazon_json
    context_parts = []

    # Título
    title = amazon_json.get("title", "")
    if title:
        context_parts.append(f"Producto: {title}")

    # Marca
    brand = amazon_json.get("brand", "")
    if brand:
        context_parts.append(f"Marca: {brand}")

    # Features (máximo 7 porque amazon tiene más)
    features = amazon_json.get("features", [])
    if features:
        features_text = ", ".join(features[:7])
        context_parts.append(f"Características: {features_text}")

    # Especificaciones técnicas (solo algunas claves)
    specs = amazon_json.get("specifications", {})
    if specs:
        important_specs = []
        for key, value in list(specs.items())[:5]:
            important_specs.append(f"{key}: {value}")
        if important_specs:
            context_parts.append("Especificaciones: " + ", ".join(important_specs))

    # Descripción corta
    desc = amazon_json.get("description", "")
    if desc:
        context_parts.append(f"Descripción: {desc[:350]}...")

    context = "\n".join(context_parts)

    # Mismo prompt ULTRA ESTRICTO
    system_prompt = """Eres un experto en ventas de US ONE WORLD. Tienes acceso COMPLETO a la información del producto en formato JSON.

🔍 INFORMACIÓN DISPONIBLE:
Te estoy dando TODO sobre el producto: ATRIBUTOS, CARACTERÍSTICAS, DESCRIPCIÓN, DIMENSIONES, etc.
La información está organizada en secciones. BUSCA en TODAS las secciones antes de responder.

🚫 PROHIBIDO TERMINANTEMENTE:
- NUNCA digas: "no especifica", "no menciona", "no dice", "la descripción no indica", "no tengo", "no aplica"
- NO invites a "revisar la descripción/publicación" - ESA es tu fuente de datos
- NO seas vago, evasivo o negativo
- NO uses frases técnicas como "N/A", "No aplica", "Sin especificar"
- NO ignores los ATRIBUTOS del producto (ahí está info como COLOR, FRAGANCIA, MATERIAL, etc.)
- Sé NATURAL y CONVERSACIONAL, como si hablaras con un amigo

✅ CÓMO RESPONDER:
1. BUSCA la respuesta en ATRIBUTOS primero (FRAGANCIA, COLOR, MATERIAL, VOLUMEN_LIQUIDO, etc.)
2. Si no está en atributos, busca en CARACTERÍSTICAS PRINCIPALES
3. Si no está ahí, busca en DESCRIPCIÓN DETALLADA
4. Si realmente NO existe el dato en NINGUNA parte: "Con gusto te confirmo esa información específica. ¿Podrías darme más detalles?"
5. Máximo 2-3 líneas, directo y útil
6. NO uses emojis

📝 EJEMPLOS OBLIGATORIOS:

P: "¿Qué aroma tiene?"
Buscar: ATRIBUTOS → FRAGANCIA
❌ MAL: "En la descripción no dice el aroma"
✅ BIEN: "La fragancia es Pure Peace, con notas de agua de rosas y peonías."

P: "¿De qué color es?"
Buscar: ATRIBUTOS → COLOR
Si no tiene color específico: ✅ "Este producto no tiene un color particular, puedes ver el diseño en las fotos."
Si tiene color: ✅ "Viene en color [COLOR]."

P: "¿Qué incluye?"
Buscar: ATRIBUTOS → ENVASE, CANTIDAD, DESCRIPCIÓN
✅ "Incluye 3 botellas de 3.4oz: gel de baño, champú y acondicionador."

P: "¿Cuántos vienen en el paquete?"
Buscar: ATRIBUTOS → CANTIDAD, ITEM_PACKAGE_QUANTITY, NUMBER_OF_ITEMS
Si viene 1: ✅ "Viene 1 unidad por paquete."
Si vienen varios: ✅ "Vienen [X] unidades en el paquete."

P: "¿De qué material es?"
Buscar: ATRIBUTOS → MATERIAL
Si no tiene material específico: ✅ "Los materiales específicos puedes verlos en las fotos del producto."
Si tiene material: ✅ "Está hecho de [MATERIAL]."

RESPONDE USANDO LA INFO DEL JSON. SÉ DIRECTO, PROFESIONAL Y NATURAL."""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Contexto del producto:\n{context}\n\nPregunta del cliente: {question}"}
            ],
            max_tokens=150,
            temperature=0.7
        )

        answer = response.choices[0].message.content.strip()
        return answer, 150

    except Exception as e:
        print(f"⚠️ Error con IA (amazon): {e}")
        return None, 0

# ========================================
# CARACTERÍSTICAS PRE-EXTRAÍDAS (0 TOKENS)
# ========================================

def load_product_characteristics(asin):
    """
    Cargar archivo de características pre-extraídas del producto.
    Este archivo se genera UNA VEZ con IA y luego se usa infinitas veces SIN costo.

    Returns: texto completo de características o None
    """
    try:
        characteristics_path = os.path.join(CHARACTERISTICS_DIR, f"{asin}.txt")

        if os.path.exists(characteristics_path):
            with open(characteristics_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        print(f"⚠️ Error cargando características: {e}")

    return None


def generate_ai_answer_from_characteristics(question, characteristics_text):
    """
    Responde pregunta usando archivo de características pre-extraídas.

    SÚPER EFICIENTE:
    - El archivo ya tiene TODO organizado (extraído UNA VEZ con ~2000 tokens)
    - Esta función solo usa ~50 tokens para encontrar la respuesta
    - Mucho más preciso porque la info ya está estructurada

    Args:
        question: pregunta del cliente
        characteristics_text: texto completo del archivo de características

    Returns:
        (respuesta, tokens_usados)
    """

    # Prompt OPTIMIZADO para buscar en características pre-organizadas
    system_prompt = """Eres un experto vendedor de US ONE WORLD.

Te voy a dar las características COMPLETAS del producto en formato estructurado y una pregunta del cliente.

Tu tarea es:
1. BUSCAR la respuesta en las características (todo está ahí)
2. Responder de forma DIRECTA y PROFESIONAL
3. Máximo 2-3 líneas

🚫 PROHIBIDO:
- Decir "no especifica", "no menciona", "no tengo información"
- Invitar a "revisar la publicación" (la info está en las características)
- Ser vago o evasivo
- Responder "con gusto te confirmo esa información"

✅ CÓMO RESPONDER:

**Si encuentras la información:**
- Responder directamente con los detalles encontrados
Ejemplo: "Sí, incluye GPS integrado" o "El volumen es de 10.2 oz"

**Si NO encuentras la característica preguntada:**
- Si es una característica técnica que NO aparece en el archivo → el producto NO la tiene
- Responder: "Este modelo no incluye [característica]. Las características disponibles son: [mencionar las que SÍ tiene]"
Ejemplos:
  - P: "¿Tiene GPS?" (reloj básico) → "Este modelo no incluye GPS. Cuenta con cronómetro, alarma, calendario y resistencia al agua."
  - P: "¿Es Bluetooth?" → "No incluye conectividad Bluetooth. Es un modelo [tipo]."

**Solo si realmente es ambiguo:**
- "Con gusto te confirmo esa información específica. ¿Podrías darme más detalles?"

- NO uses emojis
- Buscar en TODAS las secciones (=== SECCIONES ===)

Responde basándote SOLO en la información proporcionada."""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"CARACTERÍSTICAS DEL PRODUCTO:\n\n{characteristics_text}\n\n---\n\nPREGUNTA DEL CLIENTE: {question}"}
            ],
            max_tokens=100,  # Menos tokens porque ya tenemos todo organizado
            temperature=0.5
        )

        answer = response.choices[0].message.content.strip()
        return answer, 100  # Retornar respuesta y tokens aproximados

    except Exception as e:
        print(f"⚠️ Error con IA (características): {e}")
        return None, 0

# ========================================
# DIVISIÓN DE PREGUNTAS MÚLTIPLES
# ========================================

def split_multiple_questions(text):
    """
    Divide un texto que contiene múltiples preguntas en preguntas individuales.

    Ejemplos:
        "De qué color es? De donde lo envían?" → ["De qué color es?", "De donde lo envían?"]
        "Y para que sirve? Es original?" → ["Y para que sirve?", "Es original?"]

    Returns:
        List[str]: Lista de preguntas individuales
    """
    # Si el texto tiene solo un signo de interrogación, retornar como está
    if text.count('?') <= 1:
        return [text.strip()]

    # Dividir por '?' y reconstruir cada pregunta
    parts = text.split('?')
    questions = []

    for part in parts:
        part = part.strip()
        if part:  # Ignorar partes vacías
            questions.append(part + '?')

    return questions

# ========================================
# SISTEMA PRINCIPAL
# ========================================

def answer_question(asin, question, question_translated=None, item_title=None, customer_nickname=None, site_id=None, question_id=None):
    """
    Sistema principal de respuestas automáticas.

    Flujo optimizado (NUEVO):
    1. Buscar en preguntas genéricas (GRATIS - 0 tokens)
    2. Si no hay match, buscar archivo de características pre-extraídas (MUY BARATO - ~100 tokens)
    3. Si no existe archivo, usar IA con mini_ml (BARATO - ~120 tokens)
    4. Si mini_ml no existe, usar amazon_json (MÁS CARO - ~150 tokens)
    5. Siempre agregar saludo + respuesta + despedida

    Args:
        asin: ASIN del producto
        question: Texto de la pregunta (original)
        question_translated: Texto traducido por ML (opcional)
        item_title: Título del listing donde preguntaron (opcional, para contexto)
        customer_nickname: Nickname del cliente (opcional, para notificaciones)
        site_id: Site ID del país (opcional, para notificaciones)
        question_id: ID de la pregunta (opcional, para URL)

    Returns:
        dict con {answer, method, tokens_used, cost_usd}
    """
    result = {
        "answer": None,
        "method": None,
        "tokens_used": 0,
        "cost_usd": 0.0
    }

    # PASO 0: BÚSQUEDA INTELIGENTE DE PRODUCTOS (NUEVO)
    # Si la pregunta es sobre un producto específico, buscar en el catálogo
    if SMART_SEARCH_ENABLED:
        print("🔍 Verificando si es búsqueda de producto...")

        # Pasar contexto del item si está disponible
        search_result = search_product(question, item_id_context=None, item_title_context=item_title, verbose=False)

        if search_result.get("found"):
            # ¡ENCONTRADO! Responder con el link
            product_title = search_result.get("title", "producto")
            product_url = search_result.get("url")
            similarity = search_result.get("similarity", 0)

            answer = f"¡Sí, lo tenemos disponible! 😊\n\n{product_title}\n\nPodés verlo acá: {product_url}\n\n¿Te ayudo con algo más?"

            result["answer"] = answer
            result["method"] = "smart_search_found"
            result["tokens_used"] = 150  # Aproximado (Claude + OpenAI embedding)
            result["cost_usd"] = 0.000030  # ~$0.00003

            print(f"✅ Producto encontrado (similarity: {similarity:.2f})")
            return result

        elif search_result.get("is_product_search"):
            # Es búsqueda de producto pero NO encontrado
            # → NO responder, notificar por Telegram
            print(f"❌ Producto NO encontrado (es búsqueda)")

            keywords = search_result.get("keywords", "")
            best_match = search_result.get("best_match")

            # Verificar si ya notificamos esta pregunta (para evitar spam)
            cache_file = Path(__file__).parent.parent.parent / "storage" / "notified_questions.json"
            notified_questions = set()

            if cache_file.exists():
                try:
                    with open(cache_file, 'r') as f:
                        notified_questions = set(json.load(f))
                except:
                    pass

            # Si ya notificamos esta pregunta, no volver a notificar
            question_cache_key = f"{question_id}_{keywords}" if question_id else f"temp_{keywords}"

            if question_cache_key not in notified_questions:
                # Guardar solicitud en DB
                try:
                    db_path = Path(__file__).parent.parent.parent / "storage" / "listings_database.db"
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()

                    cursor.execute("""
                        INSERT OR IGNORE INTO product_requests
                        (question_id, question_text, extracted_keywords, best_match_item_id,
                         best_match_title, best_match_similarity, status)
                        VALUES (?, ?, ?, ?, ?, ?, 'pending')
                    """, (
                        question_id or f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        question,
                        keywords,
                        best_match.get("item_id") if best_match else None,
                        best_match.get("title") if best_match else None,
                        best_match.get("similarity") if best_match else None
                    ))

                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"⚠️  Error guardando en DB: {e}")

                # Construir URL de la pregunta si tenemos question_id
                question_url = None
                if question_id:
                    country_domain_map = {
                        "MLA": "mercadolibre.com.ar",
                        "MLB": "mercadolibre.com.br",
                        "MLM": "mercadolibre.com.mx",
                        "MLC": "mercadolibre.cl",
                        "MCO": "mercadolibre.com.co"
                    }
                    if site_id:
                        domain = country_domain_map.get(site_id, "mercadolibre.com")
                        question_url = f"https://www.{domain}/responder/{question_id}"

                # Notificar por Telegram
                notify_product_request(
                    question_id=question_id or f"pending_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    question_text=question,
                    customer_nickname=customer_nickname or "unknown",
                    extracted_keywords=keywords,
                    best_match=best_match,
                    item_title=item_title,
                    question_url=question_url,
                    site_id=site_id
                )

                # Guardar en caché que ya notificamos esta pregunta
                notified_questions.add(question_cache_key)
                try:
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(cache_file, 'w') as f:
                        json.dump(list(notified_questions), f)
                except Exception as e:
                    print(f"⚠️  Error guardando caché: {e}")

                print("📱 Notificación enviada por Telegram - Pregunta queda SIN RESPONDER para que la respondas manualmente")
            else:
                print("⏭️  Pregunta ya notificada anteriormente, saltando notificación")

            # NO RESPONDER - dejar pregunta sin responder para que el usuario la responda manualmente
            result["answer"] = None
            result["method"] = "smart_search_pending_no_answer"
            result["tokens_used"] = 0
            result["cost_usd"] = 0.0

            return result

    # PASO 1: Buscar en preguntas genéricas (GRATIS)
    generic_answer = find_generic_answer(question, question_translated)

    if generic_answer:
        # Formatear: saludo + respuesta + despedida (todo junto)
        full_answer = f"{SALUDO} {generic_answer} {DESPEDIDA}"

        result["answer"] = full_answer
        result["method"] = "generic_question"
        result["tokens_used"] = 0
        result["cost_usd"] = 0.0

        print("✅ Respuesta genérica (0 tokens)")
        return result

    # PASO 2: Usar archivo de características pre-extraídas (MUY EFICIENTE)
    print("🤖 No hay respuesta genérica, buscando archivo de características...")

    characteristics_text = load_product_characteristics(asin)

    if characteristics_text:
        print(f"📄 Archivo de características encontrado ({len(characteristics_text)} caracteres)")

        ai_answer, tokens = generate_ai_answer_from_characteristics(question, characteristics_text)

        if ai_answer:
            full_answer = f"{SALUDO} {ai_answer} {DESPEDIDA}"

            result["answer"] = full_answer
            result["method"] = "ai_characteristics"
            result["tokens_used"] = tokens
            result["cost_usd"] = tokens * 0.00000075  # Costo aprox gpt-4o-mini

            print(f"✅ Respuesta con IA (características): {tokens} tokens")
            return result

    # PASO 3: Usar IA con mini_ml (BARATO)
    print("🤖 No hay respuesta genérica, intentando con IA + mini_ml...")

    mini_ml = load_mini_ml(asin)

    if mini_ml:
        ai_answer, tokens = generate_ai_answer_from_mini_ml(question, mini_ml)

        if ai_answer:
            full_answer = f"{SALUDO} {ai_answer} {DESPEDIDA}"

            result["answer"] = full_answer
            result["method"] = "ai_mini_ml"
            result["tokens_used"] = tokens
            result["cost_usd"] = tokens * 0.00000075  # Costo aprox gpt-4o-mini

            print(f"✅ Respuesta con IA (mini_ml): {tokens} tokens")
            return result

    # PASO 3: Fallback a amazon_json (MÁS CARO)
    print("🤖 mini_ml no disponible, intentando con amazon_json...")

    amazon_json = load_amazon_json(asin)

    if amazon_json:
        ai_answer, tokens = generate_ai_answer_from_amazon(question, amazon_json)

        if ai_answer:
            full_answer = f"{SALUDO} {ai_answer} {DESPEDIDA}"

            result["answer"] = full_answer
            result["method"] = "ai_amazon_json"
            result["tokens_used"] = tokens
            result["cost_usd"] = tokens * 0.00000075

            print(f"✅ Respuesta con IA (amazon_json): {tokens} tokens")
            return result

    # PASO 4: No se pudo generar respuesta
    fallback = "Por favor envíame más detalles sobre tu consulta para poder ayudarte mejor."
    full_answer = f"{SALUDO} {fallback} {DESPEDIDA}"

    result["answer"] = full_answer
    result["method"] = "fallback"
    result["tokens_used"] = 0
    result["cost_usd"] = 0.0

    return result

# ========================================
# INTEGRACIÓN CON MERCADOLIBRE
# ========================================

def get_item_info(item_id):
    """
    Obtiene información de un item_id de MercadoLibre.
    item_id puede ser CBTxxxxxx (Global Selling) o MLAxxxxxx (local)

    Returns:
        dict: {"asin": str, "title": str} o None si hay error
    """
    try:
        url = f"{API}/items/{item_id}"
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        item = r.json()

        # Obtener título
        title = item.get("title", "")

        # Intentar obtener ASIN de seller_custom_field (items locales)
        asin = item.get("seller_custom_field")
        if asin:
            return {"asin": asin.strip(), "title": title}

        # Si no hay seller_custom_field, buscar en attributes (items CBT)
        # IMPORTANTE: Priorizar SELLER_SKU (ASIN) sobre GTIN
        attributes = item.get("attributes", [])

        # Primer intento: buscar SELLER_SKU o ASIN
        for attr in attributes:
            attr_id = attr.get("id", "")
            if attr_id in ["SELLER_SKU", "ASIN"]:
                value = attr.get("value_name") or attr.get("value_id")
                if value:
                    return {"asin": str(value).strip(), "title": title}

        # Segundo intento: GTIN como fallback
        for attr in attributes:
            attr_id = attr.get("id", "")
            if attr_id == "GTIN":
                value = attr.get("value_name") or attr.get("value_id")
                if value:
                    return {"asin": str(value).strip(), "title": title}

        print(f"   ⚠️ No se encontró ASIN/SKU para {item_id}")
        return {"asin": None, "title": title}

    except Exception as e:
        print(f"⚠️ Error obteniendo info para {item_id}: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"   Response: {e.response.text[:200]}")
        return None

def get_item_asin(item_id):
    """
    Backward compatibility: obtiene solo el ASIN
    """
    info = get_item_info(item_id)
    return info["asin"] if info else None

def post_answer_to_ml(question_id, answer):
    """Postea respuesta en MercadoLibre"""
    try:
        url = f"{API}/marketplace/answers"
        body = {
            "question_id": question_id,
            "text": answer
        }
        r = requests.post(url, headers=HEADERS, json=body, timeout=30)
        r.raise_for_status()
        print(f"✅ Respuesta posteada en ML (question_id: {question_id})")
        return True
    except Exception as e:
        print(f"⚠️ Error posteando respuesta: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"   Response: {e.response.text}")
        return False

def get_seller_id():
    """Obtiene el seller_id del usuario actual"""
    try:
        url = f"{API}/users/me"
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("id")
    except Exception as e:
        print(f"⚠️ Error obteniendo seller_id: {e}")
        return None

def get_unanswered_questions():
    """Obtiene preguntas sin responder de MercadoLibre"""
    try:
        seller_id = get_seller_id()
        if not seller_id:
            print("⚠️ No se pudo obtener seller_id")
            return []

        url = f"{API}/marketplace/questions/search"
        params = {
            "seller_id": seller_id,
            "status": "UNANSWERED",
            "limit": 50
        }
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        questions = data.get("questions", [])
        return questions if questions is not None else []
    except Exception as e:
        print(f"⚠️ Error obteniendo preguntas: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"   Response: {e.response.text}")
        return []

# ========================================
# LOOP AUTOMÁTICO
# ========================================

def auto_answer_loop(dry_run=True):
    """
    Loop principal para responder preguntas automáticamente.

    Args:
        dry_run: Si True, solo muestra respuestas sin postear
    """
    print("=" * 80)
    print("🤖 SISTEMA DE RESPUESTAS AUTOMÁTICAS")
    print(f"   Modo: {'DRY RUN (solo muestra)' if dry_run else 'LIVE (postea respuestas)'}")
    print(f"   Saludo: {SALUDO}")
    print(f"   Despedida: {DESPEDIDA}")
    print("=" * 80)
    print()

    questions = get_unanswered_questions()
    print(f"📩 Encontradas {len(questions)} preguntas sin responder\n")

    total_tokens = 0
    total_cost = 0.0
    answered = 0

    for q in questions:
        question_id = q.get("id")
        item_id = q.get("item_id")  # CBTxxxxxx (Global)
        marketplace_item_id = q.get("marketplace_item_id")  # MLMxxxxxx (Local)
        text = q.get("text")  # Texto original
        text_translated = q.get("text_translated")  # Texto traducido por ML
        from_user = q.get("from", {}).get("nickname", "Usuario")
        site_id = q.get("site_id", "N/A")

        print(f"\n{'=' * 80}")
        print(f"📩 Pregunta #{question_id}")
        print(f"   Site: {site_id}")
        print(f"   Item Global: {item_id}")
        if marketplace_item_id:
            print(f"   Item Local: {marketplace_item_id}")
        print(f"   De: {from_user}")
        print(f"   Texto original: {text}")
        if text_translated and text_translated != text:
            print(f"   Texto traducido: {text_translated}")
        print()

        # Obtener ASIN e información del item (preferir item_id global CBT)
        # Intentar primero con el item global (CBT), luego con el local
        asin = None
        item_title = None

        if item_id:
            item_info = get_item_info(item_id)
            if item_info:
                asin = item_info["asin"]
                item_title = item_info["title"]

        if not asin and marketplace_item_id:
            item_info = get_item_info(marketplace_item_id)
            if item_info:
                asin = item_info["asin"]
                item_title = item_info["title"]

        if not asin:
            print(f"   ⚠️ No se pudo obtener ASIN para {item_id or marketplace_item_id}")
            continue

        print(f"   ASIN: {asin}")
        if item_title:
            print(f"   Item: {item_title[:60]}{'...' if len(item_title) > 60 else ''}")

        # Dividir preguntas múltiples (ej: "De qué color es? De donde lo envían?")
        individual_questions = split_multiple_questions(text)

        if len(individual_questions) > 1:
            print(f"   🔀 Detectadas {len(individual_questions)} preguntas:")
            for i, q in enumerate(individual_questions, 1):
                print(f"      {i}. {q}")

        # Responder cada pregunta individual
        all_answers = []
        total_question_tokens = 0
        total_question_cost = 0.0

        for idx, individual_question in enumerate(individual_questions, 1):
            if len(individual_questions) > 1:
                print(f"\n   ━━━ Respondiendo pregunta {idx}/{len(individual_questions)} ━━━")

            # Generar respuesta (usar texto traducido si existe para la primera pregunta)
            # Para preguntas subsecuentes, usar el texto original dividido
            question_to_answer = individual_question
            translated_to_use = text_translated if idx == 1 else None

            result = answer_question(
                asin=asin,
                question=question_to_answer,
                question_translated=translated_to_use,
                item_title=item_title,
                customer_nickname=from_user,
                site_id=site_id,
                question_id=question_id
            )

            print(f"💬 Respuesta #{idx}:")
            print(f"   Método: {result['method']}")
            print(f"   Tokens: {result['tokens_used']}")
            print(f"   Costo: ${result['cost_usd']:.6f} USD")

            if result['answer']:
                # Remover saludo y despedida de respuestas individuales
                # (los agregaremos una sola vez al final)
                answer_body = result['answer']
                answer_body = answer_body.replace(SALUDO, '').replace(DESPEDIDA, '').strip()
                all_answers.append(answer_body)

            total_question_tokens += result['tokens_used']
            total_question_cost += result['cost_usd']

        # Combinar todas las respuestas con saludo + despedida UNA SOLA VEZ
        if all_answers:
            combined_answer = f"{SALUDO}\n\n" + "\n\n".join(all_answers) + f"\n\n{DESPEDIDA}"

            print(f"\n💬 Respuesta FINAL combinada:")
            print(f"   Total preguntas: {len(individual_questions)}")
            print(f"   Tokens totales: {total_question_tokens}")
            print(f"   Costo total: ${total_question_cost:.6f} USD")
            print(f"\n   Texto:")
            for line in combined_answer.split('\n'):
                print(f"   {line}")

            total_tokens += total_question_tokens
            total_cost += total_question_cost

            # Postear si no es dry run
            if not dry_run:
                if post_answer_to_ml(question_id, combined_answer):
                    answered += 1
        else:
            print("   ⚠️ No se generaron respuestas")

    print(f"\n{'=' * 80}")
    print("📊 RESUMEN")
    print(f"{'=' * 80}")
    print(f"Preguntas procesadas: {len(questions)}")
    print(f"Respuestas enviadas: {answered}")
    print(f"Tokens totales usados: {total_tokens}")
    print(f"Costo total: ${total_cost:.6f} USD")
    print()

if __name__ == "__main__":
    import time

    # Modo LIVE - Postea respuestas automáticamente en MercadoLibre
    print("Ejecutando en modo LIVE (postea respuestas)...\n")
    print("🔄 Loop infinito - verifica preguntas cada 60 segundos")
    print("   Para detener: systemctl stop amz-ml-auto-answer\n")

    while True:
        try:
            # Recargar token del .env en cada iteración (por si ml_token_loop lo renovó)
            load_dotenv(override=True)
            current_token = os.getenv("ML_ACCESS_TOKEN")

            # Actualizar las variables globales del módulo
            import sys
            current_module = sys.modules[__name__]
            current_module.ML_TOKEN = current_token
            current_module.HEADERS = {"Authorization": f"Bearer {current_token}"}

            auto_answer_loop(dry_run=False)

            # Esperar 60 segundos antes de volver a verificar
            print(f"\n⏸️  Esperando 60 segundos...")
            time.sleep(60)

        except KeyboardInterrupt:
            print("\n\n⛔ Detenido por usuario (Ctrl+C)")
            break
        except Exception as e:
            print(f"\n❌ Error en loop: {e}")
            print("   Esperando 60 segundos antes de reintentar...\n")
            time.sleep(60)
