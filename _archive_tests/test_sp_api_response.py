#!/usr/bin/env python3
"""
Script para capturar el request/response completo de SP-API
y enviarlo a Amazon Support
"""

import os
import sys
import json
import requests
from datetime import datetime
from src.integrations.amazon_api import get_amazon_access_token

# ASINs de ejemplo que muestran el problema
test_asins = [
    "B0D9PK465N",  # CRITICAL: API dice inmediato pero Amazon.com muestra entrega tardía
    "B0FGJ3G6V8",  # Ejemplo que mencionaste
    "B0CHY9CY3Y",  # Otro ejemplo
    "B0D6ZZLVCY",  # Otro ejemplo
]

SPAPI_BASE = "https://sellingpartnerapi-na.amazon.com"
MARKETPLACE_ID = "ATVPDKIKX0DER"

print("=" * 80)
print("CAPTURANDO REQUESTS/RESPONSES COMPLETOS DE SP-API PARA AMAZON SUPPORT")
print("=" * 80)
print()

for asin in test_asins:
    print(f"\n{'='*80}")
    print(f"ASIN: {asin}")
    print(f"{'='*80}")

    # 1. Obtener token
    token = get_amazon_access_token()

    # 2. Preparar request
    url = f"{SPAPI_BASE}/products/pricing/v0/items/{asin}/offers"

    headers = {
        "Authorization": f"Bearer {token}",
        "x-amz-access-token": token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    params = {
        "MarketplaceId": MARKETPLACE_ID,
        "ItemCondition": "New",
        "CustomerType": "Consumer",
        "deliveryPostalCode": "33172"
    }

    # 3. Mostrar REQUEST completo
    print("\n📤 COMPLETE REQUEST:")
    print("-" * 80)
    print(f"URL: {url}")
    print(f"Method: GET")
    print(f"Query Parameters:")
    for key, value in params.items():
        print(f"  - {key}: {value}")
    print()
    print("Headers:")
    for key, value in headers.items():
        if key in ["Authorization", "x-amz-access-token"]:
            print(f"  - {key}: Bearer [REDACTED - Token válido generado en {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
        else:
            print(f"  - {key}: {value}")

    # 4. Hacer request
    print()
    print("🌐 Enviando request a Amazon SP-API...")

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)

        # 5. Mostrar RESPONSE completo
        print()
        print("📥 COMPLETE RESPONSE:")
        print("-" * 80)
        print(f"Status Code: {response.status_code}")
        print(f"Status: {'✅ OK' if response.status_code == 200 else '❌ ERROR'}")
        print()
        print("Response Headers:")
        for key, value in response.headers.items():
            print(f"  - {key}: {value}")

        print()
        print("Response Body:")
        print("-" * 80)

        # Intentar parsear JSON
        try:
            data = response.json()
            print(json.dumps(data, indent=2))

            # 6. Analizar datos específicos que interesan
            if response.status_code == 200 and 'payload' in data:
                payload = data['payload']
                offers = payload.get('Offers', [])

                print()
                print("=" * 80)
                print("📊 ANÁLISIS DE OFFERS:")
                print("=" * 80)

                if not offers:
                    print("⚠️  NO HAY OFERTAS DISPONIBLES")
                else:
                    print(f"Total de ofertas: {len(offers)}")
                    print()

                    for idx, offer in enumerate(offers, 1):
                        print(f"Oferta #{idx}:")
                        print(f"  IsPrime: {offer.get('PrimeInformation', {}).get('IsPrime', False)}")
                        print(f"  IsFulfilledByAmazon: {offer.get('IsFulfilledByAmazon', False)}")
                        print(f"  IsBuyBoxWinner: {offer.get('IsBuyBoxWinner', False)}")

                        listing_price = offer.get('ListingPrice', {})
                        print(f"  Price: ${listing_price.get('Amount', 'N/A')} {listing_price.get('CurrencyCode', 'N/A')}")

                        shipping_time = offer.get('ShippingTime', {})
                        print(f"  ShippingTime:")
                        print(f"    - availabilityType: {shipping_time.get('availabilityType', 'N/A')}")
                        print(f"    - maximumHours: {shipping_time.get('maximumHours', 'N/A')}")
                        print(f"    - minimumHours: {shipping_time.get('minimumHours', 'N/A')}")
                        print(f"    - availableDate: {shipping_time.get('availableDate', 'N/A')}")

                        ships_from = offer.get('ShipsFrom', {})
                        print(f"  ShipsFrom:")
                        print(f"    - State: {ships_from.get('State', 'null')}")
                        print(f"    - Country: {ships_from.get('Country', 'N/A')}")
                        print()

        except json.JSONDecodeError:
            print("⚠️  La respuesta NO es JSON válido:")
            print(response.text[:1000])

    except requests.exceptions.Timeout:
        print("❌ TIMEOUT - No se recibió respuesta de Amazon SP-API en 15s")
    except Exception as e:
        print(f"❌ ERROR: {e}")

print()
print("=" * 80)
print("📝 INFORMACIÓN PARA AMAZON SUPPORT (Case ID: 16887186041)")
print("=" * 80)
print()
print("PROBLEMA REPORTADO:")
print("El parámetro deliveryPostalCode=33172 no está siendo respetado.")
print()
print("EVIDENCIA:")
print("- ShippingTime.maximumHours reporta 0 horas")
print("- Pero la entrega REAL en 33172 (Miami, FL) tarda 4-7 días")
print()
print("SOLICITUD:")
print("Por favor revisar por qué el endpoint getItemOffers NO respeta el")
print("parámetro deliveryPostalCode para calcular ShippingTime.maximumHours.")
print()
print("ALTERNATIVA SUGERIDA POR AMAZON:")
print("Probar getListingOffers - Requiere Seller SKU en vez de ASIN")
print()
