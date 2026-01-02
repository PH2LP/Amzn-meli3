#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Answer Engine v2.0

Sistema inteligente de respuestas automáticas usando:
- Chain-of-Thought reasoning
- Self-consistency validation
- Confidence scoring
- Smart notifications

Autor: Sistema mejorado - Diciembre 2024
"""

import os
import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

CONFIG = {
    "models": {
        "fast": "gpt-4o-mini",      # Para clasificación, extracción, validación
        "smart": "gpt-4o",           # Para razonamiento principal
        "genius": "gpt-4o"           # Usar gpt-4o también para complejos (o1-preview no disponible)
    },
    "confidence_thresholds": {
        "no_answer": 60,      # < 60% = No responder, notificar
        "review": 80,         # 60-80% = Responder pero notificar para revisión
        "auto": 100           # > 80% = Responder automático
    },
    "enable_self_consistency": True,    # Usar self-consistency para críticos
    "enable_validation": False,          # DESACTIVADO: causa falsos negativos
    "max_tokens_reasoning": 1000,
    "temperature_reasoning": 0.3,
    "logging_enabled": True
}

# ============================================================================
# SALUDO Y DESPEDIDA
# ============================================================================

def load_greeting_and_farewell():
    """Carga saludo y despedida del archivo docs/questions/saludo"""
    try:
        saludo_file = Path(__file__).parent.parent.parent / "docs" / "questions" / "saludo"

        with open(saludo_file, "r", encoding="utf-8") as f:
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
        log(f"⚠️ Error cargando saludo/despedida: {e}")
        return "¡Hola! Gracias por tu consulta!", "Cualquier otra duda, estamos para ayudarte. Saludos!"

SALUDO, DESPEDIDA = load_greeting_and_farewell()

# ============================================================================
# UTILIDADES
# ============================================================================

def format_answer_with_greeting(answer: str) -> str:
    """
    Formatea la respuesta con saludo y despedida

    Args:
        answer: La respuesta generada por el sistema

    Returns:
        str: Saludo + respuesta + despedida
    """
    if not answer:
        return None

    return f"{SALUDO}\n\n{answer}\n\n{DESPEDIDA}"

def log(message: str, level: str = "INFO"):
    """Log con timestamp"""
    if CONFIG["logging_enabled"]:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")


def call_openai(
    prompt: str,
    model: str = "gpt-4o",
    max_tokens: int = 500,
    temperature: float = 0.3,
    response_format: Optional[dict] = None
) -> str:
    """
    Wrapper para llamadas a OpenAI con manejo de errores.
    """
    try:
        params = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        if response_format:
            params["response_format"] = response_format

        response = openai.chat.completions.create(**params)
        return response.choices[0].message.content.strip()

    except Exception as e:
        log(f"Error en llamada OpenAI: {e}", "ERROR")
        raise


def parse_json_response(text: str) -> dict:
    """
    Extrae JSON de una respuesta que puede tener texto adicional.
    """
    # Buscar bloques de código JSON
    json_pattern = r'```json\s*(.*?)\s*```'
    match = re.search(json_pattern, text, re.DOTALL)

    if match:
        json_str = match.group(1)
    else:
        # Intentar parsear directamente
        json_str = text

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Buscar el primer { y el último }
        start = json_str.find('{')
        end = json_str.rfind('}') + 1
        if start != -1 and end > start:
            return json.loads(json_str[start:end])
        raise


# ============================================================================
# FASE 0: CLASIFICACIÓN INICIAL
# ============================================================================

def detect_product_search(question: str, item_title: Optional[str] = None) -> Dict:
    """
    Detecta si el cliente está buscando un producto específico.
    Mejorado para reducir falsos positivos en comparaciones y compatibilidad.
    """
    log("Detectando búsqueda de producto...")

    prompt = f"""Analiza si esta pregunta es una BÚSQUEDA de producto DIFERENTE (el cliente quiere comprar OTRO producto).

PREGUNTA: "{question}"
PRODUCTO ACTUAL: {item_title or "N/A"}

REGLAS PARA CLASIFICAR:

✅ SÍ ES BÚSQUEDA - El cliente quiere COMPRAR otro producto diferente:
Indicadores clave: "tenés?", "vendés?", "disponible?", "en stock?", "cuánto sale?"
Ejemplos:
- "Tenés el iPhone 15 disponible?" → BÚSQUEDA (quiere comprar iPhone)
- "Vendés también auriculares Sony?" → BÚSQUEDA (quiere comprar auriculares)
- "Me interesa el modelo XYZ, lo tenés?" → BÚSQUEDA (quiere comprar XYZ)

❌ NO ES BÚSQUEDA - Pregunta sobre características/compatibilidad de ESTE producto:

CASO 1 - COMPARACIÓN (menciona otro modelo para contexto):
- "¿Cuál es la diferencia con el modelo VT80H?" → NO es búsqueda (comparación)
- "¿Es mejor que el modelo anterior?" → NO es búsqueda (comparación genérica)
- "Si comparo con el A00114, ¿este tiene más torque?" → NO es búsqueda (comparación)
Regla: Si usa verbos "comparar", "diferencia", "mejor que" → NO es búsqueda

