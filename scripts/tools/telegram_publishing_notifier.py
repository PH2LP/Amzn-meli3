#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO DE NOTIFICACIONES TELEGRAM PARA PUBLICACIONES (MAIN2)
=============================================================
Bot separado para notificar sobre el progreso de publicaciones

CONFIGURACIÓN EN .ENV:
----------------------
TELEGRAM_PUBLISHING_BOT_TOKEN=tu_token_bot2
TELEGRAM_PUBLISHING_CHAT_ID=tu_chat_id
TELEGRAM_PUBLISHING_ENABLED=true
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

# Configuración Bot de Publicaciones
PUBLISHING_BOT_TOKEN = os.getenv("TELEGRAM_PUBLISHING_BOT_TOKEN", "")
PUBLISHING_CHAT_ID = os.getenv("TELEGRAM_PUBLISHING_CHAT_ID", "")
PUBLISHING_ENABLED = os.getenv("TELEGRAM_PUBLISHING_ENABLED", "false").lower() == "true"


def is_configured():
    """Verifica si el bot de publicaciones está configurado"""
    return bool(PUBLISHING_BOT_TOKEN and PUBLISHING_CHAT_ID and PUBLISHING_ENABLED)


def send_message(message, parse_mode="HTML", disable_notification=False):
    """Envía mensaje al bot de publicaciones"""
    if not is_configured():
        return False

    url = f"https://api.telegram.org/bot{PUBLISHING_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": PUBLISHING_CHAT_ID,
        "text": message,
        "parse_mode": parse_mode,
        "disable_notification": disable_notification
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Error enviando a bot de publicaciones: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Respuesta de Telegram: {e.response.text[:200]}")
            print(f"   Status code: {e.response.status_code}")
        return False


# ============================================================
# NOTIFICACIONES DE PUBLICACIÓN
# ============================================================

def notify_batch_start(total_products, run_id):
    """Notifica inicio de batch de publicaciones"""
    message = f"🚀 <b>Iniciando batch: {total_products} productos</b>"
    return send_message(message)


def notify_product_start(asin, number, total):
    """Notifica inicio de procesamiento de un producto"""
    message = f"📦 [{number}/{total}] <code>{asin}</code>"
    return send_message(message, disable_notification=True)


def notify_download_complete(asin, title, brand):
    """Notifica descarga completada (DESACTIVADA - muy verbosa)"""
    # Función desactivada para reducir spam
    return True


def notify_transform_complete(asin, category_id, category_name, confidence):
    """Notifica transformación completada (DESACTIVADA - muy verbosa)"""
    # Función desactivada para reducir spam
    return True


def translate_ml_error(error_dict):
    """Traduce errores técnicos de MercadoLibre a español claro"""
    if not isinstance(error_dict, dict):
        return str(error_dict)

    error_msg = error_dict.get("message", "")
    causes = error_dict.get("cause", [])

    # Traducción de errores comunes
    if "Validation error" in error_msg or "validation" in error_msg.lower():
        # Buscar causas específicas
        if causes:
            readable_causes = []
            for cause in causes:
                code = cause.get("code", "")
                msg = cause.get("message", "")

                # Traducir códigos comunes
                if "missing" in msg.lower():
                    field = msg.split("[")[-1].split("]")[0] if "[" in msg else "campo"
                    readable_causes.append(f"Falta {field}")
                elif "required" in msg.lower():
                    field = msg.split("Attribute")[-1].split("with")[0].strip() if "Attribute" in msg else "campo"
                    readable_causes.append(f"Requiere {field}")
                elif code == "item.not_allowed":
                    readable_causes.append("Categoría bloqueada")
                elif code == "3701" or "invalid_product_identifier" in msg.lower():
                    readable_causes.append("GTIN duplicado")
                elif "attribute" in msg.lower() and "invalid" in msg.lower():
                    readable_causes.append("Atributo inválido")
                else:
                    # Usar mensaje original si no hay traducción
                    readable_causes.append(msg[:40])

            return " | ".join(readable_causes) if readable_causes else "Error de validación"
        else:
            return "Error de validación"

    elif "3701" in error_msg or "invalid_product_identifier" in error_msg.lower():
        return "GTIN duplicado"

    elif "item.not_allowed" in error_msg:
        return "Categoría bloqueada"

    elif "price" in error_msg.lower():
        return "Error en precio"

    elif "pictures" in error_msg.lower() or "image" in error_msg.lower():
        return "Error en imágenes"

    elif "title" in error_msg.lower():
        return "Error en título"

    elif "description" in error_msg.lower():
        return "Error en descripción"

    # Si no hay traducción específica, devolver mensaje resumido
    return error_msg[:60] if error_msg else "Error desconocido"


