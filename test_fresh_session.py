#!/usr/bin/env python3
"""
TEST: Generar sesión FRESCA con curl_cffi sin cookies previas

El problema anterior: Usamos cookies generadas por un browser real (Chrome),
luego las reusamos con curl_cffi. Amazon detecta el cambio de fingerprint.

Solución: Generar cookies NUEVAS directamente con curl_cffi desde cero.
"""

from curl_cffi import requests
import json

print("=" * 80)
print("TEST: Generar sesión FRESCA con curl_cffi (sin cookies previas)")
print("=" * 80)
print()

# TEST ASIN
TEST_ASIN = "B07CTLNYVV"
url = f"https://www.amazon.com/dp/{TEST_ASIN}"

print("1️⃣  CREAR SESIÓN FRESCA CON CURL_CFFI")
print("-" * 80)

# Crear una sesión persistente
session = requests.Session()

# Headers básicos que usa Chrome
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
}

try:
    # Paso 1: Visitar homepage primero para generar cookies iniciales
    print("   📍 Visitando homepage para generar cookies...")
    response_home = session.get(
        "https://www.amazon.com",
        headers=headers,
        impersonate="chrome120",
        timeout=15
    )
    print(f"   ✅ Homepage: {response_home.status_code}")
    print(f"   📦 Cookies recibidas: {len(session.cookies)} cookies")

    # Mostrar cookies
    for cookie in session.cookies:
        print(f"      - {cookie.name}: {cookie.value[:30]}...")

    print()

    # Paso 2: Ahora intentar acceder al producto
    print("   📍 Accediendo al producto...")
    response_product = session.get(
        url,
        headers=headers,
        impersonate="chrome120",
        timeout=15
    )

    html = response_product.text

    # Verificar si está bloqueado
    if 'captcha' in html.lower() or 'robot check' in html.lower():
        print("   ❌ BLOQUEADO - Captcha detectado")
        print(f"   📏 Tamaño HTML: {len(html)} bytes")

        # Guardar para inspección
        with open('/tmp/curl_cffi_fresh_blocked.html', 'w') as f:
            f.write(html)
        print(f"   💾 HTML guardado en: /tmp/curl_cffi_fresh_blocked.html")

        # Intentar resolver el CAPTCHA automáticamente
        print()
        print("2️⃣  INTENTAR RESOLVER CAPTCHA AUTOMÁTICAMENTE")
        print("-" * 80)

        # Extraer parámetros del form
        import re
        amzn_match = re.search(r'name="amzn" value="([^"]+)"', html)
        amzn_r_match = re.search(r'name="amzn-r" value="([^"]+)"', html)
        field_keywords_match = re.search(r'name="field-keywords" value="([^"]+)"', html)

        if amzn_match and amzn_r_match:
            amzn = amzn_match.group(1)
            amzn_r = amzn_r_match.group(1).replace('&#047;', '/')
            field_keywords = field_keywords_match.group(1) if field_keywords_match else ""

            print(f"   📋 Parámetros extraídos:")
            print(f"      amzn: {amzn}")
            print(f"      amzn-r: {amzn_r}")
            print(f"      field-keywords: {field_keywords}")
            print()

            # Hacer GET a /errors/validateCaptcha
            captcha_url = f"https://www.amazon.com/errors/validateCaptcha?amzn={amzn}&amzn-r={amzn_r}&field-keywords={field_keywords}"

            print(f"   📍 Resolviendo CAPTCHA...")
            response_captcha = session.get(
                captcha_url,
                headers=headers,
                impersonate="chrome120",
                timeout=15,
                allow_redirects=True
            )

            print(f"   ✅ Respuesta: {response_captcha.status_code}")
            print(f"   📍 URL final: {response_captcha.url}")

            html_after = response_captcha.text

            # Verificar si ahora funciona
            if 'captcha' not in html_after.lower() and 'robot check' not in html_after.lower():
                print(f"   ✅ CAPTCHA RESUELTO!")
                print(f"   📏 Tamaño HTML: {len(html_after)} bytes")

                # Verificar contenido
                has_price = '$' in html_after and 'a-price' in html_after
                has_delivery = 'delivery' in html_after.lower()

                print(f"   💰 Tiene precio: {'✅' if has_price else '❌'}")
                print(f"   🚚 Tiene delivery: {'✅' if has_delivery else '❌'}")

                with open('/tmp/curl_cffi_fresh_success.html', 'w') as f:
                    f.write(html_after)
                print(f"   💾 HTML guardado en: /tmp/curl_cffi_fresh_success.html")
            else:
                print(f"   ❌ Sigue bloqueado")
                print(f"   📏 Tamaño HTML: {len(html_after)} bytes")
                with open('/tmp/curl_cffi_fresh_captcha_retry.html', 'w') as f:
                    f.write(html_after)
                print(f"   💾 HTML guardado en: /tmp/curl_cffi_fresh_captcha_retry.html")
        else:
            print("   ❌ No se pudieron extraer parámetros del CAPTCHA")

    else:
        print("   ✅ NO BLOQUEADO!")
        print(f"   📏 Tamaño HTML: {len(html)} bytes")

        # Verificar contenido
        has_price = '$' in html and 'a-price' in html
        has_delivery = 'delivery' in html.lower()

        print(f"   💰 Tiene precio: {'✅' if has_price else '❌'}")
        print(f"   🚚 Tiene delivery: {'✅' if has_delivery else '❌'}")

        with open('/tmp/curl_cffi_fresh_success.html', 'w') as f:
            f.write(html)
        print(f"   💾 HTML guardado en: /tmp/curl_cffi_fresh_success.html")

        # Guardar cookies generadas
        cookies_dict = {}
        for cookie in session.cookies:
            cookies_dict[cookie.name] = {
                'value': cookie.value,
                'domain': cookie.domain,
                'path': cookie.path,
                'secure': cookie.secure,
                'expires': cookie.expires
            }

        with open('/tmp/curl_cffi_fresh_cookies.json', 'w') as f:
            json.dump(cookies_dict, f, indent=2)
        print(f"   💾 Cookies guardadas en: /tmp/curl_cffi_fresh_cookies.json")

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("✅ Test completado")
print("=" * 80)
