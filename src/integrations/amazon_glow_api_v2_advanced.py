#!/usr/bin/env python3
"""
Amazon Glow API v2 - Advanced Anti-Detection System

Sistema profesional de scraping con técnicas de ingeniería para evitar bloqueos:
- Session Rotation (nueva sesión cada 100 requests)
- Exponential Backoff con Jitter
- Randomized request timing
- Token Bucket respecting

Basado en investigación de AWS WAF Bot Control y Amazon rate limiting.
"""

import os
import re
import requests
import random
import time
import hashlib
from datetime import datetime
from typing import Optional, Dict, List
from bs4 import BeautifulSoup

# Lista expandida de User-Agents (rotar para simular múltiples usuarios)
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
]

# === CONFIGURACIÓN DE RATE LIMITING ===
BASE_DELAY = 2.0  # Respetar refill rate de Amazon (~0.5 req/sec)
JITTER_RANGE = 0.4  # ±20% variación (1.6-2.4s)

# === SESSION MANAGEMENT ===
MAX_REQUESTS_PER_SESSION = 100  # Nueva sesión cada 100 requests
SESSION_COOLDOWN = 30  # 30s entre fin de sesión y nueva sesión

# === EXPONENTIAL BACKOFF ===
INITIAL_BACKOFF = 5  # Primer retry después de 5s
MAX_BACKOFF = 120  # Máximo 2 minutos de backoff
BACKOFF_MULTIPLIER = 2  # Duplicar cada retry
MAX_RETRIES = 3  # Máximo 3 reintentos


class SessionRotator:
    """
    Gestiona rotación de sesiones para evitar tracking de Amazon.

    Cada sesión tiene:
    - Nuevo User-Agent
    - Nuevas cookies
    - Headers ligeramente diferentes
    """

    def __init__(self):
        self.session = None
        self.request_count = 0
        self.session_created_at = None

    def get_session(self) -> requests.Session:
        """Obtiene sesión actual o crea nueva si es necesario"""

        # Crear nueva sesión si:
        # 1. No hay sesión
        # 2. Se excedió MAX_REQUESTS_PER_SESSION
        if self.session is None or self.request_count >= MAX_REQUESTS_PER_SESSION:
            # Si hay sesión anterior, esperar cooldown
            if self.session is not None:
                elapsed = time.time() - self.session_created_at
                if elapsed < SESSION_COOLDOWN:
                    wait = SESSION_COOLDOWN - elapsed
                    print(f"   🔄 Session rotation cooldown: {wait:.1f}s...")
                    time.sleep(wait)

            # Crear nueva sesión
            self.session = requests.Session()
            self.session_created_at = time.time()
            self.request_count = 0

            # User-Agent aleatorio
            user_agent = random.choice(USER_AGENTS)

            # Accept-Language aleatorio (simula diferentes regiones)
            accept_languages = [
                'en-US,en;q=0.9',
                'en-GB,en;q=0.8',
                'en-US,en;q=0.8,es;q=0.6',
            ]

            self.session.headers.update({
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': random.choice(accept_languages),
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            })

            print(f"   🆕 Nueva sesión creada (User-Agent: {user_agent[:50]}...)")

        self.request_count += 1
        return self.session

    def reset(self):
        """Forzar reset de sesión"""
        self.session = None
        self.request_count = 0


class RateLimiter:
    """
    Implementa rate limiting inteligente con:
    - Respeto al Token Bucket de Amazon
    - Jitter para simular comportamiento humano
    - Exponential backoff en caso de bloqueo
    """

    def __init__(self):
        self.last_request_time = 0

    def wait(self):
        """Espera el tiempo necesario antes del próximo request"""

        # Calcular delay con jitter
        delay = BASE_DELAY * random.uniform(1 - JITTER_RANGE/2, 1 + JITTER_RANGE/2)

        # Si es el primer request, no esperar
        if self.last_request_time == 0:
            self.last_request_time = time.time()
            return

        # Calcular tiempo desde último request
        elapsed = time.time() - self.last_request_time

        # Si no pasó suficiente tiempo, esperar
        if elapsed < delay:
            wait_time = delay - elapsed
            time.sleep(wait_time)

        self.last_request_time = time.time()