CASO 2 - COMPATIBILIDAD (menciona otro producto para compatibilidad):
- "¿Es compatible con iPhone 15?" → NO es búsqueda (compatibilidad)
- "¿Funciona con el adaptador que compré?" → NO es búsqueda (compatibilidad)
- "¿Sirve para tornillos de la NASA?" → NO es búsqueda (compatibilidad hiperbólica)
- "¿Funciona con PS5?" → NO es búsqueda (compatibilidad)
Regla: Si pregunta si ESTE producto funciona/es compatible CON algo → NO es búsqueda

CASO 3 - PREGUNTA SOBRE ACCESORIOS/CONTENIDO:
- "¿Viene con cable USB-C?" → NO es búsqueda (qué incluye)
- "¿Trae adaptador?" → NO es búsqueda (contenido)

PASO A PASO PARA CLASIFICAR:
1. ¿Usa verbos de COMPRA/DISPONIBILIDAD? (tenés, vendés, disponible, stock) → Probablemente SÍ búsqueda
2. ¿Usa verbos de COMPARACIÓN? (comparar, diferencia, mejor que) → NO es búsqueda
3. ¿Usa verbos de COMPATIBILIDAD? (compatible, funciona con, sirve para) → NO es búsqueda
4. ¿Pregunta sobre contenido/accesorios? (viene con, incluye, trae) → NO es búsqueda

CLAVE: Solo es búsqueda si el cliente claramente quiere COMPRAR/ADQUIRIR un producto diferente.

Responde SOLO este JSON:
{{
  "is_product_search": true o false,
  "product_mentioned": "nombre del producto mencionado o null",
  "confidence": 0-100,
  "reasoning": "breve explicación - indica qué caso es (comparación/compatibilidad/búsqueda)"
}}"""

    response = call_openai(prompt, model=CONFIG["models"]["fast"], max_tokens=200)
    result = parse_json_response(response)

    log(f"Búsqueda detectada: {result['is_product_search']} (confidence: {result['confidence']}%)")
    return result


def detect_critical_question(question: str) -> Dict:
    """
    Detecta si es una pregunta técnica crítica que requiere info precisa.
    Usa razonamiento IA para detectar conceptos de seguridad, no solo keywords.
    """
    log("Detectando pregunta crítica...")

    prompt = f"""Analiza si esta pregunta requiere información PRECISA del fabricante porque involucra SEGURIDAD o LEGALIDAD.

PREGUNTA: "{question}"

Una pregunta es CRÍTICA si pregunta sobre:

🔴 SEGURIDAD ELÉCTRICA (puede causar daños o incendios):
- Sobrecalentamiento, quemaduras, riesgo eléctrico que puede causar incendios
- Cortocircuitos o conexiones peligrosas
Ejemplos:
- "¿Incluye función que evite sobrecalentamiento?" → CRÍTICA (seguridad térmica)
- "¿Puede causar cortocircuito?" → CRÍTICA
- "¿Se puede incendiar si lo uso mucho tiempo?" → CRÍTICA

❌ NO SON CRÍTICAS (info técnica normal que está en specs):
- "¿Funciona a 220v?" → NO crítica (es info de specs)
- "¿Funciona a 110v?" → NO crítica (es info de specs)
- "¿Necesita transformador?" → NO crítica (es info de specs)
- "¿Qué voltaje usa?" → NO crítica (es info de specs)

🔴 SEGURIDAD FÍSICA (puede causar lesiones):
- Límites de peso/carga que pueden causar colapso
- Resistencia estructural en condiciones extremas
- Seguridad en niños pequeños
Ejemplos:
- "¿Soporta cámara de 10kg en exteriores ventosos?" → CRÍTICA (límite de carga + seguridad)
- "¿Es seguro para niños menores de 3 años?"
- "¿El trípode aguanta eso sin caerse?" → CRÍTICA (seguridad estructural)

🔴 SALUD:
- Alergias, toxicidad, materiales en contacto con piel/alimentos
Ejemplos:
- "¿Tiene materiales tóxicos?"
- "¿Es hipoalergénico?"

🔴 LEGAL/CERTIFICACIONES:
- Certificaciones obligatorias (ANATEL, FCC, CE)
- Garantías oficiales
- Homologaciones
Ejemplos:
- "¿Tiene certificación ANATEL?"
- "¿Viene con garantía del fabricante?"

🔴 INFORMACIÓN DE CONTACTO (TOTALMENTE PROHIBIDO):
- Números telefónicos, emails, direcciones, WhatsApp
- Cualquier dato de contacto del vendedor o fabricante
- Ubicación física, domicilio, locales
Ejemplos:
- "¿Cuál es su número de teléfono?"
- "¿Tienen email de contacto?"
- "¿Dónde están ubicados?"
- "¿Me pasás tu WhatsApp?"
- "¿Cuál es la dirección de su local?"

❌ NO SON CRÍTICAS (preguntas normales sobre características):
- "¿De qué color es?"
- "¿Cuánto pesa?"
- "¿Es compatible con iPhone?" (compatibilidad funcional, no eléctrica)
- "¿Viene con cable USB?" (accesorios incluidos)
- "¿La batería dura mucho?" (duración, no seguridad)
- "¿Es resistente al agua?" (característica del producto)
- "Is it water-resistant?" (característica del producto)
- "¿Qué funciones tiene?" (funcionalidades)
- "What functions does it have?" (funcionalidades)
- "¿Tiene GPS?" (característica)
- "¿Funciona con Bluetooth?" (conectividad)

