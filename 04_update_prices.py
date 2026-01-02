#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 04_update_prices.py - ACTUALIZAR PRECIOS EN MERCADOLIBRE
# ═══════════════════════════════════════════════════════════════════════════════
# 
# ¿Qué hace?
#   Actualiza los precios de todos los productos publicados en MercadoLibre
#   basándose en los precios actuales de Amazon + markup configurado.
# 
# Comando:
#   python3 04_update_prices.py
# 
# ═══════════════════════════════════════════════════════════════════════════════
import os
import sys
import json
import sqlite3
import requests
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env
load_dotenv(override=True)

# Agregar directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent))
from src.integrations.amazon_glow_api_v2_advanced import check_availability_v2_advanced

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

def update_ml_price(item_id: str, new_price: float, mini_ml: dict = None, exclude_sites: list = None) -> bool:
    """
    Actualiza el precio de una publicación en MercadoLibre CBT.

    Para listings CBT, usamos el endpoint /global/items con site_listings
    para actualizar el net_proceeds por país.

    Args:
        item_id: ID del producto CBT
        new_price: Nuevo precio en USD
        mini_ml: Datos del mini_ml incluyendo site_items
        exclude_sites: Lista de site_ids a excluir (ej: ['MLM', 'MLB'])

    Returns:
        True si se actualizó correctamente
    """
    if exclude_sites is None:
        exclude_sites = []
    try:
        url = f"https://api.mercadolibre.com/global/items/{item_id}"
        headers = {
            "Authorization": f"Bearer {ML_TOKEN}",
            "Content-Type": "application/json"
        }

        # Verificar si el item está activo antes de intentar actualizar
        try:
            check_response = requests.get(f"https://api.mercadolibre.com/items/{item_id}", headers=headers, timeout=10)
            if check_response.status_code == 200:
                item_data = check_response.json()
                item_status = item_data.get("status")
                available_qty = item_data.get("available_quantity", 0)

                if item_status == "paused" or available_qty == 0:
                    log(f"    ⏸️  Item pausado o sin stock (status: {item_status}, qty: {available_qty}) - Omitiendo", Colors.YELLOW)
                    return False
        except Exception as check_error:
            log(f"    ⚠️  No se pudo verificar status del item: {check_error}", Colors.YELLOW)
            # Continuar de todos modos
            pass

        # Extraer site_items del mini_ml si está disponible
        site_listings = []
        if mini_ml and "site_items" in mini_ml:
            site_items = mini_ml["site_items"]
            if isinstance(site_items, str):
                try:
                    site_items = json.loads(site_items)
                except:
                    site_items = []

            # Construir site_listings con net_proceeds (filtrando países excluidos)
            for site_item in site_items:
                if not isinstance(site_item, dict):
                    continue

                # Obtener site_id del país
                site_id = site_item.get("site_id")

                # Saltar si está en la lista de exclusión
                if site_id in exclude_sites:
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
    parser.add_argument("--exclude-sites", help="Override: Marketplaces a excluir (sobrescribe .env)")
    parser.add_argument("--skip-amazon-check", action="store_true", help="Omitir consulta a Amazon (usar precio DB)")

    args = parser.parse_args()

    # Procesar exclude-sites: primero desde .env, luego override con --exclude-sites
    exclude_sites = []

    # 1. Intentar leer desde .env
    exclude_from_env = os.getenv("EXCLUDE_SITES", "").strip()
    if exclude_from_env:
        exclude_sites = [site.strip().upper() for site in exclude_from_env.split(",")]

    # 2. Override con argumento de línea de comandos si se proporciona
    if args.exclude_sites:
        exclude_sites = [site.strip().upper() for site in args.exclude_sites.split(",")]

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
    if exclude_sites:
        source = "CLI override" if args.exclude_sites else ".env"
        log(f"   Países EXCLUIDOS:  {Colors.RED}{', '.join(exclude_sites)}{Colors.NC} ({source})")
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
        "sin_precio_base": 0,
        "sin_precio_amazon": 0,
        "amazon_no_disponible": 0
    }

    # Consultar precios de Amazon con Glow API
    amazon_prices = {}
    if not args.skip_amazon_check:
        log("🔍 Consultando precios actuales en Amazon (Glow API)...", Colors.CYAN)
        try:
            # Extraer todos los ASINs
            asins = [asin for asin, _, _, _, _ in listings]

            # Obtener zipcode desde .env
            buyer_zipcode = os.getenv("BUYER_ZIPCODE", "33172")
            max_delivery_days = int(os.getenv("MAX_DELIVERY_DAYS", "4"))

            log(f"   Zipcode: {buyer_zipcode}", Colors.CYAN)
            log(f"   Max delivery: {max_delivery_days} días", Colors.CYAN)
            print()

            # Consultar cada ASIN con Glow API
            for i, asin in enumerate(asins, 1):
                print(f"   [{i}/{len(asins)}] {asin}...", end=" ", flush=True)

                try:
                    glow_result = check_availability_v2_advanced(asin, buyer_zipcode)

                    # Verificar si tiene error o no está disponible
                    if glow_result.get("error") or not glow_result.get("available"):
                        print("❌ No disponible")
                        amazon_prices[asin] = None
                        continue

                    # Verificar si tiene precio
                    if not glow_result.get("price"):
                        print("❌ Sin precio")
                        amazon_prices[asin] = None
                        continue

                    # ✅ Producto tiene precio (actualizar sin importar delivery)
                    days_until = glow_result.get("days_until_delivery")
                    amazon_prices[asin] = {
                        "price": glow_result["price"],
                        "delivery_date": glow_result.get("delivery_date"),
                        "days_until_delivery": days_until
                    }

                    # Mostrar advertencia si delivery es lento, pero igual actualizar
                    if days_until is not None and days_until > max_delivery_days:
                        print(f"✅ ${glow_result['price']:.2f} ⚠️ Delivery lento: {days_until}d (sync lo pausará)")
                    else:
                        print(f"✅ ${glow_result['price']:.2f} - Llega en {days_until if days_until else '?'} días")

                except Exception as e:
                    print(f"❌ Error: {str(e)[:50]}")
                    amazon_prices[asin] = None

            available_count = sum(1 for v in amazon_prices.values() if v)
            print()
            log(f"   ✅ {available_count}/{len(asins)} productos disponibles en Amazon\n", Colors.GREEN)
        except Exception as e:
            log(f"   ⚠️  Error consultando Amazon: {e}", Colors.YELLOW)
            log(f"   Continuando con precios de la DB...\n", Colors.YELLOW)
            import traceback
            traceback.print_exc()
    else:
        log("⏭️  Omitiendo consulta a Amazon (usando precios DB)\n", Colors.YELLOW)

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

        # Obtener precio ACTUAL de Amazon (si está disponible)
        base_usd = None
        source = "DB"

        if asin in amazon_prices:
            prime_offer = amazon_prices[asin]

            if prime_offer and prime_offer.get("price"):
                # Precio actual de Amazon
                base_usd = float(prime_offer["price"])
                source = "Amazon API (actual)"
                log(f"    💵 Precio Amazon (actual): ${base_usd:.2f}", Colors.GREEN)
            else:
                # Producto no disponible en Amazon
                log(f"    ⚠️  Producto sin oferta Prime en Amazon - Omitiendo", Colors.YELLOW)
                stats["amazon_no_disponible"] += 1
                continue
        else:
            # Fallback: usar precio de la DB (puede estar desactualizado)
            if "price" in mini_ml and "base_usd" in mini_ml["price"]:
                base_usd = float(mini_ml["price"]["base_usd"])
                source = "DB (puede estar desactualizado)"
                log(f"    💵 Precio base (DB legacy): ${base_usd:.2f}", Colors.YELLOW)

        if not base_usd:
            log(f"    ⚠️  No se encontró precio base", Colors.YELLOW)
            stats["sin_precio_base"] += 1
            continue

        # Calcular nuevo precio con fórmula correcta
        price_calc = compute_new_price(base_usd)
        new_price = price_calc["net_proceeds_usd"]

        log(f"    📊 Tax (7%):            ${price_calc['tax_usd']:.2f}")
        log(f"    📦 Fulfillment:         ${price_calc['fulfillment_fee_usd']:.2f}")
        log(f"    💰 Costo total:         ${price_calc['cost_usd']:.2f}")
        log(f"    🎯 Markup ({price_calc['markup_pct']}%):       ${price_calc['net_proceeds_usd']:.2f}")
        log(f"    📍 Fuente precio:       {source}", Colors.CYAN)

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

            if update_ml_price(item_id, new_price, mini_ml, exclude_sites):
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
    log(f"   📦 Procesados:             {stats['procesados']}")
    log(f"   ✅ Actualizados:           {Colors.GREEN}{stats['actualizados']}{Colors.NC}")
    log(f"   ⏸️  Sin cambios:            {stats['sin_cambios']}")
    log(f"   ⚠️  Sin precio base:        {stats['sin_precio_base']}")
    log(f"   ⚠️  Sin oferta Prime:       {stats['amazon_no_disponible']}")
    log(f"   ❌ Errores:                {Colors.RED}{stats['errores']}{Colors.NC}")
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
