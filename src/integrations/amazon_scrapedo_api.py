#!/usr/bin/env python3
"""
Amazon Availability Checker usando Scrape.do
Verifica disponibilidad REAL con soporte de zipcode
"""
import os
import re
import requests
from datetime import datetime
from typing import Optional, Dict
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(override=True)

# Agregar tu API token de Scrape.do aquí después de registrarte
SCRAPEDO_TOKEN = os.getenv("SCRAPEDO_API_TOKEN", "")


def check_real_availability_scrapedo(asin: str, zipcode: str = None) -> Dict:
    """
    Verifica disponibilidad REAL de un producto en Amazon.com
    usando Scrape.do con soporte de zipcode específico.

    Documentación: https://scrape.do/documentation/amazon-scraper-api/

    Args:
        asin: ASIN del producto
        zipcode: Zipcode del comprador (default: desde .env BUYER_ZIPCODE)

    Returns:
        Dict con:
        {
            "available": bool,
            "delivery_date": str,
            "days_until_delivery": int,
            "is_fast_delivery": bool,
            "prime_available": bool,
            "in_stock": bool,
            "price": float,
            "error": str or None
        }
    """
    if not SCRAPEDO_TOKEN:
        return {"error": "SCRAPEDO_API_TOKEN no configurado en .env", "available": False}

    if not zipcode:
        zipcode = os.getenv("BUYER_ZIPCODE", "33172")

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
        # Scrape.do Amazon Scraper API
        # Endpoint: https://api.scrape.do

        url = "https://api.scrape.do"

        params = {
            "token": SCRAPEDO_TOKEN,
            "url": f"https://www.amazon.com/dp/{asin}",
            "render": "true",   # Habilitar JS rendering para que Amazon procese el zipcode
            "geocode": "us",    # Amazon US marketplace
            "zipcode": zipcode  # TU ZIPCODE para fechas de entrega precisas
        }

        print(f"🔍 Scrapeando {asin} con zipcode {zipcode}...")

        response = requests.get(url, params=params, timeout=90)

        if response.status_code != 200:
            result["error"] = f"HTTP {response.status_code}: {response.text[:200]}"
            return result

        html = response.text

        # DEBUG: Guardar HTML para verificar
        with open(f'/tmp/scrapedo_{asin}.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"   HTML guardado en /tmp/scrapedo_{asin}.html")

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
        delivery_patterns = [
            r'(?:Get it|Arrives?|FREE delivery|Delivery)\s+(?:by\s+)?(?:as soon as\s+)?([A-Za-z]+day,?\s+[A-Za-z]+\s+\d+)',
            r'(?:Get it|Arrives?|FREE delivery|Delivery)\s+([A-Za-z]+\s+\d+)',
            r'between\s+([A-Za-z]+,?\s+[A-Za-z]+\s+\d+)\s+(?:and|-)',
        ]

        # Buscar en divs de delivery
        delivery_divs = [
            soup.find('div', {'id': 'deliveryBlockMessage'}),
            soup.find('div', {'id': 'mir-layout-DELIVERY_BLOCK'}),
            soup.find('span', {'data-csa-c-type': 'element', 'data-csa-c-content-id': 'DEXUnifiedCXPDM'}),
            soup.find('div', {'id': 'ddmDeliveryMessage'}),
        ]

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

        # 5. Calcular días hasta entrega
        if result["delivery_date"]:
            try:
                date_str = result["delivery_date"].replace(',', '').strip()
                parts = date_str.split()

                month_name = None
                day_num = None

                months = {
                    'jan': 1, 'january': 1, 'feb': 2, 'february': 2,
                    'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
                    'may': 5, 'jun': 6, 'june': 6,
                    'jul': 7, 'july': 7, 'aug': 8, 'august': 8,
                    'sep': 9, 'september': 9, 'oct': 10, 'october': 10,
                    'nov': 11, 'november': 11, 'dec': 12, 'december': 12
                }

                for part in parts:
                    month_num = months.get(part.lower())
                    if month_num:
                        month_name = month_num

                    try:
                        day_num = int(part)
                    except:
                        pass

                if month_name and day_num:
                    today = datetime.now()
                    year = today.year

                    if month_name < today.month or (month_name == today.month and day_num < today.day):
                        year += 1

                    delivery_date = datetime(year, month_name, day_num)
                    days_until = (delivery_date - today).days

                    result["days_until_delivery"] = days_until

                    if days_until <= 3:
                        result["is_fast_delivery"] = True

            except Exception as e:
                result["error"] = f"Error parsing date: {e}"

        if result["delivery_date"] and result["in_stock"]:
            result["available"] = True

        return result

    except Exception as e:
        result["error"] = str(e)
        return result


if __name__ == "__main__":
    import sys

    test_asin = sys.argv[1] if len(sys.argv) > 1 else "B0FDWT3MXK"

    print("=" * 80)
    print(f"TEST: Verificando disponibilidad con Scrape.do")
    print(f"ASIN: {test_asin}")
    print(f"Zipcode: {os.getenv('BUYER_ZIPCODE', '33172')}")
    print("=" * 80)
    print()

    result = check_real_availability_scrapedo(test_asin)

    print("Resultados:")
    print(f"  ✅ Disponible: {result.get('available', False)}")
    print(f"  📦 In Stock: {result.get('in_stock', False)}")
    print(f"  ⭐ Prime: {result.get('prime_available', False)}")
    print(f"  💰 Precio: ${result['price']}" if result.get('price') else "  💰 Precio: No encontrado")
    print(f"  📅 Fecha entrega: {result.get('delivery_date')}")
    print(f"  ⏱️  Días hasta entrega: {result.get('days_until_delivery')}")
    print(f"  🚀 Fast delivery (≤3d): {result.get('is_fast_delivery', False)}")

    if result['error']:
        print(f"  ⚠️  Error: {result['error']}")

    print()

    # Veredicto
    if result.get('is_fast_delivery'):
        print("✅ ACEPTAR - Llega rápido (≤3 días)")
    elif result.get('days_until_delivery') and result['days_until_delivery'] > 3:
        print(f"❌ RECHAZAR - Tarda {result['days_until_delivery']} días (>3d)")
    else:
        print("⚠️  No se pudo determinar tiempo de entrega")
