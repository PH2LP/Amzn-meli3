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
    from telegram_product_notifier import notify_product_request, send_message
    SMART_SEARCH_ENABLED = True
except ImportError:
    print("⚠️  Módulos de búsqueda inteligente no disponibles")
    SMART_SEARCH_ENABLED = False

# Importar Smart Answer Engine v2
try:
    from smart_answer_engine_v2 import answer_question_v2
    SMART_ANSWER_V2_ENABLED = True
    print("✅ Smart Answer Engine v2.0 cargado")
except ImportError:
    print("⚠️  Smart Answer Engine v2.0 no disponible - usando sistema clásico")
    SMART_ANSWER_V2_ENABLED = False

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

    # 🔍 FILTROS: Detectar preguntas que NO deben usar respuestas genéricas

    # FILTRO 1: Preguntas sobre CANTIDAD/NÚMERO
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

    # FILTRO 2: Preguntas sobre DIFERENCIAS entre versiones/modelos
    difference_keywords = [
        r'\bdifferen(ce|cia)\b',  # difference, diferencia
        r'\bversus\b', r'\bvs\b',  # versus, vs
        r'\bcompara(r|cion|tive)?\b',  # comparar, comparación, comparative
        r'\bentre\b.*\by\b',  # entre X y Y
        r'\bbetween\b.*\band\b',  # between X and Y
        r'\bcual.*mejor\b',  # cual es mejor
        r'\bwhich.*better\b',  # which is better
        r'\bque.*tiene.*otro\b',  # qué tiene el otro
        r'\bwhat.*other.*have\b'  # what does the other have
    ]

    # FILTRO 3: Preguntas sobre PRECIO FINAL / PRECIO CON ENVÍO
    price_keywords = [
        r'\bprecio\s+(final|total|con\s+envio|completo)\b',  # precio final/total/con envío
        r'\b(final|total)\s+price\b',  # final price, total price
        r'\bcost.*deliver(ed|y)?\s+to\b',  # cost delivered to
        r'\bprice.*deliver(ed|y)?\s+to\b',  # price delivered to
        r'\bcuanto.*con\s+envio\b',  # cuánto sale con envío
        r'\bhow\s+much.*shipping\s+to\b',  # how much with shipping to
        r'\bcosto.*entrega\b'  # costo de entrega
    ]

    # FILTRO 4: Preguntas sobre ACCESORIOS/CONEXIONES ESPECÍFICAS
    # Detecta cuando preguntan por accesorios específicos (cable, adaptador, etc.)
    # para evitar respuesta genérica "incluye lo de la descripción"
    specific_accessory_keywords = [
        # Conexiones específicas
        r'\bconnection\s+(for|to)\b',  # connection for/to
        r'\bconexion\s+(para|al?)\b',  # conexión para/a/al
        r'\bconector\s+(para|de)\b',  # conector para/de

        # Cables específicos
        r'\bcable\s+(para|for|de|to)\b',  # cable para/for/de/to
        r'\b(usb|hdmi|aux|lightning|type-?c|charging|power|data)\s+cable\b',  # cables específicos
        r'\bcable\s+(usb|hdmi|aux|lightning|type-?c|de\s+carga|carga)\b',

        # Adaptadores
        r'\badaptador\s+(para|for|de|to)\b',  # adaptador para/for/de/to
        r'\badapter\s+(for|to)\b',  # adapter for/to
        r'\bconvertidor\s+(para|de)\b',  # convertidor para/de
        r'\bconverter\s+(for|to)\b',  # converter for/to

        # Cargadores
        r'\bcargador\s+(para|for|de)\b',  # cargador para/for/de
        r'\bcharger\s+(for)\b',  # charger for
        r'\bpower\s+adapter\b',  # power adapter
        r'\bac\s+adapter\b',  # AC adapter

        # Compatibilidad específica
        r'\bcompatible\s+(with|con)\s+\w+\b',  # compatible with [algo]
        r'\bfunciona\s+con\s+\w+\b',  # funciona con [algo]
        r'\bworks\s+with\s+\w+\b',  # works with [algo]
        r'\bsirve\s+para\s+\w+\b',  # sirve para [algo]

        # Accesorios específicos por nombre
        r'\b(estuche|case|funda|cover)\s+(para|for|de)\b',  # estuche/funda para
        r'\b(soporte|mount|holder|stand)\s+(para|for|de)\b',  # soporte para
        r'\b(bateria|battery|pila)\s+(para|for|de|incluida|included)\b',  # batería para/incluida
        r'\b(control|remote|mando)\s+(remoto|control)?\s+(para|for|incluido|included)?\b',  # control remoto
        r'\b(auricular|headphone|earbud)s?\s+(para|for|incluido|included)?\b',  # auriculares

        # Preguntas sobre qué trae específicamente
        r'\btrae\s+(cable|adaptador|cargador|bateria|control|auricular|soporte)\b',  # trae [accesorio]
        r'\binclude\s+(cable|adapter|charger|battery|remote|headphone|stand)\b',  # include [accesorio]
        r'\bcome\s+with\s+(a\s+)?(cable|adapter|charger|battery|remote|headphone|stand)\b',  # come with [accesorio]
        r'\btiene\s+(cable|adaptador|cargador|bateria|control|auricular|soporte)\b',  # tiene [accesorio]
        r'\bhas\s+(a\s+)?(cable|adapter|charger|battery|remote|headphone|stand)\b',  # has [accesorio]

        # Tipo de conexión/puerto
        r'\b(puerto|port)\s+(usb|hdmi|aux|ethernet|lightning|type-?c)\b',  # puerto USB/HDMI/etc
        r'\b(usb|hdmi|aux|ethernet|lightning|type-?c)\s+(port|puerto)\b',
        r'\b(entrada|input|salida|output)\s+(usb|hdmi|aux|audio|video)\b',  # entrada/salida

        # Encendedor de auto (caso específico que generó el bug)
        r'\bcigarette\s+lighter\b',  # cigarette lighter
        r'\bencendedor\s+(de|del)\s+(auto|carro|coche)\b',  # encendedor del auto
        r'\b12v\s+(car|auto|vehicle)\b',  # 12V car
        r'\bcar\s+charger\b'  # car charger
    ]

    for text in texts_to_search:
        # Verificar filtro de cantidad
        for cantidad_kw in cantidad_keywords:
            if re.search(cantidad_kw, text, re.IGNORECASE):
                print(f"⚠️ Pregunta de CANTIDAD detectada → IA")
                return None

        # Verificar filtro de diferencias
        for diff_kw in difference_keywords:
            if re.search(diff_kw, text, re.IGNORECASE):
                print(f"⚠️ Pregunta sobre DIFERENCIAS detectada → IA")
                return None

        # Verificar filtro de precio final
        for price_kw in price_keywords:
            if re.search(price_kw, text, re.IGNORECASE):
                print(f"⚠️ Pregunta sobre PRECIO FINAL detectada → IA")
                return None

        # Verificar filtro de accesorios específicos
        for acc_kw in specific_accessory_keywords:
            if re.search(acc_kw, text, re.IGNORECASE):
                print(f"⚠️ Pregunta sobre ACCESORIO ESPECÍFICO detectada → IA")
                return None

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
# DETECCIÓN DE PREGUNTAS TÉCNICAS CRÍTICAS
# ========================================

