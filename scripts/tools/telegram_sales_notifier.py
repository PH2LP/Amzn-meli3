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
import fcntl
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(override=True)

# Configuración - Usar rutas absolutas desde la raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "storage" / "listings_database.db"
SALES_LOG_PATH = PROJECT_ROOT / "storage" / "logs" / "sales_notified.json"
ASINS_JSON_DIR = PROJECT_ROOT / "storage" / "asins_json"
LOG_DIR = PROJECT_ROOT / "storage" / "logs" / "sales"
LOCK_FILE = PROJECT_ROOT / "storage" / "telegram_notifier.lock"
DEDUP_FILE = PROJECT_ROOT / "storage" / "telegram_messages_sent.json"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# APIs
ML_API = "https://api.mercadolibre.com"
ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ============================================================
# FUNCIONES DE FILE LOCKING Y DEDUPLICACIÓN
# ============================================================

class FileLock:
    """Context manager para file locking con fcntl"""
    def __init__(self, lock_file):
        self.lock_file = Path(lock_file)
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.fd = None

    def __enter__(self):
        self.fd = open(str(self.lock_file), 'w')
        try:
            fcntl.flock(self.fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return self
        except IOError:
            raise RuntimeError("Ya hay otra instancia ejecutándose")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd:
            fcntl.flock(self.fd.fileno(), fcntl.LOCK_UN)
            self.fd.close()


def generate_message_hash(pack_id, marketplace, asin):
    """Genera un hash único para identificar mensajes duplicados"""
    today = datetime.now().strftime("%Y-%m-%d")
    unique_str = f"{pack_id}|{marketplace}|{asin}|{today}"
    return hashlib.sha256(unique_str.encode()).hexdigest()[:16]


def load_sent_messages():
    """Carga el registro de mensajes enviados en las últimas 24h"""
    if not DEDUP_FILE.exists():
        return {}

    try:
        with open(str(DEDUP_FILE), "r") as f:
            all_messages = json.load(f)

        # Limpiar mensajes más viejos de 24 horas
        cutoff = datetime.now() - timedelta(hours=24)
        valid_messages = {}

        for msg_hash, data in all_messages.items():
            timestamp = datetime.fromisoformat(data.get("timestamp", "2000-01-01"))
            if timestamp > cutoff:
                valid_messages[msg_hash] = data

        # Guardar solo los válidos
        if len(valid_messages) != len(all_messages):
            with open(str(DEDUP_FILE), "w") as f:
                json.dump(valid_messages, f, indent=2)

        return valid_messages
    except Exception as e:
        print(f"⚠️ Error cargando mensajes enviados: {e}")
        return {}


def save_sent_message(msg_hash, pack_id, marketplace, asin):
    """Registra un mensaje como enviado"""
    DEDUP_FILE.parent.mkdir(parents=True, exist_ok=True)

    sent_messages = load_sent_messages()
    sent_messages[msg_hash] = {
        "timestamp": datetime.now().isoformat(),
        "pack_id": pack_id,
        "marketplace": marketplace,
        "asin": asin
    }

    with open(str(DEDUP_FILE), "w") as f:
        json.dump(sent_messages, f, indent=2)


def was_message_sent(msg_hash):
    """Verifica si un mensaje ya fue enviado"""
    sent_messages = load_sent_messages()
    return msg_hash in sent_messages


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
        "disable_web_page_preview": True
    }

    # Solo agregar parse_mode si no es None
    if parse_mode:
        data["parse_mode"] = parse_mode

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
    Obtiene órdenes recientes del seller (CBT - Cross Border Trade).

    Args:
        user_id: ID del usuario vendedor
        limit: Número máximo de órdenes a obtener

    Returns:
        list: Lista de órdenes completas (con pack_id agregado)
    """
    url = f"{ML_API}/marketplace/orders/search"
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

        # En CBT, cada resultado es un "cart" que contiene "orders"
        all_orders = []
        carts = data.get("results", [])

        for cart in carts:
            pack_id = cart.get("id")  # ID del pack/cart (esto es lo que se ve en ML)
            orders = cart.get("orders", [])

            for order in orders:
                order_id = order.get("id")

                # Obtener detalles completos de la orden
                order_url = f"{ML_API}/marketplace/orders/{order_id}"
                order_resp = requests.get(order_url, headers=headers, timeout=10)

                if order_resp.status_code == 200:
                    full_order = order_resp.json()
                    # Agregar el pack_id al objeto order
                    full_order["pack_id"] = pack_id
                    all_orders.append(full_order)

        return all_orders

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
    Busca tanto en item_id (CBT) como en site_items (IDs locales de cada marketplace).

    Args:
        item_id: ID del item en MercadoLibre (puede ser CBT o local como MLB, MLM, etc.)

    Returns:
        dict: {asin, title, brand, model, permalink, amazon_cost} o None
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Primero buscar por item_id exacto (CBT)
    cursor.execute("""
        SELECT asin, title, brand, model, permalink, country
        FROM listings
        WHERE item_id = ?
        LIMIT 1
    """, (item_id,))

    row = cursor.fetchone()

    # Si no encuentra, buscar en site_items (JSON con IDs locales)
    if not row:
        cursor.execute("""
            SELECT asin, title, brand, model, permalink, country
            FROM listings
            WHERE site_items LIKE ?
            LIMIT 1
        """, (f'%{item_id}%',))

        row = cursor.fetchone()

    conn.close()

    if not row:
        return None

    result = dict(row)
    asin = result.get("asin")

    # Obtener precio en TIEMPO REAL de Glow API cuando hay una venta
    amazon_cost = 0
    if asin:
        print(f"   🔄 Obteniendo precio en tiempo real de Glow API...")

        try:
            # Importar función de Glow API
            import sys
            if str(PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(PROJECT_ROOT))

            from src.integrations.amazon_glow_api import check_real_availability_glow_api

            # Obtener precio actual de Amazon con Glow API
            glow_data = check_real_availability_glow_api(asin)
            if glow_data and glow_data.get("price"):
                amazon_cost = glow_data["price"]
                print(f"   ✅ Precio de Glow API: ${amazon_cost}")
            else:
                print(f"   ⚠️ Glow API no devolvió precio, usando fallback...")
        except Exception as e:
            print(f"   ⚠️ Error con Glow API: {e}")

        # Fallback: Si Glow API falla, intentar JSON
        if amazon_cost == 0:
            print(f"   📋 Intentando obtener precio de JSON...")
            json_file = ASINS_JSON_DIR / f"{asin}.json"
            if json_file.exists():
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                        amazon_cost = data.get("prime_pricing", {}).get("price", 0)
                        print(f"   💲 Precio desde JSON (fallback): ${amazon_cost}")
                except Exception as e:
                    print(f"   ⚠️ Error leyendo JSON: {e}")
            else:
                print(f"   ❌ No hay precio disponible para ASIN {asin}")

    result["amazon_cost"] = amazon_cost
    return result


def load_notified_sales():
    """Carga el registro de ventas ya notificadas"""
    if not SALES_LOG_PATH.exists():
        return {}

    try:
        with open(str(SALES_LOG_PATH), "r") as f:
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

    # Asegurar que el directorio existe
    SALES_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(str(SALES_LOG_PATH), "w") as f:
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
    order_id = order.get("id")  # Order ID individual
    pack_id = order.get("pack_id", order_id)  # Pack ID (lo que se ve en ML)
    order_items = order.get("order_items", [])

    if not order_items:
        return None

    item = order_items[0].get("item", {})
    item_title = item.get("title", "Sin título")
    quantity = order_items[0].get("quantity", 1)

    # Datos financieros
    unit_price = order_items[0].get("unit_price", 0)
    sale_fee = order_items[0].get("sale_fee", 0)

    # Obtener el total que pagó el cliente desde payments
    payments = order.get("payments", [])
    total_paid_by_customer = payments[0].get("total_paid_amount", 0) if payments else unit_price

    # Obtener shipping cost desde el endpoint de shipments
    shipping = order.get("shipping", {})
    shipping_id = shipping.get("id")
    shipping_cost = 0

    if shipping_id:
        try:
            import requests
            headers = {"Authorization": f"Bearer {ML_TOKEN}"}
            r = requests.get(f"{ML_API}/marketplace/shipments/{shipping_id}",
                           headers=headers, timeout=10)
            if r.status_code == 200:
                shipment_data = r.json()
                lead_time = shipment_data.get("lead_time", {})
                shipping_cost = lead_time.get("list_cost", 0)
        except:
            pass

    # NET PROCEEDS - Calcular manualmente para TODAS las unidades
    # = (Precio de venta * cantidad) - (Fee ML * cantidad) - Shipping
    net_proceeds = (unit_price * quantity) - (sale_fee * quantity) - shipping_cost

    # Marketplace
    context = order.get("context", {})
    marketplace = context.get("site", "ML")

    # Comprador
    buyer = order.get("buyer", {})
    buyer_nickname = buyer.get("nickname", "N/A")

    # Datos del ASIN
    asin = asin_data.get("asin", "N/A")
    brand = asin_data.get("brand", "N/A")
    amazon_cost = asin_data.get("amazon_cost", 0)

    # Calcular ganancia (lo que recibís - costo Amazon)
    # Solo costo Amazon + 3PL (NO se paga tax) * cantidad de unidades
    fulfillment_fee = 4.0
    total_amazon_cost = (amazon_cost + fulfillment_fee) * quantity
    profit = net_proceeds - total_amazon_cost

    # Link de Amazon Business (NO amazon.com normal)
    amazon_link = f"https://www.amazon.com/business/dp/{asin}"

    # Link de MercadoLibre (orden)
    # Mapear marketplace a dominio
    ml_domains = {
        "MLM": "mercadolibre.com.mx",
        "MLA": "mercadolibre.com.ar",
        "MLB": "mercadolibre.com.br",
        "MLC": "mercadolibre.cl",
        "MLU": "mercadolibre.com.uy",
        "MCO": "mercadolibre.com.co",
        "MLV": "mercadolibre.com.ve",
        "MPA": "mercadolibre.com.pa",
        "MPE": "mercadolibre.com.pe",
    }
    ml_domain = ml_domains.get(marketplace, "mercadolibre.com")
    ml_order_link = f"https://www.{ml_domain}/ventas/{pack_id}/detalle"

    # Calcular precio total de Amazon (producto + warehouse)
    amazon_total_price = amazon_cost + fulfillment_fee

    # Formato del mensaje PRINCIPAL (sin número de orden)
    message = f"""
