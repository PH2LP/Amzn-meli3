#!/usr/bin/env python3
"""
Amazon Availability Checker usando undetected-chromedriver + Prime cookies
✅ SOLUCIÓN REAL para detectar fechas Prime correctas
✅ Bypassa detección de bots de Amazon
✅ Usa cookies Prime para ver fechas reales
⚠️  Más lento (~15s) pero PRECISO

Este es el ÚNICO método que funciona con cookies Prime.
Amazon detecta y rechaza cookies cuando usas `requests` library.
"""
import os
import pickle
import time
import re
from datetime import datetime
from typing import Dict

try:
    import undetected_chromedriver as uc
except ImportError:
    print("⚠️  undetected-chromedriver no instalado. Instalando...")
    import subprocess
    subprocess.check_call(['pip3', 'install', 'undetected-chromedriver'])
    import undetected_chromedriver as uc


def check_real_availability_undetected(asin: str, zipcode: str = None) -> Dict:
    """
    Verifica disponibilidad REAL usando undetected-chromedriver + cookies Prime.

    IMPORTANTE: Este método es más lento (~15s) pero es el ÚNICO que funciona
    correctamente con cookies Prime. Amazon detecta y bloquea requests library.

    Args:
        asin: ASIN del producto
        zipcode: Zipcode del comprador (default: desde .env BUYER_ZIPCODE)

    Returns:
        Dict con disponibilidad, fecha de entrega, días, Prime status, etc.
    """
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

    driver = None
    try:
        # Configurar navegador undetected
        options = uc.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')

        driver = uc.Chrome(options=options, use_subprocess=True)
        time.sleep(2)

        # Ir a Amazon
        driver.get("https://www.amazon.com")
        time.sleep(3)

        # Cargar cookies Prime
        cookies_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "storage",
            "amazon_cookies.pkl"
        )

        if os.path.exists(cookies_file):
            with open(cookies_file, 'rb') as f:
                cookies = pickle.load(f)

            for cookie in cookies:
                try:
                    driver.add_cookie({
                        'name': cookie['name'],
                        'value': cookie['value'],
                        'domain': cookie.get('domain', '.amazon.com'),
                        'path': cookie.get('path', '/'),
                        'secure': cookie.get('secure', False),
                    })
                except:
                    pass

        # Ir al producto
        url = f"https://www.amazon.com/dp/{asin}"
        driver.get(url)
        time.sleep(4)

        # Cambiar zipcode usando Glow API
        try:
            script = f"""
            fetch('https://www.amazon.com/portal-migration/hz/glow/address-change?actionSource=glow&deviceType=desktop&pageType=Detail&storeContext=pc', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }},
                body: JSON.stringify({{
                    'locationType': 'LOCATION_INPUT',
                    'zipCode': '{zipcode}',
                    'deviceType': 'web',
                    'storeContext': 'generic',
                    'pageType': 'Detail'
                }})
            }}).then(() => location.reload());
            """
            driver.execute_script(script)
            time.sleep(6)
        except:
            pass

        # Extraer HTML
        html = driver.page_source

        # 1. Verificar Prime
        if 'prime' in html.lower() or 'a-icon-prime' in html:
            result["prime_available"] = True

        # 2. Extraer precio
        price_patterns = [
            r'<span class="a-price-whole">([0-9,]+)<',
            r'"price":\s*"\\?\$?([0-9,.]+)"',
        ]

        for pattern in price_patterns:
            match = re.search(pattern, html)
            if match:
                try:
                    price_str = match.group(1).replace(',', '')
                    result["price"] = float(price_str)
                    break
                except:
                    pass

        # 3. Verificar stock
        if 'in stock' in html.lower():
            result["in_stock"] = True
            result["available"] = True
        elif 'currently unavailable' in html.lower() or 'out of stock' in html.lower():
            result["available"] = False
            result["error"] = "Out of stock"
            return result

        # 4. Buscar fecha de entrega
        delivery_patterns = [
            # FREE delivery <span class="a-text-bold">Monday, December 22</span>
            r'FREE delivery.*?<span class="a-text-bold">([^<]+)</span>',
            # Cualquier span bold con fecha
            r'<span class="a-text-bold">([A-Za-z]+,?\s+[A-Za-z]+\s+\d+)</span>',
            # Texto plano (fallback)
            r'(?:Get it|Arrives?|FREE delivery|Delivery)\s+(?:by\s+)?(?:as soon as\s+)?([A-Za-z]+day,?\s+[A-Za-z]+\s+\d+)',
            r'(?:Get it|Arrives?|FREE delivery|Delivery)\s+([A-Za-z]+\s+\d+)',
        ]

        for pattern in delivery_patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                result["delivery_date"] = match.group(1).strip()
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

                    max_delivery_days = int(os.getenv("MAX_DELIVERY_DAYS", "2"))
                    if days_until <= max_delivery_days:
                        result["is_fast_delivery"] = True

            except Exception as e:
                result["error"] = f"Error parsing date: {e}"

        if result["delivery_date"] and result["in_stock"]:
            result["available"] = True

        return result

    except Exception as e:
        result["error"] = str(e)
        return result

    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


# Alias para compatibilidad con código existente
check_real_availability_glow_api = check_real_availability_undetected