def is_critical_technical_question(question):
    """
    Detecta si una pregunta es técnica/crítica y requiere información precisa.

    Preguntas críticas incluyen:
    - Voltaje / compatibilidad eléctrica (110V, 220V, transformador)
    - Consumo eléctrico (watts, amperes)
    - Seguridad eléctrica
    - Especificaciones técnicas precisas

    Returns:
        bool: True si es pregunta crítica
    """
    critical_keywords = [
        r'\btransformador\b',
        r'\btransformer\b',
        r'\b110v?\b', r'\b220v?\b', r'\b120v\b', r'\b240v\b',  # 110, 110v, 220, 220v
        r'\bvoltage\b', r'\bvoltaje\b', r'\bvolt(s)?\b',
        r'\bwatt(s)?\b', r'\bamper(e)?(s)?\b',
        r'\belectrical\b', r'\beléctric[oa]\b',
        r'\bcompatib(le|ilidad)\b.*\b(eléctric|electrical|voltage|voltaje)\b',
        r'\bse\s+quema\b', r'\bburn\b',
        r'\binput\s+voltage\b',
        r'\bpower\s+adapter\b', r'\badaptador.*corriente\b',
        r'\bdual\s+voltage\b'  # Dual voltage también es crítica
    ]

    question_lower = question.lower()

    for keyword in critical_keywords:
        if re.search(keyword, question_lower, re.IGNORECASE):
            return True

    return False


def detect_feature_question(question):
    """
    Detecta qué característica específica está preguntando el cliente.

    Returns:
        dict: {
            "feature_type": str (ej: "water_resistance", "bluetooth_calls"),
            "keywords_to_verify": list (palabras clave que deben estar en el JSON)
        }
        None si no es una pregunta sobre característica específica
    """
    feature_patterns = [
        {
            "feature_type": "water_resistance",
            "question_patterns": [
                r'\b(swim|swimming|nadar)\b',
                r'\b(water\s*proof|waterproof|prueba\s*de\s*agua)\b',
                r'\b(water\s*resistant|resistente\s*al\s*agua)\b',
                r'\b(sumergir|submerge)\b',
                r'\bip\d{2}\b',  # IP67, IP68
                r'\batm\b'  # 5ATM, 10ATM
            ],
            "json_keywords": [
                "water", "waterproof", "water-resistant", "swim", "ip67", "ip68",
                "atm", "submersible", "aqua"
            ]
        },
        {
            "feature_type": "bluetooth_calls",
            "question_patterns": [
                r'\b(answer|responder|contestar).*(call|llamada)s?\b',
                r'\b(make|hacer|realizar).*(call|llamada)s?\b',
                r'\b(phone\s*call|llamada.*teléfono)\b',
                r'\b(bluetooth.*call|llamada.*bluetooth)\b',
                r'\b(speak|hablar).*(watch|reloj)\b',
                r'\bcan\s+it\s+answer\s+calls\b',  # Más específico
                r'\b(atender|recibir).*(llamadas?|calls?)\b',
                r'\btake\s+(phone\s+)?calls?\b'
            ],
            "json_keywords": [
                "call", "calls", "calling", "phone call", "bluetooth call",
                "answer calls", "make calls", "voice call", "llamada", "llamadas",
                "bluetooth calling", "hands-free"
            ]
        },
        {
            "feature_type": "gps",
            "question_patterns": [
                r'\b(gps|navegación|navigation)\b',
                r'\b(track.*route|rastrear.*ruta)\b',
                r'\b(location|ubicación)\b.*\b(tracking|rastreo)\b'
            ],
            "json_keywords": [
                "gps", "navigation", "location", "positioning", "satellite",
                "route", "track", "map"
            ]
        },
        {
            "feature_type": "nfc",
            "question_patterns": [
                r'\bnfc\b',
                r'\bcontactless\s*payment\b',
                r'\bpago\s*sin\s*contacto\b',
                r'\b(google|apple)\s*pay\b'
            ],
            "json_keywords": [
                "nfc", "contactless", "payment", "pay", "wallet",
                "google pay", "apple pay"
            ]
        }
    ]

    question_lower = question.lower()

    for feature in feature_patterns:
        for pattern in feature["question_patterns"]:
            if re.search(pattern, question_lower, re.IGNORECASE):
                return {
                    "feature_type": feature["feature_type"],
                    "json_keywords": feature["json_keywords"]
                }

    return None


