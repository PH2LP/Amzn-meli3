#!/usr/bin/env python3
"""
update_prices.py
═══════════════════════════════════════════════════════════════════════════════
ACTUALIZACIÓN MASIVA DE PRECIOS EN MERCADOLIBRE
═══════════════════════════════════════════════════════════════════════════════

Recalcula y actualiza TODOS los precios de tus publicaciones activas usando
el PRICE_MARKUP actual del archivo .env

EJEMPLO DE USO:
    1. Cambiar PRICE_MARKUP en .env de 35 → 40
    2. Ejecutar: python3 update_prices.py
    3. El script actualiza automáticamente todos los precios

LÓGICA DE CÁLCULO (igual que transform_mapper_new.py):
    1. precio_base (Amazon price)
    2. + tax (7% del precio base) - OPCIONAL, configurable con USE_TAX en .env
    3. + $4 USD (costo 3PL fulfillment)
    4. = costo_total
    5. costo_total * (1 + markup%) = net_proceeds → PRECIO EN ML

CONFIGURACIÓN TAX (.env):
    USE_TAX=true     Aplicar tax 7% (default)
    USE_TAX=false    NO aplicar tax (para ciertos productos)

OPCIONES:
    --dry-run         Simula cambios sin actualizar en ML
    --asin ASIN       Solo actualizar un ASIN específico
    --min-diff 5.0    Solo actualizar si diferencia > $5 USD (default: 1.0)
"""

import os
import sys
import json
import sqlite3
import requests
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.integrations.amazon_availability_scraper import validate_fast_fulfillment_scraper

# Cargar .env
load_dotenv(override=True)

# Colores
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

def log(msg, color=Colors.NC):
    print(f"{color}{msg}{Colors.NC}")

# Configuración
DB_PATH = "storage/listings_database.db"
ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
PRICE_MARKUP = float(os.getenv("PRICE_MARKUP", 35)) / 100  # 35% → 0.35
USE_TAX = os.getenv("USE_TAX", "true").lower() == "true"  # Aplicar tax por defecto
TAX_RATE = 0.07  # 7%
FULFILLMENT_FEE = 4.0  # $4 USD fijo

def compute_new_price(base_usd: float) -> dict:
    """
    Calcula precio usando la lógica actual del sistema.

    Args:
        base_usd: Precio base de Amazon

    Returns:
        dict con cálculos detallados
    """
    tax = round(base_usd * TAX_RATE, 2) if USE_TAX else 0.0
    cost = round(base_usd + tax + FULFILLMENT_FEE, 2)
    net_proceeds = round(cost * (1.0 + PRICE_MARKUP), 2)

    return {
        "base_usd": base_usd,
        "tax_usd": tax,
        "fulfillment_fee_usd": FULFILLMENT_FEE,
        "cost_usd": cost,
        "markup_pct": int(PRICE_MARKUP * 100),
        "net_proceeds_usd": net_proceeds,
        "use_tax": USE_TAX
    }

def update_ml_price(item_id: str, new_price: float, mini_ml: dict = None) -> bool:
    """
    Actualiza el precio de una publicación en MercadoLibre CBT.

    Para listings CBT, usamos el endpoint /global/items con site_listings
    para actualizar el net_proceeds por país.

    Returns:
        True si se actualizó correctamente
    """
    try:
        url = f"https://api.mercadolibre.com/global/items/{item_id}"
        headers = {
            "Authorization": f"Bearer {ML_TOKEN}",
            "Content-Type": "application/json"
        }

        # Extraer site_items del mini_ml si está disponible
        site_listings = []
        if mini_ml and "site_items" in mini_ml:
            site_items = mini_ml["site_items"]
            if isinstance(site_items, str):
                try:
                    site_items = json.loads(site_items)
                except:
                    site_items = []

            # Construir site_listings con net_proceeds
            for site_item in site_items:
                if not isinstance(site_item, dict):
                    continue
                # Solo incluir países con item_id válido y sin errores
                has_item_id = site_item.get("item_id") is not None
                has_error = site_item.get("error") is not None
                if has_item_id and not has_error:
                    site_listings.append({
                        "logistic_type": site_item.get("logistic_type", "remote"),
                        "listing_item_id": site_item.get("item_id"),
                        "net_proceeds": round(new_price, 2)
                    })

        if site_listings:
            # Actualizar por país (approach de sync_amazon_ml.py)
            payload = {"site_listings": site_listings}
        else:
            # Fallback: actualizar net_proceeds global
            payload = {"net_proceeds": round(new_price, 2)}

        response = requests.put(url, headers=headers, json=payload, timeout=15)

        if response.status_code == 200:
            return True
        else:
            # Mostrar error completo para debugging
            error_msg = response.text[:200] if len(response.text) > 200 else response.text
            log(f"    ⚠️  Error HTTP {response.status_code}: {error_msg}", Colors.YELLOW)
            return False

    except Exception as e:
        log(f"    ❌ Error actualizando en ML: {e}", Colors.RED)
        return False