# Instancias globales (singleton)
_session_rotator = SessionRotator()
_rate_limiter = RateLimiter()


def extract_delivery_info(html_content: str) -> Dict:
    """
    Extrae información de delivery del HTML

    Busca delivery times en este orden de prioridad:
    1. data-csa-c-delivery-time con "Tomorrow" o "Today" (Prime/rápido)
    2. data-csa-c-delivery-time con fecha específica
    3. Texto del DELIVERY_BLOCK parseado con regex

    Returns:
        dict: {found, text, date, days}
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    delivery_date = None
    days_until = None
    delivery_text = ""

    # PRIORIDAD 1: Buscar en atributos data-csa-c-delivery-time
    # Buscar TODOS los spans con data-csa-c-delivery-time
    delivery_spans = soup.find_all('span', attrs={'data-csa-c-delivery-time': True})

    fastest_days = None
    fastest_date = None
    fastest_text = None

    for span in delivery_spans:
        delivery_time = span.get('data-csa-c-delivery-time', '')

        # Detectar "Tomorrow" o "Today"
        if 'Tomorrow' in delivery_time:
            from datetime import timedelta
            current_date = datetime.now()
            delivery_date = current_date + timedelta(days=1)
            days_until = 1
            delivery_text = span.get_text(strip=True)[:150]
            # Tomorrow es lo más rápido, romper el loop
            fastest_days = 1
            fastest_date = delivery_date
            fastest_text = delivery_text
            break
        elif 'Today' in delivery_time:
            delivery_date = datetime.now()
            days_until = 0
            delivery_text = span.get_text(strip=True)[:150]
            # Today es lo más rápido posible
            fastest_days = 0
            fastest_date = delivery_date
            fastest_text = delivery_text
            break
        else:
            # Parsear fecha en data-csa-c-delivery-time
            date_pattern = r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\w+)\s+(\d+)'
            date_match = re.search(date_pattern, delivery_time)

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
                        current_date = datetime.now()
                        year = current_date.year

                        if month_num < current_date.month:
                            year += 1

                        temp_delivery_date = datetime(year, month_num, day)
                        time_delta = temp_delivery_date - current_date
                        temp_days = time_delta.days

                        # Quedarse con la fecha más rápida
                        if fastest_days is None or temp_days < fastest_days:
                            fastest_days = temp_days
                            fastest_date = temp_delivery_date
                            fastest_text = span.get_text(strip=True)[:150]
                    except:
                        pass

    # Usar la fecha más rápida encontrada
    if fastest_days is not None:
        days_until = fastest_days
        delivery_date = fastest_date
        delivery_text = fastest_text

    # FALLBACK: Si no encontramos nada en data attributes, buscar en DELIVERY_BLOCK
    if days_until is None:
        delivery_block = soup.find(id='mir-layout-DELIVERY_BLOCK')

        if not delivery_block:
            return {'found': False, 'text': None, 'date': None, 'days': None}

        delivery_text = delivery_block.get_text(strip=True)
        date_pattern = r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\w+)\s+(\d+)'
        date_match = re.search(date_pattern, delivery_text)

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
                    current_date = datetime.now()
                    year = current_date.year

                    if month_num < current_date.month:
                        year += 1

                    delivery_date = datetime(year, month_num, day)
                    time_delta = delivery_date - current_date
                    days_until = time_delta.days
                except:
                    pass

        delivery_text = delivery_text[:150]

    return {
        'found': True,
        'text': delivery_text,
        'date': delivery_date.strftime('%Y-%m-%d') if delivery_date else None,
        'days': days_until
    }


def extract_price(html_content: str) -> Optional[float]:
    """Extrae precio del HTML"""

    # MÉTODO 1: customerVisiblePrice (para productos con precio suprimido/"Show price")
    # Este es el precio real que Amazon muestra después de hacer click en "Show price"
    customer_price_match = re.search(r'items\[0\.base\]\[customerVisiblePrice\]\[amount\]" value="([0-9,.]+)"', html_content)
    if customer_price_match:
        try:
            price_value = customer_price_match.group(1).replace(',', '')
            customer_price = float(price_value)
            if customer_price > 0:
                return customer_price
        except:
            pass

    # Si no encontramos customerVisiblePrice, usar métodos tradicionales
    price_patterns = [
        (r'<span class="a-offscreen">\$([0-9,.]+)</span>', None),
        (r'<span class="a-price-whole">([0-9,]+)<', r'<span class="a-price-fraction">([0-9]+)<'),
    ]

    for whole_pattern, fraction_pattern in price_patterns:
        whole_match = re.search(whole_pattern, html_content)
        if whole_match:
            try:
                dollars = whole_match.group(1).replace(',', '')
                cents = "00"

                if fraction_pattern:
                    fraction_match = re.search(fraction_pattern, html_content)
                    if fraction_match:
                        cents = fraction_match.group(1)
                elif '.' in whole_match.group(1):
                    parts = whole_match.group(1).replace(',', '').split('.')
                    dollars = parts[0]
                    cents = parts[1] if len(parts) > 1 else "00"

                return float(f"{dollars}.{cents}")
            except:
                pass

    return None


def is_blocked_response(html_content: str, status_code: int) -> bool:
    """
    Detecta si Amazon bloqueó el request

    Señales de bloqueo:
    - CAPTCHA
    - Robot check
    - Página muy pequeña
    - Sin precio Y sin delivery
    """

    if status_code != 200:
        return True

    if len(html_content) < 10000:
        return True

    if 'captcha' in html_content.lower():
        return True

    if 'robot check' in html_content.lower():
        return True

    # Si no tiene delivery block ni precio, probablemente bloqueado
    has_delivery = 'mir-layout-DELIVERY_BLOCK' in html_content
    has_price = bool(re.search(r'<span class="a-offscreen">\$([0-9,.]+)</span>', html_content))

    if not has_delivery and not has_price:
        return True

    return False


def check_availability_v2_advanced(asin: str, zipcode: str = None) -> Dict:
    """
    Versión 2 AVANZADA con anti-detección profesional

    Features:
    - Session rotation automática
    - Exponential backoff con jitter
    - Rate limiting inteligente
    - Detección de bloqueos y auto-recuperación

    Args:
        asin: Amazon ASIN
        zipcode: Zipcode del comprador (default: BUYER_ZIPCODE de .env)

    Returns:
        Dict con resultado de validación
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

    # Implementar exponential backoff
    for attempt in range(MAX_RETRIES):
        try:
            # Rate limiting (esperar antes del request)
            _rate_limiter.wait()

            # Obtener sesión (puede crear nueva si es necesario)
            session = _session_rotator.get_session()

            # Paso 1: GET product page
            url = f"https://www.amazon.com/dp/{asin}"
            response = session.get(url, timeout=30)

            # Detectar bloqueo
            if is_blocked_response(response.text, response.status_code):
                # Bloqueo detectado - aplicar exponential backoff
                backoff_time = min(INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** attempt), MAX_BACKOFF)
                jitter = random.uniform(0, backoff_time * 0.1)
                total_wait = backoff_time + jitter

                print(f"   ⚠️  Bloqueo detectado para {asin} (intento {attempt+1}/{MAX_RETRIES})")
                print(f"   ⏳ Exponential backoff: {total_wait:.1f}s...")

                # Forzar nueva sesión después de bloqueo
                _session_rotator.reset()

                time.sleep(total_wait)
                continue

            html = response.text

            # Extraer CSRF token
            csrf_token = None
            csrf_match = re.search(r'"anti-csrftoken-a2z"\s*:\s*"([^"]+)"', html)
            if csrf_match:
                csrf_token = csrf_match.group(1)

            # Paso 2: Glow API para cambiar zipcode
            glow_url = "https://www.amazon.com/portal-migration/hz/glow/address-change"
            params = {
                'actionSource': 'glow',
                'deviceType': 'desktop',
                'pageType': 'Detail',
                'storeContext': 'pc'
            }
            payload = {
                'locationType': 'LOCATION_INPUT',
                'zipCode': zipcode,
                'deviceType': 'web',
                'storeContext': 'generic',
                'pageType': 'Detail'
            }
            headers = {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': url
            }
            if csrf_token:
                headers['anti-csrftoken-a2z'] = csrf_token

            # Glow API con retry
            glow_success = False
            for retry in range(2):
                try:
                    glow_response = session.post(glow_url, params=params, json=payload, headers=headers, timeout=15)
                    if glow_response.status_code == 200:
                        glow_success = True
                        break
                    elif glow_response.status_code == 503:
                        if retry < 1:
                            time.sleep(1)
                            continue
                except:
                    if retry < 1:
                        time.sleep(1)
                        continue

            # Paso 3: GET actualizado con delivery
            response = session.get(url, timeout=30)

            if is_blocked_response(response.text, response.status_code):
                # Bloqueo después de Glow API
                backoff_time = min(INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** attempt), MAX_BACKOFF)
                jitter = random.uniform(0, backoff_time * 0.1)
                _session_rotator.reset()
                time.sleep(backoff_time + jitter)
                continue

            html = response.text

            # Extraer precio
            result["price"] = extract_price(html)

            # Extraer delivery
            delivery = extract_delivery_info(html)
            if delivery['found']:
                result["delivery_date"] = delivery['text']
                result["days_until_delivery"] = delivery['days']

            # Marcar como disponible si tiene precio Y delivery
            if result["delivery_date"] and result["price"]:
                result["available"] = True
                result["in_stock"] = True

                max_days = int(os.getenv("MAX_DELIVERY_DAYS", "3"))
                if result["days_until_delivery"] and result["days_until_delivery"] <= max_days:
                    result["is_fast_delivery"] = True

            # Éxito - salir del loop de retry
            return result

        except Exception as e:
            result["error"] = str(e)[:100]
            # En caso de excepción, continuar con exponential backoff
            if attempt < MAX_RETRIES - 1:
                backoff_time = min(INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** attempt), MAX_BACKOFF)
                time.sleep(backoff_time)
                continue

    # Si llegamos aquí, fallaron todos los intentos
    if not result["error"]:
        result["error"] = f"Failed after {MAX_RETRIES} retries"

    return result


if __name__ == "__main__":
    import sys

    test_asin = sys.argv[1] if len(sys.argv) > 1 else "B0DW9BXCYW"
    test_zipcode = sys.argv[2] if len(sys.argv) > 2 else os.getenv("BUYER_ZIPCODE", "33172")

    print("=" * 80)
    print(f"TEST: Glow API v2 Advanced (Anti-Detection)")
    print(f"ASIN: {test_asin}")
    print(f"Zipcode: {test_zipcode}")
    print("=" * 80)
    print()

    start = time.time()
    result = check_availability_v2_advanced(test_asin, test_zipcode)
    elapsed = time.time() - start

    print()
    print("Resultados:")
    print(f"  ✅ Disponible: {result.get('available', False)}")
    print(f"  💰 Precio: ${result['price']}" if result.get('price') else "  💰 Precio: No encontrado")
    print(f"  📅 Delivery: {result.get('delivery_date')}")
    print(f"  ⏱️  Días: {result.get('days_until_delivery')}")
    print(f"  ⚡ Tiempo: {elapsed:.1f}s")

    if result.get('error'):
        print(f"  ⚠️  Error: {result['error']}")

    print()
    print("=" * 80)