def verify_feature_in_data(feature_info, mini_ml=None, amazon_json=None):
    """
    Verifica si la característica preguntada existe en los datos del producto.

    Args:
        feature_info: dict con feature_type y json_keywords
        mini_ml: datos de mini_ml (opcional)
        amazon_json: datos de amazon_json (opcional)

    Returns:
        bool: True si la característica está documentada en el JSON
    """
    if not feature_info:
        return True  # Si no es pregunta sobre característica específica, continuar normal

    keywords = feature_info["json_keywords"]

    # Convertir todos los datos a texto para buscar
    all_text = ""

    if mini_ml:
        all_text += json.dumps(mini_ml, ensure_ascii=False).lower()

    if amazon_json:
        all_text += json.dumps(amazon_json, ensure_ascii=False).lower()

    # Buscar cualquiera de los keywords
    for keyword in keywords:
        if keyword.lower() in all_text:
            return True

    return False


def send_telegram_notification_once(
    question_id,
    notification_type,
    notification_func,
    **kwargs
):
    """
    Envía notificación por Telegram UNA SOLA VEZ usando file locking.
    Evita duplicados cuando múltiples workers corren en paralelo.

    Args:
        question_id: ID de la pregunta (único)
        notification_type: Tipo de notificación ("product", "critical", "low_confidence")
        notification_func: Función a llamar para notificar (notify_product_request o notify_technical_question)
        **kwargs: Argumentos para pasar a notification_func

    Returns:
        True si se envió la notificación, False si ya estaba notificada
    """
    import fcntl
    from pathlib import Path

    cache_file = Path(__file__).parent.parent.parent / "storage" / "notified_questions.json"
    lock_file = Path(__file__).parent.parent.parent / "storage" / "notified_questions.lock"

    # Crear key única para esta pregunta
    question_cache_key = str(question_id) if question_id else f"temp_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    # 🔒 USAR FILE LOCK para evitar race conditions entre workers
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_file, 'w') as lock:
        try:
            # Obtener lock exclusivo (bloquea otros workers)
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)

            # Leer cache
            notified_questions = set()
            try:
                if cache_file.exists():
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        notified_questions = set(json.load(f))
            except Exception as e:
                print(f"⚠️  Error leyendo cache de notificaciones: {e}")

            # Si YA notificamos esta pregunta, NO volver a notificar
            if question_cache_key in notified_questions:
                print(f"✅ Pregunta {question_id} ya notificada anteriormente - SKIP notificación")
                return False

            # Enviar notificación
            try:
                notification_func(**kwargs)
                print(f"📱 Notificación {notification_type} enviada para pregunta {question_id}")
            except Exception as e:
                print(f"❌ Error enviando notificación: {e}")
                return False

            # Marcar como notificada y guardar
            notified_questions.add(question_cache_key)
            try:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(list(notified_questions), f, indent=2)
                print(f"✅ Cache actualizado: {len(notified_questions)} preguntas notificadas")
            except Exception as e:
                print(f"⚠️  Error guardando cache: {e}")

            return True

        finally:
            # Liberar lock
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def notify_technical_question(
    question_id,
    question_text,
    asin,
    item_title,
    customer_nickname,
    site_id,
    question_url,
    reason_type="electrical",
    feature_type=None
):
    """
    Notifica por Telegram que hay una pregunta técnica crítica que requiere respuesta manual.

    Args:
        question_id: ID de la pregunta en ML
        question_text: Texto de la pregunta
        asin: ASIN del producto
        item_title: Título del item
        customer_nickname: Username del cliente
        site_id: País (MLA, MLB, etc.)
        question_url: URL para responder
        reason_type: "electrical" o "missing_feature"
        feature_type: tipo de característica faltante (si reason_type="missing_feature")
    """
    if not SMART_SEARCH_ENABLED:
        return False

    # Mapa de países
    country_map = {
        "MLA": "🇦🇷 Argentina",
        "MLB": "🇧🇷 Brasil",
        "MLM": "🇲🇽 México",
        "MLC": "🇨🇱 Chile",
        "MCO": "🇨🇴 Colombia"
    }

    # Mapa de características
    feature_names = {
        "water_resistance": "resistencia al agua",
        "bluetooth_calls": "llamadas Bluetooth",
        "gps": "GPS",
        "nfc": "NFC/pagos"
    }

    message = "━━━━━━━━━━━━━━━━━━━━━\n"
    message += "⚠️ <b>PREGUNTA TÉCNICA CRÍTICA</b>\n"
    message += "━━━━━━━━━━━━━━━━━━━━━\n\n"

    if site_id:
        country_name = country_map.get(site_id, site_id)
        message += f"🌎 País: {country_name}\n"

    message += f"👤 Cliente: <code>@{customer_nickname}</code>\n"
    message += f"🏷️ ASIN: <code>{asin}</code>\n"

    if item_title:
        item_short = item_title[:60] + "..." if len(item_title) > 60 else item_title
        message += f"📦 Producto: {item_short}\n"

    message += "\n"
    message += "💬 <b>Pregunta:</b>\n"
    message += f"<i>\"{question_text}\"</i>\n\n"

    message += "⚠️ <b>Razón:</b>\n"

    if reason_type == "electrical":
        message += "Pregunta técnica sobre voltaje/electricidad.\n"
        message += "Requiere información precisa del fabricante.\n"
    elif reason_type == "missing_feature":
        feature_name = feature_names.get(feature_type, feature_type)
        message += f"Pregunta sobre <b>{feature_name}</b>\n"
        message += "⚠️ Esta información NO está en el JSON de Amazon\n"
        message += "Debés verificar manualmente en la página del producto\n"

    message += "NO se puede responder automáticamente.\n\n"

    if question_url:
        message += "📱 <b>Responder manualmente:</b>\n"
        message += f"{question_url}\n\n"
        message += f"🔗 <b>Ver en Amazon:</b>\n"
        message += f"https://www.amazon.com/dp/{asin}\n\n"

    now = datetime.now().strftime('%d/%m/%Y %H:%M')
    message += f"⏰ {now}"

    try:
        return send_message(message)
    except:
        return False


