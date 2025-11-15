#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitor automático de precios de catálogo con notificaciones Telegram

Funcionalidades:
1. Detecta cuando productos pasan a catálogo
2. Ajusta precios automáticamente
3. Notifica por Telegram cambios importantes
4. Se ejecuta cada 6 horas

Uso:
    # Ejecutar una vez
    python3 scripts/tools/catalog_price_monitor.py

    # Loop continuo (cada 6 horas)
    python3 scripts/tools/catalog_price_monitor.py --loop

    # Test inmediato
    python3 scripts/tools/catalog_price_monitor.py --test
"""

import os
import sys
import time
import sqlite3
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Importar módulos locales
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_catalog_items import check_if_catalog
from adjust_catalog_prices import adjust_catalog_prices

# Importar notificaciones Telegram si está disponible
try:
    from telegram_notifier import send_message, is_configured as telegram_configured
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    def send_message(msg, **kwargs):
        pass
    def telegram_configured():
        return False

load_dotenv()

DB_PATH = "storage/listings_database.db"


def notify_catalog_detected(asin, item_id, title, price):
    """Notifica cuando un producto pasa a catálogo"""
    if not telegram_configured():
        return

    message = f"""
🏷️ <b>PRODUCTO PASÓ A CATÁLOGO</b>

📦 <b>ASIN:</b> {asin}
🔗 <b>Item ID:</b> {item_id}
📝 <b>Título:</b> {title[:60]}...
💰 <b>Precio actual:</b> ${price:.2f}

💡 El sistema ajustará el precio automáticamente en la próxima ejecución.
"""
    send_message(message)


def notify_price_adjusted(asin, precio_original, precio_nuevo, razon, margen):
    """Notifica cuando se ajusta un precio"""
    if not telegram_configured():
        return

    diff = precio_original - precio_nuevo
    pct = (diff / precio_original) * 100

    emoji = "📉" if diff > 0 else "📊"

    message = f"""
{emoji} <b>PRECIO AJUSTADO</b>

📦 <b>ASIN:</b> {asin}
💰 <b>Precio original:</b> ${precio_original:.2f}
💵 <b>Precio nuevo:</b> ${precio_nuevo:.2f}
📊 <b>Cambio:</b> ${diff:.2f} ({pct:.1f}%)
📈 <b>Margen final:</b> {margen:.1f}%

📝 <b>Razón:</b> {razon}
"""
    send_message(message)


def notify_summary(catalogos_nuevos, precios_ajustados, no_rentables):
    """Envía resumen de la ejecución"""
    if not telegram_configured():
        return

    if catalogos_nuevos == 0 and precios_ajustados == 0:
        return  # No notificar si no hay cambios

    message = f"""
📊 <b>RESUMEN MONITOREO CATÁLOGO</b>

🏷️ Nuevos catálogos: {catalogos_nuevos}
💰 Precios ajustados: {precios_ajustados}
🚨 No rentables: {no_rentables}

