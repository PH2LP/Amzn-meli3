#!/usr/bin/env python3
"""
amazon_qa_api_test.py
═══════════════════════════════════════════════════════════════════════════════
PROBADOR DE API DE Q&A DE AMAZON
═══════════════════════════════════════════════════════════════════════════════

Endpoints descubiertos que EXISTEN:
- https://www.amazon.com/hz/askcs/questions (503)
- https://api.amazon.com/questions (403)
- https://www.amazon.com/ap/askcs (503)

Este script prueba diferentes combinaciones de headers y métodos.
"""

import requests
import json

# Endpoints confirmados
ENDPOINTS = {
    "askcs_hz": "https://www.amazon.com/hz/askcs/questions",
    "api_questions": "https://api.amazon.com/questions",
    "ap_askcs": "https://www.amazon.com/ap/askcs",
}

# Headers comunes de Amazon app
COMMON_HEADERS = {
    "User-Agent": "Amazon/2.32.0 CFNetwork/1485 Darwin/23.1.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/json",
}

# Variaciones de headers específicos de Amazon
AMAZON_HEADERS_VARIATIONS = [
    {
        **COMMON_HEADERS,
        "x-amzn-platform": "iOS",
        "x-amzn-app-name": "Amazon Shopping",
        "x-amzn-app-version": "2.32.0",
    },
    {
        **COMMON_HEADERS,
        "x-api-key": "test",  # Placeholder
        "x-amz-access-token": "test",  # Placeholder
    },
    {
        **COMMON_HEADERS,
        "Origin": "https://www.amazon.com",
        "Referer": "https://www.amazon.com/",
    }
]


def test_endpoint(name, url, method="GET", headers=None, data=None):
    """Prueba un endpoint con configuración específica"""
    print(f"\n{'='*80}")
    print(f"🧪 Testing: {name}")
    print(f"URL: {url}")
    print(f"Method: {method}")
    print(f"{'='*80}")

    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=10)
        elif method == "OPTIONS":
            response = requests.options(url, headers=headers, timeout=10)

        print(f"Status Code: {response.status_code}")
        print(f"\nResponse Headers:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")

        # Intentar mostrar body si no es HTML
        content_type = response.headers.get('Content-Type', '')
        if 'json' in content_type.lower():
            try:
                print(f"\nResponse Body (JSON):")
                print(json.dumps(response.json(), indent=2)[:1000])
            except:
                print(f"\nResponse Body (Text):")
                print(response.text[:500])
        elif 'html' not in content_type.lower():
            print(f"\nResponse Body:")
            print(response.text[:500])

        return response

    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_askcs_with_asin(asin="B0CYM126TT"):
    """Prueba el endpoint askcs con un ASIN específico"""
    print(f"\n{'#'*80}")
    print(f"🎯 TESTING ASKCS WITH ASIN: {asin}")
    print(f"{'#'*80}")

    # Probar diferentes variantes de URL
    url_variations = [
        f"https://www.amazon.com/hz/askcs/questions?asin={asin}",
        f"https://www.amazon.com/hz/askcs/questions/{asin}",
        f"https://www.amazon.com/askcs/questions/{asin}",
        f"https://api.amazon.com/questions?asin={asin}",
        f"https://api.amazon.com/questions/{asin}",
    ]

    for url in url_variations:
        for idx, headers in enumerate(AMAZON_HEADERS_VARIATIONS, 1):
            test_endpoint(
                f"URL variant with headers #{idx}",
                url,
                method="GET",
                headers=headers
            )

    # Probar POST con pregunta simulada
    print(f"\n{'#'*80}")
    print("🎯 TESTING POST REQUEST (Simular pregunta)")
    print(f"{'#'*80}")

    post_data = {
        "asin": asin,
        "question": "Is this product waterproof?",
        "questionText": "Is this product waterproof?",
        "marketplace": "ATVPDKIKX0DER"  # US marketplace
    }

    for endpoint_name, url in ENDPOINTS.items():
        for idx, headers in enumerate(AMAZON_HEADERS_VARIATIONS, 1):
            test_endpoint(
                f"{endpoint_name} POST with headers #{idx}",
                url,
                method="POST",
                headers=headers,
                data=post_data
            )


def test_options_requests():
    """Prueba OPTIONS para descubrir métodos permitidos"""
    print(f"\n{'#'*80}")
    print("🔍 TESTING OPTIONS (CORS)")
    print(f"{'#'*80}")

    for name, url in ENDPOINTS.items():
        test_endpoint(
            f"{name} OPTIONS",
            url,
            method="OPTIONS",
            headers=COMMON_HEADERS
        )


def main():
    print("""
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║         AMAZON Q&A API ENDPOINT DISCOVERY TOOL                 ║
║                                                                ║
║  Descubriendo endpoints no documentados de Amazon Q&A         ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
    """)

    print("\n🎯 PASO 1: Probar OPTIONS requests")
    test_options_requests()

    print("\n🎯 PASO 2: Probar con ASIN específico")
    test_askcs_with_asin("B0CYM126TT")  # LEGO product

    print(f"\n{'='*80}")
    print("✅ PRUEBAS COMPLETADAS")
    print(f"{'='*80}")
    print("\n💡 PRÓXIMOS PASOS:")
    print("1. Si encontraste un endpoint que retorna 200, analiza el formato de respuesta")
    print("2. Intercepta el tráfico de la app móvil con mitmproxy para ver headers reales")
    print("3. Los headers x-api-key y x-amz-access-token probablemente vienen del login")
    print("\n⚠️  IMPORTANTE: Usar estos endpoints puede violar ToS de Amazon")


if __name__ == "__main__":
    main()