def answer_with_v2_and_notify(
    asin,
    question,
    question_translated=None,
    item_title=None,
    customer_nickname=None,
    site_id=None,
    question_id=None
):
    """
    Wrapper que usa Smart Answer Engine v2.0 y maneja notificaciones de Telegram

    Retorna dict compatible con answer_question():
    {
        "answer": str,
        "method": str,
        "tokens_used": int,
        "cost_usd": float
    }
    """
    # Llamar a answer_question_v2
    result_v2 = answer_question_v2(
        question=question,
        asin=asin,
        item_title=item_title,
        question_id=question_id,
        customer_nickname=customer_nickname,
        site_id=site_id
    )

    # Crear URL de la pregunta para notificaciones
    question_url = None
    if question_id and site_id:
        question_url = f"https://www.mercadolibre.com.{site_id.lower().replace('ml', '')}/questions/{question_id}"

    # Manejar notificaciones de Telegram según el resultado
    if result_v2.get("should_notify"):
        notification_type = result_v2.get("notification_type")

        # ⚠️ ANTI-LOOP: Solo usar cache para preguntas que NO se responden
        # Las preguntas "review_recommended" SÍ se responden, solo notificamos para revisión
        should_skip_answering = notification_type in ["product_search", "critical_question", "low_confidence"]

        if should_skip_answering:
            # Solo para preguntas que NO responderemos, verificar cache
            from pathlib import Path
            import json
            import fcntl  # Para file locking

            cache_file = Path(__file__).parent.parent.parent / "storage" / "notified_questions.json"
            lock_file = Path(__file__).parent.parent.parent / "storage" / "notified_questions.lock"

            # Crear key única para esta pregunta (solo por question_id, ignorar tipo)
            question_cache_key = f"{question_id}"

            # 🔒 USAR FILE LOCK para evitar race conditions entre workers
            lock_file.parent.mkdir(parents=True, exist_ok=True)
            with open(lock_file, 'w') as lock:
                try:
                    # Obtener lock exclusivo (bloquea otros workers)
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)

                    # Leer cache
                    notified_questions = set()
                    try:
                        if cache_file.exists():
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                notified_questions = set(json.load(f))
                    except Exception as e:
                        print(f"⚠️  Error leyendo cache: {e}")

                    # Si YA notificamos esta pregunta, NO volver a notificar
                    if question_cache_key in notified_questions:
                        print(f"✅ Pregunta {question_id} ya notificada - SKIP")
                        # Asegurar formato correcto para evitar errores
                        if "method" not in result_v2:
                            result_v2["method"] = f"smart_answer_v2_cached"
                        if "tokens_used" not in result_v2:
                            result_v2["tokens_used"] = 0
                        if "cost_usd" not in result_v2:
                            result_v2["cost_usd"] = 0.0
                        return result_v2

                    # Marcar como notificada y guardar
                    notified_questions.add(question_cache_key)
                    try:
                        cache_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(list(notified_questions), f, indent=2)
                        print(f"✅ Cache actualizado: {len(notified_questions)} preguntas")
                    except Exception as e:
                        print(f"⚠️  Error guardando cache: {e}")

                finally:
                    # Liberar lock
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

        # Usar función centralizada para notificar (evita duplicados con file locking)
        if SMART_SEARCH_ENABLED:
            if notification_type == "product_search":
                # Es búsqueda de producto que NO encontramos
                send_telegram_notification_once(
                    question_id=question_id,
                    notification_type="product_search",
                    notification_func=notify_product_request,
                    question_id=question_id or 0,
                    question_text=question,
                    customer_nickname=customer_nickname or "Cliente",
                    extracted_keywords=result_v2.get("metadata", {}).get("product_searched", ""),
                    best_match=None,
                    item_title=item_title,
                    question_url=question_url,
                    site_id=site_id
                )

            elif notification_type == "critical_question":
                # Pregunta crítica de seguridad/legal
                critical_category = result_v2.get("metadata", {}).get("critical_category", "unknown")
                send_telegram_notification_once(
                    question_id=question_id,
                    notification_type="critical_question",
                    notification_func=notify_technical_question,
                    question_id=question_id or 0,
                    question_text=question,
                    asin=asin,
                    item_title=item_title or f"ASIN: {asin}",
                    customer_nickname=customer_nickname or "Cliente",
                    site_id=site_id,
                    question_url=question_url,
                    reason_type=critical_category,
                    feature_type=None
                )

            elif notification_type in ["low_confidence", "review_recommended"]:
                # Low confidence o necesita revisión
                send_telegram_notification_once(
                    question_id=question_id,
                    notification_type="low_confidence",
                    notification_func=notify_technical_question,
                    question_id=question_id or 0,
                    question_text=question,
                    asin=asin,
                    item_title=item_title or f"ASIN: {asin}",
                    customer_nickname=customer_nickname or "Cliente",
                    site_id=site_id,
                    question_url=question_url,
                    reason_type="low_confidence",
                    feature_type=None
                )

    # Preparar respuesta en formato compatible
    result_compatible = {
        "answer": result_v2.get("answer"),
        "method": f"smart_answer_v2_{result_v2.get('reason')}",
        "tokens_used": 150,  # Aproximado para v2
        "cost_usd": 0.00015  # Aproximado
    }

    return result_compatible

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

    # Características principales - TODAS para responder bien "Qué funciones trae?"
    main_chars = mini_ml.get("main_characteristics", [])
    if main_chars:
        context_parts.append("\n=== CARACTERÍSTICAS/FUNCIONES PRINCIPALES ===")
        for idx, char in enumerate(main_chars[:25], 1):  # Hasta 25 características
            if isinstance(char, dict):
                name = char.get("name", "")
                value = char.get("value_name", "")
                if name and value and value not in ["centimeters", "ounces", "en_US"]:
                    context_parts.append(f"{idx}. {name}: {value}")

    # Dimensiones
    pkg = mini_ml.get("package", {})
    if pkg:
        context_parts.append(f"\nDIMENSIONES: {pkg.get('length_cm')}×{pkg.get('width_cm')}×{pkg.get('height_cm')}cm")
        context_parts.append(f"PESO: {pkg.get('weight_kg')}kg")

    # Descripción completa
    desc = mini_ml.get("description_ai", "")
    if desc:
        # Pasar descripción completa (hasta 800 caracteres para más contexto)
        context_parts.append(f"\n=== DESCRIPCIÓN DETALLADA ===\n{desc[:800]}")

    context = "\n".join(context_parts)

    # Prompt INTELIGENTE CON CONTEXTO
    system_prompt = """Eres un vendedor profesional. Sigue estos pasos SIEMPRE:

PASO 1: Identificar el TIPO de producto
Mira el título/marca del producto y determina QUÉ ES:
- Videoportero/Timbre (Ring, Nest Doorbell, etc.)
- Reloj/Smartwatch (Fitbit, Apple Watch, Garmin, etc.)
- Micrófonos/Audio (JBL, Shure, etc.)
- Cámara fotográfica
- Smartphone
- Audífonos/Headphones
- etc.

PASO 2: Interpretar la pregunta en ESE contexto
Ejemplo:
- "Qué calidad tiene la cámara?" + VIDEOPORTERO → pregunta sobre video para ver quién toca
- "Qué calidad tiene la cámara?" + SMARTPHONE → pregunta sobre fotos/selfies
- "Usa baterías?" + MICRÓFONOS → pregunta sobre autonomía/recarga

PASO 3: Responder apropiadamente para ESE tipo de producto

✅ EJEMPLOS CON CONTEXTO CORRECTO:

🔋 BATERÍAS - MUY IMPORTANTE:
- P: "Usa baterías AA o AAA?" + Producto tiene "rechargeable battery"
  ✅ CORRECTO: "Funciona con baterías recargables integradas. No necesita pilas AA/AAA desechables, se carga directamente vía USB. Mucho más práctico y económico."
  ❌ INCORRECTO: "No, no usa baterías AA/AAA" ← Muy negativo y confuso

- P: "Tiene batería?" + Producto tiene "rechargeable"
  ✅ CORRECTO: "Sí, tiene batería recargable integrada. Se carga fácilmente con el cable incluido."

- P: "Funciona con pilas?" + Producto tiene "rechargeable battery"
  ✅ CORRECTO: "Funciona con batería recargable incorporada. No usa pilas desechables, así no tenés que estar comprándolas."

📶 CONECTIVIDAD:
- P: "Tiene NFC?" + Producto solo tiene Bluetooth
  ✅ CORRECTO: "No cuenta con NFC, pero tiene conectividad Bluetooth para sincronizar fácilmente con tu teléfono."

- P: "Es Bluetooth?" + Producto tiene Bluetooth
  ✅ CORRECTO: "Sí, tiene conectividad Bluetooth para emparejar con tus dispositivos."

💧 RESISTENCIA AL AGUA:
- P: "Es sumergible?" + Producto no menciona agua
  ✅ CORRECTO: "No es resistente al agua. Recomendamos mantenerlo seco para un óptimo funcionamiento."

- P: "Es resistente al agua?" + Producto dice "water resistant"
  ✅ CORRECTO: "Sí, es resistente al agua [agregar nivel si está disponible: IP67, 5ATM, etc]."

📦 CANTIDAD/CONTENIDO:
- P: "Cuántos vienen?" → Responder la cantidad exacta del producto
- P: "Qué incluye?" → Listar todo con entusiasmo
- P: "Viene con accesorios?" → Listar qué incluye

🎨 CARACTERÍSTICAS:
- P: "De qué color?" → Responder el color disponible
- P: "Qué tamaño?" → Responder dimensiones/talla

💰 PRECIO/ENVÍO:
- P: "Cuál es el precio final con envío a [ciudad]?"
  ✅ "El precio que ves en la publicación incluye envío gratis a todo el país. Podés verificar el costo exacto en la sección de envío de la publicación."
  ❌ "Te recomendamos verificar en el sitio web" ← MUY IMPERSONAL
- P: "Cuánto sale con envío?"
  ✅ "El envío es gratis, el precio final es el que ves en la publicación."
  ❌ "Verificar directamente en la plataforma" ← MUY ROBÓTICO

📹 VIDEOPORTEROS/TIMBRES - CONTEXTO CRÍTICO:
Producto: Ring Doorbell, Nest Doorbell, Videoportero
Función: Ver quién toca el timbre

- P: "Qué calidad tiene la cámara?"
  ✅ "Graba video en HD para que veas claramente quién está en tu puerta. Incluye visión nocturna para ver incluso de noche."
  ❌ "Ofrece 12MP para fotos nítidas y videos 4K" ← HORRIBLE, no es cámara de fotos

- P: "Qué resolución tiene?"
  ✅ "Full HD 1080p, ideal para identificar claramente las personas en tu puerta."
  ❌ "Resolución de 12 megapíxeles" ← Megapíxeles es para fotos, no video

⏱️ RELOJES/SMARTWATCHES - CONTEXTO:
Producto: Fitbit, Apple Watch, Garmin, Samsung Watch
Función: Fitness, salud, notificaciones

- P: "Es resistente al agua? Puedo nadar?"
  ✅ "Sí, es resistente al agua hasta 50 metros. Podés nadar y ducharte con él sin problemas."
  ❌ NO dar respuestas contradictorias ("Sí es resistente... Este producto no es resistente")

🎤 MICRÓFONOS - CONTEXTO:
Producto: Micrófonos inalámbricos, karaoke
Función: Grabar audio, karaoke, eventos

- P: "Usa baterías AA o AAA?"
  Si tiene batería recargable:
  ✅ "Funciona con batería recargable integrada. No necesita pilas, se carga con cable USB. Mucho más práctico."
  ❌ "No, no usa baterías AA/AAA" ← Muy negativo

⚠️ NUNCA HAGAS ESTO:
❌ "No usa baterías AA/AAA" cuando tiene batería recargable ← MUY CONFUSO
❌ "No tiene NFC" sin mencionar qué SÍ tiene ← MUY SECO
❌ Empezar con "No" cuando hay una alternativa mejor ← MUY NEGATIVO
❌ Hablar de "fotos" cuando es un videoportero/timbre ← CONFUSO, es para VIDEO
❌ Dar respuestas contradictorias (ej: "Sí es resistente... no es resistente") ← HORRIBLE

📋 FORMATO:
- Máximo 3-4 líneas
- Sin emojis
- Tono amigable y profesional
- Siempre POSITIVO primero, luego aclaraciones
- Entender el contexto real de la pregunta
- Responder según el TIPO de producto

⛔ REGLAS ABSOLUTAS - NO NEGOCIABLES:

1. TODA la información que necesitas está en el contexto del producto arriba
2. SIEMPRE debes leer y buscar la respuesta en ese contexto
3. NUNCA digas "no tengo la info", "consultanos", "para más detalles", etc.
4. NUNCA uses placeholders: "[mencionar...]", "[agregar...]", etc.
5. NUNCA dejes corchetes [] en tu respuesta

PROCESO OBLIGATORIO:
→ Lee TODO el contexto del producto (título, marca, características, especificaciones, descripción)
→ Busca la información que te preguntan
→ Responde con esos datos REALES del contexto
→ Si preguntan funciones/características: lista las que están en el contexto

LA INFORMACIÓN ESTÁ AHÍ - SOLO TENÉS QUE LEERLA Y RESPONDERLA."""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Contexto del producto:\n{context}\n\nPregunta: {question}"}
            ],
            max_tokens=200,
            temperature=0.1
        )

        answer = response.choices[0].message.content.strip()
        return answer, 150  # Retornar respuesta y tokens aproximados

    except Exception as e:
        print(f"⚠️ Error con IA: {e}")
        return None, 0

