#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SISTEMA DE NOTIFICACIONES DE VENTAS - TELEGRAM
==============================================
Monitorea ventas en MercadoLibre y envía notificación por Telegram
con toda la información necesaria para comprar en Amazon.

Configuración requerida en .env:
- TELEGRAM_BOT_TOKEN: Token del bot de Telegram
- TELEGRAM_CHAT_ID: ID del chat donde enviar notificaciones
- ML_ACCESS_TOKEN: Token de MercadoLibre

Uso:
    # Ejecutar manualmente
    python3 scripts/tools/telegram_sales_notifier.py

    # Ejecutar en loop (cada 60 segundos)
    ./scripts/tools/telegram_notifier_loop.sh
"""

import os
import sys
import json
import sqlite3
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(override=True)

# Configuración
DB_PATH = "storage/listings_database.db"
SALES_LOG_PATH = "storage/logs/sales_notified.json"
LOG_DIR = Path("storage/logs/sales")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# APIs
ML_API = "https://api.mercadolibre.com"
ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ============================================================
# FUNCIONES DE TELEGRAM
# ============================================================

def send_telegram_message(text, parse_mode="HTML"):
    """Envía un mensaje por Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Credenciales de Telegram no configuradas")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False
    }

    try:
        r = requests.post(url, json=data, timeout=30)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Error enviando mensaje a Telegram: {e}")
        return False


# ============================================================
# FUNCIONES DE MERCADOLIBRE
# ============================================================

