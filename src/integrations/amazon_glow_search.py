#!/usr/bin/env python3
"""
Amazon Search usando Glow API
Busca keywords en Amazon y extrae ASINs de los resultados
"""
import os
import re
import requests
import random
import time
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(override=True)

# Lista de User-Agents para rotar
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
]

def get_random_user_agent():
    """Retorna un User-Agent aleatorio de la lista"""
    return random.choice(USER_AGENTS)


def search_amazon_keyword(keyword: str, max_results: int = 10, zipcode: str = None,
                          filter_fast_delivery: bool = True) -> Dict:
    """
    Busca una keyword en Amazon y extrae los ASINs de los resultados.

    Args:
        keyword: Keyword a buscar
        max_results: Máximo número de ASINs a retornar (default: 10)
        zipcode: Zipcode del comprador para delivery context (default: desde .env)
        filter_fast_delivery: Si True, solo retorna productos con envío rápido visible (default: True)

    Returns:
        Dict con:
        {
            "keyword": str,
            "asins": List[str],
            "total_found": int,
            "total_checked": int,  # Total de productos revisados
            "error": str or None
        }
    """
    if not zipcode:
        zipcode = os.getenv("BUYER_ZIPCODE", "33172")

    result = {
        "keyword": keyword,
        "asins": [],
        "total_found": 0,
        "total_checked": 0,
        "error": None
    }

    session = requests.Session()
    user_agent = get_random_user_agent()

    session.headers.update({
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
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

    # Configurar proxy si está disponible
    proxies = None
    proxy_url = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
    if proxy_url:
        proxies = {
            'http': proxy_url,
            'https': proxy_url,
        }

    try:
        # Paso 1: GET homepage para obtener cookies iniciales
        homepage_url = "https://www.amazon.com"
        session.get(homepage_url, timeout=15, proxies=proxies)

        # Paso 2: Llamar a API Glow para establecer zipcode (opcional pero mejora relevancia)
        try:
            glow_url = "https://www.amazon.com/portal-migration/hz/glow/address-change"
            params = {
                'actionSource': 'glow',
                'deviceType': 'desktop',
                'pageType': 'Search',
                'storeContext': 'pc'
            }
            payload = {
                'locationType': 'LOCATION_INPUT',
                'zipCode': zipcode,
                'deviceType': 'web',
                'storeContext': 'generic',
                'pageType': 'Search'
            }
            headers = {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': homepage_url
            }
            session.post(glow_url, params=params, json=payload, headers=headers, timeout=10, proxies=proxies)
        except:
            # Si falla Glow, continuar de todas formas
            pass

        # Paso 3: Realizar búsqueda
        search_url = "https://www.amazon.com/s"
        params = {
            'k': keyword,
            'ref': 'nb_sb_noss'
        }

        response = session.get(search_url, params=params, timeout=30, proxies=proxies)

        if response.status_code != 200:
            result["error"] = f"HTTP {response.status_code}"
            return result

        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        # Extraer ASINs de los resultados CON filtro de delivery
        asins_found = []
        products_checked = 0

        # Buscar productos con data-asin
        products = soup.find_all('div', {'data-asin': True})

        for product in products:
            asin = product.get('data-asin', '').strip()

            # Validar ASIN
            if not asin or len(asin) != 10:
                continue

            # SKIP SPONSORED: Ignorar productos patrocinados
            product_html = str(product)
            if re.search(r'Sponsored', product_html, re.IGNORECASE):
                continue

            products_checked += 1

            # Si no queremos filtrar, agregar directamente
            if not filter_fast_delivery:
                if asin not in asins_found:
                    asins_found.append(asin)
                    if len(asins_found) >= max_results:
                        break
                continue

            # FILTRO DE ENVÍO RÁPIDO: Usar los mismos criterios que el sync
            # El sync usa MAX_DELIVERY_DAYS (default: 4 días) para determinar fast delivery.
            # En resultados de búsqueda no podemos calcular días exactos, pero buscamos
            # los mismos indicadores que representan delivery ≤ MAX_DELIVERY_DAYS días.
            # (product_html ya fue obtenido arriba para el check de Sponsored)

            # Indicadores de envío rápido consistentes con criterio de sync:
            # Buscar indicadores VISIBLES de delivery, no metadata JSON
            fast_delivery_indicators = [
                r'FREE\s+delivery',                                    # "FREE delivery Mon, Jan 12"
                r'Get\s+it\s+by',                                      # "Get it by Tomorrow"
                r'Get\s+it\s+(today|tomorrow)',                        # "Get it today"
                r'Arrives\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)',        # "Arrives Mon, Jan 12"
                r'\$[\d.]+\s+delivery\s+in\s+\d+\s+hours',           # "$4.99 delivery in 3 hours"
            ]

            has_fast_delivery = False
            for pattern in fast_delivery_indicators:
                if re.search(pattern, product_html, re.IGNORECASE):
                    has_fast_delivery = True
                    break

            # Solo agregar si tiene envío rápido
            if has_fast_delivery and asin not in asins_found:
                asins_found.append(asin)
                if len(asins_found) >= max_results:
                    break

        result["asins"] = asins_found
        result["total_found"] = len(asins_found)
        result["total_checked"] = products_checked

        return result

    except requests.Timeout:
        result["error"] = "Request timeout"
        return result
    except requests.RequestException as e:
        result["error"] = f"Request error: {str(e)}"
        return result
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
        return result


def search_multiple_keywords(keywords: List[str], max_results_per_keyword: int = 10,
                             delay_between_requests: float = 2.0, zipcode: str = None,
                             filter_fast_delivery: bool = True) -> List[Dict]:
    """
    Busca múltiples keywords en Amazon.

    Args:
        keywords: Lista de keywords a buscar
        max_results_per_keyword: Máximo de ASINs por keyword
        delay_between_requests: Delay en segundos entre requests (para evitar rate limiting)
        zipcode: Zipcode del comprador
        filter_fast_delivery: Si True, solo retorna productos con envío rápido visible

    Returns:
        Lista de resultados (uno por keyword)
    """
    results = []

    for i, keyword in enumerate(keywords, 1):
        print(f"  [{i}/{len(keywords)}] Buscando: {keyword}...")

        result = search_amazon_keyword(keyword, max_results=max_results_per_keyword,
                                      zipcode=zipcode, filter_fast_delivery=filter_fast_delivery)
        results.append(result)

        if result["error"]:
            print(f"    ⚠️  Error: {result['error']}")
        else:
            if filter_fast_delivery:
                print(f"    ✅ Encontrados {result['total_found']} ASINs con envío rápido (revisados: {result['total_checked']})")
            else:
                print(f"    ✅ Encontrados {result['total_found']} ASINs")

        # Delay entre requests (excepto en el último)
        if i < len(keywords):
            time.sleep(delay_between_requests)

    return results