def extract_relevant_json_snippets(question, amazon_json):
    """
    Pre-filtra el JSON para extraer solo fragmentos relevantes a la pregunta.
    Útil cuando el JSON es muy grande (muchas features/specs).

    Returns: dict con snippets relevantes
    """
    # Construir JSON simplificado con solo campos relevantes
    simplified = {
        "title": amazon_json.get("title", ""),
        "brand": amazon_json.get("brand", ""),
        "features": amazon_json.get("features", [])[:30],  # Primeras 30
        "specifications": dict(list(amazon_json.get("specifications", {}).items())[:20]),  # Primeras 20
        "description": amazon_json.get("description", "")[:1000]  # Primeros 1000 chars
    }

    # Prompt para extraer fragmentos relevantes
    extraction_prompt = f"""Analiza la pregunta del cliente y el JSON del producto.

Pregunta: "{question}"

JSON del producto:
{json.dumps(simplified, indent=2, ensure_ascii=False)}

Extrae SOLO los fragmentos del JSON relevantes para responder la pregunta.

Responde en JSON con este formato:
{{
    "relevant_features": ["feature 1", "feature 2", ...],
    "relevant_specs": {{"key": "value", ...}},
    "relevant_description_parts": ["parte 1", "parte 2", ...]
}}

Reglas:
- Max 10 features
- Max 10 specs
- Solo info relevante para la pregunta
- Si pregunta sobre funciones: incluir TODAS las features principales
"""

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",  # Usar modelo más barato para extracción
            messages=[
                {"role": "user", "content": extraction_prompt}
            ],
            max_tokens=500,
            temperature=0
        )

        content = response.choices[0].message.content.strip()

        # Extraer JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        snippets = json.loads(content)
        return snippets

    except Exception as e:
        print(f"⚠️ Error extrayendo snippets: {e}")
        # Si falla, devolver None para usar método normal
        return None