⏰ Próxima revisión en 6 horas
"""
    send_message(message, disable_notification=True)


def check_and_mark_catalogs():
    """
    Revisa todos los productos y marca los que pasaron a catálogo

    Returns:
        int: Cantidad de productos nuevos en catálogo
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT asin, item_id, title, es_catalogo
        FROM listings
        WHERE item_id IS NOT NULL AND asin NOT LIKE 'TEST%'
    """)

    productos = cursor.fetchall()
    catalogos_nuevos = 0

    print(f"\n🔍 Revisando {len(productos)} producto(s)...\n")

    for producto in productos:
        asin, item_id, title, es_catalogo_actual = producto

        result = check_if_catalog(item_id)

        if "error" in result:
            continue

        if result["is_catalog"] and es_catalogo_actual == 0:
            # Nuevo catálogo detectado!
            print(f"✅ NUEVO CATÁLOGO: {asin}")

            cursor.execute("""
                UPDATE listings
                SET es_catalogo = 1,
                    precio_actual = ?
                WHERE asin = ?
            """, (result['price'], asin))

            catalogos_nuevos += 1

            # Notificar
            notify_catalog_detected(asin, item_id, title, result['price'])

    conn.commit()
    conn.close()

    return catalogos_nuevos


def adjust_and_notify():
    """
    Ajusta precios de catálogo y notifica cambios

    Returns:
        tuple: (precios_ajustados, no_rentables)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT asin, precio_original, precio_actual
        FROM listings
        WHERE es_catalogo = 1 AND asin NOT LIKE 'TEST%'
    """)

    precios_antes = {row[0]: row[2] for row in cursor.fetchall()}
    conn.close()

    # Ejecutar ajuste (sin dry-run)
    print("\n💰 Ajustando precios de catálogo...")
    adjust_catalog_prices(dry_run=False)

    # Ver qué cambió
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT asin, precio_original, precio_actual, costo_amazon
        FROM listings
        WHERE es_catalogo = 1 AND asin NOT LIKE 'TEST%'
    """)

    productos_despues = cursor.fetchall()
    conn.close()

    ajustados = 0
    no_rentables = 0

    for asin, precio_original, precio_actual, costo_amazon in productos_despues:
        precio_anterior = precios_antes.get(asin, precio_original)

        if abs(precio_actual - precio_anterior) > 0.01:
            # Precio cambió
            ajustados += 1

            # Calcular margen
            if costo_amazon:
                costo_real = costo_amazon * 1.07
                margen = ((precio_actual / costo_real) - 1) * 100
            else:
                margen = 0

            razon = "Ajuste competitivo" if precio_actual < precio_original else "Precio no rentable, mantiene original"

            if precio_actual >= precio_original:
                no_rentables += 1

            # Notificar
            notify_price_adjusted(asin, precio_original, precio_actual, razon, margen)

    return ajustados, no_rentables


def run_monitor():
    """Ejecuta una ronda completa de monitoreo y ajuste"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"🔍 MONITOR DE PRECIOS DE CATÁLOGO")
    print(f"   {timestamp}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Paso 1: Detectar nuevos catálogos
    catalogos_nuevos = check_and_mark_catalogs()

    # Paso 2: Ajustar precios
    precios_ajustados, no_rentables = adjust_and_notify()

    # Resumen
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("📊 RESUMEN:")
    print(f"   🏷️  Nuevos catálogos: {catalogos_nuevos}")
    print(f"   💰 Precios ajustados: {precios_ajustados}")
    print(f"   🚨 No rentables: {no_rentables}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    # Notificar resumen
    notify_summary(catalogos_nuevos, precios_ajustados, no_rentables)


def run_loop():
    """Ejecuta el monitor en loop cada 6 horas"""
    print("🔄 Iniciando monitor en loop (cada 6 horas)...")
    print("   Presiona Ctrl+C para detener\n")

    while True:
        try:
            run_monitor()

            next_run = datetime.now().timestamp() + 21600  # 6 horas
            next_run_str = datetime.fromtimestamp(next_run).strftime("%Y-%m-%d %H:%M:%S")

            print(f"⏰ Próxima ejecución: {next_run_str}")
            print("   (Esperando 6 horas...)\n")

            time.sleep(21600)  # 6 horas

        except KeyboardInterrupt:
            print("\n\n🛑 Monitor detenido por el usuario")
            break
        except Exception as e:
            print(f"\n❌ Error en el monitor: {e}")
            print("   Reintentando en 5 minutos...\n")
            time.sleep(300)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor de precios de catálogo")
    parser.add_argument("--loop", action="store_true", help="Ejecutar en loop cada 6 horas")
    parser.add_argument("--test", action="store_true", help="Ejecutar una vez inmediatamente")

    args = parser.parse_args()

    if args.loop:
        run_loop()
    else:
        run_monitor()
