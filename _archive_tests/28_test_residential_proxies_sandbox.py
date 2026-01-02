#!/usr/bin/env python3
"""
SANDBOX TEST: Residential Proxies con geo-targeting por ESTADO

Probamos 3 proveedores principales que soportan geo-targeting Florida:
1. Smartproxy (recomendado - $75/mes)
2. Bright Data (más caro - $500/mes pero más confiable)
3. Oxylabs (medio - $300/mes)

NOTA: Para probar necesitás crear trial gratuito en cada uno.
Este script muestra cómo configurarlos.

NO INTEGRADO AL SISTEMA - Solo prueba
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

TEST_ASIN = "B0D9PK465N"
ZIPCODE = "33172"
PRODUCT_URL = f"https://www.amazon.com/dp/{TEST_ASIN}"

print("=" * 80)
print("🧪 SANDBOX: Residential Proxies con Geo-Targeting Florida")
print("=" * 80)
print()

def extract_delivery_days(html_content):
    """Extrae días hasta delivery"""
    soup = BeautifulSoup(html_content, 'html.parser')
    delivery_block = soup.find(id='mir-layout-DELIVERY_BLOCK')

    if not delivery_block:
        return None

    text = delivery_block.get_text(strip=True)

    # Buscar fecha
    date_pattern = r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\w+)\s+(\d+)'
    match = re.search(date_pattern, text)

    if not match:
        return None

    month_map = {
        'January': 1, 'February': 2, 'March': 3, 'April': 4,
        'May': 5, 'June': 6, 'July': 7, 'August': 8,
        'September': 9, 'October': 10, 'November': 11, 'December': 12
    }

    month = month_map.get(match.group(2))
    day = int(match.group(3))
    year = 2025 if month == 1 else datetime.now().year

    try:
        delivery_date = datetime(year, month, day)
        days = (delivery_date - datetime.now()).days
        return days, text[:100]
    except:
        return None

# ==============================================================================
# OPCIÓN 1: SMARTPROXY (Recomendado)
# ==============================================================================
print("OPCIÓN 1: SMARTPROXY - Residential Proxies")
print("-" * 80)
print("💰 Precio: $75/mes (8GB) - $200/mes (40GB)")
print("🌍 Geo-targeting: País, Estado, Ciudad")
print("📊 Pool: 40M+ IPs residenciales USA")
print()

print("CONFIGURACIÓN:")
print("-" * 80)
print("""
# .env
SMARTPROXY_USER=your_username
SMARTPROXY_PASS=your_password

# Formato para Florida:
# user-country-us-state-fl-session-{random}
# user-country-us-state-fl-city-miami-session-{random}
""")

print("CÓDIGO DE EJEMPLO:")
print("-" * 80)
print("""
import random

# Proxy con geo-targeting Florida
session_id = random.randint(10000, 99999)
proxy_user = f"user-country-us-state-fl-session-{session_id}"
proxy_pass = "your_password"

proxies = {
    'http': f'http://{proxy_user}:{proxy_pass}@gate.smartproxy.com:7000',
    'https': f'http://{proxy_user}:{proxy_pass}@gate.smartproxy.com:7000'
}

response = requests.get(product_url, proxies=proxies, headers=headers)
""")

print()
print("🎯 VENTAJAS:")
print("  ✅ Geo-targeting por estado (Florida)")
print("  ✅ Puedes especificar ciudad (Miami)")
print("  ✅ Session sticky (misma IP por 10 min)")
print("  ✅ Precio competitivo")
print("  ✅ Trial gratis: 3 días")
print()

print("📝 REGISTRO: https://smartproxy.com/proxies/residential-proxies")
print()

# ==============================================================================
# OPCIÓN 2: BRIGHT DATA (ex-Luminati)
# ==============================================================================
print("=" * 80)
print("OPCIÓN 2: BRIGHT DATA - Enterprise Grade")
print("-" * 80)
print("💰 Precio: $500/mes (20GB) - Más caro pero más confiable")
print("🌍 Geo-targeting: País, Estado, Ciudad, Zip Code (!)")
print("📊 Pool: 72M+ IPs residenciales USA")
print()

print("CONFIGURACIÓN:")
print("-" * 80)
print("""
# .env
BRIGHTDATA_USER=your_username
BRIGHTDATA_PASS=your_password
BRIGHTDATA_ZONE=residential_zone_name

# Formato para Florida + Miami + Zipcode:
# {user}-zone-{zone}-country-us-state-fl-city-miami-zip-33172-session-{random}
""")

print("CÓDIGO DE EJEMPLO:")
print("-" * 80)
print("""
import random

