#!/usr/bin/env python3
"""
Script de prueba para analizar variantes de un ASIN específico
"""
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv
import os

# Agregar path del proyecto
sys.path.insert(0, str(Path(__file__).parent))
from src.integrations.amazon_glow_search import get_product_variants, get_random_user_agent

load_dotenv(override=True)

def test_asin_variants(asin: str):
    """Testea la función de variantes con un ASIN específico"""

    print(f"🔍 Analizando variantes del ASIN: {asin}")
    print("=" * 70)
    print()

    # Configuración desde .env
    BUYER_ZIPCODE = os.getenv("BUYER_ZIPCODE", "33172")
    MIN_PRICE = float(os.getenv("GLOW_MIN_PRICE", "28"))
    MAX_PRICE = float(os.getenv("GLOW_MAX_PRICE", "450"))
    MAX_DELIVERY_DAYS = int(os.getenv("GLOW_MAX_DELIVERY_DAYS", "4"))

    print(f"📋 Configuración:")
    print(f"   Zipcode: {BUYER_ZIPCODE}")
    print(f"   Rango de precio: ${MIN_PRICE} - ${MAX_PRICE}")
    print(f"   Max días envío: {MAX_DELIVERY_DAYS}")
    print()

    # Crear sesión
    session = requests.Session()
    user_agent = get_random_user_agent()

    session.headers.update({
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })

    # Configurar zipcode con Glow API
    try:
        print("🌐 Configurando zipcode con Glow API...")
        homepage_url = "https://www.amazon.com"
        session.get(homepage_url, timeout=15)

        glow_url = "https://www.amazon.com/portal-migration/hz/glow/address-change"
        params = {
            'actionSource': 'glow',
            'deviceType': 'desktop',
            'pageType': 'Search',
            'storeContext': 'pc'
        }
        payload = {
            'locationType': 'LOCATION_INPUT',
            'zipCode': BUYER_ZIPCODE,
            'deviceType': 'web',
            'storeContext': 'generic',
            'pageType': 'Search'
        }
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': homepage_url
        }
        session.post(glow_url, params=params, json=payload, headers=headers, timeout=10)
        print("   ✅ Zipcode configurado")
    except Exception as e:
        print(f"   ⚠️  Error configurando zipcode: {e}")

    print()
    print("🔎 Buscando variantes...")
    print()

    # Buscar variantes
    variants = get_product_variants(
        asin=asin,
        session=session,
        zipcode=BUYER_ZIPCODE,
        min_price=MIN_PRICE,
        max_price=MAX_PRICE,
        max_delivery_days=MAX_DELIVERY_DAYS
    )

    print()
    print("=" * 70)
    print("📊 RESULTADOS:")
    print("=" * 70)
    print()

    if variants:
        print(f"✅ Se encontraron {len(variants)} variantes que cumplen los criterios:")
        print()
        for i, variant_asin in enumerate(variants, 1):
            product_url = f"https://www.amazon.com/dp/{variant_asin}"
            print(f"   {i}. {variant_asin}")
            print(f"      → {product_url}")
        print()
        print(f"💡 Total de variantes válidas: {len(variants)}")
    else:
        print("❌ No se encontraron variantes que cumplan los criterios")
        print()
        print("Posibles razones:")
        print("   - El producto no tiene variantes")
        print("   - Las variantes están fuera del rango de precio")
        print("   - Las variantes no tienen envío rápido disponible")
        print("   - Error al cargar la página del producto")

    print()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_asin = sys.argv[1]
    else:
        test_asin = "B0FKT28PP7"  # ASIN por defecto

    try:
        test_asin_variants(test_asin)
    except KeyboardInterrupt:
        print("\n\n🛑 Prueba detenida por usuario (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
