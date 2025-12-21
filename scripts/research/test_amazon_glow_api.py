#!/usr/bin/env python3
"""
Probar la API interna de Amazon "Glow" para cambiar zipcode
y obtener delivery dates sin Selenium
"""
import requests
from bs4 import BeautifulSoup
import re

# Esta es la estrategia que probablemente usa el software comercial:
# 1. Hacer request a la página del producto
# 2. Extraer CSRF token
# 3. Llamar a API interna de address-change con el token
# 4. Obtener nuevo HTML con delivery dates actualizados

ASIN = "B0FDWT3MXK"
ZIPCODE = "33172"

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
})

print("="*80)
print("PROBANDO API INTERNA DE AMAZON (GLOW)")
print("="*80)

# Paso 1: Get product page para obtener cookies y CSRF token
print(f"\n1️⃣ Obteniendo página del producto {ASIN}...")
url = f"https://www.amazon.com/dp/{ASIN}"
response = session.get(url)

if response.status_code != 200:
    print(f"❌ Error {response.status_code}")
    exit(1)

print(f"   ✅ Status 200")

# Extraer CSRF token
csrf_token = None
csrf_match = re.search(r'"anti-csrftoken-a2z"\s*:\s*"([^"]+)"', response.text)
if csrf_match:
    csrf_token = csrf_match.group(1)
    print(f"   🔑 CSRF Token: {csrf_token[:30]}...")

# Extraer session ID
session_id = None
session_match = re.search(r'"sessionId"\s*:\s*"([^"]+)"', response.text)
if session_match:
    session_id = session_match.group(1)
    print(f"   🆔 Session ID: {session_id[:30]}...")

# Paso 2: Llamar a API de address-change
print(f"\n2️⃣ Cambiando delivery location a zipcode {ZIPCODE}...")

glow_url = "https://www.amazon.com/portal-migration/hz/glow/address-change"

# Parámetros observados en las llamadas AJAX
params = {
    'actionSource': 'glow',
    'deviceType': 'desktop',
    'pageType': 'Detail',
    'storeContext': 'pc'
}

# Payload para cambiar zipcode
payload = {
    'locationType': 'LOCATION_INPUT',
    'zipCode': ZIPCODE,
    'deviceType': 'web',
    'storeContext': 'generic',
    'pageType': 'Detail'
}

headers = {
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
}

if csrf_token:
    headers['anti-csrftoken-a2z'] = csrf_token

try:
    response = session.post(glow_url, params=params, json=payload, headers=headers, timeout=30)

    print(f"   Status: {response.status_code}")
    print(f"   Content-Type: {response.headers.get('Content-Type')}")

    if response.status_code == 200:
        print(f"   ✅ API respondió exitosamente")

        # Intentar parsear respuesta
        try:
            data = response.json()
            print(f"   📦 Response (primeros 500 chars):")
            print(f"   {str(data)[:500]}")
        except:
            print(f"   📄 Response (texto):")
            print(f"   {response.text[:500]}")

    else:
        print(f"   ❌ Error {response.status_code}")
        print(f"   {response.text[:200]}")

except Exception as e:
    print(f"   ❌ Exception: {e}")

# Paso 3: Volver a pedir el producto para ver delivery dates actualizados
print(f"\n3️⃣ Obteniendo delivery dates con el nuevo zipcode...")

response = session.get(url)
if response.status_code == 200:
    # Buscar delivery dates
    delivery_match = re.search(
        r'((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+)',
        response.text,
        re.IGNORECASE
    )

    if delivery_match:
        print(f"   📅 Fecha encontrada: {delivery_match.group(1)}")
    else:
        print(f"   ⚠️  No se encontró fecha de entrega")

    # Verificar zipcode en location
    location_match = re.search(r'Deliver to.*?(\d{5})', response.text)
    if location_match:
        detected_zip = location_match.group(1)
        print(f"   📍 Zipcode detectado: {detected_zip}")
        if detected_zip == ZIPCODE:
            print(f"   ✅ ¡Zipcode correcto!")
        else:
            print(f"   ⚠️  Zipcode no coincide")

print("\n" + "="*80)
print("CONCLUSIÓN:")
print("Si esto funciona, podemos llamar a esta API sin Selenium")
print("="*80)
