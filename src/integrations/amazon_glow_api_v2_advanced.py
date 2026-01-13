#!/usr/bin/env python3
"""
Amazon Glow API v3 - HYBRID Anti-Detection System

Sistema híbrido profesional con:
- curl_cffi: TLS fingerprint idéntico a Chrome (método principal)
- httpx HTTP/2: Fallback con HTTP/2 nativo
- CAPTCHA Auto-Solver: Resuelve soft CAPTCHAs automáticamente
- Session Rotation
- Exponential Backoff con Jitter
- Headers en orden exacto de Chrome

Basado en ingeniería inversa de AWS WAF Bot Control.
"""

import os
import re
import random
import time
import hashlib
import json
from collections import OrderedDict
from datetime import datetime
from typing import Optional, Dict, List
from bs4 import BeautifulSoup

# Intentar imports con fallback
try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    print("⚠️  curl_cffi no disponible, usando fallback")

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    import requests  # Fallback final
    print("⚠️  httpx no disponible, usando requests estándar")

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
# Delays variables (no fijos) para evitar patrones predecibles
BASE_DELAY = 3.0  # Delay base (aumentado de 2.0 a 3.0 para reducir rate)
JITTER_RANGE = 0.4  # ±20% variación (2.4-3.6s)

# === SESSION MANAGEMENT ===
# Valores variables para evitar patrones (no siempre 100 requests exactos)
MIN_REQUESTS_PER_SESSION = 80  # Entre 80-120 requests por sesión
MAX_REQUESTS_PER_SESSION = 120
SESSION_COOLDOWN_MIN = 25  # Entre 25-35s de cooldown
SESSION_COOLDOWN_MAX = 35

# === EXPONENTIAL BACKOFF ===
INITIAL_BACKOFF = 5  # Primer retry después de 5s
MAX_BACKOFF = 120  # Máximo 2 minutos de backoff
BACKOFF_MULTIPLIER = 2  # Duplicar cada retry
MAX_RETRIES = 3  # Máximo 3 reintentos

# === BROWSER FINGERPRINT ROTATION ===
# Rotar entre diferentes browsers para parecer múltiples usuarios
BROWSER_FINGERPRINTS = ["chrome120", "chrome119", "chrome116", "safari15_5", "safari15_3"]

# === AMAZON PRIME SESSION ===
COOKIES_FILE = "cache/amazon_session_cookies.json"


def load_amazon_cookies() -> Optional[Dict]:
    """
    Carga cookies de Amazon Prime desde archivo

    Returns:
        Dict con cookies o None si no existe el archivo
    """
    if not os.path.exists(COOKIES_FILE):
        return None

    try:
        with open(COOKIES_FILE, 'r') as f:
            cookies = json.load(f)
        return cookies
    except Exception as e:
        print(f"   ⚠️  Error cargando cookies: {e}")
        return None