session_id = random.randint(10000, 99999)
proxy_user = f"your_user-zone-residential-country-us-state-fl-zip-33172-session-{session_id}"
proxy_pass = "your_password"

proxies = {
    'http': f'http://{proxy_user}:{proxy_pass}@brd.superproxy.io:22225',
    'https': f'http://{proxy_user}:{proxy_pass}@brd.superproxy.io:22225'
}

response = requests.get(product_url, proxies=proxies, headers=headers)
""")

print()
print("🎯 VENTAJAS:")
print("  ✅ Geo-targeting hasta ZIPCODE nivel (33172!)")
print("  ✅ Máxima precisión de delivery times")
print("  ✅ Muy confiable (usado por empresas Fortune 500)")
print("  ✅ Dashboard con analytics en tiempo real")
print("  ✅ Trial gratis: 7 días")
print()

print("❌ DESVENTAJAS:")
print("  ⚠️ Más caro ($500+/mes)")
print()

print("📝 REGISTRO: https://brightdata.com/")
print()

# ==============================================================================
# OPCIÓN 3: OXYLABS
# ==============================================================================
print("=" * 80)
print("OPCIÓN 3: OXYLABS - Middle Ground")
print("-" * 80)
print("💰 Precio: $300/mes (20GB)")
print("🌍 Geo-targeting: País, Estado, Ciudad")
print("📊 Pool: 100M+ IPs residenciales USA")
print()

print("CONFIGURACIÓN:")
print("-" * 80)
print("""
# .env
OXYLABS_USER=your_username
OXYLABS_PASS=your_password

# Formato para Florida:
# customer-{user}-cc-us-st-fl-city-miami-sessid-{random}
""")

print("CÓDIGO DE EJEMPLO:")
print("-" * 80)
print("""
import random

session_id = random.randint(10000, 99999)
proxy_user = f"customer-your_user-cc-us-st-fl-city-miami-sessid-{session_id}"
proxy_pass = "your_password"

proxies = {
    'http': f'http://{proxy_user}:{proxy_pass}@pr.oxylabs.io:7777',
    'https': f'http://{proxy_user}:{proxy_pass}@pr.oxylabs.io:7777'
}

response = requests.get(product_url, proxies=proxies, headers=headers)
""")

print()
print("🎯 VENTAJAS:")
print("  ✅ Geo-targeting por estado + ciudad")
print("  ✅ Buen balance precio/calidad")
print("  ✅ Trial gratis: 7 días")
print()

print("📝 REGISTRO: https://oxylabs.io/products/residential-proxy-pool")
print()

# ==============================================================================
# COMPARACIÓN Y RECOMENDACIÓN
# ==============================================================================
print("=" * 80)
print("📊 COMPARACIÓN FINAL")
print("=" * 80)
print()

comparison = [
    ["Proveedor", "Precio/mes", "Geo-Level", "Trial", "Recomendación"],
    ["-" * 15, "-" * 12, "-" * 20, "-" * 8, "-" * 30],
    ["Smartproxy", "$75-200", "Estado + Ciudad", "3 días", "⭐ MEJOR PRECIO"],
    ["Bright Data", "$500+", "Estado + Ciudad + ZIP", "7 días", "⭐ MÁS PRECISO (zipcode)"],
    ["Oxylabs", "$300", "Estado + Ciudad", "7 días", "Middle ground"],
]

for row in comparison:
    print(f"{row[0]:15s} {row[1]:12s} {row[2]:20s} {row[3]:8s} {row[4]}")

print()
print("=" * 80)
print("🎯 RECOMENDACIÓN PARA TU CASO:")
print("=" * 80)
print()
print("PARA 50,000 PRODUCTOS:")
print()
print("1️⃣  OPCIÓN ECONÓMICA: SMARTPROXY ($75-150/mes)")
print("   → Geo-targeting Florida + Miami")
print("   → Suficiente precisión para tu caso")
print("   → 8GB = ~40,000 requests (suficiente para tus 50k productos)")
print()
print("2️⃣  OPCIÓN PREMIUM: BRIGHT DATA ($500/mes)")
print("   → Geo-targeting hasta ZIPCODE 33172")
print("   → Máxima precisión (mismo resultado que tu PC)")
print("   → Vale la pena si vas a escalar más (100k+ productos)")
print()

print("=" * 80)
print("🚀 PRÓXIMOS PASOS:")
print("=" * 80)
print()
print("1. Registrate en Smartproxy (trial gratis 3 días)")
print("2. Obtén credentials (user/pass)")
print("3. Ejecuta este comando para probar:")
print()
print("   python3 29_test_smartproxy_real.py")
print()
print("4. Si funciona → implementamos procesamiento paralelo")
print("   → 50,000 productos en ~2 horas")
print()
print("=" * 80)
