#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backfill_sales_costs.py
═══════════════════════════════════════════════════════════════════════════════
ACTUALIZAR COSTOS DE VENTAS EXISTENTES
═══════════════════════════════════════════════════════════════════════════════

Actualiza las ventas en la DB que no tienen amazon_cost usando Glow API en tiempo real.

USO:
    python3 scripts/tools/backfill_sales_costs.py              # Ver ventas sin costo
    python3 scripts/tools/backfill_sales_costs.py --update     # Actualizar ventas
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(override=True)

from src.integrations.amazon_glow_api import check_real_availability_glow_api

# Configuración
DB_PATH = "storage/sales_tracking.db"
TAX_RATE = 0.00  # Tax exception
FULFILLMENT_FEE = 4.0

# Colores
class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'


def get_sales_without_cost():
    """Obtiene ventas que no tienen amazon_cost"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, order_id, asin, product_title, sale_price_usd, net_proceeds,
               amazon_cost, total_cost, profit
        FROM sales
        WHERE (amazon_cost IS NULL OR amazon_cost = 0)
          AND asin IS NOT NULL
          AND asin != ''
        ORDER BY sale_date DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def update_sale_cost(sale_id, amazon_cost, net_proceeds):
    """
    Actualiza el costo de Amazon y recalcula ganancia de una venta

    Args:
        sale_id: ID de la venta
        amazon_cost: Costo de Amazon obtenido
        net_proceeds: Ingresos netos de ML
    """
    # Calcular costos y ganancia
    amazon_tax = round(amazon_cost * TAX_RATE, 2)
    total_cost = round(amazon_cost + amazon_tax + FULFILLMENT_FEE, 2)
    profit = round(net_proceeds - total_cost, 2)

    # Calcular margen (profit / sale_price)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT sale_price_usd FROM sales WHERE id = ?", (sale_id,))
    row = cursor.fetchone()
    sale_price = row[0] if row else 0

    profit_margin = 0
    if sale_price > 0:
        profit_margin = round((profit / sale_price) * 100, 2)

    # Actualizar en DB
    cursor.execute("""
        UPDATE sales
        SET amazon_cost = ?,
            amazon_tax = ?,
            total_cost = ?,
            profit = ?,
            profit_margin = ?,
            last_updated = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (amazon_cost, amazon_tax, total_cost, profit, profit_margin, sale_id))

    conn.commit()
    conn.close()

    return {
        "amazon_cost": amazon_cost,
        "total_cost": total_cost,
        "profit": profit,
        "profit_margin": profit_margin
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Actualizar costos de ventas")
    parser.add_argument("--update", action="store_true", help="Actualizar ventas (default: solo mostrar)")
    args = parser.parse_args()

    print(f"\n{Colors.BLUE}{'═' * 80}{Colors.NC}")
    print(f"{Colors.BLUE}BACKFILL DE COSTOS DE VENTAS{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 80}{Colors.NC}\n")

    # Obtener ventas sin costo
    sales = get_sales_without_cost()

    if not sales:
        print(f"{Colors.GREEN}✅ Todas las ventas tienen costos actualizados{Colors.NC}\n")
        return

    print(f"{Colors.CYAN}📊 Encontradas {len(sales)} ventas sin costo de Amazon{Colors.NC}\n")

    if not args.update:
        # Solo mostrar
        print(f"{Colors.YELLOW}VENTAS SIN COSTO:{Colors.NC}\n")
        for i, sale in enumerate(sales[:10], 1):  # Mostrar primeras 10
            print(f"{i}. {sale['product_title'][:50]}")
            print(f"   Order: {sale['order_id']}")
            print(f"   ASIN: {sale['asin']}")
            print(f"   Precio venta: ${sale['sale_price_usd']}")
            print(f"   Neto ML: ${sale['net_proceeds']}")
            print(f"   {Colors.RED}Amazon cost: ${sale['amazon_cost'] or 0}{Colors.NC}")
            print()

        if len(sales) > 10:
            print(f"   ... y {len(sales) - 10} más\n")

        print(f"{Colors.CYAN}💡 Para actualizar con Glow API:{Colors.NC}")
        print(f"   python3 scripts/tools/backfill_sales_costs.py --update\n")
        return

    # Actualizar con Glow API
    print(f"{Colors.CYAN}🔄 Actualizando costos con Glow API...{Colors.NC}\n")

    updated = 0
    failed = 0

    for i, sale in enumerate(sales, 1):
        asin = sale['asin']
        sale_id = sale['id']

        print(f"{Colors.BLUE}[{i}/{len(sales)}]{Colors.NC} {sale['product_title'][:50]}...")
        print(f"   ASIN: {asin}")

        try:
            # Obtener precio de Glow API
            print(f"   🔄 Consultando Glow API...")
            glow_data = check_real_availability_glow_api(asin)

            amazon_cost = 0
            if glow_data and glow_data.get("price"):
                amazon_cost = glow_data["price"]
                print(f"   {Colors.GREEN}✅ Precio de Glow API: ${amazon_cost}{Colors.NC}")

            # Fallback: amazon_price_last de listings DB
            if amazon_cost == 0:
                print(f"   {Colors.CYAN}📋 Glow API falló, buscando en DB...{Colors.NC}")
                try:
                    conn_listings = sqlite3.connect("storage/listings_database.db", timeout=10)
                    cursor_listings = conn_listings.cursor()
                    cursor_listings.execute("SELECT amazon_price_last FROM listings WHERE asin = ?", (asin,))
                    price_row = cursor_listings.fetchone()
                    conn_listings.close()

                    if price_row and price_row[0]:
                        amazon_cost = price_row[0]
                        print(f"   {Colors.GREEN}💲 Precio desde DB (amazon_price_last): ${amazon_cost}{Colors.NC}")
                except Exception as e:
                    print(f"   {Colors.YELLOW}⚠️  Error leyendo DB: {e}{Colors.NC}")

            if amazon_cost > 0:
                # Actualizar en DB
                result = update_sale_cost(sale_id, amazon_cost, sale['net_proceeds'])

                print(f"   💰 Ganancia: ${result['profit']} ({result['profit_margin']}%)")
                print(f"   {Colors.GREEN}✅ Actualizado{Colors.NC}\n")

                updated += 1
            else:
                print(f"   {Colors.YELLOW}⚠️  No se pudo obtener precio de ninguna fuente{Colors.NC}\n")
                failed += 1

        except Exception as e:
            print(f"   {Colors.RED}❌ Error: {e}{Colors.NC}\n")
            failed += 1

    # Resumen
    print(f"\n{Colors.BLUE}{'═' * 80}{Colors.NC}")
    print(f"{Colors.GREEN}✅ Actualizadas: {updated}{Colors.NC}")
    if failed > 0:
        print(f"{Colors.YELLOW}⚠️  Fallidas: {failed}{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 80}{Colors.NC}\n")


if __name__ == "__main__":
    main()