class SessionRotator:
    """
    Gestiona rotación de sesiones para evitar tracking de Amazon.

    CAMBIO CRÍTICO: Usa curl_cffi con impersonate="chrome120" para bypass de WAF.

    Cada sesión tiene:
    - Nuevo User-Agent
    - COOKIES FRESCAS generadas por curl_cffi (no reusar cookies de browser)
    - TLS fingerprint idéntico a Chrome 120
    - Headers ligeramente diferentes
    """

    def __init__(self):
        self.session = None
        self.request_count = 0
        self.session_created_at = None
        # ROTAR browser fingerprint (no siempre Chrome 120)
        self.impersonate_browser = random.choice(BROWSER_FINGERPRINTS)
        # Límite variable de requests por sesión (evitar patrón fijo de 100)
        self.session_request_limit = random.randint(MIN_REQUESTS_PER_SESSION, MAX_REQUESTS_PER_SESSION)

    def get_session(self):
        """Obtiene sesión actual o crea nueva si es necesario"""

        # Crear nueva sesión si:
        # 1. No hay sesión
        # 2. Se excedió el límite variable de requests
        if self.session is None or self.request_count >= self.session_request_limit:
            # Si hay sesión anterior, esperar cooldown VARIABLE (no siempre el mismo tiempo)
            if self.session is not None:
                cooldown = random.uniform(SESSION_COOLDOWN_MIN, SESSION_COOLDOWN_MAX)
                elapsed = time.time() - self.session_created_at
                if elapsed < cooldown:
                    wait = cooldown - elapsed
                    print(f"   🔄 Session rotation cooldown: {wait:.1f}s...")
                    time.sleep(wait)

            # CRÍTICO: Usar curl_cffi en lugar de requests
            if CURL_CFFI_AVAILABLE:
                # Crear sesión con curl_cffi (TLS fingerprint)
                self.session = curl_requests.Session()
                # ROTAR fingerprint cada sesión nueva (más realista)
                self.impersonate_browser = random.choice(BROWSER_FINGERPRINTS)
                print(f"   ✅ Sesión curl_cffi creada (fingerprint={self.impersonate_browser})")
            else:
                # Fallback a requests estándar (no recomendado)
                import requests
                self.session = requests.Session()
                print(f"   ⚠️  Fallback a requests estándar (sin fingerprint)")

            self.session_created_at = time.time()
            self.request_count = 0

            # User-Agent aleatorio (Chrome 120 range)
            user_agent = random.choice(USER_AGENTS)

            # Accept-Language aleatorio (simula diferentes regiones)
            accept_languages = [
                'en-US,en;q=0.9',
                'en-GB,en;q=0.8',
                'en-US,en;q=0.8,es;q=0.6',
            ]

            # Headers más realistas para evitar bot detection
            # Variar entre Chrome y Firefox
            is_chrome = 'Chrome' in user_agent

            base_headers = {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': random.choice(accept_languages),
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
            }

            # Headers específicos de Chrome (más comunes)
            if is_chrome:
                base_headers.update({
                    'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="131", "Google Chrome";v="131"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"macOS"' if 'Mac' in user_agent else '"Windows"',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                })
            # Firefox no usa sec-ch-ua pero sí DNT
            else:
                base_headers['DNT'] = '1'

            self.session.headers.update(base_headers)

            # Cargar cookies de Amazon Prime (si existen)
            amazon_cookies = load_amazon_cookies()
            if amazon_cookies:
                # Aplicar cookies a la sesión
                for cookie_name, cookie_data in amazon_cookies.items():
                    self.session.cookies.set(
                        cookie_name,
                        cookie_data['value'],
                        domain=cookie_data.get('domain', '.amazon.com'),
                        path=cookie_data.get('path', '/')
                    )
                print(f"   🔐 Sesión Prime cargada ({len(amazon_cookies)} cookies)")
            else:
                # Si no hay cookies de Prime, generar cookies frescas con curl_cffi
                zipcode = os.getenv("BUYER_ZIPCODE")
                if zipcode and CURL_CFFI_AVAILABLE:
                    try:
                        # Visitar homepage para generar cookies iniciales
                        _ = self.session.get(
                            "https://www.amazon.com",
                            headers=base_headers,
                            impersonate=self.impersonate_browser,
                            timeout=15
                        )
                        print(f"   🍪 Cookies frescas generadas vía curl_cffi")
                    except Exception as e:
                        print(f"   ⚠️  Error generando cookies: {e}")
                else:
                    print(f"   ⚠️  Sin cookies de Prime - usando sesión anónima")

            # Generar nuevo límite aleatorio para esta sesión
            self.session_request_limit = random.randint(MIN_REQUESTS_PER_SESSION, MAX_REQUESTS_PER_SESSION)
            print(f"   🆕 Nueva sesión creada (límite: {self.session_request_limit} requests)")
            print(f"   👤 User-Agent: {user_agent[:50]}...")

        self.request_count += 1
        return self.session

    def reset(self):
        """Forzar reset de sesión"""
        self.session = None
        self.request_count = 0
        # Regenerar límite para próxima sesión
        self.session_request_limit = random.randint(MIN_REQUESTS_PER_SESSION, MAX_REQUESTS_PER_SESSION)


class RateLimiter:
    """
    Implementa rate limiting con delays variables
    - NO espera siempre el mismo tiempo (evita patrones predecibles)
    - Usa jitter para simular variabilidad natural
    """

    def __init__(self):
        self.last_request_time = 0

    def wait(self):
        """Espera el tiempo necesario antes del próximo request"""

        # Si es el primer request, no esperar
        if self.last_request_time == 0:
            self.last_request_time = time.time()
            return

        # Calcular delay con jitter (variable, no fijo)
        delay = BASE_DELAY * random.uniform(1 - JITTER_RANGE/2, 1 + JITTER_RANGE/2)

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