def get_ml_orders(user_id, limit=50):
    """
    Obtiene órdenes recientes del seller.

    Args:
        user_id: ID del usuario vendedor
        limit: Número máximo de órdenes a obtener

    Returns:
        list: Lista de órdenes
    """
    url = f"{ML_API}/orders/search"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}
    params = {
        "seller": user_id,
        "sort": "date_desc",
        "limit": limit
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("results", [])
    except Exception as e:
        print(f"❌ Error obteniendo órdenes: {e}")
        return []


def get_ml_user_id():
    """Obtiene el user_id del seller"""
    url = f"{ML_API}/users/me"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("id")
    except Exception as e:
        print(f"❌ Error obteniendo user_id: {e}")
        return None


# ============================================================
# FUNCIONES DE BASE DE DATOS
# ============================================================

def get_asin_by_item_id(item_id):
    """
    Busca el ASIN asociado a un item_id de MercadoLibre.

    Args:
        item_id: ID del item en MercadoLibre

    Returns:
        dict: {asin, title, brand, model, permalink} o None
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT asin, title, brand, model, permalink, country
        FROM listings
        WHERE item_id = ?
        LIMIT 1
    """, (item_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def load_notified_sales():
    """Carga el registro de ventas ya notificadas"""
    if not os.path.exists(SALES_LOG_PATH):
        return {}

    try:
        with open(SALES_LOG_PATH, "r") as f:
            return json.load(f)
    except:
        return {}


def save_notified_sale(order_id, order_data):
    """Guarda una venta como notificada"""
    notified = load_notified_sales()
    notified[order_id] = {
        "timestamp": datetime.now().isoformat(),
        "item_id": order_data.get("item_id"),
        "asin": order_data.get("asin")
    }

    with open(SALES_LOG_PATH, "w") as f:
        json.dump(notified, f, indent=2)


# ============================================================
# LÓGICA PRINCIPAL
# ============================================================

def format_sale_notification(order, asin_data):
    """
    Formatea el mensaje de notificación de venta.

    Args:
        order: Datos de la orden de MercadoLibre
        asin_data: Datos del ASIN desde la BD

    Returns:
        str: Mensaje formateado en HTML para Telegram
    """
    # Extraer datos de la orden
    order_id = order.get("id")
    order_items = order.get("order_items", [])

    if not order_items:
        return None

    item = order_items[0].get("item", {})
    item_id = item.get("id")
    item_title = item.get("title", "Sin título")
    quantity = order_items[0].get("quantity", 1)
    unit_price = order_items[0].get("unit_price", 0)
    total_amount = order.get("total_amount", 0)

    # Datos del comprador
    buyer = order.get("buyer", {})
    buyer_nickname = buyer.get("nickname", "N/A")

    # Datos de envío
    shipping = order.get("shipping", {})
    shipping_address = shipping.get("receiver_address", {})
    city = shipping_address.get("city", {}).get("name", "N/A")
    state = shipping_address.get("state", {}).get("name", "N/A")
    country = shipping_address.get("country", {}).get("name", "N/A")

    # Datos del ASIN
    asin = asin_data.get("asin", "N/A")
    brand = asin_data.get("brand", "N/A")
    model = asin_data.get("model", "N/A")
    ml_permalink = asin_data.get("permalink", "N/A")

    # Link de Amazon
    amazon_link = f"https://www.amazon.com/dp/{asin}"

    # Formato del mensaje
    message = f"""
🎉 <b>¡NUEVA VENTA EN MERCADOLIBRE!</b> 🎉

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 <b>PRODUCTO</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• <b>Título:</b> {item_title}
• <b>Marca:</b> {brand}
• <b>Modelo:</b> {model}
• <b>Cantidad:</b> {quantity}
• <b>Precio unitario:</b> ${unit_price:.2f}
• <b>Total:</b> ${total_amount:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛒 <b>COMPRAR EN AMAZON AHORA</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• <b>ASIN:</b> <code>{asin}</code>

🔗 <b><a href="{amazon_link}">👉 CLICK AQUÍ PARA COMPRAR EN AMAZON 👈</a></b>

⚠️ <b>Comprar {quantity} unidad(es)</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>COMPRADOR</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• <b>Usuario:</b> {buyer_nickname}
• <b>Ubicación:</b> {city}, {state}, {country}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 <b>ORDEN</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• <b>ID Orden:</b> <code>{order_id}</code>
• <b>ID MercadoLibre:</b> <code>{item_id}</code>
• <b>Link ML:</b> <a href="{ml_permalink}">Ver publicación</a>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Comprar en Amazon y marcar como enviado en ML.
"""

    return message.strip()


def check_new_sales():
    """
    Revisa si hay nuevas ventas y envía notificaciones.

    Returns:
        dict: Estadísticas de ventas procesadas
    """
    print("=" * 80)
    print("🔔 VERIFICANDO NUEVAS VENTAS")
    print("=" * 80)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Verificar credenciales
    if not ML_TOKEN:
        print("❌ ML_ACCESS_TOKEN no configurado en .env")
        return {"error": "Missing ML token"}

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Credenciales de Telegram no configuradas")
        print("   Agrega TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID al .env")
        return {"error": "Missing Telegram credentials"}

    # Obtener user_id
    print("🔐 Obteniendo información del seller...")
    user_id = get_ml_user_id()
    if not user_id:
        print("❌ No se pudo obtener el user_id")
        return {"error": "Could not get user_id"}

    print(f"✅ Seller ID: {user_id}\n")

    # Cargar ventas ya notificadas
    notified_sales = load_notified_sales()
    print(f"📋 Ventas ya notificadas: {len(notified_sales)}")

    # Obtener órdenes recientes
    print("📦 Consultando órdenes recientes...")
    orders = get_ml_orders(user_id, limit=50)
    print(f"✅ Encontradas {len(orders)} órdenes\n")

    # Estadísticas
    stats = {
        "total_orders": len(orders),
        "new_sales": 0,
        "already_notified": 0,
        "notifications_sent": 0,
        "errors": 0
    }

    # Procesar cada orden
    for order in orders:
        order_id = str(order.get("id"))
        order_status = order.get("status")

        # Solo notificar órdenes pagadas
        if order_status not in ["paid", "confirmed"]:
            continue

        # Verificar si ya fue notificada
        if order_id in notified_sales:
            stats["already_notified"] += 1
            continue

        stats["new_sales"] += 1

        # Extraer item_id
        order_items = order.get("order_items", [])
        if not order_items:
            continue

        item = order_items[0].get("item", {})
        item_id = item.get("id")

        print(f"\n{'─'*80}")
        print(f"🆕 NUEVA VENTA DETECTADA")
        print(f"{'─'*80}")
        print(f"   Orden ID: {order_id}")
        print(f"   Item ID: {item_id}")
        print(f"   Estado: {order_status}")

        # Buscar ASIN en la BD
        print(f"   🔍 Buscando ASIN en BD...")
        asin_data = get_asin_by_item_id(item_id)

        if not asin_data:
            print(f"   ⚠️ No se encontró ASIN para item_id: {item_id}")
            stats["errors"] += 1
            continue

        print(f"   ✅ ASIN encontrado: {asin_data.get('asin')}")

        # Formatear mensaje
        message = format_sale_notification(order, asin_data)

        if not message:
            print(f"   ❌ Error formateando mensaje")
            stats["errors"] += 1
            continue

        # Enviar notificación
        print(f"   📤 Enviando notificación a Telegram...")
        if send_telegram_message(message):
            print(f"   ✅ Notificación enviada exitosamente")
            stats["notifications_sent"] += 1

            # Guardar como notificada
            save_notified_sale(order_id, {
                "item_id": item_id,
                "asin": asin_data.get("asin")
            })
        else:
            print(f"   ❌ Error enviando notificación")
            stats["errors"] += 1

    # Resumen
    print(f"\n{'='*80}")
    print("📊 RESUMEN")
    print(f"{'='*80}")
    print(f"Total órdenes revisadas:  {stats['total_orders']}")
    print(f"Nuevas ventas:            {stats['new_sales']}")
    print(f"Ya notificadas:           {stats['already_notified']}")
    print(f"Notificaciones enviadas:  {stats['notifications_sent']}")
    print(f"Errores:                  {stats['errors']}")
    print()

    # Guardar log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"check_{timestamp}.json"

    with open(log_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "statistics": stats
        }, f, indent=2)

    print(f"📄 Log guardado en: {log_file}")

    return stats


def main():
    """Función principal"""
    try:
        check_new_sales()
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
