#!/usr/bin/env python3
"""
Verificar si el parámetro deliveryPostalCode está siendo enviado
en el request a Amazon SP-API
"""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(override=True)

import requests
from src.integrations.amazon_api import get_amazon_access_token

SPAPI_BASE = "https://sellingpartnerapi-na.amazon.com"
MARKETPLACE_ID = "ATVPDKIKX0DER"

# Monkey-patch requests.get para interceptar los parámetros
original_get = requests.get

def patched_get(url, **kwargs):
    if "pricing" in url:
        print("\n" + "=" * 80)
        print("🔍 INTERCEPTADO REQUEST A PRICING API:")
        print("=" * 80)
        print(f"URL: {url}")
        print(f"\nParams enviados:")
        if 'params' in kwargs:
            for key, value in kwargs['params'].items():
                print(f"  - {key}: {value}")
        else:
            print("  (Sin params)")
        print("=" * 80 + "\n")

    return original_get(url, **kwargs)

requests.get = patched_get

# Ahora hacer el request
from src.integrations.amazon_pricing import get_prime_offer

print("Probando con ASIN: B0FDWT3MXK")
print(f"BUYER_ZIPCODE configurado: {os.getenv('BUYER_ZIPCODE')}")
print()

result = get_prime_offer("B0FDWT3MXK")

print("\nResultado:")
if result:
    print(f"  Precio: ${result['price']}")
    print(f"  Availability: {result.get('availability_type', 'N/A')}")
else:
    print("  Sin oferta Prime")
