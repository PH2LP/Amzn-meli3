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


def extract_price_from_product(product) -> Optional[float]:
    """
    Extrae el precio de un producto de los resultados de búsqueda de Amazon.

    Args:
        product: BeautifulSoup element del producto

    Returns:
        Precio como float, o None si no se encuentra
    """
    # Patrones comunes de precio en Amazon search results
    price_patterns = [
        # Precio en span con clase a-price
        {'name': 'span', 'class_': 'a-price'},
        # Precio en span con clase a-offscreen (precio accesible)
        {'name': 'span', 'class_': 'a-offscreen'},
        # Precio whole + fraction
        {'name': 'span', 'class_': 'a-price-whole'},
    ]

    for pattern in price_patterns:
        price_elem = product.find(pattern['name'], class_=re.compile(pattern['class_']))
        if price_elem:
            # Buscar dentro del elemento o en a-offscreen si existe
            offscreen = price_elem.find('span', class_='a-offscreen')
            if offscreen:
                price_text = offscreen.get_text(strip=True)
            else:
                price_text = price_elem.get_text(strip=True)

            # Limpiar y convertir: "$123.45" -> 123.45
            price_text = price_text.replace('$', '').replace(',', '').strip()

            # Intentar extraer número
            match = re.search(r'(\d+(?:\.\d{1,2})?)', price_text)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue

    return None


