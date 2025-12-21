#!/usr/bin/env python3
"""Debug detallado de B0FDY4QW8H"""
import os
import re
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

asin = "B0FDY4QW8H"
zipcode = os.getenv("BUYER_ZIPCODE", "33172")

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
})

# GET product page
url = f"https://www.amazon.com/dp/{asin}"
response = session.get(url, timeout=30)

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
    glow_response = session.post(glow_url, json=payload, timeout=15)
    print(f"Glow API response: {glow_response.status_code}")
    response = session.get(url, timeout=30)
    html = response.text
except Exception as e:
    print(f"Glow error: {e}")

print("=" * 80)
print("BÚSQUEDA DE PRECIO")
print("=" * 80)

# Buscar TODOS los precios
price_patterns = [
    r'<span class="a-price-whole">([0-9,]+)<',
    r'"price":\s*"\\$([0-9,.]+)"',
    r'<span class="a-offscreen">\$([0-9,.]+)</span>',
]

for i, pattern in enumerate(price_patterns, 1):
    matches = re.findall(pattern, html)
    print(f"{i}. Pattern: {pattern[:50]}...")
    if matches:
        print(f"   Matches: {matches[:5]}")
    else:
        print(f"   No matches")

print()
print("=" * 80)
print("BÚSQUEDA DE DELIVERY")
print("=" * 80)

# Buscar delivery block
delivery_block = re.search(r'<div id="mir-layout-DELIVERY_BLOCK"[^>]*>(.*?)</div></div></div>', html, re.DOTALL)
if delivery_block:
    print("✅ DELIVERY_BLOCK encontrado")
    block_html = delivery_block.group(1)

    # Buscar data-csa-c
    pattern = r'data-csa-c-delivery-time="([^"]*)"'
    matches = re.findall(pattern, block_html)
    print(f"   data-csa-c-delivery-time matches: {matches}")

    # Buscar FREE delivery en texto
    free_delivery = re.findall(r'FREE delivery[^<>]{0,100}', block_html, re.IGNORECASE)
    print(f"   FREE delivery texts: {free_delivery[:3]}")
else:
    print("❌ DELIVERY_BLOCK NO encontrado")

    # Buscar en todo el HTML
    free_delivery = re.findall(r'FREE delivery[^<>]{0,100}', html, re.IGNORECASE)
    print(f"   FREE delivery en HTML completo: {free_delivery[:3]}")

print()
print("=" * 80)
print("BÚSQUEDA DE DISPONIBILIDAD")
print("=" * 80)

indicators = ["buy new", "add to cart", "in stock", "currently unavailable", "order within"]
for indicator in indicators:
    if indicator in html.lower():
        print(f"✅ Found: '{indicator}'")
    else:
        print(f"❌ Not found: '{indicator}'")