def notify_publish_success(asin, item_id, countries_ok, countries_failed_details=None, title=None, current=None, total=None):
    """Notifica publicación exitosa con detalles completos

    Args:
        countries_failed_details: Lista de dicts con {site_id, error_msg} o lista simple de site_ids
    """
    # Normalizar countries_failed_details
    if countries_failed_details and isinstance(countries_failed_details, list):
        if countries_failed_details and isinstance(countries_failed_details[0], str):
            # Lista simple de site_ids (compatibilidad hacia atrás)
            countries_failed = countries_failed_details
            failed_details = {}
        else:
            # Lista de dicts con detalles
            countries_failed = [f.get("site_id") for f in countries_failed_details if f.get("site_id")]
            failed_details = {f.get("site_id"): f.get("error", "") for f in countries_failed_details}
    else:
        countries_failed = []
        failed_details = {}

    total_countries = len(countries_ok) + len(countries_failed)
    emoji = "✅" if not countries_failed else "⚠️"

    # Agregar progreso si está disponible
    progress_str = ""
    if current is not None and total is not None:
        progress_str = f"[{current}/{total}] "

    # Formato: "[40/100] ✅ B0ABC123 → 5/5 MCO, MLM, MLA, MLB, MLC"
    countries_str = ", ".join(countries_ok) if countries_ok else "N/A"
    message = f"{progress_str}{emoji} <code>{asin}</code> → {len(countries_ok)}/{total_countries} {countries_str}"

    # Agregar título del producto si está disponible
    if title:
        # Limitar título a 80 caracteres para que no sea muy largo
        title_short = title[:80] + "..." if len(title) > 80 else title
        message += f"\n📦 {title_short}"

    # Si hay países fallidos, agregarlos con sus errores traducidos
    if countries_failed:
        message += f"\n❌ Fallidos:"
        for site_id in countries_failed:
            if site_id in failed_details and failed_details[site_id]:
                error_translated = translate_ml_error(failed_details[site_id])
                message += f"\n   • {site_id}: {error_translated}"
            else:
                message += f"\n   • {site_id}"

    return send_message(message)


