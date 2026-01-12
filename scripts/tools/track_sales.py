#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
track_sales.py
═══════════════════════════════════════════════════════════════════════════════
SISTEMA DE TRACKING DE VENTAS - AMAZON → MERCADOLIBRE
═══════════════════════════════════════════════════════════════════════════════

Monitorea ventas en MercadoLibre y registra:
- Datos de la orden (país, fecha, producto)
- Ingresos (precio venta - comisiones ML)
- Costos (Amazon + tax + 3PL)
- Ganancia neta y margen

USO:
    python3 scripts/tools/track_sales.py              # Revisar ventas (último día)
    python3 scripts/tools/track_sales.py --check-all  # Revisar TODAS las ventas
    python3 scripts/tools/track_sales.py --stats      # Ver estadísticas
    python3 scripts/tools/track_sales.py --export     # Exportar a Excel

WEBHOOK (opcional):
    Configurar webhook en ML para recibir notificaciones en tiempo real
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

load_dotenv(override=True)

# Configuración
DB_PATH = "storage/sales_tracking.db"
LISTINGS_DB_PATH = "storage/listings_database.db"

ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")
ML_USER_ID = os.getenv("ML_USER_ID")

# Costos fijos
TAX_RATE = 0.00  # Tax exception - sin impuestos en Florida
FULFILLMENT_FEE = 4.0

# Colores
class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'


