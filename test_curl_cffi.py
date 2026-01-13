#!/usr/bin/env python3
"""
TEST: curl_cffi vs requests - Comparación de bloqueos de Amazon

Este script testea si curl_cffi con impersonate='chrome120' puede bypasear
el CAPTCHA de Amazon que requests recibe.
"""

import json
from curl_cffi import requests as curl_requests
import requests as std_requests

# Cargar cookies Prime
with open('cache/amazon_session_cookies.json') as f:
    amazon_cookies = json.load(f)
    cookies_dict = {name: data['value'] for name, data in amazon_cookies.items()}

# ASIN que actualmente está bloqueado
TEST_ASIN = "B07CTLNYVV"  # Uno de los que falló
url = f"https://www.amazon.com/dp/{TEST_ASIN}"

print("=" * 80)
print("TEST: curl_cffi vs requests")
print("=" * 80)
print()

# TEST 1: requests estándar (debería bloquearse)
print("1️⃣  TEST CON REQUESTS ESTÁNDAR")
print("-" * 80)
try:
    response1 = std_requests.get(url, cookies=cookies_dict, timeout=15)
    html1 = response1.text

    if 'captcha' in html1.lower() or 'robot check' in html1.lower():
        print("❌ BLOQUEADO - Captcha detectado")
        print(f"   Tamaño HTML: {len(html1)} bytes")
    else:
        print(f"✅ NO BLOQUEADO - Tamaño HTML: {len(html1)} bytes")
except Exception as e:
    print(f"❌ Error: {e}")

print()
print("2️⃣  TEST CON CURL_CFFI (impersonate=chrome120)")
print("-" * 80)
try:
    response2 = curl_requests.get(
        url,
        cookies=cookies_dict,
        impersonate="chrome120",  # ← CLAVE: Fingerprint de Chrome 120
        timeout=15
    )
    html2 = response2.text

    if 'captcha' in html2.lower() or 'robot check' in html2.lower():
        print("❌ BLOQUEADO - Captcha detectado")
        print(f"   Tamaño HTML: {len(html2)} bytes")
        # Guardar para inspección
        with open('/tmp/curl_cffi_blocked.html', 'w') as f:
            f.write(html2)
        print(f"   HTML guardado en: /tmp/curl_cffi_blocked.html")
    else:
        print(f"✅ NO BLOQUEADO - Tamaño HTML: {len(html2)} bytes")

        # Verificar si tiene precio y delivery
        has_price = '$' in html2 and 'a-price' in html2
        has_delivery = 'delivery' in html2.lower() or 'shipping' in html2.lower()

        print(f"   Tiene precio: {'✅' if has_price else '❌'}")
        print(f"   Tiene delivery: {'✅' if has_delivery else '❌'}")

        # Guardar para inspección
        with open('/tmp/curl_cffi_success.html', 'w') as f:
            f.write(html2)
        print(f"   HTML guardado en: /tmp/curl_cffi_success.html")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("✅ Test completado")
print("=" * 80)