def notify_partial_success(asin, item_id, countries_ok, countries_failed_details, title, current, total, max_retries_reached, partial_error):
    """Notifica publicación parcial exitosa (publicado en algunos países, pero no en todos)

    Args:
        asin: ASIN del producto
        item_id: ID del item en MercadoLibre
        countries_ok: Lista de site_ids donde se publicó exitosamente
        countries_failed_details: Lista de dicts con {site_id, error} de países fallidos
        title: Título del producto
        current: Número de productos procesados
        total: Total de productos a procesar
        max_retries_reached: True si se alcanzó el máximo de reintentos
        partial_error: Mensaje de error adicional si aplica
    """
    # Normalizar countries_failed_details
    if countries_failed_details and isinstance(countries_failed_details, list):
        if countries_failed_details and isinstance(countries_failed_details[0], str):
            # Lista simple de site_ids (compatibilidad hacia atrás)
            countries_failed = countries_failed_details
            failed_details = {}
        else:
            # Lista de dicts con detalles
            countries_failed = [f.get("site_id") for f in countries_failed_details if f.get("site_id")]
            failed_details = {f.get("site_id"): f.get("error", "") for f in countries_failed_details}
    else:
        countries_failed = []
        failed_details = {}

    total_countries = len(countries_ok) + len(countries_failed)

    # Progreso
    progress_str = f"[{current}/{total}] " if current and total else ""

    # Emoji y mensaje principal según el contexto
    if max_retries_reached:
        emoji = "⚠️"
        status_msg = "Publicado parcialmente (intentos agotados)"
    else:
        emoji = "⚠️"
        status_msg = "Publicado parcialmente"

    # Formato: "[40/100] ⚠️ B0ABC123 → Publicado parcialmente"
    countries_str = ", ".join(countries_ok) if countries_ok else "ninguno"
    message = f"{progress_str}{emoji} <code>{asin}</code> → {status_msg}\n"

    # Agregar título del producto
    if title:
        title_short = title[:80] + "..." if len(title) > 80 else title
        message += f"📦 {title_short}\n"

    # Detalles de publicación
    message += f"   ✅ Publicado en: {countries_str} ({len(countries_ok)}/{total_countries})\n"
    message += f"   🔗 Item ID: <code>{item_id}</code>"

    # Si hay países fallidos, agregarlos con sus errores traducidos
    if countries_failed:
        message += f"\n   ❌ No se pudo agregar:"
        for site_id in countries_failed:
            if site_id in failed_details and failed_details[site_id]:
                error_translated = translate_ml_error(failed_details[site_id])
                message += f"\n      • {site_id}: {error_translated}"
            else:
                message += f"\n      • {site_id}"

    # Agregar error adicional si hay
    if partial_error and isinstance(partial_error, str):
        error_short = partial_error[:100]
        message += f"\n   ℹ️ {error_short}"

    return send_message(message)


def notify_publish_error(asin, error_msg, current=None, total=None, title=None):
    """Notifica error en publicación"""
    # Agregar progreso si está disponible
    progress_str = ""
    if current is not None and total is not None:
        progress_str = f"[{current}/{total}] "

    # Intentar traducir el error si es un dict
    if isinstance(error_msg, dict):
        error_translated = translate_ml_error(error_msg)
    elif isinstance(error_msg, str):
        # Intentar parsear como dict si parece JSON
        if error_msg.startswith("{"):
            try:
                import json
                error_dict = json.loads(error_msg)
                error_translated = translate_ml_error(error_dict)
            except:
                error_translated = error_msg[:80]
        else:
            error_translated = error_msg[:80]
    else:
        error_translated = str(error_msg)[:80]

    message = f"{progress_str}❌ <code>{asin}</code> → {error_translated}"

    # Agregar título del producto si está disponible
    if title:
        # Limitar título a 80 caracteres
        title_short = title[:80] + "..." if len(title) > 80 else title
        message += f"\n📦 {title_short}"

    return send_message(message)


def notify_batch_complete(total, success, failed, duration_minutes):
    """Notifica finalización del batch"""
    success_rate = (success / total * 100) if total > 0 else 0
    message = f"🏁 <b>Completado: {success}/{total} OK ({success_rate:.0f}%)</b> en {duration_minutes:.0f}min"
    return send_message(message)


def notify_category_detected(asin, category_name, method, similarity=None):
    """Notifica categoría detectada (DESACTIVADA - muy verbosa)"""
    # Función desactivada para reducir spam
    return True


# ============================================================
# FUNCIÓN DE TEST
# ============================================================

def test_notification():
    """Envía mensaje de prueba al bot de publicaciones"""
    if not is_configured():
        print("❌ Bot de publicaciones no configurado")
        print("\nPara configurar:")
        print("1. Crea un SEGUNDO bot con @BotFather")
        print("2. Obtén el token")
        print("3. Ejecuta: ./setup_telegram.sh TOKEN --publishing")
        return False

    message = """
🤖 <b>Test - Bot de Publicaciones</b>

✅ Bot configurado correctamente
📦 Notificaciones de main2 activas

🕐 {}
""".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    success = send_message(message)
    if success:
        print("✅ Mensaje de prueba enviado al bot de publicaciones")
    else:
        print("❌ Error enviando mensaje de prueba")

    return success


if __name__ == "__main__":
    test_notification()
