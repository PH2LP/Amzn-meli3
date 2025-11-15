#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NOTIFICADOR TELEGRAM PARA SYNC AMAZON-ML
=========================================
Bot separado para notificar sincronizaciones de precio/stock entre Amazon y ML

CONFIGURACIÓN EN .ENV:
----------------------
TELEGRAM_SYNC_BOT_TOKEN=tu_token_bot4
TELEGRAM_SYNC_CHAT_ID=tu_chat_id
TELEGRAM_SYNC_ENABLED=true
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

# Configuración Bot de Sync
SYNC_BOT_TOKEN = os.getenv("TELEGRAM_SYNC_BOT_TOKEN", "")
SYNC_CHAT_ID = os.getenv("TELEGRAM_SYNC_CHAT_ID", "")
SYNC_ENABLED = os.getenv("TELEGRAM_SYNC_ENABLED", "true").lower() == "true"


def is_configured():
    """Verifica si el bot de sync está configurado"""
    return bool(SYNC_BOT_TOKEN and SYNC_CHAT_ID and SYNC_ENABLED)


def send_message(message, parse_mode="HTML", disable_notification=False):
    """Envía mensaje al bot de sync"""
    if not is_configured():
        return False

    url = f"https://api.telegram.org/bot{SYNC_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": SYNC_CHAT_ID,
        "text": message,
        "parse_mode": parse_mode,
        "disable_notification": disable_notification
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Error enviando a bot de sync: {e}")
        return False


# ============================================================
# NOTIFICACIONES DE SYNC
# ============================================================

def notify_sync_start(total_products):
    """Notifica inicio de sincronización"""
    message = f"🔄 <b>Iniciando sync: {total_products} productos</b>"
    return send_message(message)


def notify_listing_paused(asin, item_id, reason):
    """Notifica producto pausado"""
    message = f"⏸️ <code>{asin}</code>\n"
    message += f"   Pausado: {reason[:50]}"
    return send_message(message, disable_notification=True)


def notify_listing_reactivated(asin, item_id):
    """Notifica producto reactivado"""
    message = f"♻️ <code>{asin}</code> → Reactivado (stock: 0 → 10)"
    return send_message(message, disable_notification=True)


def notify_price_update(asin, old_price, new_price, countries):
    """Notifica actualización de precio"""
    change_percent = abs((new_price - old_price) / old_price * 100) if old_price > 0 else 0

    # Emoji según la dirección del cambio
    emoji = "📈" if new_price > old_price else "📉"

    message = f"{emoji} <code>{asin}</code>\n"
    message += f"   ${old_price:.2f} → ${new_price:.2f} ({change_percent:+.1f}%)\n"

    # Agregar países si están disponibles
    if countries:
        countries_str = ", ".join(countries[:3])  # Limitar a 3 para que no sea muy largo
        if len(countries) > 3:
            countries_str += f" +{len(countries)-3}"
        message += f"   {countries_str}"

    return send_message(message, disable_notification=True)


def notify_sync_error(asin, error_msg):
    """Notifica error en sincronización"""
    message = f"❌ <code>{asin}</code>\n"
    message += f"   Error: {error_msg[:60]}"
    return send_message(message, disable_notification=False)


def notify_sync_complete(stats, duration_minutes=0):
    """Notifica finalización de sincronización

    Args:
        stats: Dict con {total, paused, price_updated, no_change, errors}
        duration_minutes: Duración en minutos
    """
    total = stats.get("total", 0)
    paused = stats.get("paused", 0)
    updated = stats.get("price_updated", 0)
    errors = stats.get("errors", 0)
    no_change = stats.get("no_change", 0)

    message = "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += "✅ <b>SYNC COMPLETADO</b>\n"
    message += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    message += f"📊 <b>Resumen:</b>\n"
    message += f"   • Total procesados: {total}\n"
    message += f"   • Precios actualizados: {updated}\n"
    message += f"   • Productos pausados: {paused}\n"
    message += f"   • Sin cambios: {no_change}\n"

    if errors > 0:
        message += f"   • Errores: {errors}\n"

    if duration_minutes > 0:
        message += f"\n⏱️ Duración: {duration_minutes:.1f} min"

    return send_message(message)


def notify_sync_success(message_text):
    """Notifica operación exitosa genérica"""
    return send_message(f"✅ {message_text}", disable_notification=True)


# ============================================================
# FUNCIÓN DE TEST
# ============================================================

def test_notification():
    """Envía mensaje de prueba al bot de sync"""
    if not is_configured():
        print("❌ Bot de sync no configurado")
        print("\nPara configurar:")
        print("1. Crea un bot con @BotFather")
        print("2. Obtén el token")
        print("3. Agrega a .env:")
        print("   TELEGRAM_SYNC_BOT_TOKEN=tu_token")
        print("   TELEGRAM_SYNC_CHAT_ID=tu_chat_id")
        print("   TELEGRAM_SYNC_ENABLED=true")
        return False

    message = """
🤖 <b>Test - Bot de Sync Amazon-ML</b>

✅ Bot configurado correctamente
🔄 Notificaciones de precio/stock activas

🕐 {}
""".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    success = send_message(message)
    if success:
        print("✅ Mensaje de prueba enviado al bot de sync")
    else:
        print("❌ Error enviando mensaje de prueba")

    return success


if __name__ == "__main__":
    test_notification()
