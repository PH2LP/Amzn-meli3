#!/usr/bin/env python3
"""
TEST REAL: Smartproxy con geo-targeting Florida

IMPORTANTE: Antes de ejecutar, creá un usuario en el dashboard de Smartproxy con:
- Location: United States > Florida > Miami
- Session: Sticky (10min)

Luego agregá las credenciales al .env:
SMARTPROXY_USER=tu_username
SMARTPROXY_PASS=tu_password
"""

import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import re
from datetime import datetime
import random

load_dotenv()

# Configuración
TEST_ASINS = [
    "B0D9PK465N",  # CRÍTICO: SP-API dice inmediato, real es 10 días
    "B0FGJ3G6V8",  # Otro test
    "B09P53JX4R",  # Otro test
]

ZIPCODE = "33172"

# Credenciales Smartproxy
SMARTPROXY_USER = os.getenv('SMARTPROXY_USER')
SMARTPROXY_PASS = os.getenv('SMARTPROXY_PASS')

if not SMARTPROXY_USER or not SMARTPROXY_PASS:
    print("❌ ERROR: Falta configurar SMARTPROXY_USER y SMARTPROXY_PASS en .env")
    print()
    print("Agregá estas líneas al archivo .env:")
    print("SMARTPROXY_USER=tu_username")
    print("SMARTPROXY_PASS=tu_password")
    print()
    exit(1)

print("=" * 80)
print("🧪 TEST REAL: Smartproxy + Geo-targeting Florida")
print("=" * 80)
print(f"Usuario: {SMARTPROXY_USER}")
print(f"Zipcode target: {ZIPCODE}")
print()

