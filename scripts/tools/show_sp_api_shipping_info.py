#!/usr/bin/env python3
"""
Mostrar información detallada de ShippingTime del SP-API
Para entender qué datos tenemos disponibles
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.integrations.amazon_api import get_amazon_access_token
import requests

# ASINs de prueba
test_asins = [
    "B0FGJ3G6V8",  # El que el usuario ve que llega Lunes 22
    "B0FDWT3MXK",
    "B0D9H19PBL",
    "B0DJH46BBL",
]

SPAPI_BASE = "https://sellingpartnerapi-na.amazon.com"
MARKETPLACE_ID = "ATVPDKIKX0DER"

print("="*80)
print("INFORMACIÓN DE SHIPPING DEL SP-API")
print("="*80)
print()

token = get_amazon_access_token()
headers = {
    "Authorization": f"Bearer {token}",
    "x-amz-access-token": token,
    "Content-Type": "application/json",
}

for asin in test_asins:
    print(f"\n{'='*80}")
    print(f"ASIN: {asin}")
    print('='*80)

    url = f"{SPAPI_BASE}/products/pricing/v0/items/{asin}/offers"
    params = {
        "MarketplaceId": MARKETPLACE_ID,
        "ItemCondition": "New",
        "deliveryPostalCode": "33172"  # Zipcode Miami
    }

    response = requests.get(url, headers=headers, params=params, timeout=15)

    if response.status_code != 200:
        print(f"❌ Error {response.status_code}")
        continue

    data = response.json()
    offers = data.get('payload', {}).get('Offers', [])

    if not offers:
        print("❌ Sin ofertas")
        continue

    # Mostrar info de la primera oferta FBA + Prime
    for offer in offers:
        is_fba = offer.get('IsFulfilledByAmazon', False)
        is_prime = offer.get('PrimeInformation', {}).get('IsPrime', False)

        if is_fba and is_prime:
            print("\n✅ OFERTA PRIME + FBA:")
            print(f"  Precio: ${offer.get('ListingPrice', {}).get('Amount')}")
            print(f"  IsBuyBoxWinner: {offer.get('IsBuyBoxWinner', False)}")

            # ShippingTime - ESTO ES LO IMPORTANTE
            shipping_time = offer.get('ShippingTime', {})
            print(f"\n  📦 ShippingTime:")
            print(f"     availabilityType: {shipping_time.get('availabilityType', 'N/A')}")
            print(f"     maximumHours: {shipping_time.get('maximumHours', 'N/A')}")
            print(f"     minimumHours: {shipping_time.get('minimumHours', 'N/A')}")
            print(f"     availableDate: {shipping_time.get('availableDate', 'N/A')}")

            # ShipsFrom
            ships_from = offer.get('ShipsFrom', {})
            print(f"\n  🚚 ShipsFrom:")
            print(f"     State: {ships_from.get('State', 'N/A')}")
            print(f"     Country: {ships_from.get('Country', 'N/A')}")

            # PrimeInformation
            prime_info = offer.get('PrimeInformation', {})
            print(f"\n  ⭐ PrimeInformation:")
            print(f"     IsPrime: {prime_info.get('IsPrime', 'N/A')}")
            print(f"     IsNationalPrime: {prime_info.get('IsNationalPrime', 'N/A')}")

            # IsFeaturedMerchant
            print(f"\n  IsFeaturedMerchant: {offer.get('IsFeaturedMerchant', 'N/A')}")

            # Mostrar oferta completa en JSON
            print(f"\n  📄 Oferta completa (JSON):")
            print(json.dumps(offer, indent=2))

            break
    else:
        print("❌ Sin oferta Prime + FBA")

print("\n" + "="*80)
print("CONCLUSIÓN:")
print("SP-API NO provee:")
print("  ❌ Fecha estimada de entrega (delivery date)")
print("  ❌ Días hasta entrega")
print("  ❌ Si es entrega Prime rápida vs regular")
print()
print("SP-API SÍ provee:")
print("  ✅ availabilityType (NOW, FUTURE_WITH_DATE, etc)")
print("  ✅ maximumHours (tiempo en warehouse)")
print("  ✅ ShipsFrom State (desde qué estado envía)")
print()
print("PROBLEMA:")
print("  maximumHours solo mide tiempo en warehouse, NO tiempo de tránsito")
print("  Un producto puede tener maximumHours=0 pero tardar 7 días desde WA->FL")
print("="*80)