IMPORTANTE:
- Si la pregunta menciona CONSECUENCIAS NEGATIVAS (daños, roturas, quemaduras, colapso) → Probablemente ES crítica
- Si solo pregunta sobre CARACTERÍSTICAS del producto (resistencia al agua, funciones, GPS, etc.) → NO es crítica

Responde SOLO este JSON:
{{
  "is_critical": true o false,
  "category": "electrical_safety|physical_safety|health_safety|legal|contact_info|none",
  "safety_concern": "descripción del riesgo de seguridad detectado",
  "confidence": 0-100,
  "reasoning": "por qué es o no es crítica"
}}"""

    try:
        response = call_openai(prompt, model=CONFIG["models"]["fast"], max_tokens=300, temperature=0.1)
        result = parse_json_response(response)

        if result.get("is_critical"):
            log(f"⚠️  Pregunta CRÍTICA detectada: {result.get('category')} (confidence: {result.get('confidence')}%)")
            log(f"    Riesgo: {result.get('safety_concern', 'N/A')}")
            return {
                "is_critical": True,
                "category": result.get("category", "unknown"),
                "keyword_matched": result.get("safety_concern", ""),
                "reason": result.get("reasoning", "Pregunta crítica de seguridad detectada")
            }
        else:
            log(f"Pregunta NO crítica (confidence: {result.get('confidence')}%)")
            return {"is_critical": False}

    except Exception as e:
        log(f"Error en detección de críticas: {e}", "WARNING")
        # Fallback a keywords básicos
        critical_keywords = ["voltaje", "voltage", "110v", "220v", "transformador",
                           "certificación", "anatel", "garantía", "tóxico", "alergia"]
        question_lower = question.lower()
        for keyword in critical_keywords:
            if keyword in question_lower:
                log(f"⚠️  Fallback: keyword '{keyword}' detectada como crítica")
                return {
                    "is_critical": True,
                    "category": "fallback_detection",
                    "keyword_matched": keyword,
                    "reason": f"Keyword crítica detectada: {keyword}"
                }
        return {"is_critical": False}


# ============================================================================
# FASE 1: EXTRACCIÓN DE INFORMACIÓN DEL PRODUCTO
# ============================================================================

def load_product_data(asin: str) -> Tuple[Optional[dict], Optional[dict]]:
    """
    Carga datos del producto desde mini_ml y/o amazon_json.
    Si no existen, intenta descargarlos con SP API.
    """
    mini_ml = None
    amazon_json = None

    # Intentar cargar mini_ml
    mini_ml_path = f"storage/logs/publish_ready/{asin}_mini_ml.json"
    if os.path.exists(mini_ml_path):
        try:
            with open(mini_ml_path, 'r', encoding='utf-8') as f:
                mini_ml = json.load(f)
            log(f"mini_ml cargado: {mini_ml_path}")
        except Exception as e:
            log(f"Error cargando mini_ml: {e}", "WARNING")

    # Intentar cargar amazon_json
    amazon_json_path = f"storage/asins_json/{asin}.json"
    if os.path.exists(amazon_json_path):
        try:
            with open(amazon_json_path, 'r', encoding='utf-8') as f:
                amazon_json = json.load(f)
            log(f"amazon_json cargado: {amazon_json_path}")
        except Exception as e:
            log(f"Error cargando amazon_json: {e}", "WARNING")

    # Si no hay datos, intentar descargar con SP API
    if not mini_ml and not amazon_json:
        log(f"No se encontraron datos locales para {asin}, descargando con SP API...")
        try:
            import sys
            sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
            from src.integrations.amazon_api import get_product_data_from_asin

            log(f"Descargando producto {asin} desde Amazon SP API...")
            # Guardar directamente en storage/asins_json/
            os.makedirs("storage/asins_json", exist_ok=True)
            product_data = get_product_data_from_asin(asin, save_path=amazon_json_path)

            if product_data and os.path.exists(amazon_json_path):
                log(f"✅ Producto {asin} descargado y guardado en {amazon_json_path}")
                amazon_json = product_data
            else:
                log(f"⚠️ No se pudo descargar información para {asin}", "WARNING")
        except Exception as e:
            log(f"Error descargando producto con SP API: {e}", "ERROR")

    return mini_ml, amazon_json


def extract_smart_context(asin: str) -> Dict:
    """
    Extrae información estructurada del producto usando IA.

    Retorna un contexto rico y relevante, no solo copia de datos.
    """
    log(f"Extrayendo contexto inteligente para ASIN {asin}...")

    # 1. Cargar datos disponibles
    mini_ml, amazon_json = load_product_data(asin)

    if not mini_ml and not amazon_json:
        log("No hay datos del producto disponibles", "ERROR")
        return {
            "error": "no_data",
            "completeness_score": 0.0
        }

    # 2. Preparar datos para análisis
    # Usar mini_ml preferentemente (más compacto y limpio)
    source_data = mini_ml or amazon_json

    # Limitar tamaño para el prompt (12000 chars para capturar más info)
    source_json_str = json.dumps(source_data, ensure_ascii=False)[:12000]

    # 3. Prompt para extracción inteligente
    extraction_prompt = f"""Analiza este producto y extrae TODA la información técnica disponible.

DATOS DEL PRODUCTO (JSON completo):
{source_json_str}

═══════════════════════════════════════════════════════════════
INSTRUCCIONES DE EXTRACCIÓN DINÁMICA
═══════════════════════════════════════════════════════════════

