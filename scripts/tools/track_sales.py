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
    python3 scripts/tools/track_sales.py              # Revisar nuevas ventas
    python3 scripts/tools/track_sales.py --backfill   # Importar ventas históricas
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


def get_ml_orders(since_date=None):
    """
    Obtiene órdenes de MercadoLibre

    Args:
        since_date: datetime - Fecha desde la cual buscar (default: últimas 24h)

    Returns:
        list: Lista de órdenes
    """
    if not since_date:
        from datetime import timezone
        since_date = datetime.now(timezone.utc) - timedelta(days=1)

    url = f"https://api.mercadolibre.com/marketplace/orders/search"

    headers = {
        "Authorization": f"Bearer {ML_ACCESS_TOKEN}"
    }

    params = {
        "seller": ML_USER_ID,
        "sort": "date_desc",
        "offset": 0,
        "limit": 50
    }

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
            orders = cart.get("orders", [])
            for order in orders:
                order_id = order.get("id")

                # Obtener detalles completos de la orden
                order_url = f"https://api.mercadolibre.com/marketplace/orders/{order_id}"
                order_resp = requests.get(order_url, headers=headers, timeout=10)

                if order_resp.status_code == 200:
                    full_order = order_resp.json()

                    # Filtrar por fecha
                    order_date = datetime.fromisoformat(full_order["date_created"].replace("Z", "+00:00"))
                    if order_date >= since_date:
                        all_orders.append(full_order)
                    else:
                        return all_orders  # Ya llegamos a órdenes más viejas

        # Paginación
        params["offset"] += params["limit"]

        # Límite de seguridad
        if params["offset"] >= 200:
            break

    return all_orders


def get_item_data_from_listing(ml_item_id):
    """
    Obtiene datos del producto desde la base de datos de listings

    Args:
        ml_item_id: ID del item en ML (ej: CBT123...)

    Returns:
        dict: {asin, amazon_cost, title} o None
    """
    try:
        conn = sqlite3.connect(LISTINGS_DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT asin, title
            FROM listings
            WHERE item_id = ?
        """, (ml_item_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

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

    Args:
        order: Orden de MercadoLibre API

    Returns:
        bool: True si se procesó exitosamente
    """
    order_id = order["id"]

    # Verificar si ya existe
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM sales WHERE order_id = ?", (str(order_id),))
    if cursor.fetchone():
        conn.close()
        return False  # Ya existe

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

        if ml_finances["sale_price"] > 0:
            profit_margin = round((profit / ml_finances["sale_price"]) * 100, 2)

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


def track_new_sales():
    """Revisa y registra nuevas ventas de las últimas 24 horas"""
    print(f"\n{Colors.BLUE}{'═' * 80}{Colors.NC}")
    print(f"{Colors.BLUE}TRACKING DE VENTAS - ÚLTIMAS 24 HORAS{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 80}{Colors.NC}\n")

    # Obtener órdenes
    print(f"{Colors.CYAN}📡 Obteniendo órdenes de MercadoLibre...{Colors.NC}")
    orders = get_ml_orders()

    print(f"   Encontradas: {len(orders)} órdenes\n")

    if not orders:
        print(f"{Colors.YELLOW}⚠️  No hay nuevas órdenes{Colors.NC}")
        return

    # Procesar cada orden
    new_sales = 0
    for order in orders:
        if process_order(order):
            new_sales += 1

    print(f"\n{Colors.GREEN}{'═' * 80}{Colors.NC}")
    print(f"{Colors.GREEN}✅ Procesamiento completado: {new_sales} nuevas ventas registradas{Colors.NC}")
    print(f"{Colors.GREEN}{'═' * 80}{Colors.NC}\n")


def show_stats():
    """Muestra estadísticas de ventas"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Stats generales
    cursor.execute("""
        SELECT
            COUNT(*) as total_sales,
            SUM(quantity) as total_units,
            SUM(sale_price_usd) as total_revenue,
            SUM(profit) as total_profit,
            AVG(profit_margin) as avg_margin
        FROM sales
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

    # Top productos
    print(f"\n{Colors.CYAN}🏆 TOP 5 PRODUCTOS MÁS VENDIDOS:{Colors.NC}\n")

    cursor.execute("""
        SELECT
            product_title,
            asin,
            COUNT(*) as sales,
            SUM(quantity) as units,
            SUM(profit) as total_profit
        FROM sales
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
    else:
        # Default: track new sales
        track_new_sales()


if __name__ == "__main__":
    main()
