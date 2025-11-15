#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MONITOREO DE MERCADOLIBRE
=========================
Monitorea en tiempo real:
- Nuevas ventas
- Preguntas recibidas
- Mensajes de compradores
- Publicaciones pausadas por ML
- Cambios de estado

Se ejecuta en loop cada X minutos
"""

import os
import json
import sqlite3
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from time import sleep

load_dotenv(override=True)

# Importar notificaciones
try:
    from telegram_notifier import (
        notify_sale,
        notify_question_answered,
        notify_critical_error,
        send_message,
        is_configured as telegram_configured
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    def notify_sale(*args): pass
    def notify_question_answered(*args): pass
    def notify_critical_error(*args): pass
    def send_message(*args): pass
    def telegram_configured(): return False

# Configuración
ML_API = "https://api.mercadolibre.com"
ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
USER_ID = os.getenv("ML_USER_ID", "2629793984")

# Archivo de estado para tracking
STATE_FILE = Path("storage/ml_monitor_state.json")
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_state():
    """Carga el último estado conocido"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        "last_order_id": None,
        "last_question_id": None,
        "last_message_id": None,
        "checked_at": None
    }


def save_state(state):
    """Guarda el estado actual"""
    state["checked_at"] = datetime.now().isoformat()
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def get_orders():
    """Obtiene órdenes recientes"""
    url = f"{ML_API}/orders/search"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}
    params = {
        "seller": USER_ID,
        "sort": "date_desc",
        "limit": 50
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        print(f"❌ Error obteniendo órdenes: {e}")
        return []


def get_questions():
    """Obtiene preguntas recientes"""
    url = f"{ML_API}/my/received_questions/search"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}
    params = {
        "status": "UNANSWERED",
        "sort_fields": "date_created",
        "sort_types": "DESC",
        "limit": 50
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("questions", [])
    except Exception as e:
        print(f"❌ Error obteniendo preguntas: {e}")
        return []


def get_messages():
    """Obtiene mensajes recientes"""
    url = f"{ML_API}/messages/packs/{USER_ID}/sellers"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        print(f"❌ Error obteniendo mensajes: {e}")
        return []


def check_new_orders(state):
    """Verifica si hay nuevas ventas"""
    orders = get_orders()
    if not orders:
        return

    last_known_id = state.get("last_order_id")
    new_orders = []

    for order in orders:
        order_id = order.get("id")

        # Si encontramos la última orden conocida, paramos
        if order_id == last_known_id:
            break

        new_orders.append(order)

    # Notificar nuevas ventas
    for order in reversed(new_orders):  # Más viejas primero
        order_id = order.get("id")
        buyer_nickname = order.get("buyer", {}).get("nickname", "Desconocido")
        total = order.get("total_amount", 0)

        # Obtener items
        items_text = ""
        for item in order.get("order_items", []):
            title = item.get("item", {}).get("title", "")[:50]
            qty = item.get("quantity", 1)
            items_text += f"  • {title} (x{qty})\n"

        print(f"🎉 Nueva venta: #{order_id} - ${total} - {buyer_nickname}")

        if telegram_configured():
            message = f"""
🎉 <b>¡NUEVA VENTA!</b>

💰 Total: <b>${total:.2f}</b>
👤 Comprador: {buyer_nickname}
🆔 Orden: <code>{order_id}</code>

📦 Productos:
{items_text}
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            send_message(message)

    # Actualizar último order_id
    if orders:
        state["last_order_id"] = orders[0].get("id")


def check_new_questions(state):
    """Verifica si hay nuevas preguntas sin responder"""
    questions = get_questions()
    if not questions:
        return

    last_known_id = state.get("last_question_id")
    new_questions = []

    for q in questions:
        q_id = q.get("id")

        if q_id == last_known_id:
            break

        new_questions.append(q)

    # Notificar preguntas nuevas
    for q in reversed(new_questions):
        q_id = q.get("id")
        text = q.get("text", "")
        item_id = q.get("item_id", "")

        print(f"❓ Nueva pregunta: #{q_id} - {text[:50]}...")

        if telegram_configured():
            message = f"""
❓ <b>Nueva Pregunta Sin Responder</b>

💬 Pregunta: {text}
🆔 Item: <code>{item_id}</code>
🆔 Pregunta ID: <code>{q_id}</code>

⚠️ Requiere respuesta manual o verificar auto-respuesta
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            send_message(message)

    if questions:
        state["last_question_id"] = questions[0].get("id")


def check_paused_listings():
    """Verifica publicaciones pausadas por ML"""
    url = f"{ML_API}/users/{USER_ID}/items/search"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}
    params = {
        "status": "paused",
        "limit": 50
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        paused_items = r.json().get("results", [])

        if paused_items:
            print(f"⏸️  {len(paused_items)} publicaciones pausadas")

            # Notificar solo si hay muchas (más de 5)
            if len(paused_items) > 5 and telegram_configured():
                message = f"""
⏸️  <b>Publicaciones Pausadas</b>

⚠️ {len(paused_items)} publicaciones están pausadas

Verifica en MercadoLibre la razón.
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
                send_message(message, disable_notification=True)

    except Exception as e:
        print(f"❌ Error verificando publicaciones pausadas: {e}")


def monitor_loop(interval_minutes=5):
    """Loop principal de monitoreo"""
    print("═" * 70)
    print("🔍 MONITOREO DE MERCADOLIBRE INICIADO")
    print("═" * 70)
    print(f"⏱️  Intervalo: Cada {interval_minutes} minutos")
    print(f"📱 Telegram: {'✅ Activado' if telegram_configured() else '❌ Desactivado'}")
    print("🛑 Para detener: Ctrl+C")
    print("═" * 70)
    print()

    while True:
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔍 Monitoreando...")

            state = load_state()

            # Verificar ventas
            check_new_orders(state)

            # Verificar preguntas
            check_new_questions(state)

            # Verificar publicaciones pausadas
            check_paused_listings()

            # Guardar estado
            save_state(state)

            print(f"   ✅ Verificación completada")
            print(f"   💤 Durmiendo {interval_minutes} minutos...")
            print()

            sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            print()
            print("═" * 70)
            print("🛑 Monitoreo detenido por usuario")
            print("═" * 70)
            break
        except Exception as e:
            print(f"❌ Error en monitoreo: {e}")

            if telegram_configured():
                notify_critical_error("Monitoreo ML", str(e))

            sleep(60)  # Esperar 1 minuto antes de reintentar


if __name__ == "__main__":
    import sys

    interval = 5  # Default: 5 minutos

    if len(sys.argv) > 1:
        try:
            interval = int(sys.argv[1])
        except:
            pass

    monitor_loop(interval)