1. BUSCA información en TODOS estos campos del JSON:
   - title / itemName / title_ai
   - bullet_points / bullet_point / features
   - attributes / attributes_mapped / main_characteristics / second_characteristics
   - description / description_ai
   - whats_included / package_includes
   - dimensions / weight / package
   - battery / power / voltage
   - connectivity / wireless / bluetooth / wifi
   - memory / storage / flash_memory
   - warranty / guarantee
   - material / color / style
   - ¡Y CUALQUIER OTRO CAMPO QUE ENCUENTRES!

2. EXTRAE TODAS LAS ESPECIFICACIONES TÉCNICAS que encuentres:
   - NO te limites a categorías predefinidas
   - Si ves un campo con información útil → INCLÚYELO en key_specs
   - Ejemplos de lo que debes buscar:
     * Almacenamiento: "flash_memory", "storage", "SD", "microSD", "128GB"
     * Batería: "battery", "rechargeable", "40H", "AAA", "lithium"
     * Dimensiones: "dimensions", "weight", "size", "height", "width", "depth"
     * Conectividad: "bluetooth", "wifi", "USB", "Lightning", "wireless"
     * Resistencia: "waterproof", "IP65", "water_resistant"
     * Material: "plastic", "metal", "aluminum", "stainless steel"
     * Voltaje: "110v", "220v", "voltage", "power_source"
     * Profundidad de teclas: "key_travel", "key_depth", "stroke"
     * Peso máximo: "max_weight", "capacity", "load_capacity"
     * Cualquier spec técnica: sensor, resolution, speed, rpm, watts, etc.

3. FORMATO para key_specs:
   - Usa nombres descriptivos en español
   - Valor claro y conciso
   - Si NO encuentras una spec → NO la incluyas (no pongas "no especificada")
   - Ejemplo: "almacenamiento": "Tarjetas Micro SD (no incluidas)"
   - Ejemplo: "profundidad_teclas": "4mm de recorrido"
   - Ejemplo: "peso_maximo": "Soporta hasta 150kg"

4. Extrae las 10 características MÁS IMPORTANTES para un comprador

5. Da un score de completitud (0.0-1.0) según cuánta info útil encontraste

Responde SOLO este JSON:
{{
  "product_type": "tipo específico de producto",
  "purpose": "para qué sirve en 1 línea",
  "brand": "marca",
  "title_short": "título resumido en 60 caracteres",
  "top_features": ["feature 1", "feature 2", ..., "feature 10"],
  "key_specs": {{
    "spec_name_1": "valor claro y útil",
    "spec_name_2": "valor claro y útil",
    ...
    (INCLUYE TODAS las specs técnicas que encuentres - puede ser 5, 10, 20 o más)
  }},
  "whats_included": ["item 1", "item 2", ...],
  "completeness_score": 0.0-1.0
}}

IMPORTANTE:
- Extrae TODO lo que encuentres - no te limites
- USA nombres descriptivos en español para las specs
- Si algo está en inglés en el JSON, tradúcelo al español
- NO inventes información que no está en el JSON"""

    try:
        response = call_openai(
            extraction_prompt,
            model=CONFIG["models"]["fast"],
            max_tokens=3000,  # Tokens generosos para extraer todas las specs posibles
            temperature=0.1
        )

        context = parse_json_response(response)
        log(f"Contexto extraído (completeness: {context.get('completeness_score', 0):.2f})")

        return context

    except Exception as e:
        log(f"Error extrayendo contexto: {e}", "ERROR")

        # Fallback: usar datos básicos sin IA
        fallback_context = {
            "product_type": "unknown",
            "purpose": source_data.get("title_ai", source_data.get("title", ""))[:100],
            "brand": source_data.get("brand", ""),
            "completeness_score": 0.3
        }
        return fallback_context


# ============================================================================
# FASE 2: RAZONAMIENTO CON CHAIN-OF-THOUGHT
# ============================================================================

def generate_answer_with_reasoning(
    question: str,
    product_context: Dict,
    use_genius_model: bool = False
) -> Dict:
    """
    Genera respuesta usando Chain-of-Thought reasoning.
    """
    log("Generando respuesta con razonamiento estructurado...")

    # Seleccionar modelo
    model = CONFIG["models"]["genius"] if use_genius_model else CONFIG["models"]["smart"]

    # Preparar contexto del producto en formato legible
    context_str = json.dumps(product_context, ensure_ascii=False, indent=2)

    # Prompt con Chain-of-Thought
    reasoning_prompt = f"""Eres un VENDEDOR de MercadoLibre respondiendo preguntas de clientes en tu publicación.

CONTEXTO IMPORTANTE:
- Respondés DIRECTO como vendedor, sin formalidades excesivas
- Si no tenés la información específica, NO INVENTÉS ni des respuestas genéricas
- Para temas de IMPORTACIÓN/ADUANAS/IMPUESTOS: Explicá que MercadoLibre se encarga de toda la gestión

INFORMACIÓN DEL PRODUCTO:
{context_str}

PREGUNTA DEL CLIENTE:
"{question}"

═══════════════════════════════════════════════════════════════

PIENSA PASO A PASO:

<thinking>
PASO 1 - ENTENDER EL PRODUCTO:
- ¿Qué tipo de producto es exactamente?
- ¿Para qué se usa?
- ¿Cuáles son sus 3 características principales?

