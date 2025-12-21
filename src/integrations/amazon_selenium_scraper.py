#!/usr/bin/env python3
"""
Amazon Availability Checker usando Selenium
ÚNICA SOLUCIÓN que respeta el zipcode correctamente
"""
import os
import re
from datetime import datetime
from typing import Optional, Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time


def check_real_availability_selenium(asin: str, zipcode: str = None) -> Dict:
    """
    Verifica disponibilidad REAL de un producto en Amazon.com
    usando Selenium para configurar el delivery location correctamente.

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
        # Configurar Chrome en headless mode
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')

        driver = webdriver.Chrome(options=chrome_options)
        wait = WebDriverWait(driver, 15)

        # Paso 1: Abrir Amazon homepage
        driver.get("https://www.amazon.com")
        time.sleep(2)

        # Paso 2: Configurar delivery location
        try:
            # Click en el widget de delivery
            deliver_button = wait.until(
                EC.element_to_be_clickable((By.ID, "nav-global-location-popover-link"))
            )
            deliver_button.click()
            time.sleep(1)

            # Ingresar zipcode
            zipcode_input = wait.until(
                EC.presence_of_element_located((By.ID, "GLUXZipUpdateInput"))
            )
            zipcode_input.clear()
            zipcode_input.send_keys(zipcode)

            # Click en Apply
            apply_button = driver.find_element(By.CSS_SELECTOR, "input[aria-labelledby='GLUXZipUpdate-announce']")
            apply_button.click()
            time.sleep(3)

        except Exception as e:
            result["error"] = f"No se pudo configurar zipcode: {e}"
            # Intentar continuar de todas formas

        # Paso 3: Navegar al producto
        driver.get(f"https://www.amazon.com/dp/{asin}")
        time.sleep(3)

        html = driver.page_source

        # DEBUG: Guardar HTML para inspección
        import tempfile
        with open(f'/tmp/selenium_debug_{asin}.html', 'w', encoding='utf-8') as f:
            f.write(html)

        # Verificar que el zipcode esté configurado correctamente
        try:
            location_element = driver.find_element(By.ID, "contextualIngressPtLabel_deliveryShortLine")
            location_text = location_element.text

            if zipcode not in location_text and zipcode not in html:
                result["error"] = f"Zipcode no configurado correctamente. Location: {location_text}"
        except:
            pass

        # 1. Verificar Prime
        if "prime" in html.lower():
            result["prime_available"] = True

        # 2. Extraer precio
        price_patterns = [
            r'<span class="a-price-whole">([0-9,]+)<',
            r'"price":\s*"\\$([0-9,.]+)"',
            r'US\$\s*([0-9,.]+)'
        ]

        for pattern in price_patterns:
            match = re.search(pattern, html)
            if match:
                try:
                    price_str = match.group(1).replace(',', '').replace('.', '')
                    if len(price_str) >= 2:
                        # Separar últimos 2 dígitos como centavos
                        dollars = price_str[:-2] if len(price_str) > 2 else "0"
                        cents = price_str[-2:]
                        result["price"] = float(f"{dollars}.{cents}")
                        break
                except:
                    pass

        # 3. Verificar disponibilidad (In Stock)
        availability_indicators = [
            "in stock",
            "en stock",
            "disponible",
            "available",
            "queda(n)",  # "Solo queda(n) X en stock"
            "quedán",
            "quedan"
        ]

        html_lower = html.lower()
        for indicator in availability_indicators:
            if indicator in html_lower:
                result["in_stock"] = True
                result["available"] = True
                break

        # Verificar indisponibilidad SOLO si no encontramos stock
        if not result["in_stock"]:
            unavailable_indicators = [
                "currently unavailable",
                "out of stock",
                "no disponible",
                "agotado",
                "sin stock"
            ]

            for indicator in unavailable_indicators:
                if indicator in html_lower:
                    result["available"] = False
                    result["error"] = "Out of stock"
                    return result

        # 4. Buscar fecha de entrega (buscar en divs específicos primero)
        delivery_date_found = False

        # Intentar con divs específicos primero
        try:
            delivery_divs = driver.find_elements(By.ID, "deliveryBlockMessage")
            if not delivery_divs:
                delivery_divs = driver.find_elements(By.ID, "mir-layout-DELIVERY_BLOCK")

            for div in delivery_divs:
                div_text = div.text

                # Patrones en español e inglés
                date_patterns = [
                    # Español: "el sábado, 27 de diciembre"
                    r'el\s+((?:lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo),?\s+\d+\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre))',
                    # Inglés: "Wednesday, December 24"
                    r'((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+)',
                    # "Get it by Wednesday, December 24"
                    r'(?:Get it|Arrives?|FREE delivery|Delivery|Recíbelo)\s+(?:by\s+|el\s+)?((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo),?\s+(?:\d+\s+(?:de\s+)?)?(?:January|February|March|April|May|June|July|August|September|October|November|December|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+\d+)',
                ]

                for pattern in date_patterns:
                    match = re.search(pattern, div_text, re.IGNORECASE)
                    if match:
                        result["delivery_date"] = match.group(1).strip()
                        delivery_date_found = True
                        break

                if delivery_date_found:
                    break

        except Exception as e:
            pass

        # Si no encontramos en divs, buscar en todo el HTML
        if not delivery_date_found:
            delivery_patterns = [
                # Español
                r'el\s+((?:lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo),?\s+\d+\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre))',
                # Inglés
                r'((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+)',
            ]

            for pattern in delivery_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    result["delivery_date"] = match.group(1).strip()
                    break

        # 5. Calcular días hasta entrega
        if result["delivery_date"]:
            try:
                date_str = result["delivery_date"].replace(',', '').strip()

                # Normalizar fecha
                # Español -> Inglés
                months_es = {
                    'enero': 'January', 'febrero': 'February', 'marzo': 'March',
                    'abril': 'April', 'mayo': 'May', 'junio': 'June',
                    'julio': 'July', 'agosto': 'August', 'septiembre': 'September',
                    'octubre': 'October', 'noviembre': 'November', 'diciembre': 'December'
                }

                for es, en in months_es.items():
                    date_str = date_str.replace(es, en)

                # Remover "de" si existe
                date_str = date_str.replace(' de ', ' ')

                parts = date_str.split()

                # Extraer mes y día
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
                result["error"] = f"Error parsing date: {e}"

        # Si encontramos fecha de entrega y está en stock, confirmar disponible
        if result["delivery_date"] and result["in_stock"]:
            result["available"] = True

        return result

    except Exception as e:
        result["error"] = str(e)
        return result

    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    import sys

    test_asin = sys.argv[1] if len(sys.argv) > 1 else "B0FDWT3MXK"
    test_zipcode = sys.argv[2] if len(sys.argv) > 2 else os.getenv("BUYER_ZIPCODE", "33172")

    print("=" * 80)
    print(f"TEST: Verificando disponibilidad REAL con Selenium")
    print(f"ASIN: {test_asin}")
    print(f"Zipcode: {test_zipcode}")
    print("=" * 80)
    print()

    result = check_real_availability_selenium(test_asin, test_zipcode)

    print("Resultados:")
    print(f"  ✅ Disponible: {result.get('available', False)}")
    print(f"  📦 In Stock: {result.get('in_stock', False)}")
    print(f"  ⭐ Prime: {result.get('prime_available', False)}")
    print(f"  💰 Precio: ${result['price']}" if result.get('price') else "  💰 Precio: No encontrado")
    print(f"  📅 Fecha entrega: {result.get('delivery_date')}")
    print(f"  ⏱️  Días hasta entrega: {result.get('days_until_delivery')}")
    print(f"  🚀 Fast delivery (≤3d): {result.get('is_fast_delivery', False)}")

    if result.get('error'):
        print(f"  ⚠️  Error: {result['error']}")

    print()

    # Veredicto
    max_days = int(os.getenv("MAX_DELIVERY_DAYS", "3"))

    if result.get('is_fast_delivery'):
        print(f"✅ ACEPTAR - Llega rápido (≤{max_days} días)")
    elif result.get('days_until_delivery') and result['days_until_delivery'] > max_days:
        print(f"❌ RECHAZAR - Tarda {result['days_until_delivery']} días (>{max_days}d)")
    else:
        print("⚠️  No se pudo determinar tiempo de entrega")