def detect_and_resolve_variants(html_content: str, original_asin: str) -> Optional[Dict]:
    """
    FALLBACK: Detecta si un ASIN tiene variantes y extrae información para seleccionarla.

    Solo se llama cuando el producto ya fue marcado como unavailable.

    Args:
        html_content: HTML de la página de Amazon
        original_asin: ASIN que TENEMOS en la BD

    Returns:
        Dict con:
        - asin: El ASIN de la variante
        - dimensions: Dict con dimensiones (ej: {"size_name": "7", "color_name": "Black"})
        - variant_info: Lista con valores de la variante
        O None si no tiene variantes o no se pudo extraer
    """

    # DETECCIÓN: ¿Es producto con variantes?
    has_variant_selector = (
        'To buy, select' in html_content or
        'Choose from options' in html_content or
        re.search(r'Select (Size|Color|Style)', html_content) or
        'id="twister"' in html_content
    )

    if not has_variant_selector:
        return None  # No tiene variantes

    # EXTRACCIÓN 1: Buscar dimensionValuesDisplayData (mapeo ASIN -> valores)
    dim_data_match = re.search(
        r'"dimensionValuesDisplayData"\s*:\s*(\{[^}]+\})',
        html_content
    )

    if not dim_data_match:
        return None  # No se pudo extraer mapa de variantes

    try:
        import json
        variant_map = json.loads(dim_data_match.group(1))

        # VERIFICACIÓN: ¿Nuestro ASIN está en el mapa?
        if original_asin not in variant_map:
            print(f"   ⚠️  ASIN padre detectado (no es variante específica)")
            print(f"      Variantes disponibles: {list(variant_map.keys())[:3]}")
            return None

        variant_info = variant_map[original_asin]

        # EXTRACCIÓN 2: Buscar dimensionToAsinMap (mapeo valores -> ASIN)
        # Esto nos da los nombres de las dimensiones (size_name, color_name, etc)
        dim_to_asin_match = re.search(
            r'"dimensionToAsinMap"\s*:\s*(\{.+?\})\s*,',
            html_content,
            re.DOTALL
        )

        dimensions = {}
        if dim_to_asin_match:
            try:
                dim_to_asin = json.loads(dim_to_asin_match.group(1))
                # dim_to_asin tiene estructura: {"{size_value},{color_value}": "ASIN", ...}
                # Necesitamos encontrar qué keys corresponden a nuestro ASIN
                for key, asin in dim_to_asin.items():
                    if asin == original_asin:
                        # Parsear los valores (ej: "7,Black" -> ["7", "Black"])
                        values = key.split(',')
                        # Asumimos orden: primer dimensión = size, segunda = color
                        # (esto puede variar, pero es lo más común)
                        if len(values) >= 1:
                            dimensions['dimension_1'] = values[0]
                        if len(values) >= 2:
                            dimensions['dimension_2'] = values[1]
                        break
            except:
                pass

        print(f"   🔄 FALLBACK: Producto con variantes detectado")
        print(f"      ASIN: {original_asin}")
        print(f"      Variante: {' - '.join(str(v) for v in variant_info)}")
        print(f"      Total variantes: {len(variant_map)}")
        if dimensions:
            print(f"      Dimensiones: {dimensions}")

        return {
            'asin': original_asin,
            'variant_info': variant_info,
            'dimensions': dimensions
        }

    except Exception as e:
        print(f"   ⚠️  Error detectando variantes: {str(e)[:100]}")
        return None


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
    # IMPORTANTE: Solo buscar dentro del delivery block del producto principal
    # para evitar extraer fechas de productos patrocinados (ads)
    delivery_block = soup.find(id='deliveryBlockMessage')
    if not delivery_block:
        # Fallback: buscar contenedor principal de delivery
        delivery_block = soup.find(id='mir-layout-DELIVERY_BLOCK')

    if delivery_block:
        # Buscar SOLO dentro del delivery block del producto principal
        delivery_spans = delivery_block.find_all('span', attrs={'data-csa-c-delivery-time': True})
    else:
        # Si no hay delivery block, buscar en toda la página pero con cuidado
        # Excluir secciones de productos patrocinados
        all_spans = soup.find_all('span', attrs={'data-csa-c-delivery-time': True})
        delivery_spans = []
        for span in all_spans:
            # Verificar que el span NO esté dentro de un ad/sponsored product
            parent_text = ' '.join([p.get('id', '') + ' ' + ' '.join(p.get('class', []))
                                    for p in span.parents])
            if 'sp_detail' not in parent_text and 'acswidget' not in parent_text:
                delivery_spans.append(span)

    fastest_days = None
    fastest_date = None
    fastest_text = None

    for span in delivery_spans:
        delivery_time = span.get('data-csa-c-delivery-time', '')
        span_text = span.get_text(strip=True)

        # Detectar "Overnight" (entrega al día siguiente)
        if 'Overnight' in delivery_time or 'Overnight' in span_text:
            from datetime import timedelta
            current_date = datetime.now()
            delivery_date = current_date + timedelta(days=1)
            days_until = 1
            delivery_text = span_text[:150]
            # Overnight es entrega mañana
            fastest_days = 1
            fastest_date = delivery_date
            fastest_text = delivery_text
            break
        # Detectar "Tomorrow" o "Today"
        elif 'Tomorrow' in delivery_time:
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
            # Parsear fecha en data-csa-c-delivery-time (inglés y español)
            date_pattern_en = r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\w+)\s+(\d+)'
            date_pattern_es = r'(lunes|martes|miércoles|jueves|viernes|sábado|domingo),\s+(\d+)\s+de\s+(\w+)'
            # Rango de fechas (ej: "February 2 - March 4" o "January 14 - 16")
            # Capturar AMBAS fechas del rango para tomar la última
            date_range_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d+)\s*-\s*(?:(January|February|March|April|May|June|July|August|September|October|November|December)\s+)?(\d+)'

            date_match = re.search(date_pattern_en, delivery_time)
            is_spanish = False
            is_range = False

            if not date_match:
                # Intentar español
                date_match = re.search(date_pattern_es, delivery_time, re.IGNORECASE)
                is_spanish = True

            if not date_match:
                # Intentar rango de fechas (tomar la primera fecha)
                # Buscar tanto en delivery_time como en span_text
                range_match = re.search(date_range_pattern, delivery_time)
                if not range_match:
                    range_match = re.search(date_range_pattern, span_text)

                if range_match:
                    # Crear un match "fake" compatible con el formato normal
                    # Tomar la ÚLTIMA fecha del rango (más conservador)
                    is_range = True
                    is_spanish = False  # Los rangos siempre son en inglés

                    # Grupos del regex:
                    # 1: Primer mes (siempre presente)
                    # 2: Primer día
                    # 3: Segundo mes (opcional, puede ser None si es mismo mes)
                    # 4: Segundo día (fecha final del rango)

                    # Si hay segundo mes, usarlo. Si no, usar el primero
                    month_str = range_match.group(3) if range_match.group(3) else range_match.group(1)
                    day_str = range_match.group(4)  # Siempre el último día

                    # Simular match compatible
                    class FakeMatch:
                        def __init__(self, month, day):
                            self._month = month
                            self._day = day
                        def group(self, n):
                            if n == 1:
                                return self._month
                            elif n == 2:
                                return self._day
                            return None
                    date_match = FakeMatch(month_str, day_str)

            if date_match:
                month_map_en = {
                    'January': 1, 'February': 2, 'March': 3, 'April': 4,
                    'May': 5, 'June': 6, 'July': 7, 'August': 8,
                    'September': 9, 'October': 10, 'November': 11, 'December': 12
                }
                month_map_es = {
                    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                }

                month_map = month_map_es if is_spanish else month_map_en

                # El orden de día/mes es diferente en español vs inglés vs rango
                if is_range:
                    # Rango: "February 2 - March 4" -> ya está en FakeMatch
                    month_str = date_match.group(1)  # February
                    day = int(date_match.group(2))   # 2
                elif is_spanish:
                    # Español: "sábado, 10 de enero" -> grupo(2)=día, grupo(3)=mes
                    day = int(date_match.group(2))
                    month_str = date_match.group(3).lower()
                else:
                    # Inglés: "Monday, January 10" -> grupo(2)=mes, grupo(3)=día
                    month_str = date_match.group(2)
                    day = int(date_match.group(3))

                month_num = month_map.get(month_str)

                if month_num:
                    try:
                        current_date = datetime.now()
                        year = current_date.year

                        if month_num < current_date.month:
                            year += 1

                        temp_delivery_date = datetime(year, month_num, day)
                        # Calcular días hasta la entrega (diferencia de fechas)
                        # Si hoy es 8 y llega el 15 = 15-8 = 7 días
                        temp_days = (temp_delivery_date.date() - current_date.date()).days

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
        # Usar el mismo delivery_block que encontramos al principio
        # (puede ser deliveryBlockMessage o mir-layout-DELIVERY_BLOCK)
        if not delivery_block:
            return {'found': False, 'text': None, 'date': None, 'days': None}

        delivery_text = delivery_block.get_text(strip=True)

        # Intentar inglés primero, después español, después rangos
        date_pattern_en = r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\w+)\s+(\d+)'
        date_pattern_es = r'(lunes|martes|miércoles|jueves|viernes|sábado|domingo),\s+(\d+)\s+de\s+(\w+)'
        date_range_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d+)\s*-\s*(?:(January|February|March|April|May|June|July|August|September|October|November|December)\s+)?(\d+)'

        date_match = re.search(date_pattern_en, delivery_text)
        is_spanish = False
        is_range = False

        if not date_match:
            date_match = re.search(date_pattern_es, delivery_text, re.IGNORECASE)
            is_spanish = True

        if not date_match:
            # Intentar rango de fechas
            range_match = re.search(date_range_pattern, delivery_text)
            if range_match:
                is_range = True
                is_spanish = False  # Los rangos siempre son en inglés

                # Si hay segundo mes, usarlo. Si no, usar el primero
                month_str = range_match.group(3) if range_match.group(3) else range_match.group(1)
                day_str = range_match.group(4)  # Siempre el último día

                class FakeMatch:
                    def __init__(self, month, day):
                        self._month = month
                        self._day = day
                    def group(self, n):
                        if n == 1:
                            return self._month
                        elif n == 2:
                            return self._day
                        return None
                date_match = FakeMatch(month_str, day_str)

        if date_match:
            month_map_en = {
                'January': 1, 'February': 2, 'March': 3, 'April': 4,
                'May': 5, 'June': 6, 'July': 7, 'August': 8,
                'September': 9, 'October': 10, 'November': 11, 'December': 12
            }
            month_map_es = {
                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
            }

            month_map = month_map_es if is_spanish else month_map_en

            if is_range:
                # Rango: ya está en FakeMatch
                month_str = date_match.group(1)
                day = int(date_match.group(2))
            elif is_spanish:
                day = int(date_match.group(2))
                month_str = date_match.group(3).lower()
            else:
                month_str = date_match.group(2)
                day = int(date_match.group(3))

            month_num = month_map.get(month_str)

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
    - Página muy pequeña (pero NO 404s)
    - Sin precio Y sin delivery
    - Mensaje de "automated access"

    NO es bloqueo:
    - 404: Producto descontinuado/no existe
    - 503/429: Error temporal del servidor (diferente a bloqueo)
    """

    # 404 = producto no existe/descontinuado, NO es bloqueo WAF
    if status_code == 404:
        return False

    # 503/429 = Rate limit/server error, reintentar pero no cambiar sesión
    if status_code in [503, 429]:
        return True

    # Otros códigos != 200 = error/bloqueo
    if status_code != 200:
        return True

    # Página muy pequeña (< 10KB) suele ser bloqueo
    if len(html_content) < 10000:
        return True

    if 'captcha' in html_content.lower():
        return True

    if 'robot check' in html_content.lower():
        return True

    # NUEVO: Detectar mensaje de "automated access to Amazon"
    if 'automated access to Amazon data' in html_content:
        return True

    if 'api-services-support@amazon.com' in html_content:
        return True

    # Si no tiene delivery block ni precio, probablemente bloqueado
    has_delivery = 'mir-layout-DELIVERY_BLOCK' in html_content
    has_price = bool(re.search(r'<span class="a-offscreen">\$([0-9,.]+)</span>', html_content))

    if not has_delivery and not has_price:
        return True

    return False


def solve_captcha_clickthrough(session, html_content: str, impersonate_browser: str) -> bool:
    """
    Resuelve automáticamente el CAPTCHA tipo click-through de Amazon

    Args:
        session: curl_cffi Session actual
        html_content: HTML con el CAPTCHA
        impersonate_browser: Browser fingerprint para mantener consistencia

    Returns:
        True si se resolvió exitosamente, False si falló
    """
    from urllib.parse import urlencode

    # Extraer parámetros del formulario CAPTCHA
    amzn_match = re.search(r'name="amzn"\s+value="([^"]+)"', html_content)
    amzn_r_match = re.search(r'name="amzn-r"\s+value="([^"]+)"', html_content)
    keywords_match = re.search(r'name="field-keywords"\s+value="([^"]+)"', html_content)

    if not amzn_match:
        print("   ❌ No se pudieron extraer parámetros del CAPTCHA")
        return False

    # Construir parámetros del formulario
    params = {
        'amzn': amzn_match.group(1),
        'amzn-r': amzn_r_match.group(1) if amzn_r_match else '',
        'field-keywords': keywords_match.group(1) if keywords_match else ''
    }

    # URL de validación
    captcha_url = f"https://www.amazon.com/errors/validateCaptcha?{urlencode(params)}"

    headers = {
        'Referer': 'https://www.amazon.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        # Simular el click del botón "Continue shopping"
        get_kwargs = {'headers': headers, 'timeout': 30, 'allow_redirects': True}
        if CURL_CFFI_AVAILABLE:
            get_kwargs['impersonate'] = impersonate_browser

        response = session.get(captcha_url, **get_kwargs)

        # Verificar si el CAPTCHA se resolvió (Amazon devuelve página completa)
        if len(response.text) > 50000:
            print("   ✅ CAPTCHA resuelto exitosamente")
            return True
        else:
            print(f"   ❌ CAPTCHA no resuelto (respuesta: {len(response.text)} bytes)")
            return False

    except Exception as e:
        print(f"   ❌ Error resolviendo CAPTCHA: {e}")
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

            # Headers adicionales para el GET inicial simulando tráfico orgánico
            # Simular que viene de Google search (60% del tiempo) o directo (40%)
            get_headers = {}
            if random.random() < 0.6:
                # Simular tráfico de Google
                search_queries = [
                    f"{asin} amazon",
                    f"buy {asin}",
                    f"{asin} price",
                    f"{asin} review"
                ]
                query = random.choice(search_queries)
                get_headers['Referer'] = f"https://www.google.com/search?q={query.replace(' ', '+')}"
                get_headers['Sec-Fetch-Site'] = 'cross-site'

            # CRÍTICO: Agregar impersonate si usamos curl_cffi
            get_kwargs = {'headers': get_headers, 'timeout': 30}
            if CURL_CFFI_AVAILABLE:
                get_kwargs['impersonate'] = _session_rotator.impersonate_browser

            response = session.get(url, **get_kwargs)

            # Manejar 404s (producto no existe) - NO reintentar
            if response.status_code == 404:
                print(f"   ❌ Producto no encontrado (404) - ASIN descontinuado o inválido")
                return {
                    "available": False,
                    "price": None,
                    "buyable": False,
                    "status": "unavailable",
                    "error": "Product not found (404 - discontinued)",
                    "delivery_date": None,
                    "days_until_delivery": None,
                    "prime_available": False,
                    "in_stock": False
                }

            # Detectar bloqueo
            if is_blocked_response(response.text, response.status_code):
                # Guardar HTML y metadata para debugging
                from pathlib import Path
                debug_dir = Path("logs/amazon_debug")
                debug_dir.mkdir(parents=True, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                debug_html = debug_dir / f"{asin}_{timestamp}_status{response.status_code}.html"
                debug_json = debug_dir / f"{asin}_{timestamp}_metadata.json"

                # Guardar HTML
                with open(debug_html, 'w', encoding='utf-8') as f:
                    f.write(response.text)

                # Guardar metadata
                metadata = {
                    "asin": asin,
                    "url": url,
                    "status_code": response.status_code,
                    "timestamp": timestamp,
                    "html_size": len(response.text),
                    "attempt": attempt + 1,
                    "has_captcha": 'captcha' in response.text.lower(),
                    "has_robot_check": 'robot check' in response.text.lower(),
                    "has_delivery_block": 'mir-layout-DELIVERY_BLOCK' in response.text,
                    "has_price": bool(re.search(r'<span class="a-offscreen">\$([0-9,.]+)</span>', response.text)),
                    "headers": dict(response.headers)
                }

                with open(debug_json, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2)

                print(f"   🔍 DEBUG: Status {response.status_code} detectado para {asin}")
                print(f"   📁 HTML: {debug_html.name}")
                print(f"   📊 Metadata: has_price={metadata['has_price']}, has_delivery={metadata['has_delivery_block']}, has_captcha={metadata['has_captcha']}")

                # Verificar si es un CAPTCHA tipo click-through (puede resolverse automáticamente)
                is_captcha = metadata['has_captcha'] and len(response.text) < 10000

                if is_captcha:
                    print(f"   🔓 CAPTCHA detectado para {asin} - intentando resolver...")

                    # Intentar resolver CAPTCHA automáticamente
                    if solve_captcha_clickthrough(session, response.text, _session_rotator.impersonate_browser):
                        # CAPTCHA resuelto - esperar un momento y reintentar
                        time.sleep(2)

                        print(f"   🔄 Reintentando GET después de resolver CAPTCHA...")
                        response = session.get(url, **get_kwargs)

                        # Verificar si ahora sí obtuvimos la página
                        if not is_blocked_response(response.text, response.status_code):
                            print(f"   ✅ Página obtenida exitosamente después de resolver CAPTCHA")
                            html = response.text
                            # Continuar con el flujo normal (no hacer continue)
                        else:
                            print(f"   ❌ Sigue bloqueado después de resolver CAPTCHA")
                            # Continuar con backoff normal
                            backoff_time = min(INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** attempt), MAX_BACKOFF)
                            jitter = random.uniform(0, backoff_time * 0.1)
                            total_wait = backoff_time + jitter

                            print(f"   ⏳ Exponential backoff: {total_wait:.1f}s...")
                            _session_rotator.reset()
                            _rate_limiter.last_request_time = 0
                            time.sleep(total_wait)
                            continue
                    else:
                        # No se pudo resolver CAPTCHA - aplicar backoff
                        print(f"   ❌ No se pudo resolver CAPTCHA automáticamente")
                        backoff_time = min(INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** attempt), MAX_BACKOFF)
                        jitter = random.uniform(0, backoff_time * 0.1)
                        total_wait = backoff_time + jitter

                        print(f"   ⏳ Exponential backoff: {total_wait:.1f}s...")
                        _session_rotator.reset()
                        _rate_limiter.last_request_time = 0
                        time.sleep(total_wait)
                        continue
                else:
                    # Bloqueo que NO es CAPTCHA click-through - aplicar exponential backoff normal
                    backoff_time = min(INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** attempt), MAX_BACKOFF)
                    jitter = random.uniform(0, backoff_time * 0.1)
                    total_wait = backoff_time + jitter

                    print(f"   ⚠️  Bloqueo detectado para {asin} (intento {attempt+1}/{MAX_RETRIES})")
                    print(f"   ⏳ Exponential backoff: {total_wait:.1f}s...")

                    # Forzar nueva sesión después de bloqueo
                    _session_rotator.reset()

                    # CRÍTICO: Resetear rate limiter para que agregue delay después del backoff
                    # Sin esto, el próximo request es inmediato y Amazon detecta el patrón
                    _rate_limiter.last_request_time = 0

                    time.sleep(total_wait)
                    continue
            else:
                # Sin bloqueo - continuar normalmente
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

            # Glow API con retry mejorado
            glow_success = False
            for retry in range(3):  # Aumentar a 3 intentos
                try:
                    # CRÍTICO: Agregar impersonate para POST también
                    post_kwargs = {'params': params, 'json': payload, 'headers': headers, 'timeout': 15}
                    if CURL_CFFI_AVAILABLE:
                        post_kwargs['impersonate'] = _session_rotator.impersonate_browser

                    glow_response = session.post(glow_url, **post_kwargs)
                    if glow_response.status_code == 200:
                        glow_success = True
                        # Delay mayor para dar tiempo a Amazon a procesar el cambio
                        time.sleep(2.5)
                        break
                    elif glow_response.status_code == 503:
                        if retry < 2:
                            time.sleep(2)
                            continue
                except:
                    if retry < 2:
                        time.sleep(2)
                        continue

            # Paso 3: GET actualizado con delivery
            # Verificar que el zipcode se aplicó correctamente
            get_kwargs_final = {'timeout': 30}
            if CURL_CFFI_AVAILABLE:
                get_kwargs_final['impersonate'] = _session_rotator.impersonate_browser

            response = session.get(url, **get_kwargs_final)
            html = response.text

            # VERIFICACIÓN: ¿El zipcode se aplicó correctamente?
            # Si vemos "Select delivery location", significa que NO se aplicó
            zipcode_applied = zipcode in html or 'deliveryBlockMessage' in html
            if not zipcode_applied and 'Select delivery location' in html:
                # El Glow API falló silenciosamente - reintentar con estrategia alternativa
                print(f"   ⚠️  Zipcode no se aplicó - reintentando con estrategia alternativa...")

                # Estrategia alternativa: Hacer un GET con el zipcode en la URL
                alt_url = f"{url}?zipCode={zipcode}"
                time.sleep(1)
                response = session.get(alt_url, timeout=30)
                html = response.text

                # Si aún no funciona, reintent con Glow API de nuevo
                if zipcode not in html and 'Select delivery location' in html:
                    time.sleep(1.5)
                    try:
                        session.post(glow_url, params=params, json=payload, headers=headers, timeout=15)
                        time.sleep(3)  # Delay aún mayor
                        response = session.get(url, timeout=30)
                        html = response.text
                    except:
                        pass

            if is_blocked_response(html, response.status_code):
                # Bloqueo después de Glow API
                backoff_time = min(INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** attempt), MAX_BACKOFF)
                jitter = random.uniform(0, backoff_time * 0.1)
                _session_rotator.reset()
                time.sleep(backoff_time + jitter)
                continue

            # Extraer precio
            result["price"] = extract_price(html)

            # Extraer delivery
            delivery = extract_delivery_info(html)
            if delivery['found']:
                result["delivery_date"] = delivery['text']
                result["delivery_date_clean"] = delivery['date']  # Fecha limpia YYYY-MM-DD
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

            # FALLBACK: Si tiene precio pero NO tiene delivery, puede ser variante
            if result["price"] and not result["delivery_date"]:
                print(f"   ⚠️  Producto con precio pero sin delivery - intentando fallback de variantes...")

                variant_data = detect_and_resolve_variants(html, asin)

                if variant_data:
                    # ESTRATEGIA: Agregar parámetros th=1&psc=1 para forzar selección de variante
                    print(f"   🔄 Consultando variante con parámetros de selección...")

                    # Construir URL con parámetros que fuerzan la selección de la variante
                    variant_url = f"https://www.amazon.com/dp/{asin}?th=1&psc=1"

                    # Pequeño delay antes del request adicional
                    time.sleep(1.5)

                    # GET con parámetros de variante
                    variant_response = session.get(variant_url, timeout=30)

                    if is_blocked_response(variant_response.text, variant_response.status_code):
                        print(f"   ⚠️  Bloqueo en consulta de variante")
                        # Continuar con retry normal
                        backoff_time = min(INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** attempt), MAX_BACKOFF)
                        jitter = random.uniform(0, backoff_time * 0.1)
                        _session_rotator.reset()
                        time.sleep(backoff_time + jitter)
                        continue

                    variant_html = variant_response.text

                    # Extraer CSRF token de la variante
                    csrf_token_variant = None
                    csrf_match_variant = re.search(r'"anti-csrftoken-a2z"\s*:\s*"([^"]+)"', variant_html)
                    if csrf_match_variant:
                        csrf_token_variant = csrf_match_variant.group(1)

                    # Glow API para actualizar zipcode en la variante seleccionada
                    print(f"   🔄 Ejecutando Glow API para variante seleccionada...")
                    glow_url_variant = "https://www.amazon.com/portal-migration/hz/glow/address-change"
                    params_variant = {
                        'actionSource': 'glow',
                        'deviceType': 'desktop',
                        'pageType': 'Detail',
                        'storeContext': 'pc'
                    }
                    payload_variant = {
                        'locationType': 'LOCATION_INPUT',
                        'zipCode': zipcode,
                        'deviceType': 'web',
                        'storeContext': 'generic',
                        'pageType': 'Detail'
                    }
                    glow_headers_variant = {
                        'Accept': 'application/json, text/javascript, */*; q=0.01',
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        'Referer': variant_url
                    }
                    if csrf_token_variant:
                        glow_headers_variant['anti-csrftoken-a2z'] = csrf_token_variant

                    # Glow API call
                    try:
                        glow_response_variant = session.post(
                            glow_url_variant,
                            params=params_variant,
                            json=payload_variant,
                            headers=glow_headers_variant,
                            timeout=15
                        )
                        if glow_response_variant.status_code == 200:
                            print(f"   ✅ Glow API ejecutado para variante")
                    except:
                        print(f"   ⚠️  Glow API falló para variante (continuando...)")

                    # GET actualizado con delivery para la variante
                    time.sleep(0.5)
                    variant_response_updated = session.get(variant_url, timeout=30)
                    variant_html = variant_response_updated.text

                    # VALIDACIÓN CRÍTICA: Verificar que el ASIN en la página sea el correcto
                    # Buscar el ASIN actual en el HTML (múltiples patrones)
                    asin_patterns = [
                        r'"ASIN"\s*:\s*"([A-Z0-9]+)"',
                        r'data-asin="([A-Z0-9]+)"',
                        r'"asin"\s*:\s*"([A-Z0-9]+)"',
                        r'/dp/([A-Z0-9]{10})',
                    ]

                    current_asin = None
                    for pattern in asin_patterns:
                        asin_match = re.search(pattern, variant_html)
                        if asin_match:
                            current_asin = asin_match.group(1)
                            break

                    if not current_asin:
                        print(f"   ⚠️  FALLBACK ABORTADO: No se pudo extraer ASIN del HTML")
                        print(f"      No podemos verificar que el precio/delivery sean del producto correcto")
                        # Rechazar por seguridad - no sabemos de qué producto es el precio
                        result["available"] = False
                        result["price"] = None
                        result["delivery_date"] = None
                        return result

                    if current_asin != asin:
                        print(f"   ⚠️  FALLBACK ABORTADO: ASIN incorrecto detectado")
                        print(f"      Buscábamos: {asin}")
                        print(f"      Amazon mostró: {current_asin}")
                        print(f"      Esto indica que Amazon redirigió a otra variante")
                        # NO usar este resultado - el precio/delivery es de otro producto
                        result["available"] = False
                        result["price"] = None
                        result["delivery_date"] = None
                        return result

                    # Re-extraer PRECIO de la variante (puede haber cambiado)
                    variant_price = extract_price(variant_html)
                    if variant_price and variant_price != result["price"]:
                        print(f"   ⚠️  Precio cambió después de seleccionar variante:")
                        print(f"      Antes: ${result['price']}")
                        print(f"      Ahora: ${variant_price}")
                        result["price"] = variant_price  # Usar el precio actualizado

                    # Re-extraer delivery de la variante
                    variant_delivery = extract_delivery_info(variant_html)
                    if variant_delivery['found']:
                        result["delivery_date"] = variant_delivery['text']
                        result["delivery_date_clean"] = variant_delivery['date']
                        result["days_until_delivery"] = variant_delivery['days']

                        # Marcar como disponible
                        if result["delivery_date"]:
                            result["available"] = True
                            result["in_stock"] = True

                            max_days = int(os.getenv("MAX_DELIVERY_DAYS", "3"))
                            if result["days_until_delivery"] and result["days_until_delivery"] <= max_days:
                                result["is_fast_delivery"] = True

                            print(f"   ✅ FALLBACK exitoso - delivery encontrado")
                            print(f"   ✅ ASIN verificado: {current_asin}")
                            return result
                        else:
                            print(f"   ⚠️  FALLBACK: delivery aún no encontrado")
                    else:
                        print(f"   ⚠️  FALLBACK: no se pudo extraer delivery de variante")

            # Si llegamos aquí, no hay delivery (con o sin fallback)
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