def init_database():
    """Crea la base de datos de ventas si no existe"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            -- Identificación
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL UNIQUE,
            ml_item_id TEXT,
            asin TEXT,
            sku TEXT,

            -- Ubicación
            country TEXT,
            marketplace TEXT,
            buyer_nickname TEXT,

            -- Producto
            product_title TEXT,
            quantity INTEGER DEFAULT 1,

            -- Fechas
            sale_date DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,

            -- Financiero ML (lo que recibís)
            sale_price_usd DECIMAL(10,2),
            ml_fee DECIMAL(10,2),
            shipping_cost DECIMAL(10,2),
            ml_taxes DECIMAL(10,2),
            net_proceeds DECIMAL(10,2),

            -- Costos Amazon + 3PL
            amazon_cost DECIMAL(10,2),
            amazon_tax DECIMAL(10,2),
            fulfillment_fee DECIMAL(10,2),
            total_cost DECIMAL(10,2),

            -- Ganancia
            profit DECIMAL(10,2),
            profit_margin DECIMAL(5,2),

            -- Status
            status TEXT DEFAULT 'pending',
            tracking_number TEXT,

            -- Metadata
            raw_ml_data TEXT,
            notes TEXT
        )
    """)

    # Crear índices
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_date ON sales(sale_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_country ON sales(country)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_asin ON sales(asin)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_id ON sales(order_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON sales(status)")

    conn.commit()
    conn.close()

    print(f"{Colors.GREEN}✅ Base de datos inicializada: {DB_PATH}{Colors.NC}")


def get_ml_orders(since_date=None, get_all=False, limit_orders=None, days_back=None):
    """
    Obtiene órdenes de MercadoLibre

    Args:
        since_date: datetime - Fecha desde la cual buscar
        get_all: bool - Si es True, trae TODAS las órdenes sin filtro de fecha
        limit_orders: int - Si se especifica, limita a N órdenes (para chequeos rápidos)
        days_back: int - Días hacia atrás (default: 1 día)

    Returns:
        list: Lista de órdenes
    """
    if not get_all and not since_date:
        from datetime import timezone
        # Default: último día (para chequeos rápidos cada 1 min)
        days = days_back if days_back else 1
        since_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Recargar token FRESCO del .env (el daemon corre en loop y necesita token actualizado)
    load_dotenv(override=True)
    ml_token = os.getenv("ML_ACCESS_TOKEN")

    url = f"https://api.mercadolibre.com/marketplace/orders/search"

    headers = {
        "Authorization": f"Bearer {ml_token}"
    }

    params = {
        "seller": ML_USER_ID,
        "sort": "date_desc",
        "offset": 0,
        "limit": 50
    }

    # Agregar filtro de fecha si corresponde
    if not get_all and since_date:
        # Formato: yyyy-MM-ddThh:mm:ss.ms-TZD
        params["date_created.from"] = since_date.strftime("%Y-%m-%dT%H:%M:%S-00:00")

    all_orders = []

    while True:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code != 200:
            print(f"{Colors.RED}❌ Error obteniendo órdenes: {response.status_code}{Colors.NC}")
            print(response.text)
            break

        data = response.json()
        carts = data.get("results", [])

        if not carts:
            break

        # En CBT, cada resultado es un "cart" que contiene "orders"
        for cart in carts:
            # Usar fecha del cart para filtrar (evita llamadas innecesarias)
            cart_date_str = cart.get("date_created")

            if not get_all and cart_date_str:
                cart_date = datetime.fromisoformat(cart_date_str.replace("Z", "+00:00"))
                if cart_date < since_date:
                    return all_orders  # Ya llegamos a carts más viejos, salir

            # Obtener pack_id del cart
            pack_id = cart.get("id")
            orders = cart.get("orders", [])

            for order in orders:
                order_id = order.get("id")

                # Obtener detalles completos (necesario para status y datos financieros)
                order_url = f"https://api.mercadolibre.com/marketplace/orders/{order_id}"
                order_resp = requests.get(order_url, headers=headers, timeout=10)

                if order_resp.status_code == 200:
                    full_order = order_resp.json()

                    # AGREGAR pack_id a la orden (necesario para agrupar packs)
                    full_order["pack_id"] = pack_id

                    # Filtrar por fecha de la orden individual (más preciso)
                    if not get_all:
                        order_date = datetime.fromisoformat(full_order["date_created"].replace("Z", "+00:00"))
                        if order_date < since_date:
                            continue  # Saltar esta orden vieja

                    all_orders.append(full_order)

                    # Si hay límite de órdenes, salir cuando lo alcancemos
                    if limit_orders and len(all_orders) >= limit_orders:
                        return all_orders

        # Paginación
        params["offset"] += params["limit"]

        # Límite de seguridad (solo si no estamos trayendo todas)
        if not get_all and params["offset"] >= 200:
            break

        # Si hay límite de órdenes y ya lo alcanzamos, salir
        if limit_orders and len(all_orders) >= limit_orders:
            break

    return all_orders


def find_global_item_id(ml_item_id):
    """
    Encuentra el item ID global (CBT principal) desde un item de variante

    Args:
        ml_item_id: ID del item (puede ser variante o principal)

    Returns:
        str: Item ID global o el mismo ID si no se encuentra
    """
    try:
        # Recargar token FRESCO
        load_dotenv(override=True)
        ml_token = os.getenv("ML_ACCESS_TOKEN")

        # Consultar ML API para obtener info del item
        url = f"https://api.mercadolibre.com/items/{ml_item_id}"
        headers = {"Authorization": f"Bearer {ml_token}"}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return ml_item_id

        item_data = response.json()
        catalog_product_id = item_data.get("catalog_product_id")

        if not catalog_product_id:
            return ml_item_id

        # Buscar todos los items con ese catalog_product_id en nuestra DB
        conn = sqlite3.connect(LISTINGS_DB_PATH, timeout=10)
        cursor = conn.cursor()

        # Buscar en site_items JSON para encontrar match
        cursor.execute("SELECT item_id, site_items FROM listings")
        rows = cursor.fetchall()
        conn.close()

        # Intentar encontrar un item que exista en nuestra DB
        for row in rows:
            item_id = row[0]
            site_items_json = row[1]

            if site_items_json:
                try:
                    site_items = json.loads(site_items_json)
                    # Verificar si alguno de los site_items coincide con el ml_item_id buscado
                    for site_item in site_items:
                        if site_item.get("item_id") == ml_item_id:
                            # Encontramos el item global que contiene esta variante
                            print(f"{Colors.GREEN}   ✅ Encontrado item global: {item_id} (variante: {ml_item_id}){Colors.NC}")

                            # Guardar variante en DB clonando el item global
                            try:
                                conn_save = sqlite3.connect(LISTINGS_DB_PATH, timeout=10)
                                cursor_save = conn_save.cursor()

                                # Copiar todos los datos del item global
                                cursor_save.execute("""
                                    INSERT OR IGNORE INTO listings
                                    (item_id, asin, title, description, brand, model, category_id, category_name,
                                     price_usd, length_cm, width_cm, height_cm, weight_kg, images_urls, attributes,
                                     main_features, marketplaces, site_items, date_published, date_updated,
                                     amazon_price_last, costo_amazon)
                                    SELECT ?, asin, title, description, brand, model, category_id, category_name,
                                           price_usd, length_cm, width_cm, height_cm, weight_kg, images_urls, attributes,
                                           main_features, marketplaces, site_items, datetime('now'), datetime('now'),
                                           amazon_price_last, costo_amazon
                                    FROM listings WHERE item_id = ?
                                """, (ml_item_id, item_id))

                                conn_save.commit()
                                conn_save.close()

                                if cursor_save.rowcount > 0:
                                    print(f"{Colors.GREEN}   💾 Variante {ml_item_id} guardada en DB{Colors.NC}")
                            except Exception as e:
                                print(f"{Colors.YELLOW}   ⚠️ Error guardando variante en DB: {e}{Colors.NC}")

                            return item_id
                except:
                    pass

        # Si no encontramos nada, devolver el original
        return ml_item_id

    except Exception as e:
        print(f"{Colors.YELLOW}   ⚠️ Error buscando item global: {e}{Colors.NC}")
        return ml_item_id


def get_asin_from_ml_api(ml_item_id):
    """
    Obtiene el ASIN directamente de la API de MercadoLibre leyendo el atributo SELLER_SKU

    Args:
        ml_item_id: ID del item en ML (ej: CBT123...)

    Returns:
        tuple: (asin, title) o (None, None) si no se encuentra
    """
    try:
        # Recargar token FRESCO
        load_dotenv(override=True)
        ml_token = os.getenv("ML_ACCESS_TOKEN")

        url = f"https://api.mercadolibre.com/items/{ml_item_id}"
        headers = {"Authorization": f"Bearer {ml_token}"}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"{Colors.RED}   ❌ Error consultando ML API: {response.status_code}{Colors.NC}")
            return None, None

        item_data = response.json()
        title = item_data.get("title", "Unknown")

        # Buscar ASIN en el atributo SELLER_SKU
        asin = None
        for attr in item_data.get("attributes", []):
            if attr.get("id") == "SELLER_SKU":
                asin = attr.get("value_name")
                break

        if asin:
            print(f"{Colors.GREEN}   ✅ ASIN obtenido de ML API (SELLER_SKU): {asin}{Colors.NC}")
            return asin, title
        else:
            print(f"{Colors.RED}   ❌ No se encontró SELLER_SKU en el item {ml_item_id}{Colors.NC}")
            return None, title

    except Exception as e:
        print(f"{Colors.RED}   ❌ Error obteniendo ASIN de ML API: {e}{Colors.NC}")
        return None, None


def get_item_data_from_listing(ml_item_id):
    """
    Obtiene datos del producto desde la base de datos de listings

    Args:
        ml_item_id: ID del item en ML (ej: CBT123...)

    Returns:
        dict: {asin, amazon_cost, title} o None
    """
    try:
        # Primero intentar con el ID directo
        conn = sqlite3.connect(LISTINGS_DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT asin, title
            FROM listings
            WHERE item_id = ?
        """, (ml_item_id,))

        row = cursor.fetchone()

        # Si no se encuentra, intentar buscar el item global
        if not row:
            conn.close()
            print(f"{Colors.YELLOW}   ⚠️ Item {ml_item_id} no encontrado en DB, buscando item global...{Colors.NC}")
            global_item_id = find_global_item_id(ml_item_id)

            if global_item_id != ml_item_id:
                # Reintentar con el item global
                conn = sqlite3.connect(LISTINGS_DB_PATH, timeout=10)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT asin, title
                    FROM listings
                    WHERE item_id = ?
                """, (global_item_id,))
                row = cursor.fetchone()

        conn.close()

        # Si aún no se encuentra, obtener ASIN directamente de ML API (SELLER_SKU)
        if not row:
            print(f"{Colors.YELLOW}   ⚠️ Item no encontrado en DB, consultando ML API para obtener SELLER_SKU...{Colors.NC}")
            asin, title = get_asin_from_ml_api(ml_item_id)
            if not asin:
                return None
        else:
            asin = row["asin"]
            title = row["title"]

        # Obtener precio de Amazon en TIEMPO REAL desde Glow API
        amazon_cost = 0
        if asin:
            print(f"{Colors.CYAN}   🔄 Obteniendo precio en tiempo real de Glow API...{Colors.NC}")
            try:
                # Importar función de Glow API
                import sys
                sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                from src.integrations.amazon_glow_api import check_real_availability_glow_api

                # Obtener precio actual de Amazon con Glow API
                glow_data = check_real_availability_glow_api(asin)
                if glow_data and glow_data.get("price"):
                    amazon_cost = glow_data["price"]
                    print(f"{Colors.GREEN}   ✅ Precio de Glow API: ${amazon_cost}{Colors.NC}")
                else:
                    print(f"{Colors.YELLOW}   ⚠️ Glow API no devolvió precio, usando fallback...{Colors.NC}")
            except Exception as e:
                print(f"{Colors.YELLOW}   ⚠️ Error con Glow API: {e}{Colors.NC}")

            # Fallback 1: amazon_price_last de la base de datos
            if amazon_cost == 0:
                print(f"{Colors.CYAN}   📋 Buscando último precio conocido en DB...{Colors.NC}")
                try:
                    conn_db = sqlite3.connect(LISTINGS_DB_PATH, timeout=10)
                    cursor_db = conn_db.cursor()
                    cursor_db.execute("SELECT amazon_price_last FROM listings WHERE asin = ?", (asin,))
                    price_row = cursor_db.fetchone()
                    conn_db.close()

                    if price_row and price_row[0]:
                        amazon_cost = price_row[0]
                        print(f"{Colors.GREEN}   💲 Precio desde DB (amazon_price_last): ${amazon_cost}{Colors.NC}")
                except Exception as e:
                    print(f"{Colors.YELLOW}   ⚠️ Error leyendo precio de DB: {e}{Colors.NC}")

            # Fallback 2: Si aún no hay precio, intentar JSON local
            if amazon_cost == 0:
                print(f"{Colors.CYAN}   📋 Intentando obtener precio de JSON local...{Colors.NC}")
                json_file = Path(f"storage/asins_json/{asin}.json")
                if json_file.exists():
                    try:
                        with open(json_file, 'r') as f:
                            data = json.load(f)
                            amazon_cost = data.get("prime_pricing", {}).get("price", 0)
                            print(f"{Colors.GREEN}   💲 Precio desde JSON (fallback): ${amazon_cost}{Colors.NC}")
                    except Exception as e:
                        print(f"{Colors.YELLOW}   ⚠️ Error leyendo JSON: {e}{Colors.NC}")
                else:
                    print(f"{Colors.RED}   ❌ No hay precio disponible para ASIN {asin}{Colors.NC}")

        return {
            "asin": asin,
            "amazon_cost": amazon_cost,
            "title": title
        }

    except Exception as e:
        print(f"{Colors.YELLOW}⚠️  Error leyendo listings DB: {e}{Colors.NC}")
        return None


def get_order_billing(order):
    """
    Extrae la información financiera REAL de la orden de MercadoLibre

    Args:
        order: Dict con la orden completa de ML API

    Returns:
        dict: {sale_price, ml_fee, shipping_cost, taxes, net_proceeds}
    """
    try:
        # Items de la orden
        order_items = order.get("order_items", [])
        if not order_items:
            return None

        first_item = order_items[0]

        # Precio de venta (lo que pagó el cliente)
        sale_price = first_item.get("full_unit_price") or 0
        quantity = first_item.get("quantity") or 1
        total_sale_price = sale_price * quantity

        # Fee de MercadoLibre (comisión)
        sale_fee = first_item.get("sale_fee") or 0

        # Obtener shipping cost desde el endpoint de shipments
        shipping = order.get("shipping", {})
        shipping_id = shipping.get("id")
        shipping_cost = 0

        if shipping_id:
            try:
                import requests
                # Recargar token FRESCO
                load_dotenv(override=True)
                ml_token = os.getenv("ML_ACCESS_TOKEN")
                headers = {"Authorization": f"Bearer {ml_token}"}
                r = requests.get(f"https://api.mercadolibre.com/marketplace/shipments/{shipping_id}",
                               headers=headers, timeout=10)
                if r.status_code == 200:
                    shipment_data = r.json()
                    lead_time = shipment_data.get("lead_time", {})
                    shipping_cost = lead_time.get("list_cost", 0)
            except:
                pass

        # Taxes (los paga el cliente, no afectan lo que recibís)
        taxes_obj = order.get("taxes", {})
        taxes = taxes_obj.get("amount") or 0 if taxes_obj else 0

        # NET PROCEEDS - Calcular manualmente
        # = Precio de venta - Fee ML - Shipping
        net_proceeds = total_sale_price - sale_fee - shipping_cost

        return {
            "sale_price": round(total_sale_price or 0, 2),
            "ml_fee": round(sale_fee or 0, 2),
            "shipping_cost": round(shipping_cost or 0, 2),
            "taxes": round(taxes or 0, 2),
            "net_proceeds": round(net_proceeds or 0, 2)
        }

    except Exception as e:
        print(f"{Colors.YELLOW}⚠️  Error extrayendo billing info: {e}{Colors.NC}")
        return None


def process_order(order):
    """
    Procesa una orden de ML y la registra en la DB
    Si ya existe, actualiza el status (para detectar cancelaciones)

    Args:
        order: Orden de MercadoLibre API

    Returns:
        bool: True si se procesó exitosamente (nueva venta o actualización)
    """
    order_id = order["id"]

    # Status de la orden
    order_status = order.get("status", "pending")

    # Verificar si ya existe
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, status FROM sales WHERE order_id = ?", (str(order_id),))
    existing = cursor.fetchone()

    if existing:
        existing_id, existing_status = existing

        # Si el status cambió, actualizar el registro
        if existing_status != order_status:
            print(f"\n{Colors.YELLOW}⚠️  CAMBIO DE STATUS DETECTADO{Colors.NC}")
            print(f"   Orden:        {order_id}")
            print(f"   Status prev:  {existing_status}")
            print(f"   Status nuevo: {order_status}")

            # Actualizar status y timestamp
            cursor.execute("""
                UPDATE sales
                SET status = ?,
                    last_updated = CURRENT_TIMESTAMP,
                    raw_ml_data = ?
                WHERE order_id = ?
            """, (order_status, json.dumps(order), str(order_id)))

            conn.commit()

            # Si fue cancelada, ajustar las estadísticas
            if order_status == "cancelled":
                print(f"{Colors.RED}   ❌ VENTA CANCELADA{Colors.NC}")
                # Marcar profit como 0 para que no cuente en estadísticas
                cursor.execute("""
                    UPDATE sales
                    SET profit = 0,
                        profit_margin = 0,
                        notes = 'Cancelada por el comprador'
                    WHERE order_id = ?
                """, (str(order_id),))
                conn.commit()

            # Si fue entregada, registrar la entrega
            elif order_status == "delivered":
                print(f"{Colors.GREEN}   ✅ VENTA ENTREGADA{Colors.NC}")
                # Actualizar nota
                cursor.execute("""
                    UPDATE sales
                    SET notes = 'Entregada al comprador'
                    WHERE order_id = ?
                """, (str(order_id),))
                conn.commit()

            conn.close()
            return True  # Se actualizó

        conn.close()
        return False  # Ya existe y no cambió

    # Extraer datos de la orden
    order_items = order.get("order_items", [])
    if not order_items:
        conn.close()
        return False

    # Por ahora procesamos solo el primer item
    # TODO: Manejar órdenes con múltiples items
    item = order_items[0]["item"]
    order_item = order_items[0]

    ml_item_id = item.get("id")  # ID local del marketplace (MLM, MLU, etc.)
    parent_item_id = item.get("parent_item_id")  # ID de CBT (CBT...)
    product_title = item.get("title", "Unknown")
    quantity = order_item.get("quantity", 1)

    # Obtener ASIN y precio de Amazon desde listings DB usando parent_item_id (CBT)
    listing_data = get_item_data_from_listing(parent_item_id if parent_item_id else ml_item_id)

    asin = None
    amazon_cost = None

    if listing_data:
        asin = listing_data["asin"]
        # Intentar obtener precio en tiempo real con Glow API
        if asin:
            print(f"{Colors.CYAN}   🔄 Obteniendo precio en tiempo real de Glow API...{Colors.NC}")
            try:
                # Importar función de Glow API
                sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                from src.integrations.amazon_glow_api import check_real_availability_glow_api

                # Obtener precio actual de Amazon con Glow API
                glow_data = check_real_availability_glow_api(asin)
                if glow_data and glow_data.get("price"):
                    amazon_cost = glow_data["price"]
                    print(f"{Colors.GREEN}   ✅ Precio de Glow API: ${amazon_cost}{Colors.NC}")
                else:
                    print(f"{Colors.YELLOW}   ⚠️  Glow API no devolvió precio, usando fallback...{Colors.NC}")
                    # Fallback: usar precio del JSON si existe
                    amazon_cost = listing_data["amazon_cost"]
            except Exception as e:
                print(f"{Colors.YELLOW}   ⚠️  Error con Glow API: {e}, usando fallback{Colors.NC}")
                # Fallback: usar precio del JSON
                amazon_cost = listing_data["amazon_cost"]
        else:
            # No hay ASIN, usar lo que venga del listing
            amazon_cost = listing_data["amazon_cost"]
    else:
        # Si no se encontró en listings DB, intentar obtener ASIN directamente de ML API
        print(f"{Colors.YELLOW}   ⚠️ Item no encontrado en DB, consultando ML API...{Colors.NC}")
        asin_from_api, title_from_api = get_asin_from_ml_api(parent_item_id if parent_item_id else ml_item_id)

        if asin_from_api:
            asin = asin_from_api
            print(f"{Colors.GREEN}   ✅ ASIN obtenido de ML API: {asin}{Colors.NC}")

            # Obtener precio de Glow API
            print(f"{Colors.CYAN}   🔄 Obteniendo precio de Glow API...{Colors.NC}")
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                from src.integrations.amazon_glow_api import check_real_availability_glow_api

                glow_data = check_real_availability_glow_api(asin)
                if glow_data and glow_data.get("price"):
                    amazon_cost = glow_data["price"]
                    print(f"{Colors.GREEN}   ✅ Precio de Glow API: ${amazon_cost}{Colors.NC}")
            except Exception as e:
                print(f"{Colors.YELLOW}   ⚠️ Error con Glow API: {e}{Colors.NC}")
                amazon_cost = 0
        else:
            print(f"{Colors.RED}   ❌ No se pudo obtener ASIN para este item{Colors.NC}")

    # Datos del comprador
    buyer = order.get("buyer", {})
    buyer_nickname = buyer.get("nickname", "Unknown")

    # País y marketplace desde context (CBT)
    context = order.get("context", {})
    marketplace = context.get("site", "MLU")  # MLM, MLU, MLB, MLC, MLA, etc.

    # Mapeo de marketplace a país
    country_map = {
        "MLM": "Mexico",
        "MLU": "Uruguay",
        "MLB": "Brazil",
        "MLC": "Chile",
        "MLA": "Argentina",
        "CBT": "US"
    }
    country = country_map.get(marketplace, "Unknown")

    # Fecha de venta
    sale_date = order.get("date_created")

    # Status
    status = order.get("status", "pending")

    # Obtener información financiera REAL desde la orden
    print(f"{Colors.CYAN}   📊 Extrayendo datos financieros de la orden...{Colors.NC}")
    ml_finances = get_order_billing(order)

    if not ml_finances:
        print(f"{Colors.YELLOW}   ⚠️  No se pudo obtener billing info, saltando orden{Colors.NC}")
        conn.close()
        return False

    # Calcular costos Amazon + 3PL
    amazon_tax = 0
    total_cost = 0
    profit = 0
    profit_margin = 0

    if amazon_cost:
        # Multiplicar amazon_cost por cantidad para obtener costo total
        amazon_cost_total = round(amazon_cost * quantity, 2)
        amazon_tax = round(amazon_cost_total * TAX_RATE, 2)
        total_cost = round(amazon_cost_total + amazon_tax + FULFILLMENT_FEE, 2)
        profit = round(ml_finances["net_proceeds"] - total_cost, 2)

        # Margen = ganancia sobre el costo, no sobre la venta
        if total_cost > 0:
            profit_margin = round((profit / total_cost) * 100, 2)

    # Insertar en DB
    cursor.execute("""
        INSERT INTO sales (
            order_id, ml_item_id, asin, country, marketplace,
            buyer_nickname, product_title, quantity, sale_date,
            sale_price_usd, ml_fee, shipping_cost, ml_taxes, net_proceeds,
            amazon_cost, amazon_tax, fulfillment_fee, total_cost,
            profit, profit_margin, status, raw_ml_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(order_id),
        parent_item_id if parent_item_id else ml_item_id,  # Usar CBT ID si existe
        asin,
        country,
        marketplace,
        buyer_nickname, product_title, quantity, sale_date,
        ml_finances["sale_price"], ml_finances["ml_fee"],
        ml_finances["shipping_cost"], ml_finances["taxes"], ml_finances["net_proceeds"],
        amazon_cost, amazon_tax, FULFILLMENT_FEE, total_cost,
        profit, profit_margin, status, json.dumps(order)
    ))

    conn.commit()
    conn.close()

    # Log
    print(f"\n{Colors.GREEN}✅ NUEVA VENTA REGISTRADA{Colors.NC}")
    print(f"   Orden:         {order_id}")
    print(f"   Producto:      {product_title[:50]}...")
    print(f"   ASIN:          {asin or 'N/A'}")
    print(f"   Comprador:     {buyer_nickname}")
    print(f"   Cantidad:      {quantity}")
    print()
    print(f"   {Colors.YELLOW}💵 INGRESOS ML:{Colors.NC}")
    print(f"      Precio venta:     ${ml_finances['sale_price']}")
    print(f"      - Fee ML:         -${ml_finances['ml_fee']}")
    print(f"      - Envío:          -${ml_finances['shipping_cost']}")
    print(f"      - Impuestos ML:   -${ml_finances['taxes']}")
    print(f"      = Neto ML:        ${ml_finances['net_proceeds']}")
    print()
    print(f"   {Colors.RED}💸 COSTOS:{Colors.NC}")
    print(f"      Amazon:           -${amazon_cost or 0}")
    print(f"      Tax 7%:           -${amazon_tax}")
    print(f"      3PL:              -${FULFILLMENT_FEE}")
    print(f"      = Total costo:    -${total_cost}")
    print()
    print(f"   {Colors.CYAN}💰 GANANCIA NETA:  ${profit} ({profit_margin}%){Colors.NC}")

    return True


def process_pack(pack_orders):
    """
    Procesa un pack de órdenes (1 o más) con shipping distribuido proporcionalmente.

    Args:
        pack_orders: Lista de órdenes del mismo pack

    Returns:
        bool: True si se procesó exitosamente al menos una orden
    """
    if not pack_orders:
        return False

    # Obtener shipping cost UNA SOLA VEZ (es compartido para todo el pack)
    first_order = pack_orders[0]
    shipping = first_order.get("shipping", {})
    shipping_id = shipping.get("id")
    total_shipping_cost = 0

    if shipping_id:
        try:
            load_dotenv(override=True)
            ml_token = os.getenv("ML_ACCESS_TOKEN")
            headers = {"Authorization": f"Bearer {ml_token}"}
            r = requests.get(f"https://api.mercadolibre.com/marketplace/shipments/{shipping_id}",
                           headers=headers, timeout=10)
            if r.status_code == 200:
                shipment_data = r.json()
                lead_time = shipment_data.get("lead_time", {})
                total_shipping_cost = lead_time.get("list_cost", 0)
        except:
            pass

    # Calcular el total de unit_price de todos los items (para distribuir shipping proporcionalmente)
    total_unit_price = sum(
        order.get("order_items", [{}])[0].get("unit_price", 0)
        for order in pack_orders
    )

    # Procesar cada orden del pack con su parte proporcional del shipping
    success = False
    for order in pack_orders:
        order_items = order.get("order_items", [])
        if not order_items:
            continue

        unit_price = order_items[0].get("unit_price", 0)

        # Calcular la porción de shipping que le corresponde a este item
        if total_unit_price > 0:
            item_shipping_share = (unit_price / total_unit_price) * total_shipping_cost
        else:
            item_shipping_share = 0

        # Procesar la orden con su shipping proporcional
        if process_order_with_shipping(order, item_shipping_share):
            success = True

    return success


def process_order_with_shipping(order, shipping_cost_override):
    """
    Procesa una orden con un shipping_cost específico (para packs con shipping distribuido).

    Args:
        order: Orden de MercadoLibre API
        shipping_cost_override: Costo de shipping a usar (ya calculado proporcionalmente)

    Returns:
        bool: True si se procesó exitosamente
    """
    order_id = order["id"]
    order_status = order.get("status", "pending")

    # Verificar si ya existe
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, status FROM sales WHERE order_id = ?", (str(order_id),))
    existing = cursor.fetchone()

    if existing:
        existing_id, existing_status = existing

        # Si el status cambió, actualizar el registro
        if existing_status != order_status:
            print(f"\n{Colors.YELLOW}⚠️  CAMBIO DE STATUS DETECTADO{Colors.NC}")
            print(f"   Orden:        {order_id}")
            print(f"   Status prev:  {existing_status}")
            print(f"   Status nuevo: {order_status}")

            cursor.execute("""
                UPDATE sales
                SET status = ?,
                    last_updated = CURRENT_TIMESTAMP,
                    raw_ml_data = ?
                WHERE order_id = ?
            """, (order_status, json.dumps(order), str(order_id)))

            conn.commit()

            if order_status == "cancelled":
                print(f"{Colors.RED}   ❌ VENTA CANCELADA{Colors.NC}")
                cursor.execute("""
                    UPDATE sales
                    SET profit = 0,
                        profit_margin = 0,
                        notes = 'Cancelada por el comprador'
                    WHERE order_id = ?
                """, (str(order_id),))
                conn.commit()

            conn.close()
            return True

        # Ya existe y no cambió - saltar
        conn.close()
        return False

    # Nueva venta - procesar
    order_items = order.get("order_items", [])
    if not order_items:
        conn.close()
        return False

    first_item = order_items[0]
    item = first_item.get("item", {})

    ml_item_id = item.get("id")
    parent_item_id = item.get("parent_item_id")
    title = item.get("title", "Unknown")
    quantity = first_item.get("quantity", 1)

    # Obtener marketplace
    context = order.get("context", {})
    marketplace = context.get("site", "MLU")

    # Buyer
    buyer = order.get("buyer", {})
    buyer_nickname = buyer.get("nickname", "Unknown")

    # Financiero
    unit_price = first_item.get("unit_price", 0)
    sale_fee = first_item.get("sale_fee", 0)

    # Usar el shipping_cost que ya viene calculado proporcionalmente
    # NET PROCEEDS = unit_price - sale_fee - shipping_cost_proporcional
    net_proceeds = (unit_price * quantity) - (sale_fee * quantity) - shipping_cost_override

    # Buscar ASIN y costo de Amazon
    asin = None
    amazon_cost = 0

    if parent_item_id:
        asin_data = get_asin_info(parent_item_id)
        if asin_data:
            asin = asin_data.get("asin")
            amazon_cost = asin_data.get("amazon_cost", 0)

    if not asin and ml_item_id:
        asin_data = get_asin_info(ml_item_id)
        if asin_data:
            asin = asin_data.get("asin")
            amazon_cost = asin_data.get("amazon_cost", 0)

    # Calcular profit
    total_amazon_cost = (amazon_cost + FULFILLMENT_FEE) * quantity
    profit = net_proceeds - total_amazon_cost
    profit_margin = (profit / total_amazon_cost * 100) if total_amazon_cost > 0 else 0

    # Guardar en DB
    try:
        cursor.execute("""
            INSERT INTO sales (
                order_id, ml_item_id, asin, country, marketplace,
                buyer_nickname, product_title, quantity, sale_date,
                sale_price_usd, ml_fee, shipping_cost, net_proceeds,
                amazon_cost, fulfillment_fee, total_cost,
                profit, profit_margin, status, raw_ml_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(order_id),
            ml_item_id,
            asin,
            marketplace[:2],
            marketplace,
            buyer_nickname,
            title,
            quantity,
            order.get("date_created"),
            round(unit_price * quantity, 2),
            round(sale_fee * quantity, 2),
            round(shipping_cost_override, 2),
            round(net_proceeds, 2),
            round(amazon_cost, 2),
            round(FULFILLMENT_FEE, 2),
            round(total_amazon_cost, 2),
            round(profit, 2),
            round(profit_margin, 2),
            order_status,
            json.dumps(order)
        ))

        conn.commit()
        conn.close()

        print(f"\n{Colors.GREEN}✅ NUEVA VENTA REGISTRADA{Colors.NC}")
        print(f"   Orden: {order_id}")
        print(f"   ASIN: {asin}")
        print(f"   Producto: {title[:50]}")
        print(f"   Cantidad: {quantity}")
        print(f"   Net proceeds: ${net_proceeds:.2f}")
        print(f"   Shipping (proporcional): ${shipping_cost_override:.2f}")
        print(f"   Profit: ${profit:.2f} ({profit_margin:.1f}%)")

        return True

    except Exception as e:
        print(f"{Colors.RED}❌ Error guardando venta: {e}{Colors.NC}")
        conn.close()
        return False


def track_new_sales(check_all=False, days_back=1, limit_orders=None):
    """
    Revisa y registra nuevas ventas

    Args:
        check_all: bool - Si es True, revisa todas las ventas históricas
        days_back: int - Cuántos días hacia atrás revisar (default: 1 día)
        limit_orders: int - Si se especifica, limita a N órdenes más recientes

    Returns:
        int: Número de ventas nuevas registradas o actualizadas
    """
    print(f"\n{Colors.BLUE}{'═' * 80}{Colors.NC}")
    if check_all:
        print(f"{Colors.BLUE}TRACKING DE VENTAS - TODAS LAS ÓRDENES{Colors.NC}")
    elif limit_orders:
        print(f"{Colors.BLUE}TRACKING DE VENTAS - ÚLTIMAS {limit_orders} ÓRDENES (RÁPIDO){Colors.NC}")
    else:
        print(f"{Colors.BLUE}TRACKING DE VENTAS - ÚLTIMOS {days_back} DÍA(S){Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 80}{Colors.NC}\n")

    # Obtener órdenes
    print(f"{Colors.CYAN}📡 Obteniendo órdenes de MercadoLibre...{Colors.NC}")
    orders = get_ml_orders(get_all=check_all, days_back=days_back, limit_orders=limit_orders)

    print(f"   Encontradas: {len(orders)} órdenes\n")

    if not orders:
        print(f"{Colors.YELLOW}⚠️  No hay nuevas órdenes{Colors.NC}")
        return 0

    # AGRUPAR ÓRDENES POR PACK_ID (para manejar packs con múltiples items)
    packs = {}
    for order in orders:
        pack_id = str(order.get("pack_id", order.get("id")))
        if pack_id not in packs:
            packs[pack_id] = []
        packs[pack_id].append(order)

    # Procesar cada pack (puede tener 1 o más órdenes)
    changes = 0  # Cuenta nuevas ventas Y actualizaciones (cancelaciones)
    for pack_id, pack_orders in packs.items():
        # Procesar el pack completo (distribuye shipping entre items)
        if process_pack(pack_orders):
            changes += len(pack_orders)  # Contar cada orden del pack

    print(f"\n{Colors.GREEN}{'═' * 80}{Colors.NC}")
    print(f"{Colors.GREEN}✅ Procesamiento completado: {changes} cambio(s) detectado(s){Colors.NC}")
    print(f"{Colors.GREEN}{'═' * 80}{Colors.NC}\n")

    return changes


def show_stats():
    """Muestra estadísticas de ventas"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Stats generales (excluyendo canceladas)
    cursor.execute("""
        SELECT
            COUNT(*) as total_sales,
            SUM(quantity) as total_units,
            SUM(sale_price_usd) as total_revenue,
            SUM(profit) as total_profit,
            AVG(profit_margin) as avg_margin
        FROM sales
        WHERE status != 'cancelled'
    """)

    stats = cursor.fetchone()

    print(f"\n{Colors.BLUE}{'═' * 80}{Colors.NC}")
    print(f"{Colors.BLUE}📊 ESTADÍSTICAS DE VENTAS{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 80}{Colors.NC}\n")

    if stats['total_sales'] == 0:
        print(f"{Colors.YELLOW}   ⚠️  No hay ventas registradas aún{Colors.NC}")
        print(f"\n{Colors.CYAN}   💡 Ejecuta: python3 17_track_sales.py{Colors.NC}")
        print(f"{Colors.CYAN}      para revisar nuevas ventas{Colors.NC}\n")
        conn.close()
        return

    print(f"   Total ventas:       {stats['total_sales']}")
    print(f"   Total unidades:     {stats['total_units'] or 0}")
    print(f"   Revenue total:      ${stats['total_revenue'] or 0:.2f}")
    print(f"   {Colors.GREEN}Ganancia total:     ${stats['total_profit'] or 0:.2f}{Colors.NC}")
    print(f"   Margen promedio:    {stats['avg_margin'] or 0:.1f}%")

    # Top productos (excluyendo canceladas)
    print(f"\n{Colors.CYAN}🏆 TOP 5 PRODUCTOS MÁS VENDIDOS:{Colors.NC}\n")

    cursor.execute("""
        SELECT
            product_title,
            asin,
            COUNT(*) as sales,
            SUM(quantity) as units,
            SUM(profit) as total_profit
        FROM sales
        WHERE status != 'cancelled'
        GROUP BY asin
        ORDER BY sales DESC
        LIMIT 5
    """)

    for i, row in enumerate(cursor.fetchall(), 1):
        print(f"   {i}. {row['product_title'][:50]}")
        print(f"      ASIN: {row['asin']} | Ventas: {row['sales']} | Ganancia: ${row['total_profit']:.2f}\n")

    conn.close()


def export_to_excel():
    """Exporta ventas a Excel"""
    try:
        import pandas as pd

        conn = sqlite3.connect(DB_PATH)

        # Leer todas las ventas
        df = pd.read_sql_query("""
            SELECT
                order_id, sale_date, country, marketplace,
                product_title, asin, quantity,
                sale_price_usd, ml_fee, net_proceeds,
                amazon_cost, amazon_tax, fulfillment_fee, total_cost,
                profit, profit_margin, status, buyer_nickname
            FROM sales
            ORDER BY sale_date DESC
        """, conn)

        conn.close()

        # Exportar
        output_file = "storage/sales_report.xlsx"
        df.to_excel(output_file, index=False, sheet_name="Sales")

        print(f"{Colors.GREEN}✅ Reporte exportado: {output_file}{Colors.NC}")
        print(f"   Total filas: {len(df)}")

    except ImportError:
        print(f"{Colors.RED}❌ Error: pandas y openpyxl requeridos{Colors.NC}")
        print(f"   Instalar: pip install pandas openpyxl")
    except Exception as e:
        print(f"{Colors.RED}❌ Error exportando: {e}{Colors.NC}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Track sales from MercadoLibre")
    parser.add_argument("--init", action="store_true", help="Initialize database")
    parser.add_argument("--backfill", action="store_true", help="Import historical sales")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--export", action="store_true", help="Export to Excel")
    parser.add_argument("--check-all", action="store_true", help="Check ALL orders (not just last 24h)")

    args = parser.parse_args()

    # Verificar configuración
    if not ML_ACCESS_TOKEN or not ML_USER_ID:
        print(f"{Colors.RED}❌ Error: ML_ACCESS_TOKEN y ML_USER_ID requeridos en .env{Colors.NC}")
        sys.exit(1)

    # Crear DB si no existe
    if not os.path.exists(DB_PATH) or args.init:
        init_database()

    if args.stats:
        show_stats()
    elif args.export:
        export_to_excel()
    elif args.backfill:
        print(f"{Colors.YELLOW}📅 Importando ventas históricas (últimos 30 días)...{Colors.NC}")
        # TODO: Implementar backfill
        print(f"{Colors.YELLOW}⚠️  Función en desarrollo{Colors.NC}")
    elif args.check_all:
        # Check ALL orders (update status for existing ones)
        track_new_sales(check_all=True)
    else:
        # Default: track new sales (last 24h only)
        track_new_sales(check_all=False)


if __name__ == "__main__":
    main()
