#!/usr/bin/env python3
"""
Selenium Scraper - Verifica FBA/Prime REAL desde la página de Amazon
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def scrape_amazon_seller_info(asin, headless=True):
    """
    Usa Selenium para obtener info REAL de seller/shipping

    Args:
        asin: ASIN del producto
        headless: Si True, no muestra ventana del browser

    Returns:
        dict con info del seller
    """
    print(f"\n{'='*70}")
    print(f"🔍 Scrapeando {asin} con Selenium...")
    print('='*70)

    # Configurar Chrome
    chrome_options = Options()
    if headless:
        chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    # Iniciar Chrome
    print("Iniciando Chrome...")
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        return {'error': f'No se pudo iniciar Chrome: {e}'}

    try:
        # Abrir producto
        url = f'https://www.amazon.com/dp/{asin}'
        print(f"Abriendo: {url}")
        driver.get(url)

        # Esperar a que cargue completamente
        print("Esperando a que cargue la página...")
        time.sleep(5)  # Dar más tiempo

        # Scroll down para que cargue lazy content
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(2)

        result = {
            'asin': asin,
            'url': url,
        }

        # 1. Buscar badge Prime
        try:
            prime_badge = driver.find_elements(By.CSS_SELECTOR, '[aria-label*="Prime"]')
            result['has_prime_badge'] = len(prime_badge) > 0
            print(f"Prime badge: {'✅ Sí' if result['has_prime_badge'] else '❌ No'}")
        except:
            result['has_prime_badge'] = False

        # 2. Buscar info de seller/shipping - MÚLTIPLES SELECTORES
        seller_patterns = [
            # Merchant info div
            '#merchant-info',
            'div#merchant-info',
            '#merchantInfoFeature_feature_div',
            # Tabular buybox
            '#tabular-buybox',
            '#tabular-buybox-truncate-1',
            # Seller info spans
            'span.tabular-buybox-text',
            'span[class*="offer-display"]',
            # XPath más específicos
            '//div[@id="merchant-info"]//span',
            '//div[contains(@id, "merchant")]',
            '//span[contains(text(), "Ships from")]',
            '//span[contains(text(), "Sold by")]',
            '//div[contains(text(), "Ships from")]',
            '//a[contains(text(), "Sold by")]',
        ]

        seller_text = None
        for pattern in seller_patterns:
            try:
                if pattern.startswith('//'):
                    # XPath
                    elements = driver.find_elements(By.XPATH, pattern)
                else:
                    # CSS
                    elements = driver.find_elements(By.CSS_SELECTOR, pattern)

                if elements:
                    for elem in elements:
                        text = elem.text.strip()
                        if text and ('ships' in text.lower() or 'sold' in text.lower()):
                            seller_text = text
                            print(f"✅ Encontrado con selector: {pattern}")
                            print(f"   Texto: {text[:100]}")
                            break
                    if seller_text:
                        break
            except Exception as e:
                continue

        # Si no encontró con selectores, buscar en todo el body
        if not seller_text:
            print("⚠️  No encontrado con selectores, buscando en página completa...")
            try:
                body_text = driver.find_element(By.TAG_NAME, 'body').text
                # Buscar patrón "Ships from ... Sold by ..."
                import re
                patterns_to_try = [
                    r'(Ships from and sold by [^\.]+)',
                    r'(Sold by [^\.]+and Fulfilled by Amazon)',
                    r'(Ships from[^\.]+\.?\s*Sold by[^\.]+\.?)',
                ]
                for pattern in patterns_to_try:
                    match = re.search(pattern, body_text, re.IGNORECASE)
                    if match:
                        seller_text = match.group(1).strip()
                        print(f"✅ Encontrado en body: {seller_text[:100]}")
                        break
            except:
                pass

        # Si aún no encontró, guardar HTML para debug
        if not seller_text:
            html_file = f'/tmp/amazon_{asin}.html'
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            print(f"⚠️  HTML guardado en: {html_file}")
            print(f"   Abrí el archivo para ver el HTML completo")

        result['seller_text'] = seller_text

        # 3. Analizar el texto para determinar FBA/FBM
        if seller_text:
            seller_lower = seller_text.lower()

            # Patrones FBA
            is_amazon_seller = 'sold by amazon.com' in seller_lower
            is_ships_from_amazon = 'ships from amazon' in seller_lower
            is_fulfilled_by_amazon = 'fulfilled by amazon' in seller_lower

            # Patrones FBM
            is_shipped_by_seller = 'shipped by' in seller_lower and 'amazon' not in seller_lower.split('shipped by')[1][:30]
            has_third_party_name = not is_amazon_seller and 'sold by' in seller_lower

            result['is_amazon_seller'] = is_amazon_seller
            result['is_ships_from_amazon'] = is_ships_from_amazon
            result['is_fulfilled_by_amazon'] = is_fulfilled_by_amazon
            result['is_fbm'] = is_shipped_by_seller or (has_third_party_name and not is_fulfilled_by_amazon)
            result['is_fba'] = (is_amazon_seller or is_fulfilled_by_amazon) and not result['is_fbm']
        else:
            result['is_fba'] = None
            result['is_fbm'] = None
            print("❌ No se pudo encontrar info de seller")

        # 4. Delivery date
        try:
            delivery_elem = driver.find_elements(By.CSS_SELECTOR, '[data-csa-c-content-id*="DEXUnifiedCXPDM"]')
            if delivery_elem:
                result['delivery_text'] = delivery_elem[0].text
                print(f"Delivery: {delivery_elem[0].text[:50]}...")
        except:
            result['delivery_text'] = None

        # 5. Stock
        try:
            add_to_cart = driver.find_elements(By.ID, 'add-to-cart-button')
            result['in_stock'] = len(add_to_cart) > 0
            print(f"In Stock: {'✅ Sí' if result['in_stock'] else '❌ No'}")
        except:
            result['in_stock'] = False

        # Decisión final
        result['is_valid'] = (
            result.get('has_prime_badge', False) and
            result.get('is_fba', False) and
            not result.get('is_fbm', False) and
            result.get('in_stock', False)
        )

        return result

    except Exception as e:
        return {'error': str(e)}

    finally:
        driver.quit()


if __name__ == '__main__':
    # Probar con el ASIN problemático
    test_asins = {
        'B0D2F4T9RJ': 'Usuario ve: "Ships from and sold by FocusProAudio"',
        'B08X6LYPHK': 'Debería ser FBA real',
    }

    print('='*70)
    print('SELENIUM SCRAPER TEST')
    print('='*70)
    print('\nEsto va a abrir Chrome y scrapear Amazon...')
    print('(puede tardar 5-10 seg por producto)\n')

    for asin, description in test_asins.items():
        print(f"\n{'='*70}")
        print(f"{asin}: {description}")
        print('='*70)

        result = scrape_amazon_seller_info(asin, headless=False)  # headless=False para que veas la ventana

        if 'error' in result:
            print(f"\n❌ ERROR: {result['error']}")
        else:
            print(f"\n{'='*70}")
            print("RESULTADO:")
            print('='*70)
            print(f"✅ Seller text: {result.get('seller_text', 'N/A')}")
            print(f"   Is FBA: {result.get('is_fba')}")
            print(f"   Is FBM: {result.get('is_fbm')}")
            print(f"   Has Prime: {result.get('has_prime_badge')}")
            print(f"   In Stock: {result.get('in_stock')}")
            print(f"\n{'✅ VÁLIDO - ACEPTAR' if result.get('is_valid') else '❌ INVÁLIDO - RECHAZAR'}")

        print("\nEsperando 3 segundos antes del siguiente...\n")
        time.sleep(3)

    print('\n' + '='*70)
    print('COMPARACIÓN CON APIs:')
    print('='*70)
    print("""
    B0D2F4T9RJ:
      Amazon SP-API: IsFBA=True (MINTIÓ)
      SearchAPI: ships_from=Amazon (MINTIÓ)
      Selenium: ¿Detectó FocusProAudio correctamente?
    """)
