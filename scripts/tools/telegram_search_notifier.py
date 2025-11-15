#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO DE NOTIFICACIONES TELEGRAM PARA BÚSQUEDA DE ASINS
=========================================================
Bot para notificar sobre el progreso de búsqueda autónoma de ASINs

CONFIGURACIÓN EN .ENV:
----------------------
TELEGRAM_SEARCH_BOT_TOKEN=tu_token_bot_busqueda
TELEGRAM_SEARCH_CHAT_ID=tu_chat_id
TELEGRAM_SEARCH_ENABLED=true

Nota: Usa el MISMO bot que publicaciones si quieres todo en un canal
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

# Configuración Bot de Búsqueda (usa el mismo que publicaciones por defecto)
SEARCH_BOT_TOKEN = os.getenv("TELEGRAM_SEARCH_BOT_TOKEN") or os.getenv("TELEGRAM_PUBLISHING_BOT_TOKEN", "")
SEARCH_CHAT_ID = os.getenv("TELEGRAM_SEARCH_CHAT_ID") or os.getenv("TELEGRAM_PUBLISHING_CHAT_ID", "")
SEARCH_ENABLED = os.getenv("TELEGRAM_SEARCH_ENABLED", "true").lower() == "true"


def is_configured():
    """Verifica si el bot de búsqueda está configurado"""
    return bool(SEARCH_BOT_TOKEN and SEARCH_CHAT_ID and SEARCH_ENABLED)


def send_message(message, parse_mode="HTML", disable_notification=False):
    """Envía mensaje al bot de búsqueda"""
    if not is_configured():
        return False

    url = f"https://api.telegram.org/bot{SEARCH_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": SEARCH_CHAT_ID,
        "text": message,
        "parse_mode": parse_mode,
        "disable_notification": disable_notification
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Error enviando a bot de búsqueda: {e}")
        return False


# ============================================================
# NOTIFICACIONES DE BÚSQUEDA
# ============================================================

def notify_search_start(keyword, target_asins):
    """Notifica inicio de búsqueda para una keyword"""
    message = f"🔍 <b>Buscando: {keyword}</b>\n📊 Objetivo: ~{target_asins} ASINs Prime"
    return send_message(message, disable_notification=True)


def notify_search_phase(phase_name, current_count, details=None):
    """Notifica progreso de una fase de búsqueda

    Args:
        phase_name: Nombre de la fase (Búsqueda, Filtrado, Prime, BSR)
        current_count: Cantidad actual de ASINs
        details: Detalles adicionales (opcional)
    """
    emoji_map = {
        "Búsqueda": "🔎",
        "Filtrado": "🔄",
        "Prime": "⭐",
        "BSR": "📊",
        "Calidad": "✨"
    }

    emoji = emoji_map.get(phase_name, "📌")
    message = f"{emoji} {phase_name}: {current_count} ASINs"

    if details:
        message += f"\n   {details}"

    return send_message(message, disable_notification=True)


def notify_search_complete(keyword, final_count, stats):
    """Notifica finalización de búsqueda con resumen

    Args:
        keyword: Keyword buscada
        final_count: Cantidad final de ASINs seleccionados
        stats: Dict con estadísticas (total_found, filtered_brands, prime_count, etc)
    """
    total_found = stats.get("total_found", 0)
    filtered_brands = stats.get("filtered_brands", 0)
    prime_count = stats.get("prime_count", 0)
    quality = stats.get("quality", "N/A")

    # Calcular ratios
    brand_ratio = (filtered_brands / total_found * 100) if total_found > 0 else 0
    prime_ratio = (prime_count / filtered_brands * 100) if filtered_brands > 0 else 0
    final_ratio = (final_count / total_found * 100) if total_found > 0 else 0

    message = f"""✅ <b>Búsqueda completada: {keyword}</b>

📊 Resumen:
   🔎 Encontrados: {total_found} ASINs
   ✅ Marcas OK: {filtered_brands} ({brand_ratio:.0f}%)
   ⭐ Con Prime: {prime_count} ({prime_ratio:.0f}%)
   🎯 Seleccionados: <b>{final_count}</b> ({final_ratio:.0f}%)

✨ Calidad: {quality}
"""
    return send_message(message)


def notify_search_error(keyword, error_msg):
    """Notifica error en búsqueda"""
    message = f"❌ <b>Error buscando: {keyword}</b>\n{error_msg[:100]}"
    return send_message(message)


def notify_cycle_start(cycle_num, keywords_count):
    """Notifica inicio de ciclo autónomo"""
    message = f"🔄 <b>Ciclo #{cycle_num}</b>\n📝 {keywords_count} keywords en cola"
    return send_message(message)


def notify_cycle_complete(cycle_num, total_asins, duration_min):
    """Notifica finalización de ciclo"""
    message = f"""🏁 <b>Ciclo #{cycle_num} completado</b>

📦 Total ASINs: {total_asins}
⏱️ Duración: {duration_min:.0f} min
"""
    return send_message(message)


def notify_daily_summary(stats):
    """Notifica resumen diario

    Args:
        stats: Dict con estadísticas del día
    """
    cycles = stats.get("cycles", 0)
    keywords = stats.get("keywords_processed", 0)
    total_asins = stats.get("total_asins", 0)
    published = stats.get("published", 0)

    message = f"""📊 <b>Resumen del día</b>

🔄 Ciclos: {cycles}
🔍 Keywords: {keywords}
📦 ASINs buscados: {total_asins}
✅ Publicados: {published}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
    return send_message(message)


# ============================================================
# FUNCIÓN DE TEST
# ============================================================

def test_notification():
    """Envía mensaje de prueba al bot de búsqueda"""
    if not is_configured():
        print("❌ Bot de búsqueda no configurado")
        print("\nPara configurar:")
        print("1. Agrega a .env:")
        print("   TELEGRAM_SEARCH_ENABLED=true")
        print("2. O usa el mismo bot de publicaciones (por defecto)")
        return False

    message = """
🤖 <b>Test - Bot de Búsqueda</b>

✅ Bot configurado correctamente
🔍 Notificaciones de búsqueda activas

🕐 {}
""".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    success = send_message(message)
    if success:
        print("✅ Mensaje de prueba enviado al bot de búsqueda")
    else:
        print("❌ Error enviando mensaje de prueba")

    return success


if __name__ == "__main__":
    test_notification()
