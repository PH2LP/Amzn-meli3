#!/usr/bin/env python3
"""
SANDBOX TEST: Scrapedo API con residential proxies

Probamos si Scrapedo con proxies residenciales de Florida da la misma info que tu PC.

NO INTEGRADO AL SISTEMA - Solo prueba
"""

import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import json
from datetime import datetime
import re

load_dotenv()

SCRAPEDO_TOKEN = os.getenv('SCRAPEDO_API_TOKEN')
TEST_ASINS = [
    "B0D9PK465N",  # El que está dando problemas
    "B0FGJ3G6V8",  # Otro test
]
ZIPCODE = "33172"

print("=" * 80)
print("🧪 SANDBOX TEST: Scrapedo API")
print("=" * 80)
print(f"Token: {SCRAPEDO_TOKEN[:20]}...")
print(f"Zipcode: {ZIPCODE}")
print()

def extract_delivery_info(html_content):
    """Extrae información de delivery del HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')

    # Buscar bloque de delivery
    delivery_block = soup.find(id='mir-layout-DELIVERY_BLOCK')
    if not delivery_block:
        delivery_block = soup.find('div', {'data-csa-c-content-id': 'DEXUnifiedCXPDM'})

    if not delivery_block:
        return {
            'found': False,
            'text': None,
            'date': None,
            'days': None
        }

    delivery_text = delivery_block.get_text(strip=True)

    # Extraer fecha (ej: "Wednesday, December 31")
    date_pattern = r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\w+)\s+(\d+)'
    date_match = re.search(date_pattern, delivery_text)

    delivery_date = None
    days_until = None

    if date_match:
        # Parsear fecha
        month_str = date_match.group(2)
        day = int(date_match.group(3))

        # Calcular días hasta delivery (aproximado)
        month_map = {
            'January': 1, 'February': 2, 'March': 3, 'April': 4,
            'May': 5, 'June': 6, 'July': 7, 'August': 8,
            'September': 9, 'October': 10, 'November': 11, 'December': 12
        }

        month_num = month_map.get(month_str)
        if month_num:
            try:
                year = 2025 if month_num == 1 else datetime.now().year
                delivery_date = datetime(year, month_num, day)
                days_until = (delivery_date - datetime.now()).days
            except:
                pass

    return {
        'found': True,
        'text': delivery_text[:200],
        'date': delivery_date.strftime('%Y-%m-%d') if delivery_date else None,
        'days': days_until
    }

# ==============================================================================
# TEST 1: Scrapedo básico sin opciones especiales
# ==============================================================================
print("TEST 1: Scrapedo básico (sin geo-targeting)")
print("-" * 80)

asin = TEST_ASINS[0]
product_url = f'https://www.amazon.com/dp/{asin}'

scrapedo_url = 'https://api.scrape.do'
params = {
    'token': SCRAPEDO_TOKEN,
    'url': product_url,
}

try:
    print(f"📡 Request a: {product_url}")
    response = requests.get(scrapedo_url, params=params, timeout=30)
    print(f"✅ Status: {response.status_code}")
    print(f"📦 Response size: {len(response.text):,} chars")

    delivery = extract_delivery_info(response.text)

    if delivery['found']:
        print(f"✅ Delivery info encontrada:")
        print(f"   Texto: {delivery['text']}")
        print(f"   Fecha: {delivery['date']}")
        print(f"   Días: {delivery['days']}")
    else:
        print("❌ No se encontró delivery info")

except Exception as e:
    print(f"❌ Error: {e}")

print()

# ==============================================================================
# TEST 2: Scrapedo con geo-targeting Florida
# ==============================================================================
print("TEST 2: Scrapedo con geo-targeting (us-fl)")
print("-" * 80)

params2 = {
    'token': SCRAPEDO_TOKEN,
    'url': product_url,
    'geoCode': 'us-fl',  # Proxy de Florida
    'render': 'false',    # No necesitamos JavaScript para delivery info
}

try:
    print(f"📡 Request con geoCode=us-fl")
    response2 = requests.get(scrapedo_url, params=params2, timeout=30)
    print(f"✅ Status: {response2.status_code}")
    print(f"📦 Response size: {len(response2.text):,} chars")

    delivery2 = extract_delivery_info(response2.text)

    if delivery2['found']:
        print(f"✅ Delivery info encontrada:")
        print(f"   Texto: {delivery2['text']}")
        print(f"   Fecha: {delivery2['date']}")
        print(f"   Días: {delivery2['days']}")
    else:
        print("❌ No se encontró delivery info")

except Exception as e:
    print(f"❌ Error: {e}")

print()

# ==============================================================================
# TEST 3: Scrapedo con JavaScript rendering + geo-targeting
# ==============================================================================
print("TEST 3: Scrapedo con rendering + geo-targeting")
print("-" * 80)

params3 = {
    'token': SCRAPEDO_TOKEN,
    'url': product_url,
    'geoCode': 'us-fl',
    'render': 'true',     # Ejecutar JavaScript (más lento pero más completo)
}

try:
    print(f"📡 Request con render=true + geoCode=us-fl")
    print("⏳ Esto puede tardar 5-10 segundos...")
    response3 = requests.get(scrapedo_url, params=params3, timeout=60)
    print(f"✅ Status: {response3.status_code}")
    print(f"📦 Response size: {len(response3.text):,} chars")

    delivery3 = extract_delivery_info(response3.text)

    if delivery3['found']:
        print(f"✅ Delivery info encontrada:")
        print(f"   Texto: {delivery3['text']}")
        print(f"   Fecha: {delivery3['date']}")
        print(f"   Días: {delivery3['days']}")
    else:
        print("❌ No se encontró delivery info")

except Exception as e:
    print(f"❌ Error: {e}")

print()

# ==============================================================================
# TEST 4: Scrapedo con custom session (para mantener zipcode)
# ==============================================================================
print("TEST 4: Scrapedo con session ID persistente")
print("-" * 80)

params4 = {
    'token': SCRAPEDO_TOKEN,
    'url': product_url,
    'geoCode': 'us-fl',
    'sessionId': f'amazon_{ZIPCODE}',  # Mantiene misma IP/sesión
    'render': 'false',
}

try:
    print(f"📡 Request con sessionId=amazon_{ZIPCODE}")
    response4 = requests.get(scrapedo_url, params=params4, timeout=30)
    print(f"✅ Status: {response4.status_code}")
    print(f"📦 Response size: {len(response4.text):,} chars")

    delivery4 = extract_delivery_info(response4.text)

    if delivery4['found']:
        print(f"✅ Delivery info encontrada:")
        print(f"   Texto: {delivery4['text']}")
        print(f"   Fecha: {delivery4['date']}")
        print(f"   Días: {delivery4['days']}")
    else:
        print("❌ No se encontró delivery info")

except Exception as e:
    print(f"❌ Error: {e}")

print()

# ==============================================================================
# COMPARACIÓN FINAL
# ==============================================================================
print("=" * 80)
print("📊 COMPARACIÓN DE RESULTADOS")
print("=" * 80)
print(f"ASIN: {asin}")
print()

methods = [
    ("Básico (sin geo)", delivery if 'delivery' in locals() else None),
    ("Geo Florida", delivery2 if 'delivery2' in locals() else None),
    ("Render + Geo", delivery3 if 'delivery3' in locals() else None),
    ("Session + Geo", delivery4 if 'delivery4' in locals() else None),
]

for method_name, result in methods:
    if result and result['found']:
        status = "✅"
        days = f"{result['days']} días" if result['days'] else "N/A"
    else:
        status = "❌"
        days = "No encontrado"

    print(f"{status} {method_name:20s} → {days}")

print()
print("=" * 80)
print("CONCLUSIÓN:")
print("=" * 80)
print("Si algún método muestra delivery info similar a tu PC:")
print("→ Ese método es viable para escalar a 50,000 productos")
print()
print("Si todos fallan:")
print("→ Necesitarás Smartproxy residential proxies o browser automation")
print("=" * 80)
