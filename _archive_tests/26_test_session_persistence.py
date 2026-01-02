#!/usr/bin/env python3
"""
Test: Por qué VPS de Miami da diferente info que tu PC

Vamos a probar 3 métodos y comparar resultados:
1. Request simple (lo que hace Glow API ahora)
2. Request con session + cookies persistentes
3. Request con headers exactos de tu browser
"""

import requests
import pickle
import os
from bs4 import BeautifulSoup
import re
from datetime import datetime

ASIN = "B0D9PK465N"
ZIPCODE = "33172"

print("=" * 80)
print("TEST: Comparación de métodos de scraping Amazon")
print("=" * 80)
print()

# ==============================================================================
# MÉTODO 1: Request simple (actual)
# ==============================================================================
print("MÉTODO 1: Request simple sin sesión")
print("-" * 80)

url = f"https://www.amazon.com/dp/{ASIN}"
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

response1 = requests.get(url, headers=headers)
print(f"Status: {response1.status_code}")
print(f"Response size: {len(response1.text)} chars")

# Buscar delivery info
soup1 = BeautifulSoup(response1.text, 'html.parser')
delivery1 = soup1.find(id='mir-layout-DELIVERY_BLOCK')
if delivery1:
    print(f"Delivery info: {delivery1.get_text(strip=True)[:100]}")
else:
    print("❌ No delivery info found")

print()

# ==============================================================================
# MÉTODO 2: Session persistente
# ==============================================================================
print("MÉTODO 2: Session con cookies persistentes")
print("-" * 80)

session = requests.Session()

# Intentar cargar cookies guardadas
cookie_file = 'storage/amazon_session_cookies.pkl'
if os.path.exists(cookie_file):
    with open(cookie_file, 'rb') as f:
        session.cookies.update(pickle.load(f))
    print("✅ Cookies cargadas desde archivo")

# Primero: setear zipcode
zip_url = 'https://www.amazon.com/gp/delivery/ajax/address-change.html'
zip_params = {
    'locationType': 'LOCATION_INPUT',
    'zipCode': ZIPCODE,
    'deviceType': 'web',
    'pageType': 'Detail',
    'actionSource': 'glow'
}
zip_headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'text/html,*/*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': url,
}

zip_response = session.post(zip_url, params=zip_params, headers=zip_headers)
print(f"Zipcode set status: {zip_response.status_code}")

# Segundo: obtener producto
response2 = session.get(url, headers=headers)
print(f"Product page status: {response2.status_code}")
print(f"Response size: {len(response2.text)} chars")

soup2 = BeautifulSoup(response2.text, 'html.parser')
delivery2 = soup2.find(id='mir-layout-DELIVERY_BLOCK')
if delivery2:
    print(f"Delivery info: {delivery2.get_text(strip=True)[:100]}")
else:
    print("❌ No delivery info found")

# Guardar cookies para próxima vez
os.makedirs('storage', exist_ok=True)
with open(cookie_file, 'wb') as f:
    pickle.dump(session.cookies, f)
print("✅ Cookies guardadas")

print()

# ==============================================================================
# MÉTODO 3: Headers completos de browser real
# ==============================================================================
print("MÉTODO 3: Headers exactos de Chrome")
print("-" * 80)

session3 = requests.Session()

# Headers EXACTOS de Chrome (copiá estos de tu browser con DevTools)
full_headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
}

# Setear zipcode primero
zip_response3 = session3.post(zip_url, params=zip_params, headers=full_headers)
print(f"Zipcode set status: {zip_response3.status_code}")

# Obtener producto
response3 = session3.get(url, headers=full_headers)
print(f"Product page status: {response3.status_code}")
print(f"Response size: {len(response3.text)} chars")

soup3 = BeautifulSoup(response3.text, 'html.parser')
delivery3 = soup3.find(id='mir-layout-DELIVERY_BLOCK')
if delivery3:
    print(f"Delivery info: {delivery3.get_text(strip=True)[:100]}")
else:
    print("❌ No delivery info found")

print()

# ==============================================================================
# COMPARACIÓN
# ==============================================================================
print("=" * 80)
print("COMPARACIÓN DE RESULTADOS")
print("=" * 80)

print(f"Método 1 (simple): {'✅' if delivery1 else '❌'} delivery info")
print(f"Método 2 (session): {'✅' if delivery2 else '❌'} delivery info")
print(f"Método 3 (full headers): {'✅' if delivery3 else '❌'} delivery info")

print()
print("CONCLUSIÓN:")
print("El método que funcione es el que deberías usar en Glow API")
