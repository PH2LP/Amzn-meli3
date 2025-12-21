#!/usr/bin/env python3
"""
Amazon Availability Checker usando ScraperAPI
Verifica disponibilidad REAL de productos en Amazon.com
"""
import os
import re
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict
from bs4 import BeautifulSoup

SCRAPERAPI_KEY = "67463e2c254c24bf2980d50c5d62953d"


def check_real_availability_scraperapi(asin: str, zipcode: str = None) -> Dict:
    """
    Verifica disponibilidad REAL de un producto en Amazon.com
    usando ScraperAPI para bypass anti-bot.

    Args:
        asin: ASIN del producto
        zipcode: Zipcode del comprador (default: desde .env BUYER_ZIPCODE)

    Returns:
        Dict con:
        {
            "available": bool,
            "delivery_date": str,
            "days_until_delivery": int,
            "is_fast_delivery": bool,  # True si llega en ≤3 días
            "prime_available": bool,
            "in_stock": bool,
            "price": float,
            "error": str or None
        }
    """
    if not zipcode:
        zipcode = os.getenv("BUYER_ZIPCODE", "33172")

    # URL de Amazon con el ASIN
    amazon_url = f"https://www.amazon.com/dp/{asin}"

    result = {
        "available": False,
        "delivery_date": None,
        "days_until_delivery": None,
        "is_fast_delivery": False,
        "prime_available": False,
        "in_stock": False,
        "price": None,
        "error": None
    }

    try:
        # Request usando ScraperAPI con ZIP code targeting
        # Documentación: https://docs.scraperapi.com/making-requests/customizing-requests/amazon-zip-code-targeting

        payload = {
            'api_key': SCRAPERAPI_KEY,
            'url': amazon_url,
            'zip': zipcode,  # ZIP code targeting
            'country_code': 'us',
            'premium': 'true',  # Amazon requiere premium proxies
            'render': 'false'
        }

        response = requests.get(
            'https://api.scraperapi.com/',
            params=payload,
            timeout=60
        )

        if response.status_code != 200:
            result["error"] = f"HTTP {response.status_code}"
            return result

        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        # 1. Verificar si tiene Prime badge
        prime_badge = soup.find('i', {'class': 'a-icon-prime'})
        if prime_badge:
            result["prime_available"] = True

        # 2. Verificar precio
        price_whole = soup.find('span', {'class': 'a-price-whole'})
        price_fraction = soup.find('span', {'class': 'a-price-fraction'})

        if price_whole:
            try:
                whole = price_whole.get_text().strip().replace(',', '').replace('.', '')
                fraction = price_fraction.get_text().strip() if price_fraction else "00"
                result["price"] = float(f"{whole}.{fraction}")
            except:
                pass

        # 3. Verificar disponibilidad (In Stock)
        availability_div = soup.find('div', {'id': 'availability'})
        if availability_div:
            text = availability_div.get_text().strip().lower()

            if 'in stock' in text:
                result["in_stock"] = True
                result["available"] = True
            elif 'currently unavailable' in text or 'out of stock' in text:
                result["available"] = False
                result["error"] = "Out of stock"
                return result

        # 4. Buscar fecha de entrega estimada
        # Patrones comunes en Amazon:
        # - "Get it by Thursday, Jan 15"
        # - "Arrives Thursday, Jan 15"
        # - "Delivery Jan 15 - Jan 18"
        # - "FREE delivery Monday, December 23"

        delivery_patterns = [
            r'(?:Get it|Arrives?|FREE delivery|Delivery)\s+(?:by\s+)?(?:as soon as\s+)?([A-Za-z]+day,?\s+[A-Za-z]+\s+\d+)',
            r'(?:Get it|Arrives?|FREE delivery|Delivery)\s+([A-Za-z]+\s+\d+)',
            r'between\s+([A-Za-z]+,?\s+[A-Za-z]+\s+\d+)\s+(?:and|-)',
        ]

        # Buscar en múltiples divs de delivery
        delivery_divs = [
            soup.find('div', {'id': 'deliveryBlockMessage'}),
            soup.find('div', {'id': 'mir-layout-DELIVERY_BLOCK'}),
            soup.find('span', {'data-csa-c-type': 'element', 'data-csa-c-content-id': 'DEXUnifiedCXPDM'}),
            soup.find('div', {'id': 'ddmDeliveryMessage'}),
        ]

        # También buscar en todo el HTML por si acaso
        full_text = soup.get_text()

        for div in delivery_divs:
            if not div:
                continue

            delivery_text = div.get_text()

            for pattern in delivery_patterns:
                match = re.search(pattern, delivery_text, re.IGNORECASE)
                if match:
                    result["delivery_date"] = match.group(1).strip()
                    break

            if result["delivery_date"]:
                break

        # Si no encontramos en divs específicos, buscar en todo el texto
        if not result["delivery_date"]:
            for pattern in delivery_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    result["delivery_date"] = match.group(1).strip()
                    break

        # 5. Calcular días hasta entrega
        if result["delivery_date"]:
            try:
                # Limpiar la fecha
                date_str = result["delivery_date"].replace(',', '').strip()
                parts = date_str.split()

                # Extraer mes y día
                month_name = None
                day_num = None

                for part in parts:
                    # Intentar parsear como mes
                    months = {
                        'jan': 1, 'january': 1,
                        'feb': 2, 'february': 2,
                        'mar': 3, 'march': 3,
                        'apr': 4, 'april': 4,
                        'may': 5,
                        'jun': 6, 'june': 6,
                        'jul': 7, 'july': 7,
                        'aug': 8, 'august': 8,
                        'sep': 9, 'september': 9,
                        'oct': 10, 'october': 10,
                        'nov': 11, 'november': 11,
                        'dec': 12, 'december': 12
                    }

                    month_num = months.get(part.lower())
                    if month_num:
                        month_name = month_num

                    # Intentar parsear como día
                    try:
                        day_num = int(part)
                    except:
                        pass

                if month_name and day_num:
                    # Determinar año
                    today = datetime.now()
                    year = today.year

                    # Si el mes ya pasó este año, asumir año siguiente
                    if month_name < today.month or (month_name == today.month and day_num < today.day):
                        year += 1

                    delivery_date = datetime(year, month_name, day_num)
                    days_until = (delivery_date - today).days

                    result["days_until_delivery"] = days_until

                    # Fast delivery = llega en ≤3 días
                    if days_until <= 3:
                        result["is_fast_delivery"] = True

            except Exception as e:
                # Error parseando fecha, no es crítico
                result["error"] = f"Error parsing date: {e}"

        # Si encontramos fecha de entrega y está en stock, confirmar disponible
        if result["delivery_date"] and result["in_stock"]:
            result["available"] = True

        return result

    except Exception as e:
        result["error"] = str(e)
        return result