PASO 2 - ANALIZAR EL TIPO DE PREGUNTA:
- ¿Es una pregunta SIMPLE (color, peso, tamaño)?
- ¿Es COMPARACIÓN con otro modelo? → Enfócate en ESTE producto, no puedes comparar
- ¿Son MÚLTIPLES preguntas en una? → Identifica TODAS y responde TODAS
- ¿Está formulada NEGATIVAMENTE? → Cuidado con doble negación ("¿No usa pilas, verdad?" → si NO usa = confirmar que es recargable)
- ¿Pregunta COMPATIBILIDAD? → Busca specs técnicas (conectores, voltaje, sistemas)

PASO 3 - ENTENDER LA INTENCIÓN:
- ¿Qué quiere saber REALMENTE el cliente?
- ¿Por qué pregunta esto? ¿Qué le preocupa?
- ¿Qué información le ayudaría a tomar la decisión de compra?

PASO 4 - BUSCAR LA INFORMACIÓN:
- La INFORMACIÓN DEL PRODUCTO tiene todas las specs extraídas del JSON
- Busca en key_specs la información que el cliente necesita
- Ejemplo: si pregunta "memory" o "storage", busca en specs: "almacenamiento", "storage", "memoria"
- Ejemplo: si pregunta "garantía", busca: "garantia", "warranty"
- Ejemplo: si pregunta "peso", busca: "peso", "weight"
- Ejemplo: si pregunta "profundidad de teclas", busca: "profundidad_teclas", "key_travel", "recorrido"
- ¿Tengo la información específica que necesita en las specs?
- Si son múltiples preguntas, identifica cuáles SÍ puedes responder
- IMPORTANTE: Si son varias preguntas y no puedes responder TODAS, responde SOLO las que SÍ sabes
- NO menciones que falta información o que no sabes algo

PASO 5 - EVALUAR CONFIANZA:
- ¿Puedo responder con CERTEZA basándome en los datos?
- ¿O la información es insuficiente/ambigua?
- Si faltan datos para alguna parte, ¿qué confidence dar?
- Nivel de confianza: ____%

PASO 6 - PLANEAR LA RESPUESTA:
- ¿Cómo presentar la info de forma clara y útil?
- Si son múltiples preguntas, estructurar respuesta punto por punto
- Si es comparación, explicar que solo puedo hablar de ESTE producto
- Si es negativa, asegurarme de responder correctamente la negación
- ¿Qué tono usar? (amigable, técnico, persuasivo)
- ¿Hay algo POSITIVO que destacar?
</thinking>

AHORA GENERA TU RESPUESTA EN ESTE FORMATO:

INSTRUCCIONES PARA CADA TAG:
- <answer> = Tu respuesta de 2-5 líneas, tono amigable, SIN saludos ni despedidas
- <confidence> = Solo el número de 0 a 100
- <key_points> = Puntos clave que usaste para responder

FORMATO (escribe TODO entre los tags, NO dejes tags vacíos):

<answer></answer>

<confidence></confidence>

<key_points></key_points>

═══════════════════════════════════════════════════════════════

REGLAS ABSOLUTAS:

1. NUNCA inventes información que no está en el contexto

2. ⚠️ MUY IMPORTANTE - FALTA DE INFORMACIÓN:
   Si NO tienes la información específica que el cliente pregunta:
   - PON confidence=0 (CERO)
   - DEJA answer VACÍO o con texto mínimo explicando que no tienes esa info
   - Ejemplos de preguntas SIN INFO: watts, amperes, potencia, consumo eléctrico específico
   - Si el JSON no tiene esa spec técnica → confidence=0 SIEMPRE
   - NO des respuestas genéricas tipo "Te recomendaría verificar con el fabricante"

3. 🚢 IMPORTACIÓN, ADUANAS E IMPUESTOS - Regla especial:
   Si preguntan sobre:
   - Costos de importación
   - Aranceles o tarifas aduaneras
   - Impuestos de importación
   - Gestión de aduana
   - Trámites de importación

   RESPUESTA EXACTA:
   "MercadoLibre se encarga de toda la gestión de importación, aduanas e impuestos. El precio publicado es el precio final que pagás, sin costos adicionales sorpresa."

   Confidence: 95% (es información general de cómo funciona ML)
   NUNCA digas "verificá con el vendedor" o "consultar con ML" - vos SOS el vendedor

4. Sé POSITIVO pero HONESTO - destaca beneficios sin mentir

5. Evita lenguaje robótico o frases template

6. NO generes saludos ("Hola") ni despedidas - se agregan automáticamente

7. Empieza DIRECTO con la respuesta

8. Si preguntan "funciona con X" y tiene "Y integrado", destaca lo POSITIVO de Y primero

9. NUNCA te contradigas en la misma respuesta

10. Si es COMPARACIÓN, enfócate solo en ESTE producto

11. Si es NEGATIVA, entiende bien: "¿No usa pilas?" = pregunta si NO usa pilas

12. VOLTAJE - Reglas importantes:
    - Si el JSON dice "110-120V" → Menciona "clavija americana recta" + "necesitará transformador para 220V"
    - Si el JSON NO especifica voltaje → Di "Su ficha técnica no indica el voltaje específico, usualmente este tipo de dispositivos funcionan tanto con 110V como 220V"
    - NUNCA digas "no se especifica" o "te recomendaría verificar" - suena poco profesional