def generate_ai_answer_from_amazon(question, amazon_json):
    """
    Genera respuesta con IA usando amazon_json de SP-API.
    Solo se usa si mini_ml no tiene suficiente info.

    Lee formato SP-API: {attributes: {bullet_point: [...], ...}, summaries: [...]}
    """
    # Extraer información del formato SP-API
    bullet_points = amazon_json.get("attributes", {}).get("bullet_point", [])
    features = [bp.get("value", "") for bp in bullet_points if bp.get("value")]

    # Título y marca desde summaries
    summaries = amazon_json.get("summaries", [])
    title = summaries[0].get("itemName", "") if summaries else ""
    brand = summaries[0].get("brand", "") if summaries else ""

    # Detectar si tiene muchas features
    num_features = len(features)
    is_large_json = num_features > 15

    # Construir contexto con la información extraída
    context_parts = []

    # Título y marca
    if title:
        context_parts.append(f"Producto: {title}")
    if brand:
        context_parts.append(f"Marca: {brand}")

    # Features (bullet points de SP-API)
    if features:
        context_parts.append("\n=== CARACTERÍSTICAS/FUNCIONES ===")
        # Si es largo, pre-filtrar; sino, todas
        if is_large_json:
            # Pre-filtrar solo relevantes (TO DO: implementar pre-filtrado)
            features_to_show = features[:20]
        else:
            features_to_show = features

        for idx, feature in enumerate(features_to_show, 1):
            context_parts.append(f"{idx}. {feature}")

    context = "\n".join(context_parts)

    # Prompt ULTRA SIMPLE - El AI debe leer el contexto y responder
    system_prompt = """Sos un vendedor respondiendo preguntas de clientes.

TODA la información del producto está arriba: título, marca, características, especificaciones, descripción.

TU TRABAJO:
1. Lee el título/marca para identificar QUÉ tipo de producto es
2. Lee las características/especificaciones para encontrar la info que te preguntan
3. Responde con ESA información

⚠️ REGLAS ABSOLUTAS:
• NUNCA digas "necesito más información" o "para más detalles consultanos"
• NUNCA uses corchetes [] ni placeholders como "[mencionar...]"
• La info YA está en el contexto arriba - léela y úsala

💡 CONTEXTO IMPORTA:
• Ring/Nest Doorbell = timbre con cámara para ver quién toca (NO es cámara de fotos)
• Fitbit/Smartwatch = reloj fitness/salud
• JBL/Shure Mic = micrófonos para audio/karaoke
• Andonstar = microscopio digital

🔋 BATERÍAS - SER POSITIVO:
Si preguntan "Usa pilas AA/AAA?" y tiene batería recargable:
✅ "Funciona con batería recargable integrada, no necesita pilas desechables"
❌ "No, no usa baterías AA/AAA" (muy negativo)

📹 VIDEOPORTEROS - NO CONFUNDIR CON CÁMARA DE FOTOS:
Si preguntan "Qué cámara tiene?" en un Ring/videoportero:
✅ "Graba video HD para que veas claramente quién está en tu puerta"
❌ "12MP para fotos nítidas" (es timbre, no cámara de fotos)

📋 FORMATO:
• Máximo 3-4 líneas
• Tono amigable y vendedor
• Positivo primero, luego aclaraciones
• Sin emojis

AHORA: Lee el contexto del producto arriba y responde la pregunta usando ESA información."""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Contexto del producto:\n{context}\n\nPregunta: {question}"}
            ],
            max_tokens=200,
            temperature=0.1
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

    # Prompt INTELIGENTE para características pre-organizadas
    system_prompt = """Eres un vendedor profesional y amigable. IMPORTANTE: Sé INTELIGENTE al interpretar las preguntas.

Te daré las características COMPLETAS del producto y una pregunta del cliente.

🎯 REGLA DE ORO - RESPONDE POSITIVO PRIMERO:
Si el producto TIENE una versión mejorada de lo preguntado, responde con lo que SÍ TIENE primero, sin empezar con "No".

✅ EJEMPLOS INTELIGENTES:

🔋 BATERÍAS:
- P: "Usa baterías AA/AAA?" + Producto tiene "rechargeable"
  ✅ "Funciona con baterías recargables integradas. No necesita pilas AA/AAA desechables, se carga directamente. Mucho más práctico."
  ❌ "No usa baterías AA/AAA" ← MUY CONFUSO

- P: "Tiene batería?" + Producto tiene "rechargeable"
  ✅ "Sí, tiene batería recargable integrada que se carga fácilmente."

📶 CONECTIVIDAD:
- P: "Tiene NFC?" + Solo tiene Bluetooth
  ✅ "No cuenta con NFC, pero tiene Bluetooth para sincronizar fácilmente con tu teléfono."

- P: "Es Bluetooth?" + Tiene Bluetooth
  ✅ "Sí, tiene conectividad Bluetooth."

💧 AGUA:
- P: "Es impermeable?" + No menciona agua
  ✅ "No es resistente al agua. Recomendamos mantenerlo seco."

- P: "Es resistente al agua?" + Dice "water resistant"
  ✅ "Sí, es resistente al agua [agregar nivel si disponible]."

📹 VIDEOPORTEROS/TIMBRES:
- P: "Qué calidad tiene la cámara?" + Es Ring/Videoportero
  ✅ "Graba video en Full HD 1080p con visión nocturna para ver claramente quién toca el timbre."
  ❌ "Ofrece 12 megapíxeles para fotos" ← NO hablar de fotos en timbres

🚫 NUNCA:
- Empezar con "No" si hay alternativa mejor
- Decir "no especifica" o "no tengo información"
- Ser vago o evasivo
- Hablar de "fotos" cuando es videoportero/timbre

📋 FORMATO:
- Máximo 3-4 líneas
- Sin emojis
- Tono amigable
- Siempre POSITIVO primero
- Entender el contexto real
- Responder según TIPO de producto"""

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

    # NUEVO: Usar Smart Answer Engine v2.0 si está disponible
    if SMART_ANSWER_V2_ENABLED:
        print("🚀 Usando Smart Answer Engine v2.0...")
        return answer_with_v2_and_notify(
            asin=asin,
            question=question,
            question_translated=question_translated,
            item_title=item_title,
            customer_nickname=customer_nickname,
            site_id=site_id,
            question_id=question_id
        )

    # PASO 0: BÚSQUEDA INTELIGENTE DE PRODUCTOS
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

            # Notificar por Telegram usando función centralizada (evita duplicados)
            send_telegram_notification_once(
                question_id=question_id,
                notification_type="product_search",
                notification_func=notify_product_request,
                question_id=question_id or f"pending_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                question_text=question,
                customer_nickname=customer_nickname or "unknown",
                extracted_keywords=keywords,
                best_match=best_match,
                item_title=item_title,
                question_url=question_url,
                site_id=site_id
            )

            # NO RESPONDER - dejar pregunta sin responder para que el usuario la responda manualmente
            result["answer"] = None
            result["method"] = "smart_search_pending_no_answer"
            result["tokens_used"] = 0
            result["cost_usd"] = 0.0

            return result

    # PASO 0.5: Detectar preguntas técnicas críticas (voltaje, transformador, etc.)
    if is_critical_technical_question(question):
        print("⚠️  Pregunta técnica crítica detectada - requiere respuesta manual")

        # Construir URL de la pregunta
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

        # Notificar por Telegram usando función centralizada (evita duplicados)
        send_telegram_notification_once(
            question_id=question_id,
            notification_type="critical_question",
            notification_func=notify_technical_question,
            question_id=question_id or f"technical_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            question_text=question,
            asin=asin,
            item_title=item_title,
            customer_nickname=customer_nickname or "unknown",
            site_id=site_id,
            question_url=question_url,
            reason_type="electrical"
        )

        # NO RESPONDER - dejar para respuesta manual
        result["answer"] = None
        result["method"] = "critical_technical_no_answer"
        result["tokens_used"] = 0
        result["cost_usd"] = 0.0

        return result

    # PASO 0.6: Detectar preguntas sobre características específicas
    feature_info = detect_feature_question(question)

    if feature_info:
        print(f"🔍 Pregunta sobre característica específica detectada: {feature_info['feature_type']}")

        # Cargar datos para verificar
        mini_ml = load_mini_ml(asin)
        amazon_json = load_amazon_json(asin)

        # Verificar si la característica está documentada
        has_feature_data = verify_feature_in_data(feature_info, mini_ml, amazon_json)

        if not has_feature_data:
            print(f"⚠️  Característica '{feature_info['feature_type']}' NO encontrada en JSON - requiere verificación manual")

            # Construir URL de la pregunta
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

            # Notificar por Telegram usando función centralizada (evita duplicados)
            send_telegram_notification_once(
                question_id=question_id,
                notification_type="missing_feature",
                notification_func=notify_technical_question,
                question_id=question_id or f"feature_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                question_text=question,
                asin=asin,
                item_title=item_title,
                customer_nickname=customer_nickname or "unknown",
                site_id=site_id,
                question_url=question_url,
                reason_type="missing_feature",
                feature_type=feature_info['feature_type']
            )

            # NO RESPONDER - dejar para respuesta manual
            result["answer"] = None
            result["method"] = "missing_feature_no_answer"
            result["tokens_used"] = 0
            result["cost_usd"] = 0.0

            return result
        else:
            print(f"✅ Característica '{feature_info['feature_type']}' encontrada en JSON - continuando con respuesta normal")

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

        # NO dividir preguntas - responder todo junto para evitar contradicciones
        # (antes dividía y podía dar respuestas contradictorias)
        individual_questions = [text]  # Mantener pregunta original completa

        # Solo informar si hay múltiples ?
        if text.count('?') > 1:
            print(f"   ⚠️  Pregunta con múltiples interrogantes - respondiendo como una sola")

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
