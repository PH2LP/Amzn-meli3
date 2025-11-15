#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO DE NOTIFICACIONES TELEGRAM
==================================
Sistema pre-configurado para enviar notificaciones a Telegram

CONFIGURACIÓN:
--------------
1. Crear bot con @BotFather en Telegram
2. Obtener el token del bot
3. Enviar un mensaje al bot desde tu cuenta
4. Ejecutar get_chat_id() para obtener tu chat_id
5. Agregar estas variables al .env:
   TELEGRAM_BOT_TOKEN=tu_token_aqui
   TELEGRAM_CHAT_ID=tu_chat_id_aqui

TIPOS DE NOTIFICACIONES DISPONIBLES:
------------------------------------
- Sync de precios (éxito/fallo)
- Nuevas publicaciones
- Errores críticos
- Ventas (futuro)
- Respuestas automáticas (futuro)
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

# Configuración
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLED = os.getenv("TELEGRAM_NOTIFICATIONS_ENABLED", "false").lower() == "true"


def is_configured():
    """Verifica si Telegram está configurado"""
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and TELEGRAM_ENABLED)


def send_message(message, parse_mode="HTML", disable_notification=False):
    """
    Envía un mensaje a Telegram

    Args:
        message: Texto del mensaje (soporta HTML)
        parse_mode: "HTML" o "Markdown"
        disable_notification: True para enviar silenciosamente

    Returns:
        bool: True si se envió exitosamente
    """
    if not is_configured():
        print("⚠️ Telegram no configurado - Notificación omitida")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": parse_mode,
        "disable_notification": disable_notification
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Error enviando mensaje a Telegram: {e}")
        return False


def get_chat_id():
    """
    Obtiene el chat_id de Telegram

    INSTRUCCIONES:
    1. Envía un mensaje a tu bot
    2. Ejecuta esta función
    3. Copia el chat_id al .env
    """
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN no configurado en .env")
        return None

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data.get("result"):
            print("⚠️ No hay mensajes. Envía un mensaje al bot primero.")
            return None

        chat_id = data["result"][-1]["message"]["chat"]["id"]
        print(f"✅ Tu chat_id es: {chat_id}")
        print(f"\nAgrega esto al .env:")
        print(f"TELEGRAM_CHAT_ID={chat_id}")
        return chat_id

    except Exception as e:
        print(f"❌ Error obteniendo chat_id: {e}")
        return None


# ============================================================
# NOTIFICACIONES PRE-CONFIGURADAS
# ============================================================

def notify_sync_success(products_updated, total_products):
    """Notifica sincronización exitosa de precios"""
    message = f"""
🔄 <b>Sincronización Exitosa</b>

✅ {products_updated}/{total_products} productos actualizados
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    return send_message(message, disable_notification=True)


def notify_sync_error(asin, error_msg):
    """Notifica error en sincronización de un producto"""
    message = f"""
⚠️ <b>Error en Sincronización</b>

📦 ASIN: <code>{asin}</code>
❌ Error: {error_msg}
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    return send_message(message)


def notify_price_update(asin, old_price, new_price, countries):
    """Notifica actualización de precio"""
    change = ((new_price - old_price) / old_price) * 100
    emoji = "📈" if change > 0 else "📉"

    message = f"""
{emoji} <b>Precio Actualizado</b>

📦 ASIN: <code>{asin}</code>
💵 Precio anterior: ${old_price:.2f}
💵 Precio nuevo: ${new_price:.2f}
📊 Cambio: {change:+.1f}%
🌍 Países: {', '.join(countries)}
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    return send_message(message, disable_notification=True)


def notify_listing_paused(asin, item_id, reason):
    """Notifica cuando una publicación fue pausada automáticamente (stock=0)"""
    message = f"""
⏸️ <b>Publicación Sin Stock</b>

📦 ASIN: <code>{asin}</code>
🆔 Item ID: <code>{item_id}</code>
📦 Stock: 0 (sin disponibilidad)
⚠️ Razón: {reason}
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    return send_message(message)


def notify_listing_reactivated(asin, item_id):
    """Notifica cuando una publicación fue reactivada automáticamente"""
    message = f"""
♻️ <b>Publicación Reactivada</b>

📦 ASIN: <code>{asin}</code>
🆔 Item ID: <code>{item_id}</code>
📦 Stock: 10 (disponible nuevamente)
✅ Producto disponible en Amazon
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    return send_message(message)


def notify_new_publication(asin, item_id, title, countries):
    """Notifica nueva publicación"""
    message = f"""
🆕 <b>Nueva Publicación</b>

📦 ASIN: <code>{asin}</code>
🆔 Item ID: <code>{item_id}</code>
📝 {title[:50]}...
🌍 Países: {', '.join(countries)}
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    return send_message(message)


def notify_publication_error(asin, error_msg):
    """Notifica error en publicación"""
    message = f"""
❌ <b>Error en Publicación</b>

📦 ASIN: <code>{asin}</code>
❌ Error: {error_msg}
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    return send_message(message)


def notify_sale(item_id, title, price, buyer):
    """Notifica nueva venta (futuro)"""
    message = f"""
🎉 <b>¡Nueva Venta!</b>

📦 {title[:50]}
💰 Precio: ${price:.2f}
👤 Comprador: {buyer}
🆔 Item: <code>{item_id}</code>
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    return send_message(message)


def notify_question_answered(item_id, question, answer):
    """Notifica pregunta respondida automáticamente (futuro)"""
    message = f"""
💬 <b>Pregunta Respondida</b>

❓ Pregunta: {question[:100]}...
✅ Respuesta: {answer[:100]}...
🆔 Item: <code>{item_id}</code>
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    return send_message(message, disable_notification=True)


def notify_critical_error(error_type, error_msg):
    """Notifica error crítico del sistema"""
    message = f"""
🚨 <b>ERROR CRÍTICO</b>

⚠️ Tipo: {error_type}
❌ Error: {error_msg}
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

<i>Requiere atención inmediata</i>
"""
    return send_message(message)


# ============================================================
# FUNCIÓN DE TEST
# ============================================================

def test_notification():
    """Envía un mensaje de prueba"""
    if not is_configured():
        print("❌ Telegram no está configurado")
        print("\nPara configurar:")
        print("1. Crea un bot con @BotFather")
        print("2. Obtén el token y agrégalo al .env como TELEGRAM_BOT_TOKEN")
        print("3. Envía un mensaje al bot")
        print("4. Ejecuta: python3 -c 'from scripts.tools.telegram_notifier import get_chat_id; get_chat_id()'")
        print("5. Agrega el chat_id al .env como TELEGRAM_CHAT_ID")
        print("6. Agrega TELEGRAM_NOTIFICATIONS_ENABLED=true al .env")
        return False

    message = """
🤖 <b>Test de Notificaciones</b>

✅ Telegram configurado correctamente
🕐 {}

<i>Sistema de notificaciones activo</i>
""".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    success = send_message(message)
    if success:
        print("✅ Mensaje de prueba enviado exitosamente")
    else:
        print("❌ Error enviando mensaje de prueba")

    return success


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "get_chat_id":
        get_chat_id()
    else:
        test_notification()
