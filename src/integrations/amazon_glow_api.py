#!/usr/bin/env python3
"""
Amazon Availability Checker usando API INTERNA Glow

Usa requests + Glow API para verificar disponibilidad y fechas de entrega.
Detecta automáticamente FREE delivery vs delivery pago (fastest).
"""
import os
import re
import requests
from datetime import datetime
from typing import Optional, Dict
from bs4 import BeautifulSoup


def check_real_availability_glow_api(asin: str, zipcode: str = None) -> Dict:
    """
    Verifica disponibilidad REAL de un producto en Amazon.com
    usando la API interna "Glow" de Amazon para cambiar zipcode.

    VENTAJAS sobre Selenium:
    - 4x más rápido (~5s vs ~20s)
    - No requiere Chrome/ChromeDriver
    - Usa API interna estable
    - Filtra delivery pago vs FREE delivery

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

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
    })

    # NO usar cookies - sistema simple que detecta FREE delivery vs paid delivery

    try:
        # Paso 1: GET product page para obtener cookies y tokens
        url = f"https://www.amazon.com/dp/{asin}"
        response = session.get(url, timeout=30)

        if response.status_code != 200:
            result["error"] = f"HTTP {response.status_code}"
            return result

        html = response.text

        # Extraer CSRF token (necesario para algunas llamadas)
        csrf_token = None
        csrf_match = re.search(r'"anti-csrftoken-a2z"\s*:\s*"([^"]+)"', html)
        if csrf_match:
            csrf_token = csrf_match.group(1)

        # Paso 2: Llamar a API Glow para cambiar zipcode
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

        glow_response = session.post(glow_url, params=params, json=payload, headers=headers, timeout=15)

        if glow_response.status_code != 200:
            result["error"] = f"Glow API error {glow_response.status_code}"
            # Continuar de todas formas, a veces funciona sin el cambio

        # Paso 3: GET product page nuevamente para obtener delivery dates actualizados
        response = session.get(url, timeout=30)

        if response.status_code != 200:
            result["error"] = f"HTTP {response.status_code} (after glow)"
            return result

        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        # NO setear prime_available aquí - solo si detectamos fecha Prime FREE delivery más adelante
        # La presencia de la palabra "prime" en HTML no significa que tenga Prime FREE delivery

        # Extraer precio
        price_patterns = [
            # Patrón 1: "a-price-whole">25<" (dollars) + buscar cents después
            (r'<span class="a-price-whole">([0-9,]+)<', r'<span class="a-price-fraction">([0-9]+)<'),
            # Patrón 2: JSON con precio completo "$25.99"
            (r'"price":\s*"\\$([0-9,.]+)"', None),
        ]

        for whole_pattern, fraction_pattern in price_patterns:
            whole_match = re.search(whole_pattern, html)
            if whole_match:
                try:
                    dollars = whole_match.group(1).replace(',', '')
                    cents = "00"

                    # Si hay patrón de cents, buscarlo
                    if fraction_pattern:
                        fraction_match = re.search(fraction_pattern, html)
                        if fraction_match:
                            cents = fraction_match.group(1)
                    elif '.' in whole_match.group(1):
                        # Ya tiene decimales (formato "$25.99")
                        parts = whole_match.group(1).replace(',', '').split('.')
                        dollars = parts[0]
                        cents = parts[1] if len(parts) > 1 else "00"

                    result["price"] = float(f"{dollars}.{cents}")
                    break
                except:
                    pass

        # Verificar disponibilidad
        availability_indicators = [
            "in stock", "en stock", "disponible", "available",
            "queda(n)", "quedán", "quedan"
        ]

        html_lower = html.lower()
        for indicator in availability_indicators:
            if indicator in html_lower:
                result["in_stock"] = True
                result["available"] = True
                break

        # Verificar indisponibilidad
        if not result["in_stock"]:
            unavailable_indicators = [
                "currently unavailable", "out of stock",
                "no disponible", "agotado", "sin stock"
            ]

            for indicator in unavailable_indicators:
                if indicator in html_lower:
                    result["available"] = False
                    result["error"] = "Out of stock"
                    return result

        # Buscar fecha de entrega
        # ESTRATEGIA: Buscar TODAS las fechas de entrega y elegir la más temprana
        # Amazon a veces muestra múltiples fechas (regular, Prime, etc)

        all_dates = []

        # PRIORIDAD 0: Buscar atributos data-csa-c-delivery-time (Amazon los usa para delivery dates)
        # IMPORTANTE: SOLO detectar delivery FREE, ignorar "fastest" (se paga)
        # Ejemplo: data-csa-c-delivery-price="FREE" data-csa-c-delivery-time="Monday, December 29"

        # Buscar todas las fechas de entrega
        data_delivery_pattern = r'data-csa-c-delivery-time="([^"]+)"'
        data_matches = re.findall(data_delivery_pattern, html, re.IGNORECASE)

        if data_matches:
            for date_str in data_matches:
                # Buscar el contexto del elemento HTML que contiene esta fecha
                idx = html.find(f'data-csa-c-delivery-time="{date_str}"')
                if idx >= 0:
                    # Obtener el contexto del elemento completo (antes y después)
                    # Buscar el <span> o elemento que contiene este atributo
                    context_start = max(0, idx - 500)
                    context_end = min(len(html), idx + 500)
                    context = html[context_start:context_end]

                    # FILTRO CRÍTICO: Solo aceptar si tiene data-csa-c-delivery-price="FREE"
                    # O si es delivery de Prime members
                    is_free_delivery = 'data-csa-c-delivery-price="FREE"' in context
                    is_prime_delivery = 'prime' in context.lower() and 'members' in context.lower()

                    # RECHAZAR si es "fastest" (se paga extra)
                    is_paid_fastest = 'data-csa-c-delivery-price="fastest"' in context

                    if is_paid_fastest:
                        # Ignorar delivery pago
                        continue

                    if is_free_delivery or is_prime_delivery:
                        # Es delivery FREE o Prime
                        if is_prime_delivery:
                            all_dates.append(('prime', date_str))
                            result["prime_available"] = True
                        else:
                            all_dates.append(('regular', date_str))

        # PRIORIDAD 1: Buscar fecha de Prime (más rápida)

        # PRIMERA PRIORIDAD: Detectar same-day/next-day ("hoy", "today", "mañana", "tomorrow")
        if not all_dates:
            same_day_patterns = [
                # "miembros Prime reciben entrega GRATIS hoy"
                # "Prime members get FREE delivery today"
                r'(?:miembros?\s+)?Prime\s+(?:members?\s+)?(?:get|reciben)\s+(?:entrega\s+)?(?:GRATIS|FREE)?\s+(?:delivery\s+)?(?:entrega\s+)?(hoy|today)',
                # "FREE delivery today for Prime members"
                r'FREE\s+delivery\s+(today|hoy)\s+for\s+Prime\s+members?',
            ]

            for pattern in same_day_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    # Same-day delivery detectado
                    from datetime import datetime as dt
                    today = dt.now()
                    today_str = today.strftime("%A, %B %d")  # "Friday, December 20"
                    all_dates.append(('prime', today_str))
                    result["prime_available"] = True
                    break

        # SEGUNDA PRIORIDAD: Next-day delivery
        if not all_dates:
            next_day_patterns = [
                # "miembros Prime reciben entrega GRATIS mañana"
                # "Prime members get FREE delivery tomorrow"
                r'(?:miembros?\s+)?Prime\s+(?:members?\s+)?(?:get|reciben)\s+(?:entrega\s+)?(?:GRATIS|FREE)?\s+(?:delivery\s+)?(?:entrega\s+)?(mañana|tomorrow)',
                # "FREE delivery tomorrow for Prime members"
                r'FREE\s+delivery\s+(tomorrow|mañana)\s+for\s+Prime\s+members?',
            ]

            for pattern in next_day_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    # Next-day delivery detectado
                    from datetime import datetime as dt, timedelta
                    tomorrow = dt.now() + timedelta(days=1)
                    tomorrow_str = tomorrow.strftime("%A, %B %d")  # "Saturday, December 21"
                    all_dates.append(('prime', tomorrow_str))
                    result["prime_available"] = True
                    break

        # TERCERA PRIORIDAD: Buscar fechas específicas de Prime
        if not all_dates:
            prime_patterns = [
                # "FREE delivery Monday, December 29 for Prime members"
                r'FREE\s+delivery\s+((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+)\s+for\s+Prime\s+members?',
                # "Or Prime members get FREE delivery Monday, December 22"
                # "Prime members get FREE delivery Sunday, December 21"
                r'Prime\s+members?\s+get\s+FREE\s+delivery\s+((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+)',
                # Versión más flexible sin "FREE"
                r'Prime\s+members?\s+get\s+\w+\s+delivery\s+((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+)',
                # "miembros Prime reciben entrega GRATIS el domingo, 21 de diciembre"
                r'miembros?\s+Prime\s+[^<>]{0,100}?entrega[^<>]{0,50}?el\s+((?:lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo),?\s+\d+\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre))',
            ]

            # Buscar fecha de Prime primero
            for pattern in prime_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    all_dates.append(('prime', match.group(1).strip()))
                    result["prime_available"] = True
                    break

        # PRIORIDAD 2: Buscar SOLO fechas de FREE delivery (ignorar "fastest delivery" que se paga)
        delivery_patterns = [
            # SOLO FREE delivery con rangos "FREE delivery December 26 - 28"
            r'FREE\s+delivery\s+(?:<[^>]+>)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+\s*-\s*((?:January|February|March|April|May|June|July|August|September|October|November|December)?\s*\d+)',
            # SOLO FREE delivery con fecha simple "FREE delivery Friday, December 26"
            r'FREE\s+delivery\s+(?:<[^>]+>)?((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+)',
            # Atributos data-* con delivery-price="FREE"
            r'data-csa-c-delivery-price="FREE"[^>]*data-csa-c-delivery-time="((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+(?:\s*-\s*\d+)?)"',
            # Español: "entrega GRATIS el sábado, 27 de diciembre"
            r'entrega\s+(?:GRATIS|gratis)\s+el\s+((?:lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo),?\s+\d+\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre))',
        ]

        # Variable para rastrear el último mes visto (para rangos como "December 26 - 28")
        last_seen_month = None

        for pattern in delivery_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match_date in matches[:3]:  # Max 3 fechas por patrón
                date_str = match_date.strip()

                # Si la fecha es solo un número (ej: "28" del rango "December 26 - 28")
                # Agregarle el mes del contexto
                if date_str.isdigit():
                    # Buscar el mes en el contexto anterior
                    context_match = re.search(
                        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+\s*-\s*' + date_str,
                        html,
                        re.IGNORECASE
                    )
                    if context_match:
                        month = context_match.group(1)
                        date_str = f"{month} {date_str}"

                all_dates.append(('regular', date_str))

        # Si encontramos fechas, elegir la MÁS TARDÍA para ser CONSERVADOR
        if all_dates:
            # Si hay fecha de Prime explícita, usarla
            prime_dates = [d[1] for d in all_dates if d[0] == 'prime']
            if prime_dates:
                result["delivery_date"] = prime_dates[0]
                result["prime_available"] = True
            else:
                # Sino, parsear todas las fechas y elegir la MÁS TARDÍA
                # (para ser conservador y evitar aceptar productos que pueden tardar más)
                from datetime import datetime as dt

                parsed_dates = []
                for date_type, date_str in all_dates:
                    try:
                        # Normalizar fecha
                        clean_date = date_str.replace(',', '').strip()

                        # Parsear "Monday December 22" o "December 22" -> date object
                        parts = clean_date.split()

                        month_name = None
                        day_num = None

                        # Intentar encontrar mes y día
                        for i, part in enumerate(parts):
                            months = {
                                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                                'september': 9, 'october': 10, 'november': 11, 'december': 12
                            }
                            month_num = months.get(part.lower())
                            if month_num and i + 1 < len(parts):
                                try:
                                    day_num = int(parts[i + 1])
                                    month_name = month_num
                                    break
                                except:
                                    pass

                        if month_name and day_num:
                            today = dt.now()
                            year = today.year
                            if month_name < today.month or (month_name == today.month and day_num < today.day):
                                year += 1

                            date_obj = dt(year, month_name, day_num)
                            parsed_dates.append((date_obj, date_str))
                    except:
                        pass

                # Elegir la fecha MÁS TEMPRANA
                # (la fecha de Prime es la más temprana, queremos detectarla)
                if parsed_dates:
                    earliest = min(parsed_dates, key=lambda x: x[0])
                    result["delivery_date"] = earliest[1]
                elif all_dates:
                    # Fallback: usar la primera fecha encontrada
                    result["delivery_date"] = all_dates[0][1]

        # Calcular días hasta entrega
        if result["delivery_date"]:
            try:
                date_str = result["delivery_date"].replace(',', '').strip()

                # Normalizar español -> inglés
                months_es = {
                    'enero': 'January', 'febrero': 'February', 'marzo': 'March',
                    'abril': 'April', 'mayo': 'May', 'junio': 'June',
                    'julio': 'July', 'agosto': 'August', 'septiembre': 'September',
                    'octubre': 'October', 'noviembre': 'November', 'diciembre': 'December'
                }

                for es, en in months_es.items():
                    date_str = date_str.replace(es, en)

                date_str = date_str.replace(' de ', ' ')

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

                    max_days = int(os.getenv("MAX_DELIVERY_DAYS", "3"))
                    if days_until <= max_days:
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
    test_zipcode = sys.argv[2] if len(sys.argv) > 2 else os.getenv("BUYER_ZIPCODE", "33172")

    print("=" * 80)
    print(f"TEST: Verificando disponibilidad con API Glow (RÁPIDO)")
    print(f"ASIN: {test_asin}")
    print(f"Zipcode: {test_zipcode}")
    print("=" * 80)
    print()

    import time
    start = time.time()

    result = check_real_availability_glow_api(test_asin, test_zipcode)

    elapsed = time.time() - start

    print("Resultados:")
    print(f"  ✅ Disponible: {result.get('available', False)}")
    print(f"  📦 In Stock: {result.get('in_stock', False)}")
    print(f"  ⭐ Prime: {result.get('prime_available', False)}")
    print(f"  💰 Precio: ${result['price']}" if result.get('price') else "  💰 Precio: No encontrado")
    print(f"  📅 Fecha entrega: {result.get('delivery_date')}")
    print(f"  ⏱️  Días hasta entrega: {result.get('days_until_delivery')}")
    print(f"  🚀 Fast delivery (≤3d): {result.get('is_fast_delivery', False)}")
    print(f"  ⚡ Tiempo: {elapsed:.1f}s")

    if result.get('error'):
        print(f"  ⚠️  Error: {result['error']}")

    print()

    max_days = int(os.getenv("MAX_DELIVERY_DAYS", "3"))

    if result.get('is_fast_delivery'):
        print(f"✅ ACEPTAR - Llega rápido (≤{max_days} días)")
    elif result.get('days_until_delivery') and result['days_until_delivery'] > max_days:
        print(f"❌ RECHAZAR - Tarda {result['days_until_delivery']} días (>{max_days}d)")
    else:
        print("⚠️  No se pudo determinar tiempo de entrega")

    print()
    print("💡 Esta técnica es la que usa software comercial de sync")
    print("   - API interna no documentada de Amazon")
    print("   - 4x más rápido que Selenium")
    print("   - No requiere Chrome")
