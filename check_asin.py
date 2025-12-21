#!/usr/bin/env python3
"""Verificar ASIN manualmente en Amazon"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

asin = sys.argv[1] if len(sys.argv) > 1 else "B0FDY4QW8H"
zipcode = os.getenv("BUYER_ZIPCODE", "33172")

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
})

# GET product page
url = f"https://www.amazon.com/dp/{asin}"
response = session.get(url, timeout=30)

print(f"Status: {response.status_code}")
print(f"URL: {url}")
print()

html = response.text

# Cambiar zipcode
glow_url = "https://www.amazon.com/portal-migration/hz/glow/address-change"
payload = {
    'locationType': 'LOCATION_INPUT',
    'zipCode': zipcode,
    'deviceType': 'web',
    'storeContext': 'generic',
    'pageType': 'Detail'
}

try:
    session.post(glow_url, json=payload, timeout=15)
    response = session.get(url, timeout=30)
    html = response.text
except:
    pass

# Buscar indicadores de disponibilidad
print("INDICADORES DE DISPONIBILIDAD:")
print("-" * 80)

if "currently unavailable" in html.lower():
    print("❌ Encontrado: 'Currently unavailable'")
elif "out of stock" in html.lower():
    print("❌ Encontrado: 'Out of stock'")
elif "in stock" in html.lower():
    print("✅ Encontrado: 'In stock'")
else:
    print("⚠️ No se encontró indicador de stock")

print()

# Buscar precio
import re
price_patterns = [
    (r'<span class="a-price-whole">([0-9,]+)<', r'<span class="a-price-fraction">([0-9]+)<'),
    (r'"price":\s*"\\$([0-9,.]+)"', None),
]

for whole_pattern, fraction_pattern in price_patterns:
    whole_match = re.search(whole_pattern, html)
    if whole_match:
        dollars = whole_match.group(1).replace(',', '')
        cents = "00"

        if fraction_pattern:
            fraction_match = re.search(fraction_pattern, html)
            if fraction_match:
                cents = fraction_match.group(1)
        elif '.' in whole_match.group(1):
            parts = whole_match.group(1).replace(',', '').split('.')
            dollars = parts[0]
            cents = parts[1] if len(parts) > 1 else "00"

        price = float(f"{dollars}.{cents}")
        print(f"💰 PRECIO: ${price:.2f}")
        break
else:
    print("💰 PRECIO: No encontrado")

print()

# Buscar delivery
delivery_match = re.search(r'data-csa-c-delivery-time="([^"]*)"', html)
if delivery_match:
    print(f"📦 DELIVERY: {delivery_match.group(1)}")
else:
    print("📦 DELIVERY: No encontrado")

print()

# Buscar título
title_match = re.search(r'<span id="productTitle"[^>]*>([^<]+)</span>', html)
if title_match:
    title = title_match.group(1).strip()
    print(f"📋 TÍTULO: {title[:100]}...")