def extract_delivery_info(html_content):
    """Extrae información de delivery del HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')

    # Buscar bloque de delivery
    delivery_block = soup.find(id='mir-layout-DELIVERY_BLOCK')

    if not delivery_block:
        return {
            'found': False,
            'text': None,
            'date': None,
            'days': None
        }

    delivery_text = delivery_block.get_text(strip=True)

    # Extraer fecha
    date_pattern = r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\w+)\s+(\d+)'
    date_match = re.search(date_pattern, delivery_text)

    delivery_date = None
    days_until = None

    if date_match:
        month_map = {
            'January': 1, 'February': 2, 'March': 3, 'April': 4,
            'May': 5, 'June': 6, 'July': 7, 'August': 8,
            'September': 9, 'October': 10, 'November': 11, 'December': 12
        }

        month_num = month_map.get(date_match.group(2))
        day = int(date_match.group(3))

        if month_num:
            try:
                year = 2025 if month_num == 1 else datetime.now().year
                delivery_date = datetime(year, month_num, day)
                days_until = (delivery_date - datetime.now()).days
            except:
                pass

    return {
        'found': True,
        'text': delivery_text[:150],
        'date': delivery_date.strftime('%Y-%m-%d') if delivery_date else None,
        'days': days_until
    }

def test_with_smartproxy(asin, geo_config=None):
    """
    Test con Smartproxy

    geo_config puede ser:
    - None: usar configuración del dashboard
    - "country-us-state-fl": forzar Florida en username
    - "country-us-state-fl-city-miami": forzar Florida + Miami
    """

    url = f"https://www.amazon.com/dp/{asin}"

    # Configurar proxy
    if geo_config:
        # Formato: user-country-us-state-fl-session-{random}
        session_id = random.randint(10000, 99999)
        proxy_user = f"{SMARTPROXY_USER}-{geo_config}-session-{session_id}"
    else:
        # Usar configuración del dashboard
        proxy_user = SMARTPROXY_USER

    proxy_pass = SMARTPROXY_PASS

    # Smartproxy endpoints (decodo.com es el dominio de Smartproxy)
    proxy_url = f"http://{proxy_user}:{proxy_pass}@us.decodo.com:10001"

    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }

    # Headers normales de browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }

    try:
        print(f"📡 Request para ASIN {asin}...")
        print(f"   Proxy: {proxy_user}@gate.smartproxy.com:7000")

        response = requests.get(url, proxies=proxies, headers=headers, timeout=30)

        print(f"   ✅ Status: {response.status_code}")
        print(f"   📦 Size: {len(response.text):,} chars")

        # Extraer delivery info
        delivery = extract_delivery_info(response.text)

        return {
            'success': True,
            'status_code': response.status_code,
            'size': len(response.text),
            'delivery': delivery
        }

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# ==============================================================================
# TEST 1: Usando configuración del dashboard
# ==============================================================================
print("TEST 1: Configuración del dashboard")
print("-" * 80)
print("Esto usa la configuración de Location que seteaste en el dashboard")
print()

results_dashboard = []

for asin in TEST_ASINS:
    result = test_with_smartproxy(asin)
    results_dashboard.append((asin, result))

    if result['success'] and result['delivery']['found']:
        days = result['delivery']['days']
        text = result['delivery']['text']
        print(f"   ✅ Delivery: {days} días - {text[:80]}")
    elif result['success']:
        print(f"   ⚠️  No encontró delivery info")

    print()

# ==============================================================================
# TEST 2: Forzar geo en username (Florida)
# ==============================================================================
print("=" * 80)
print("TEST 2: Geo-targeting en username (Florida)")
print("-" * 80)
print("Formato: user-country-us-state-fl-session-{random}")
print()

asin = TEST_ASINS[0]  # Solo probar con el primero
result_fl = test_with_smartproxy(asin, geo_config="country-us-state-fl")

if result_fl['success'] and result_fl['delivery']['found']:
    days = result_fl['delivery']['days']
    text = result_fl['delivery']['text']
    print(f"   ✅ Delivery: {days} días - {text[:80]}")
elif result_fl['success']:
    print(f"   ⚠️  No encontró delivery info")

print()

# ==============================================================================
# TEST 3: Forzar geo en username (Florida + Miami)
# ==============================================================================
print("=" * 80)
print("TEST 3: Geo-targeting en username (Florida + Miami)")
print("-" * 80)
print("Formato: user-country-us-state-fl-city-miami-session-{random}")
print()

result_miami = test_with_smartproxy(asin, geo_config="country-us-state-fl-city-miami")

if result_miami['success'] and result_miami['delivery']['found']:
    days = result_miami['delivery']['days']
    text = result_miami['delivery']['text']
    print(f"   ✅ Delivery: {days} días - {text[:80]}")
elif result_miami['success']:
    print(f"   ⚠️  No encontró delivery info")

print()

# ==============================================================================
# COMPARACIÓN FINAL
# ==============================================================================
print("=" * 80)
print("📊 RESULTADOS FINALES")
print("=" * 80)
print()

print(f"ASIN CRÍTICO: {TEST_ASINS[0]}")
print(f"Expectativa: ~10 días (NO inmediato como dice SP-API)")
print()

configs = [
    ("Dashboard config", results_dashboard[0][1] if results_dashboard else None),
    ("Florida (state)", result_fl if 'result_fl' in locals() else None),
    ("Florida + Miami", result_miami if 'result_miami' in locals() else None),
]

for config_name, result in configs:
    if result and result['success'] and result.get('delivery', {}).get('found'):
        days = result['delivery']['days']
        print(f"✅ {config_name:20s} → {days} días")
    elif result and result['success']:
        print(f"⚠️  {config_name:20s} → Sin delivery info")
    else:
        print(f"❌ {config_name:20s} → Error")

print()
print("=" * 80)
print("✅ CONCLUSIÓN:")
print("=" * 80)

# Encontrar el mejor resultado
best_result = None
best_config = None

for config_name, result in configs:
    if result and result['success'] and result.get('delivery', {}).get('found'):
        if best_result is None or result['delivery']['days'] is not None:
            best_result = result
            best_config = config_name

if best_result:
    days = best_result['delivery']['days']
    print(f"✅ FUNCIONA! Mejor configuración: {best_config}")
    print(f"   Delivery time detectado: {days} días")
    print()
    print("🚀 PRÓXIMO PASO:")
    print("   Implementar procesamiento paralelo con Smartproxy")
    print("   → 50,000 productos en ~2 horas")
else:
    print("❌ Ninguna configuración funcionó")
    print()
    print("⚠️  VERIFICAR:")
    print("   1. ¿El usuario está correctamente creado en dashboard?")
    print("   2. ¿La Location está seteada a Florida/Miami?")
    print("   3. ¿El trial tiene créditos disponibles?")

print("=" * 80)