def get_listings_to_update(asin_filter=None):
    """
    Obtiene todas las publicaciones activas de la DB.

    Returns:
        Lista de tuplas (asin, item_id, mini_ml_data, price_usd, site_items)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if asin_filter:
        cursor.execute("""
            SELECT asin, item_id, mini_ml_data, price_usd, site_items
            FROM listings
            WHERE asin = ? AND item_id IS NOT NULL
        """, (asin_filter,))
    else:
        cursor.execute("""
            SELECT asin, item_id, mini_ml_data, price_usd, site_items
            FROM listings
            WHERE item_id IS NOT NULL
        """)

    listings = cursor.fetchall()
    conn.close()

    return listings

def main():
    parser = argparse.ArgumentParser(description="Actualizar precios masivamente")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin actualizar")
    parser.add_argument("--asin", help="Solo actualizar este ASIN")
    parser.add_argument("--min-diff", type=float, default=1.0, help="Diferencia mínima para actualizar (USD)")

    args = parser.parse_args()

    print()
    log("╔════════════════════════════════════════════════════════════════╗", Colors.BLUE)
    log("║        ACTUALIZACIÓN MASIVA DE PRECIOS - MERCADOLIBRE         ║", Colors.BLUE)
    log("╚════════════════════════════════════════════════════════════════╝", Colors.BLUE)
    print()

    # Mostrar configuración
    log(f"⚙️  CONFIGURACIÓN:", Colors.CYAN)
    log(f"   Markup actual:     {Colors.YELLOW}{int(PRICE_MARKUP * 100)}%{Colors.NC}")
    tax_status = f"{int(TAX_RATE * 100)}% ACTIVADO" if USE_TAX else "DESACTIVADO"
    tax_color = Colors.GREEN if USE_TAX else Colors.RED
    log(f"   Tax (Florida):     {tax_color}{tax_status}{Colors.NC}")
    log(f"   Fulfillment fee:   {Colors.YELLOW}${FULFILLMENT_FEE}{Colors.NC}")
    log(f"   Diferencia mínima: {Colors.YELLOW}${args.min_diff}{Colors.NC}")
    if args.asin:
        log(f"   Filtro ASIN:       {Colors.YELLOW}{args.asin}{Colors.NC}")
    if args.dry_run:
        log(f"   Modo:              {Colors.YELLOW}DRY-RUN (simulación){Colors.NC}")
    print()

    # Confirmar
    if not args.dry_run:
        confirm = input("¿Continuar con la actualización de precios? (s/N): ")
        if confirm.lower() != 's':
            log("❌ Actualización cancelada", Colors.YELLOW)
            return
        print()

    # Obtener listings
    log("📊 Obteniendo publicaciones de la DB...", Colors.CYAN)
    listings = get_listings_to_update(args.asin)

    if not listings:
        log("❌ No se encontraron publicaciones para actualizar", Colors.RED)
        return

    log(f"✅ Encontradas {len(listings)} publicaciones\n", Colors.GREEN)

    # Estadísticas
    stats = {
        "procesados": 0,
        "actualizados": 0,
        "sin_cambios": 0,
        "errores": 0,
        "sin_precio_base": 0
    }

    # Procesar cada listing
    for i, (asin, item_id, mini_ml_json, current_price, site_items_json) in enumerate(listings, 1):
        log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", Colors.CYAN)
        log(f"[{i}/{len(listings)}] 📦 ASIN: {asin}", Colors.CYAN)
        log(f"         🔖 Item ID: {item_id}", Colors.CYAN)

        stats["procesados"] += 1

        # Parsear mini_ml_data para obtener precio base
        try:
            mini_ml = json.loads(mini_ml_json) if mini_ml_json else {}
        except:
            mini_ml = {}

        # Agregar site_items al mini_ml para la función update_ml_price
        if site_items_json:
            try:
                mini_ml["site_items"] = json.loads(site_items_json) if isinstance(site_items_json, str) else site_items_json
            except:
                pass

        # Obtener precio base de Amazon
        base_usd = None
        if "price" in mini_ml and "base_usd" in mini_ml["price"]:
            base_usd = float(mini_ml["price"]["base_usd"])

        if not base_usd:
            log(f"    ⚠️  No se encontró precio base en mini_ml_data", Colors.YELLOW)
            stats["sin_precio_base"] += 1
            continue

        # Calcular nuevo precio
        price_calc = compute_new_price(base_usd)
        new_price = price_calc["net_proceeds_usd"]

        log(f"    💵 Precio base Amazon:  ${price_calc['base_usd']:.2f}")
        log(f"    📊 Tax (7%):            ${price_calc['tax_usd']:.2f}")
        log(f"    📦 Fulfillment:         ${price_calc['fulfillment_fee_usd']:.2f}")
        log(f"    💰 Costo total:         ${price_calc['cost_usd']:.2f}")
        log(f"    🎯 Markup ({price_calc['markup_pct']}%):       ${price_calc['net_proceeds_usd']:.2f}")

        # Comparar con precio actual
        if current_price:
            diff = abs(new_price - current_price)
            log(f"    📈 Precio actual ML:    ${current_price:.2f}")
            log(f"    🔄 Precio nuevo:        ${new_price:.2f}")
            log(f"    📊 Diferencia:          ${diff:.2f}",
                Colors.GREEN if diff > 0 else Colors.YELLOW)

            if diff < args.min_diff:
                log(f"    ✓ Sin cambios (diferencia < ${args.min_diff})", Colors.YELLOW)
                stats["sin_cambios"] += 1
                continue
        else:
            log(f"    🆕 Precio nuevo:        ${new_price:.2f}")

        # Actualizar en ML
        if not args.dry_run:
            log(f"    🔄 Actualizando en MercadoLibre...", Colors.CYAN)

            if update_ml_price(item_id, new_price, mini_ml):
                # Actualizar DB
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE listings
                    SET price_usd = ?,
                        costo_amazon = ?,
                        tax_florida = ?,
                        precio_actual = ?,
                        ultima_actualizacion_precio = ?
                    WHERE asin = ?
                """, (
                    new_price,
                    base_usd,
                    price_calc['tax_usd'],
                    new_price,
                    datetime.now().isoformat(),
                    asin
                ))

                conn.commit()
                conn.close()

                log(f"    ✅ Actualizado correctamente", Colors.GREEN)
                stats["actualizados"] += 1
            else:
                log(f"    ❌ Error al actualizar", Colors.RED)
                stats["errores"] += 1
        else:
            log(f"    🔵 DRY-RUN: No se actualizó", Colors.BLUE)
            stats["actualizados"] += 1

    # Resumen final
    print()
    log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", Colors.BLUE)
    log("📊 RESUMEN FINAL:", Colors.BLUE)
    log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", Colors.BLUE)
    log(f"   📦 Procesados:        {stats['procesados']}")
    log(f"   ✅ Actualizados:      {Colors.GREEN}{stats['actualizados']}{Colors.NC}")
    log(f"   ⏸️  Sin cambios:       {stats['sin_cambios']}")
    log(f"   ⚠️  Sin precio base:   {stats['sin_precio_base']}")
    log(f"   ❌ Errores:           {Colors.RED}{stats['errores']}{Colors.NC}")
    log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", Colors.BLUE)
    print()

    if args.dry_run:
        log("ℹ️  Esto fue una simulación. Ejecuta sin --dry-run para actualizar.", Colors.CYAN)
    elif stats["actualizados"] > 0:
        log("✅ Actualización completada!", Colors.GREEN)
    else:
        log("⚠️  No se actualizó ningún precio", Colors.YELLOW)
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Actualización cancelada por usuario (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        log(f"\n❌ Error: {e}", Colors.RED)
        import traceback
        traceback.print_exc()
        sys.exit(1)