EJEMPLO VOLTAJE CON INFO EN JSON:
Pregunta: "¿Funciona a 220v?"
Contexto: voltage: "110-120V"
Respuesta: "El producto funciona con 110-120V y clavija americana recta, por lo que si tienes 220V en tu país necesitarás un transformador de voltaje para su correcto funcionamiento."

EJEMPLO VOLTAJE SIN INFO EN JSON:
Pregunta: "¿Funciona a 220v?"
Contexto: voltage: null o no mencionado
Respuesta EXACTA: "Su ficha técnica no indica el voltaje específico, usualmente este tipo de dispositivos funcionan tanto con 110v como 220v"

IMPORTANTE: Usa EXACTAMENTE esta frase cuando no haya voltaje en JSON
"""

    try:
        response = call_openai(
            reasoning_prompt,
            model=model,
            max_tokens=CONFIG["max_tokens_reasoning"],
            temperature=CONFIG["temperature_reasoning"]
        )

        # Parsear respuesta estructurada
        result = parse_structured_response(response)

        log(f"Respuesta generada (confidence: {result['confidence']}%)")
        return result

    except Exception as e:
        log(f"Error generando respuesta: {e}", "ERROR")
        return {
            "answer": "",
            "confidence": 0,
            "thinking": "",
            "key_points": [],
            "error": str(e)
        }


def parse_structured_response(response_text: str) -> Dict:
    """
    Parsea respuesta estructurada con tags.
    """
    result = {
        "thinking": "",
        "answer": "",
        "confidence": 0,
        "key_points": []
    }

    # Extraer <thinking>
    thinking_match = re.search(r'<thinking>(.*?)</thinking>', response_text, re.DOTALL)
    if thinking_match:
        result["thinking"] = thinking_match.group(1).strip()

    # Extraer <answer>
    answer_match = re.search(r'<answer>(.*?)</answer>', response_text, re.DOTALL)
    if answer_match:
        result["answer"] = answer_match.group(1).strip()

    # Extraer <confidence>
    confidence_match = re.search(r'<confidence>(.*?)</confidence>', response_text, re.DOTALL)
    if confidence_match:
        confidence_text = confidence_match.group(1).strip()
        # Extraer número
        numbers = re.findall(r'\d+', confidence_text)
        if numbers:
            result["confidence"] = int(numbers[0])

    # Extraer <key_points>
    keypoints_match = re.search(r'<key_points>(.*?)</key_points>', response_text, re.DOTALL)
    if keypoints_match:
        keypoints_text = keypoints_match.group(1).strip()
        # Convertir a lista si es posible
        result["key_points"] = keypoints_text

    return result


# ============================================================================
# FASE 3: VALIDACIÓN Y CONFIDENCE SCORING
# ============================================================================

def calculate_final_confidence(
    result: Dict,
    product_context: Dict,
    question: str
) -> Dict:
    """
    Calcula confidence final considerando múltiples factores.
    """
    log("Calculando confidence final...")

    factors = []

    # Factor 1: Confidence del modelo (peso 55% - aumentado para compensar)
    model_confidence = result.get("confidence", 0)
    factors.append(("model_confidence", model_confidence, 0.55))

    # Factor 2: Completitud de información del producto (peso 20%)
    info_completeness = product_context.get("completeness_score", 0.5) * 100
    factors.append(("info_completeness", info_completeness, 0.2))

    # Factor 3: Longitud de respuesta apropiada (peso 10%)
    answer_length = len(result.get("answer", "").split())
    # 15-50 palabras es ideal
    if 15 <= answer_length <= 50:
        length_score = 100
    elif answer_length < 15:
        length_score = max(0, (answer_length / 15) * 100)
    else:  # > 50
        length_score = max(50, 100 - ((answer_length - 50) * 2))
    factors.append(("answer_length", length_score, 0.1))

    # Factor 4: No contiene palabras sospechosas (peso 15% - reducido)
    # Palabras que indican incertidumbre REAL o falta de información
    critical_uncertain_words = [
        "no tengo información",
        "no sé",
        "no estoy seguro",
        "no puedo confirmar",
        "debés consultar",
        "no especifica",  # Movido a críticas - indica falta de info
        "no indica",      # Similar a "no especifica"
        "no menciona",    # Similar a "no especifica"
        "no se especifica",
        "no está especificado",
        "[", "]"  # Placeholders
    ]

    # Palabras menos críticas (pueden ser válidas en ciertos contextos)
    minor_uncertain_words = [
        "consulta",
        "verifica"
    ]

    answer_lower = result.get("answer", "").lower()

    # Contar palabras críticas vs menores
    critical_count = sum(1 for word in critical_uncertain_words if word in answer_lower)
    minor_count = sum(1 for word in minor_uncertain_words if word in answer_lower)

    # Penalización gradual en vez de binaria
    if critical_count > 0:
        suspicious_score = 0  # Muy sospechoso
    elif minor_count > 1:
        suspicious_score = 50  # Algo sospechoso
    elif minor_count == 1:
        suspicious_score = 80  # Ligeramente sospechoso
    else:
        suspicious_score = 100  # Sin problemas

    factors.append(("no_suspicious_words", suspicious_score, 0.15))  # Peso reducido de 20% a 15%

    # Calcular weighted average
    final_confidence = sum(score * weight for _, score, weight in factors)

    log(f"Confidence final: {final_confidence:.1f}%")
    log(f"  - Model: {model_confidence}%")
    log(f"  - Info completeness: {info_completeness:.1f}%")
    log(f"  - Answer length: {length_score:.1f}%")
    log(f"  - No suspicious: {suspicious_score}%")

    return {
        "final_confidence": final_confidence,
        "factors": factors
    }


def check_contradictions(answer: str, product_context: Dict) -> Dict:
    """
    Verifica que la respuesta no tenga contradicciones.
    """
    if not CONFIG["enable_validation"]:
        return {"has_contradictions": False, "score": 100}

    log("Validando coherencia...")

    product_type = product_context.get("product_type", "producto")

    validation_prompt = f"""Verifica esta respuesta de un vendedor:

TIPO DE PRODUCTO: {product_type}
RESPUESTA: "{answer}"

Verifica:
1. ¿Tiene contradicciones internas? (ej: "Sí... pero no es")
2. ¿Es coherente con el tipo de producto?
3. ¿El tono es apropiado para ventas? (amigable, útil, no robótico)

Responde SOLO este JSON:
{{
  "has_contradictions": true/false,
  "issues": ["problema 1", "problema 2", ...],
  "is_coherent": true/false,
  "tone_appropriate": true/false,
  "score": 0-100
}}"""

    try:
        response = call_openai(
            validation_prompt,
            model=CONFIG["models"]["fast"],
            max_tokens=300,
            temperature=0.1
        )

        validation = parse_json_response(response)

        if validation.get("has_contradictions"):
            log(f"⚠️  Contradicciones detectadas: {validation.get('issues')}", "WARNING")

        return validation

    except Exception as e:
        log(f"Error en validación: {e}", "WARNING")
        return {"has_contradictions": False, "score": 100}


def apply_self_consistency(
    question: str,
    product_context: Dict,
    n: int = 3
) -> Dict:
    """
    Genera N respuestas y selecciona la más consistente.
    Solo para preguntas críticas.
    """
    if not CONFIG["enable_self_consistency"]:
        return generate_answer_with_reasoning(question, product_context)

    log(f"Aplicando self-consistency con {n} muestras...")

    responses = []

    # Generar N respuestas con temperatura ligeramente diferente
    for i in range(n):
        temp = 0.2 + (i * 0.15)  # 0.2, 0.35, 0.5

        result = generate_answer_with_reasoning(question, product_context)
        result["temperature"] = temp
        responses.append(result)

    # Usar GPT para seleccionar la mejor
    answers_text = "\n\n".join([
        f"RESPUESTA {i+1} (confidence {r['confidence']}%):\n{r['answer']}"
        for i, r in enumerate(responses)
    ])

    selection_prompt = f"""Analiza estas {n} respuestas a la misma pregunta sobre un producto:

PREGUNTA: "{question}"

{answers_text}

¿Cuál es la MÁS PRECISA, ÚTIL y CONSISTENTE?

