#!/usr/bin/env python3
"""Test individual de ASIN con Glow API para sync"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

load_dotenv(override=True)

from src.integrations.amazon_availability_scraper import check_real_availability

def test_asin_sync(asin: str):
    """Test individual de un ASIN simulando la lógica del sync"""

    print("=" * 80)
    print("🌐 TEST GLOW API - SYNC")
    print("=" * 80)
    print(f"ASIN: {asin}")

    buyer_zipcode = os.getenv("BUYER_ZIPCODE", "33172")
    print(f"Zipcode: {buyer_zipcode}")

    max_delivery_days = int(os.getenv("MAX_DELIVERY_DAYS", "2"))
    print(f"Max delivery: {max_delivery_days} días")
    print("=" * 80)
    print()

    print("⏳ Consultando Amazon.com con Glow API...")
    print()

    # Llamar a Glow API
    result = check_real_availability(asin, buyer_zipcode)

    # Mostrar resultado
    print("📊 RESULTADO DE GLOW API:")
    print("-" * 80)

    if result.get("price"):
        print(f"💰 PRECIO: ${result['price']:.2f} USD")
    else:
        print(f"💰 PRECIO: No disponible")

    if result.get("delivery_date"):
        print(f"📦 DELIVERY: {result['delivery_date']}")
        print(f"📅 DÍAS HASTA ENTREGA: {result['days_until_delivery']} días")

        if result['days_until_delivery'] <= max_delivery_days:
            print(f"✅ CUMPLE FAST DELIVERY (≤{max_delivery_days} días)")
        else:
            print(f"❌ NO CUMPLE FAST DELIVERY (>{max_delivery_days} días)")
    else:
        print(f"📦 DELIVERY: No disponible")

    print()
    print("📋 DATOS ADICIONALES:")
    print(f"   • Disponible: {'✅ Sí' if result.get('available') else '❌ No'}")
    print(f"   • En stock: {'✅ Sí' if result.get('in_stock') else '❌ No'}")
    print(f"   • Prime: {'✅ Sí' if result.get('prime_available') else '❌ No'}")
    print(f"   • Fast delivery: {'✅ Sí' if result.get('is_fast_delivery') else '❌ No'}")
    print("-" * 80)
    print()

    # Decisión del sync
    print("🔄 DECISIÓN DEL SYNC:")
    print("-" * 80)

    # Validación completa (igual que en sync)
    if not result.get("available") or not result.get("in_stock"):
        print("❌ RECHAZADO: Producto no disponible")
        print("   → Acción: Pausar en MercadoLibre (stock=0)")
    elif not result.get("price"):
        print("❌ RECHAZADO: Sin precio válido")
        print("   → Acción: Pausar en MercadoLibre (stock=0)")
    elif not result.get("delivery_date"):
        print("❌ RECHAZADO: Sin fecha de entrega")
        print("   → Acción: Pausar en MercadoLibre (stock=0)")
    elif result['days_until_delivery'] > max_delivery_days:
        print(f"❌ RECHAZADO: Delivery tarda {result['days_until_delivery']} días (max: {max_delivery_days})")
        print("   → Acción: Pausar en MercadoLibre (stock=0)")
    else:
        print("✅ APROBADO: Cumple todos los requisitos")
        print(f"   → Precio: ${result['price']:.2f}")
        print(f"   → Delivery: {result['days_until_delivery']} días")
        print("   → Acción: Sincronizar precio en MercadoLibre")

        # Calcular precio ML
        print()
        print("💵 CÁLCULO DE PRECIO ML:")
        print("-" * 80)

        fulfillment_fee = float(os.getenv("FULFILLMENT_FEE", "4.0"))
        price_markup = float(os.getenv("PRICE_MARKUP", "15"))

        cost = result['price'] + fulfillment_fee
        ml_price = cost * (1 + price_markup / 100)

        print(f"   Precio Amazon: ${result['price']:.2f}")
        print(f"   + Fulfillment Fee: ${fulfillment_fee:.2f}")
        print(f"   = Costo total: ${cost:.2f}")
        print(f"   × Markup {price_markup}%: ×{1 + price_markup/100}")
        print()
        print(f"   💰 PRECIO FINAL ML: ${ml_price:.2f} USD")
        print("-" * 80)

    if result.get("error"):
        print()
        print(f"⚠️ Error: {result['error']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python test_glow_sync.py <ASIN>")
        sys.exit(1)

    asin = sys.argv[1]
    test_asin_sync(asin)
