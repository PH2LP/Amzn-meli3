#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NOTIFICADOR TELEGRAM PARA SOLICITUDES DE PRODUCTOS
==================================================
Envía notificaciones cuando un cliente pregunta por un producto
que no tenemos en el catálogo
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

# Configuración Bot de Solicitudes de Productos
PRODUCT_BOT_TOKEN = os.getenv("TELEGRAM_PRODUCT_REQUESTS_BOT_TOKEN", "")
PRODUCT_CHAT_ID = os.getenv("TELEGRAM_PRODUCT_REQUESTS_CHAT_ID", "")
PRODUCT_ENABLED = os.getenv("TELEGRAM_PRODUCT_REQUESTS_ENABLED", "true").lower() == "true"


def is_configured():
    """Verifica si el bot de solicitudes está configurado"""
    return bool(PRODUCT_BOT_TOKEN and PRODUCT_CHAT_ID and PRODUCT_ENABLED)


def send_message(message, parse_mode="HTML", disable_notification=False):
    """Envía mensaje al bot de solicitudes de productos"""
    if not is_configured():
        print("⚠️  Bot de solicitudes no configurado")
        return False

    url = f"https://api.telegram.org/bot{PRODUCT_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": PRODUCT_CHAT_ID,
        "text": message,
        "parse_mode": parse_mode,
        "disable_notification": disable_notification,
        "disable_web_page_preview": False  # Mostrar preview de links de ML
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Error enviando notificación de producto: {e}")
        return False


def notify_product_request(
    question_id,
    question_text,
    customer_nickname,
    extracted_keywords,
    best_match=None,
    item_title=None,
    question_url=None,
    site_id=None
):
    """
    Notifica solicitud de producto no encontrado

    Args:
        question_id: ID de la pregunta en ML
        question_text: Texto de la pregunta del cliente
        customer_nickname: Username del cliente
        extracted_keywords: Palabras clave extraídas del producto
        best_match: Dict con mejor coincidencia encontrada (opcional)
        item_title: Título del listing donde preguntaron
        question_url: URL para responder la pregunta
        site_id: Código del país (MLA, MLM, etc.)
    """

    if not is_configured():
        return False

    # Mapa de países
    country_map = {
        "MLA": "🇦🇷 Argentina",
        "MLB": "🇧🇷 Brasil",
        "MLM": "🇲🇽 México",
        "MLC": "🇨🇱 Chile",
        "MCO": "🇨🇴 Colombia",
        "MLU": "🇺🇾 Uruguay",
        "MLV": "🇻🇪 Venezuela"
    }

    # Construir mensaje
    message = "━━━━━━━━━━━━━━━━━━━━━\n"
    message += "🔍 <b>PRODUCTO SOLICITADO</b>\n"
    message += "━━━━━━━━━━━━━━━━━━━━━\n\n"

    # País
    if site_id:
        country_name = country_map.get(site_id, site_id)
        message += f"🌎 País: {country_name}\n"

    # Cliente
    message += f"👤 Cliente: <code>@{customer_nickname}</code>\n"

    # Item donde preguntaron
    if item_title:
        item_short = item_title[:60] + "..." if len(item_title) > 60 else item_title
        message += f"📦 Item: {item_short}\n"

    message += "\n"

    # Pregunta
    message += "💬 <b>Pregunta:</b>\n"
    message += f"<i>\"{question_text}\"</i>\n\n"

    # Producto buscado
    message += "🎯 <b>Producto buscado:</b>\n"
    message += f"{extracted_keywords}\n\n"

    # Mejor match si existe (aunque sea bajo)
    if best_match and best_match.get("similarity"):
        similarity = best_match["similarity"]
        match_title = best_match.get("title", "N/A")

        # Emoji según qué tan cerca estuvo
        if similarity >= 0.7:
            emoji = "🟡"  # Cerca pero no suficiente
        elif similarity >= 0.5:
            emoji = "🟠"  # Lejos
        else:
            emoji = "🔴"  # Muy lejos

        message += f"{emoji} <b>Mejor match:</b> {similarity:.2f}\n"
        match_short = match_title[:50] + "..." if len(match_title) > 50 else match_title
        message += f"   {match_short}\n\n"

    # Link para responder
    if question_url:
        message += "📱 <b>Responder:</b>\n"
        message += f"{question_url}\n\n"

    # Timestamp
    now = datetime.now().strftime('%d/%m/%Y %H:%M')
    message += f"⏰ {now}"

    return send_message(message)


def notify_product_found_after_upload(
    question_id,
    customer_nickname,
    original_keywords,
    new_item_id,
    new_item_title,
    new_item_url
):
    """
    Notifica que se encontró/subió el producto que buscaba el cliente

    Args:
        question_id: ID de la pregunta original
        customer_nickname: Username del cliente
        original_keywords: Keywords originales que buscó
        new_item_id: ID del nuevo listing
        new_item_title: Título del producto
        new_item_url: URL del producto en ML
    """

    if not is_configured():
        return False

    message = "━━━━━━━━━━━━━━━━━━━━━\n"
    message += "✅ <b>PRODUCTO ENCONTRADO</b>\n"
    message += "━━━━━━━━━━━━━━━━━━━━━\n\n"

    message += f"👤 Cliente: <code>@{customer_nickname}</code>\n"
    message += f"🔍 Buscaba: <i>{original_keywords}</i>\n\n"

    message += "📦 <b>Producto publicado:</b>\n"
    message += f"{new_item_title}\n\n"

    message += f"🔗 <b>Link:</b>\n"
    message += f"{new_item_url}\n\n"

    message += "💡 <i>Ahora podés responder al cliente con este link</i>"

    return send_message(message)


def test_notification():
    """Envía mensaje de prueba al bot de solicitudes"""
    if not is_configured():
        print("❌ Bot de solicitudes no configurado")
        print("\nPara configurar:")
        print("1. Creá un bot con @BotFather")
        print("2. Obtené el token")
        print("3. Agregá a .env:")
        print("   TELEGRAM_PRODUCT_REQUESTS_BOT_TOKEN=tu_token")
        print("   TELEGRAM_PRODUCT_REQUESTS_CHAT_ID=tu_chat_id")
        print("   TELEGRAM_PRODUCT_REQUESTS_ENABLED=true")
        return False

    message = """
🤖 <b>Test - Bot de Solicitudes de Productos</b>

✅ Bot configurado correctamente
🔍 Notificaciones de productos no encontrados activas

🕐 {}
""".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    success = send_message(message)
    if success:
        print("✅ Mensaje de prueba enviado al bot de solicitudes")
    else:
        print("❌ Error enviando mensaje de prueba")

    return success


if __name__ == "__main__":
    # Test notification
    print("🧪 Probando notificador de productos...\n")
    test_notification()

    # Test de solicitud de producto
    print("\n🧪 Probando notificación de solicitud...\n")
    notify_product_request(
        question_id="MLA-12345678",
        question_text="Hola, tenés el filtro Waterdrop WD-G3-W?",
        customer_nickname="juanperez",
        extracted_keywords="filtro Waterdrop WD-G3-W",
        best_match={
            "similarity": 0.65,
            "title": "Waterdrop G2 Water Filter Replacement"
        },
        item_title="Filtro de Agua Universal para Nevera Samsung",
        question_url="https://www.mercadolibre.com.ar/p/questions/12345678"
    )