🎉 <b>¡NUEVA VENTA!</b>

📦 <b>{item_title}</b>
🏷️ Marca: <b>{brand}</b>
👤 Comprador: <b>{buyer_nickname}</b>

━━━━━━━━━━━━━━━━━━━━━
💰 <b>FINANCIERO</b>
━━━━━━━━━━━━━━━━━━━━━
📊 Cantidad: <b>{quantity}</b>
💵 Total pagado: <b>${total_paid_by_customer:.2f}</b>
💰 Recibís (neto): <b>${net_proceeds:.2f}</b>
✅ Ganancia: <b>${profit:.2f}</b>

━━━━━━━━━━━━━━━━━━━━━
🛒 <b>COMPRAR EN AMAZON</b>
━━━━━━━━━━━━━━━━━━━━━
<code>{asin}</code>
💲 Precio Amazon + Warehouse = <b>${amazon_total_price:.2f} x {quantity} = ${amazon_total_price * quantity:.2f}</b>
🔗 <a href="{amazon_link}">👉 CLICK PARA COMPRAR 👈</a>

<a href="{ml_order_link}">🔗 Ver orden completa en MercadoLibre</a>
"""

    # Mensaje SEPARADO con solo el número de orden (para copiar fácil)
    order_number_message = f"{marketplace}-{pack_id}"

    # Retornar ambos mensajes
    return (message.strip(), order_number_message)


def check_new_sales():
    """
    Revisa si hay nuevas ventas y envía notificaciones.
    Usa file locking para evitar ejecuciones concurrentes.

    Returns:
        dict: Estadísticas de ventas procesadas
    """
    # Intentar obtener el lock
    try:
        with FileLock(LOCK_FILE):
            print("=" * 80)
            print("🔔 VERIFICANDO NUEVAS VENTAS")
            print("=" * 80)
            print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("🔒 Lock adquirido - procesando...\n")

            return _check_new_sales_impl()
    except RuntimeError as e:
        print(f"⚠️ {e}")
        print("   Otra instancia ya está procesando ventas. Saltando...")
        return {"error": "Instance already running"}


def _check_new_sales_impl():
    """
    Implementación interna de check_new_sales (sin lock).

    Returns:
        dict: Estadísticas de ventas procesadas
    """

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
        "duplicates_detected": 0,
        "notifications_sent": 0,
        "errors": 0
    }

    # Procesar cada orden
    for order in orders:
        order_id = str(order.get("id"))  # Order ID individual
        pack_id = str(order.get("pack_id", order_id))  # Pack ID (lo que se ve en ML)
        order_status = order.get("status")

        # Solo notificar órdenes pagadas
        if order_status not in ["paid", "confirmed"]:
            continue

        # Verificar si ya fue notificada (usar pack_id para evitar duplicados)
        if pack_id in notified_sales:
            stats["already_notified"] += 1
            continue

        stats["new_sales"] += 1

        # Extraer item_id y parent_item_id (CBT)
        order_items = order.get("order_items", [])
        if not order_items:
            continue

        item = order_items[0].get("item", {})
        item_id = item.get("id")  # ID local del marketplace (MLM, MLU, etc.)
        parent_item_id = item.get("parent_item_id")  # ID de CBT (CBT...)

        # Obtener marketplace del context
        context = order.get("context", {})
        marketplace = context.get("site", "MLU")

        print(f"\n{'─'*80}")
        print(f"🆕 NUEVA VENTA DETECTADA")
        print(f"{'─'*80}")
        print(f"   Pack ID (ML): {pack_id}")
        print(f"   Order ID: {order_id}")
        print(f"   Marketplace: {marketplace}")
        print(f"   Item ID: {item_id}")
        print(f"   CBT ID: {parent_item_id}")
        print(f"   Estado: {order_status}")

        # Buscar ASIN en la BD usando CBT ID o item_id local
        print(f"   🔍 Buscando ASIN en BD...")

        # Intentar primero con CBT ID (parent_item_id)
        asin_data = None
        if parent_item_id:
            print(f"      Buscando por CBT: {parent_item_id}")
            asin_data = get_asin_by_item_id(parent_item_id)

        # Si no encuentra, intentar con item_id local (MLB, MLM, etc.)
        if not asin_data:
            print(f"      Buscando por item_id local: {item_id}")
            asin_data = get_asin_by_item_id(item_id)

        if not asin_data:
            print(f"   ⚠️ No se encontró ASIN para:")
            print(f"      CBT: {parent_item_id}")
            print(f"      Item local: {item_id}")
            stats["errors"] += 1
            continue

        asin = asin_data.get('asin')
        print(f"   ✅ ASIN encontrado: {asin}")

        # Generar hash único para detectar duplicados
        msg_hash = generate_message_hash(pack_id, marketplace, asin)
        print(f"   🔑 Hash: {msg_hash}")

        # Verificar si ya se envió este mensaje (deduplicación por hash)
        if was_message_sent(msg_hash):
            print(f"   🔄 Mensaje ya enviado anteriormente (duplicado detectado)")
            print(f"      Saltando notificación...")
            stats["duplicates_detected"] += 1
            stats["already_notified"] += 1
            continue

        # Formatear mensaje (retorna 2 mensajes: principal y número de orden)
        messages = format_sale_notification(order, asin_data)

        if not messages:
            print(f"   ❌ Error formateando mensaje")
            stats["errors"] += 1
            continue

        main_message, order_number_message = messages

        # Enviar MENSAJE PRINCIPAL (con toda la info)
        print(f"   📤 Enviando notificación principal a Telegram...")
        if send_telegram_message(main_message):
            print(f"   ✅ Notificación principal enviada exitosamente")

            # Enviar NÚMERO DE ORDEN en mensaje separado (para copiar fácil)
            print(f"   📤 Enviando número de orden separado...")
            send_telegram_message(order_number_message, parse_mode=None)
            print(f"   ✅ Número de orden enviado en mensaje separado")

            stats["notifications_sent"] += 1

            # Guardar hash del mensaje enviado para deduplicación
            save_sent_message(msg_hash, pack_id, marketplace, asin)
            print(f"   💾 Hash registrado para evitar duplicados")

            # Guardar como notificada en el sistema legacy
            save_notified_sale(pack_id, {
                "item_id": item_id,
                "asin": asin
            })

            # Registrar venta en DB y actualizar Excel + Dropbox
            print(f"   💾 Registrando venta en DB y actualizando Excel...")
            try:
                import subprocess
                import sys

                # 1. Registrar venta en DB (track_sales.py)
                track_cmd = [sys.executable, "scripts/tools/track_sales.py"]
                subprocess.run(track_cmd, cwd=str(PROJECT_ROOT), timeout=30, capture_output=True)

                # 2. Generar Excel y subir a Dropbox (generate_excel_desktop.py hace todo)
                excel_cmd = [sys.executable, "scripts/tools/generate_excel_desktop.py"]
                subprocess.run(excel_cmd, cwd=str(PROJECT_ROOT), timeout=30, capture_output=True)

                print(f"   ✅ Venta registrada, Excel generado y subido a Dropbox")

            except Exception as e:
                print(f"   ⚠️  Error: {e}")

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
    print(f"  └─ Duplicados bloqueados: {stats['duplicates_detected']}")
    print(f"Notificaciones enviadas:  {stats['notifications_sent']}")
    print(f"Errores:                  {stats['errors']}")
    print()

    # Guardar log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"check_{timestamp}.json"

    with open(str(log_file), "w") as f:
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