Responde SOLO este JSON:
{{
  "best_index": 0 o 1 o 2,
  "reason": "breve explicación de 1 línea"
}}"""

    try:
        response = call_openai(
            selection_prompt,
            model=CONFIG["models"]["fast"],
            max_tokens=200
        )

        selection = parse_json_response(response)
        best_index = selection.get("best_index", 0)

        log(f"Self-consistency seleccionó respuesta #{best_index + 1}: {selection.get('reason')}")

        best_response = responses[best_index]
        best_response["self_consistency_applied"] = True

        return best_response

    except Exception as e:
        log(f"Error en self-consistency, usando primera respuesta: {e}", "WARNING")
        return responses[0]


# ============================================================================
# SISTEMA PRINCIPAL
# ============================================================================

def answer_question_v2(
    question: str,
    asin: str,
    item_title: Optional[str] = None,
    question_id: Optional[int] = None,
    customer_nickname: Optional[str] = None,
    site_id: Optional[str] = None
) -> Dict:
    """
    Sistema completo de respuestas v2.0

    Retorna:
    {
        "action": "answered" | "no_answer",
        "answer": str | None,
        "confidence": float,
        "reason": str,
        "should_notify": bool,
        "notification_type": str,
        "metadata": {...}
    }
    """
    log(f"\n{'='*80}")
    log(f"Procesando pregunta: {question[:60]}...")
    log(f"ASIN: {asin}")

    result = {
        "action": None,
        "answer": None,
        "confidence": 0.0,
        "reason": "",
        "should_notify": False,
        "notification_type": None,
        "metadata": {}
    }

    try:
        # ═══════════════════════════════════════════════════════════════
        # FASE 0: CLASIFICACIÓN INICIAL
        # ═══════════════════════════════════════════════════════════════

        # Detectar búsqueda de producto
        search_detection = detect_product_search(question, item_title)

        if search_detection["is_product_search"] and search_detection["confidence"] > 75:
            log("✋ Búsqueda de producto detectada - NO responder")
            result.update({
                "action": "no_answer",
                "reason": "product_search",
                "should_notify": True,
                "notification_type": "product_search",
                "metadata": {
                    "product_searched": search_detection.get("product_mentioned"),
                    "detection_confidence": search_detection["confidence"]
                }
            })
            return result

        # Detectar pregunta crítica
        critical = detect_critical_question(question)

        if critical["is_critical"]:
            log(f"⚠️  Pregunta crítica detectada ({critical['category']}) - NO responder")
            result.update({
                "action": "no_answer",
                "reason": "critical_question",
                "should_notify": True,
                "notification_type": "critical_question",
                "metadata": {
                    "critical_category": critical["category"],
                    "keyword_matched": critical.get("keyword_matched")
                }
            })
            return result

        # ═══════════════════════════════════════════════════════════════
        # FASE 1: EXTRACCIÓN DE INFORMACIÓN
        # ═══════════════════════════════════════════════════════════════

        product_context = extract_smart_context(asin)

        if product_context.get("error") == "no_data":
            log("❌ No hay datos del producto - NO responder")
            result.update({
                "action": "no_answer",
                "reason": "no_product_data",
                "should_notify": True,
                "notification_type": "no_data"
            })
            return result

        # ═══════════════════════════════════════════════════════════════
        # FASE 2: GENERACIÓN CON RAZONAMIENTO
        # ═══════════════════════════════════════════════════════════════

        # Decidir si usar modelo genius para preguntas complejas
        use_genius = (
            critical.get("is_critical", False) or
            len(question.split()) > 20 or  # Pregunta muy larga
            "?" in question and question.count("?") > 1  # Múltiples preguntas
        )

        if use_genius:
            log(f"🧠 Usando modelo genius ({CONFIG['models']['genius']}) para pregunta compleja")

        # Generar respuesta
        answer_result = generate_answer_with_reasoning(
            question,
            product_context,
            use_genius_model=use_genius
        )

        # ═══════════════════════════════════════════════════════════════
        # FASE 3: VALIDACIÓN Y CONFIDENCE
        # ═══════════════════════════════════════════════════════════════

        # Calcular confidence final
        confidence_analysis = calculate_final_confidence(
            answer_result,
            product_context,
            question
        )
        final_confidence = confidence_analysis["final_confidence"]

        # Validar coherencia si confidence es suficiente
        if final_confidence > 40:
            validation = check_contradictions(
                answer_result["answer"],
                product_context
            )

            if not validation.get("is_coherent", True):
                log("⚠️  Respuesta incoherente detectada - penalizando levemente")
                final_confidence = final_confidence * 0.9

            if validation.get("has_contradictions", False):
                log("⚠️  Contradicciones detectadas - penalizando confidence")
                final_confidence = final_confidence * 0.6

        # Self-consistency para preguntas críticas con low confidence
        if (critical.get("is_critical", False) and
            final_confidence < 90 and
            final_confidence > 50):
            log("🔄 Aplicando self-consistency para mejorar confidence...")
            answer_result = apply_self_consistency(question, product_context, n=3)
            # Recalcular confidence
            confidence_analysis = calculate_final_confidence(
                answer_result,
                product_context,
                question
            )
            final_confidence = min(95, confidence_analysis["final_confidence"] + 5)

        # ═══════════════════════════════════════════════════════════════
        # DECISIÓN FINAL
        # ═══════════════════════════════════════════════════════════════

        thresholds = CONFIG["confidence_thresholds"]

        if final_confidence < thresholds["no_answer"]:
            # NO responder - confidence muy bajo
            log(f"❌ Confidence muy bajo ({final_confidence:.1f}%) - NO responder")
            result.update({
                "action": "no_answer",
                "reason": "low_confidence",
                "confidence": final_confidence,
                "should_notify": True,
                "notification_type": "low_confidence",
                "metadata": {
                    "generated_answer": answer_result["answer"],
                    "reasoning": answer_result.get("thinking", "")[:300],
                    "confidence_factors": confidence_analysis["factors"]
                }
            })

        elif final_confidence < thresholds["review"]:
            # Responder PERO notificar para revisión
            log(f"⚠️  Confidence medio ({final_confidence:.1f}%) - Responder + notificar")
            result.update({
                "action": "answered",
                "answer": format_answer_with_greeting(answer_result["answer"]),
                "confidence": final_confidence,
                "reason": "medium_confidence",
                "should_notify": True,
                "notification_type": "review_recommended",
                "metadata": {
                    "reasoning": answer_result.get("thinking", "")[:300],
                    "confidence_factors": confidence_analysis["factors"]
                }
            })

        else:
            # Responder con confianza - NO notificar
            log(f"✅ Confidence alto ({final_confidence:.1f}%) - Responder automático")
            result.update({
                "action": "answered",
                "answer": format_answer_with_greeting(answer_result["answer"]),
                "confidence": final_confidence,
                "reason": "high_confidence",
                "should_notify": False,
                "metadata": {
                    "reasoning": answer_result.get("thinking", "")[:200]
                }
            })

        log(f"{'='*80}\n")
        return result

    except Exception as e:
        log(f"❌ Error inesperado: {e}", "ERROR")
        import traceback
        traceback.print_exc()

        result.update({
            "action": "no_answer",
            "reason": "system_error",
            "should_notify": True,
            "notification_type": "error",
            "metadata": {"error": str(e)}
        })
        return result


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    # Test básico
    print("\n" + "="*80)
    print("SMART ANSWER ENGINE v2.0 - TEST")
    print("="*80 + "\n")

    # Caso de prueba
    test_question = "Does it work at 220v or does it need a transformer?"
    test_asin = "B0BFJWCYTL"  # Reemplazar con un ASIN real

    result = answer_question_v2(
        question=test_question,
        asin=test_asin,
        item_title="Test Product"
    )

    print("\n" + "="*80)
    print("RESULTADO:")
    print("="*80)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()