if __name__ == "__main__":
    # Test
    import sys

    test_asin = sys.argv[1] if len(sys.argv) > 1 else "B0FDWT3MXK"

    print("=" * 80)
    print(f"TEST: Verificando disponibilidad REAL con ScraperAPI")
    print(f"ASIN: {test_asin}")
    print("=" * 80)
    print()

    result = check_real_availability_scraperapi(test_asin)

    print("Resultados:")
    print(f"  ✅ Disponible: {result['available']}")
    print(f"  📦 In Stock: {result['in_stock']}")
    print(f"  ⭐ Prime: {result['prime_available']}")
    print(f"  💰 Precio: ${result['price']}" if result['price'] else "  💰 Precio: No encontrado")
    print(f"  📅 Fecha entrega: {result['delivery_date']}")
    print(f"  ⏱️  Días hasta entrega: {result['days_until_delivery']}")
    print(f"  🚀 Fast delivery (≤3d): {result['is_fast_delivery']}")

    if result['error']:
        print(f"  ⚠️  Error: {result['error']}")

    print()

    # Veredicto final
    if result['is_fast_delivery']:
        print("✅ ACEPTAR - Llega rápido (≤3 días)")
    elif result['days_until_delivery'] and result['days_until_delivery'] > 3:
        print(f"❌ RECHAZAR - Tarda {result['days_until_delivery']} días (>3d)")
    else:
        print("⚠️  No se pudo determinar tiempo de entrega")