def get_product_variants(asin: str, session: requests.Session, zipcode: str = None,
                        min_price: float = 28.0, max_price: float = 450.0,
                        max_delivery_days: int = 4) -> List[str]:
    """
    Obtiene las variantes de un producto y retorna los ASINs que cumplen con los criterios.

    Args:
        asin: ASIN del producto padre
        session: Sesión de requests configurada
        zipcode: Zipcode para verificar envío
        min_price: Precio mínimo permitido
        max_price: Precio máximo permitido
        max_delivery_days: Máximo días de envío

    Returns:
        Lista de ASINs de variantes que cumplen criterios (puede estar vacía)
    """
    valid_variants = []

    try:
        # Visitar página del producto
        product_url = f"https://www.amazon.com/dp/{asin}"
        response = session.get(product_url, timeout=15)

        if response.status_code != 200:
            return valid_variants

        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        # Buscar variantes en el HTML
        # Método 1: Buscar en twister-main (selector de variantes)
        variant_asins = set()

        # Buscar en data attributes de las opciones de variantes
        variant_selects = soup.find_all('select', {'id': re.compile(r'native_dropdown_selected_')})
        for select in variant_selects:
            options = select.find_all('option', {'value': True})
            for option in options:
                value = option.get('value', '')
                # El value puede contener el ASIN
                if len(value) == 10 and value.isalnum():
                    variant_asins.add(value)

        # Método 2: Buscar en links de variantes
        variant_links = soup.find_all('a', {'href': re.compile(r'/dp/[A-Z0-9]{10}')})
        for link in variant_links:
            href = link.get('href', '')
            match = re.search(r'/dp/([A-Z0-9]{10})', href)
            if match:
                variant_asins.add(match.group(1))

        # Método 3: Buscar en JSON embebido (twisterData)
        scripts = soup.find_all('script', {'type': 'text/javascript'})
        for script in scripts:
            script_text = script.string if script.string else ''
            # Buscar patrones de ASIN en el script
            asin_matches = re.findall(r'"asin"\s*:\s*"([A-Z0-9]{10})"', script_text)
            for asin_match in asin_matches:
                variant_asins.add(asin_match)

        # Remover el ASIN original
        variant_asins.discard(asin)

        # Si no encontramos variantes, retornar vacío
        if not variant_asins:
            return valid_variants

        # Verificar cada variante (precio y envío)
        for variant_asin in variant_asins:
            variant_url = f"https://www.amazon.com/dp/{variant_asin}"

            try:
                variant_response = session.get(variant_url, timeout=10)
                if variant_response.status_code != 200:
                    continue

                variant_html = variant_response.text
                variant_soup = BeautifulSoup(variant_html, 'html.parser')

                # Verificar precio - múltiples métodos
                price = None

                # Método 1: a-price con a-offscreen (más común actualmente)
                price_span = variant_soup.find('span', class_='a-price')
                if price_span:
                    offscreen = price_span.find('span', class_='a-offscreen')
                    if offscreen:
                        price_text = offscreen.get_text(strip=True).replace('$', '').replace(',', '')
                        match = re.search(r'(\d+(?:\.\d{1,2})?)', price_text)
                        if match:
                            try:
                                price = float(match.group(1))
                            except ValueError:
                                pass

                # Método 2: priceblock IDs (legacy)
                if not price:
                    for price_id in ['priceblock_ourprice', 'priceblock_dealprice', 'priceblock_saleprice']:
                        price_elem = variant_soup.find('span', {'id': price_id})
                        if price_elem:
                            price_text = price_elem.get_text(strip=True).replace('$', '').replace(',', '')
                            match = re.search(r'(\d+(?:\.\d{1,2})?)', price_text)
                            if match:
                                try:
                                    price = float(match.group(1))
                                    break
                                except ValueError:
                                    continue

                # Método 3: Buscar en cualquier span con patrón $XX.XX
                if not price:
                    all_text = variant_html
                    # Buscar patrones como $99.99 o $99
                    price_matches = re.findall(r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', all_text)
                    if price_matches:
                        # Tomar el primer precio que parezca razonable (no código postal, etc)
                        for pm in price_matches:
                            try:
                                potential_price = float(pm.replace(',', ''))
                                if 1 <= potential_price <= 10000:  # Rango razonable
                                    price = potential_price
                                    break
                            except:
                                continue

                # Si no encontramos precio o está fuera de rango, skip
                if price is None:
                    continue
                if min_price is not None and price < min_price:
                    continue
                if max_price is not None and price > max_price:
                    continue

                # Verificar envío
                has_fast_delivery = False
                delivery_patterns = [
                    r'FREE\s+delivery',
                    r'Get\s+it\s+by',
                    r'Get\s+it\s+(today|tomorrow)',
                    r'Arrives\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)',
                ]

                for pattern in delivery_patterns:
                    if re.search(pattern, variant_html, re.IGNORECASE):
                        has_fast_delivery = True
                        break

                # Si cumple criterios, agregar
                if has_fast_delivery:
                    valid_variants.append(variant_asin)

                # Pequeño delay entre variantes
                time.sleep(0.5)

            except Exception:
                # Si falla una variante, continuar con las demás
                continue

        return valid_variants

    except Exception:
        return valid_variants


def search_amazon_keyword(keyword: str, max_results: int = 10, zipcode: str = None,
                          filter_fast_delivery: bool = True, use_blacklist: bool = True,
                          max_delivery_days: int = 4, min_price: float = 28.0, max_price: float = 450.0,
                          check_variants: bool = True) -> Dict:
    """
    Busca una keyword en Amazon y extrae los ASINs de los resultados.

    Args:
        keyword: Keyword a buscar
        max_results: Máximo número de ASINs a retornar (default: 10)
        zipcode: Zipcode del comprador para delivery context (default: desde .env)
        filter_fast_delivery: Si True, solo retorna productos con envío rápido visible (default: True)
        use_blacklist: Si True, aplica filtro de blacklist de marcas/categorías (default: True)
        max_delivery_days: Máximo días de envío permitidos (default: 4)
        min_price: Precio mínimo permitido en USD (default: 28.0, None = sin límite mínimo)
        max_price: Precio máximo permitido en USD (default: 450.0, None = sin límite)
        check_variants: Si True, analiza variantes de cada producto encontrado (default: True)

    Returns:
        Dict con:
        {
            "keyword": str,
            "asins": List[str],
            "total_found": int,
            "total_checked": int,  # Total de productos revisados
            "filtered_by_blacklist": int,  # Productos filtrados por blacklist
            "filtered_by_price": int,  # Productos filtrados por precio (min/max)
            "variants_found": int,  # Total de variantes encontradas
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
        "filtered_by_blacklist": 0,
        "filtered_by_price": 0,
        "variants_found": 0,
        "using_prime": False,
        "error": None
    }

    # Inicializar filtro de blacklist si está habilitado
    if use_blacklist:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from scripts.autonomous.brand_filter import ProductFilter
        product_filter = ProductFilter()
    else:
        product_filter = None

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

        # Paso 3: Realizar búsqueda con paginación (hasta 5 páginas)
        search_url = "https://www.amazon.com/s"
        asins_found = []
        products_checked = 0
        MAX_PAGES = 5

        for page in range(1, MAX_PAGES + 1):
            params = {
                'k': keyword,
                'page': page,
                'ref': 'nb_sb_noss'
            }

            response = session.get(search_url, params=params, timeout=30, proxies=proxies)

            if response.status_code != 200:
                result["error"] = f"HTTP {response.status_code}"
                return result

            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            # Buscar productos con data-asin
            products = soup.find_all('div', {'data-asin': True})

            # Si no hay productos en esta página, terminamos
            if not products:
                break

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

                # FILTRO DE PRECIO: Verificar que esté en rango min_price - max_price
                price = extract_price_from_product(product)
                if price is not None:
                    # Filtrar si es menor al mínimo
                    if min_price is not None and price < min_price:
                        result["filtered_by_price"] += 1
                        continue
                    # Filtrar si es mayor al máximo
                    if max_price is not None and price > max_price:
                        result["filtered_by_price"] += 1
                        continue

                # FILTRO DE BLACKLIST: Verificar marca/categoría/keywords prohibidas
                if product_filter:
                    # Extraer título del producto
                    title = ""
                    title_tag = product.find('h2', class_=re.compile('s-line-clamp'))
                    if title_tag:
                        title = title_tag.get_text(strip=True)
                    if not title:
                        title_span = product.find('span', {'aria-label': True})
                        if title_span:
                            title = title_span.get('aria-label', '').strip()
                    if not title:
                        h2_tag = product.find('h2')
                        if h2_tag:
                            title = h2_tag.get_text(strip=True)

                    # Extraer marca (si está visible)
                    brand = ""
                    brand_span = product.find('span', class_=re.compile('a-size-base-plus'))
                    if brand_span:
                        brand = brand_span.get_text(strip=True)

                    # Construir datos para el filtro
                    product_data = {
                        "title": title,
                        "brand": brand,
                        "product_type": "",
                    }

                    # Filtrar productos refurbished
                    if title and "refurbished" in title.lower():
                        result["filtered_by_blacklist"] += 1
                        continue

                    # Aplicar filtro (modo no estricto para no rechazar por falta de brand)
                    is_allowed, reason = product_filter.is_allowed(asin, product_data, strict=False)
                    if not is_allowed:
                        result["filtered_by_blacklist"] += 1
                        continue

                # Si no queremos filtrar, agregar directamente
                if not filter_fast_delivery:
                    if asin not in asins_found:
                        asins_found.append(asin)

                        # Revisar variantes si está habilitado
                        if check_variants:
                            variants = get_product_variants(
                                asin=asin,
                                session=session,
                                zipcode=zipcode,
                                min_price=min_price,
                                max_price=max_price,
                                max_delivery_days=max_delivery_days
                            )
                            for variant_asin in variants:
                                # Verificar que no sea el mismo ASIN y que no esté ya en la lista
                                if variant_asin != asin and variant_asin not in asins_found:
                                    asins_found.append(variant_asin)
                                    result["variants_found"] += 1

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

                    # Revisar variantes si está habilitado
                    if check_variants:
                        variants = get_product_variants(
                            asin=asin,
                            session=session,
                            zipcode=zipcode,
                            min_price=min_price,
                            max_price=max_price,
                            max_delivery_days=max_delivery_days
                        )
                        for variant_asin in variants:
                            # Verificar que no sea el mismo ASIN y que no esté ya en la lista
                            if variant_asin != asin and variant_asin not in asins_found:
                                asins_found.append(variant_asin)
                                result["variants_found"] += 1

                    if len(asins_found) >= max_results:
                        break

            # Si ya tenemos suficientes ASINs, salir del loop de páginas
            if len(asins_found) >= max_results:
                break

            # Delay entre páginas para evitar rate limiting
            if page < MAX_PAGES:
                time.sleep(1.5)

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
                             filter_fast_delivery: bool = True, use_blacklist: bool = True,
                             max_delivery_days: int = 4, min_price: float = 28.0, max_price: float = 450.0,
                             check_variants: bool = True) -> List[Dict]:
    """
    Busca múltiples keywords en Amazon.

    Args:
        keywords: Lista de keywords a buscar
        max_results_per_keyword: Máximo de ASINs por keyword
        delay_between_requests: Delay en segundos entre requests (para evitar rate limiting)
        zipcode: Zipcode del comprador
        filter_fast_delivery: Si True, solo retorna productos con envío rápido visible
        use_blacklist: Si True, aplica filtro de blacklist de marcas/categorías
        max_delivery_days: Máximo días de envío permitidos
        min_price: Precio mínimo permitido en USD (default: 28.0, None = sin límite mínimo)
        max_price: Precio máximo permitido en USD (default: 450.0, None = sin límite)
        check_variants: Si True, analiza variantes de cada producto encontrado (default: True)

    Returns:
        Lista de resultados (uno por keyword)
    """
    results = []

    for i, keyword in enumerate(keywords, 1):
        print(f"  [{i}/{len(keywords)}] Buscando: {keyword}...")

        result = search_amazon_keyword(keyword, max_results=max_results_per_keyword,
                                      zipcode=zipcode, filter_fast_delivery=filter_fast_delivery,
                                      use_blacklist=use_blacklist, max_delivery_days=max_delivery_days,
                                      min_price=min_price, max_price=max_price, check_variants=check_variants)
        results.append(result)

        if result["error"]:
            print(f"    ⚠️  Error: {result['error']}")
        else:
            prime_icon = "🔐" if result.get("using_prime") else ""
            blacklist_info = f" (blacklist: {result['filtered_by_blacklist']})" if result.get('filtered_by_blacklist', 0) > 0 else ""
            price_info = f" (precio: {result['filtered_by_price']})" if result.get('filtered_by_price', 0) > 0 else ""
            variants_info = f" +{result['variants_found']} variantes" if result.get('variants_found', 0) > 0 else ""
            if filter_fast_delivery:
                print(f"    ✅ {prime_icon} Encontrados {result['total_found']} ASINs con envío ≤{max_delivery_days}d (revisados: {result['total_checked']}){variants_info}{blacklist_info}{price_info}")
            else:
                print(f"    ✅ {prime_icon} Encontrados {result['total_found']} ASINs{variants_info}{blacklist_info}{price_info}")

        # Delay entre requests (excepto en el último)
        if i < len(keywords):
            time.sleep(delay_between_requests)

    return results
