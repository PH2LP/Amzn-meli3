#!/usr/bin/env python3
"""
amazon_scraper_with_login.py
═══════════════════════════════════════════════════════════════════════════════
SCRAPER DE AMAZON CON LOGIN PERSISTENTE
═══════════════════════════════════════════════════════════════════════════════

Usa Selenium + tu cuenta de Amazon para scrapear reviews.
Las cookies se guardan y reutilizan automáticamente.

SETUP INICIAL (solo una vez):
    brew install chromedriver
    pip3 install --break-system-packages selenium

PRIMER USO (con login manual):
    python3 amazon_scraper_with_login.py --asin B0CYM126TT --login

USOS SIGUIENTES (automático):
    python3 amazon_scraper_with_login.py --asin B0CYM126TT
"""

import os
import sys
import json
import time
import pickle
import argparse
from pathlib import Path
from typing import List, Dict

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
except ImportError:
    print("❌ Selenium no instalado")
    print("\nInstalar:")
    print("  pip3 install --break-system-packages selenium")
    print("  brew install chromedriver")
    sys.exit(1)


COOKIES_FILE = Path("storage/amazon_cookies.pkl")


def setup_driver(headless=False):
    """Configura Chrome con opciones anti-detección"""
    chrome_options = Options()

    if headless:
        chrome_options.add_argument("--headless")

    # Anti-detección
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")

    # User agent real
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # Tamaño de ventana
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=chrome_options)

    # Script anti-detección adicional
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """
    })

    return driver


def save_cookies(driver):
    """Guarda cookies de la sesión"""
    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    cookies = driver.get_cookies()

    with open(COOKIES_FILE, 'wb') as f:
        pickle.dump(cookies, f)

    print(f"✅ Cookies guardadas en: {COOKIES_FILE}")


def load_cookies(driver):
    """Carga cookies guardadas"""
    if not COOKIES_FILE.exists():
        return False

    try:
        with open(COOKIES_FILE, 'rb') as f:
            cookies = pickle.load(f)

        # Ir a Amazon primero
        driver.get("https://www.amazon.com")
        time.sleep(2)

        # Cargar cookies
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                # Algunas cookies pueden fallar, continuar
                pass

        print("✅ Cookies cargadas")
        return True

    except Exception as e:
        print(f"⚠️  Error cargando cookies: {e}")
        return False


def manual_login(driver, is_business=True):
    """Login manual - el usuario ingresa credenciales en el navegador"""
    print("\n" + "="*80)
    print("🔐 LOGIN MANUAL EN AMAZON")
    print("="*80)
    print("\nSe abrirá Chrome. Por favor:")
    print("1. Ingresa tu email/teléfono")
    print("2. Ingresa tu contraseña")
    print("3. Completa verificación 2FA si es necesario")
    print("4. Espera a que cargue la página principal de Amazon")
    print("\n⏱️  Tienes 2 minutos para completar el login...")
    print("="*80 + "\n")

    # Si es Amazon Business, ir a la página de Business
    if is_business:
        print("🏢 Detectado: Amazon Business")
        driver.get("https://www.amazon.com/business/login")
    else:
        driver.get("https://www.amazon.com/ap/signin")

    # Esperar hasta que el usuario haga login (max 2 minutos)
    wait_time = 120
    start_time = time.time()

    while time.time() - start_time < wait_time:
        # Verificar si ya está logueado
        if "signin" not in driver.current_url.lower():
            print("\n✅ Login exitoso!")
            save_cookies(driver)
            return True

        time.sleep(2)

    print("\n❌ Timeout - Login no completado")
    return False


def scrape_reviews(driver, asin: str, max_reviews=30, is_business=True) -> List[Dict]:
    """Scrape reviews del producto"""
    print(f"\n🕷️  Scrapeando reviews de ASIN: {asin}")

    # URL diferente para Amazon Business
    if is_business:
        product_url = f"https://www.amazon.com/dp/{asin}"
        print(f"📦 Verificando producto (Business): {product_url}")
    else:
        product_url = f"https://www.amazon.com/dp/{asin}"
        print(f"📦 Verificando producto: {product_url}")

    driver.get(product_url)
    time.sleep(3)

    # Verificar si pide login
    if "signin" in driver.current_url.lower():
        print("⚠️  Sesión expirada, relogin necesario")
        return []

    # Verificar si el producto existe
    if "looking for something" in driver.page_source.lower() or "page on our site" in driver.page_source.lower():
        print(f"❌ ASIN {asin} no existe o no está disponible")
        return []

    print("✅ Producto existe")

    # Ahora buscar el link de "See all reviews" o ir directo a reviews
    try:
        # Intentar hacer click en "See all reviews"
        see_all_reviews = driver.find_element(By.CSS_SELECTOR, '[data-hook="see-all-reviews-link-foot"]')
        reviews_url = see_all_reviews.get_attribute('href')
        print(f"📝 Yendo a reviews: {reviews_url}")
        driver.get(reviews_url)
    except:
        # Si no encuentra el botón, usar URL directa alternativa
        reviews_url = f"https://www.amazon.com/product-reviews/{asin}/ref=cm_cr_arp_d_viewopt_srt?reviewerType=all_reviews&sortBy=recent"
        print(f"📝 Yendo a reviews (método alternativo): {reviews_url}")
        driver.get(reviews_url)

    time.sleep(3)

    reviews = []
    page = 1
    max_pages = 3  # Limitar a 3 páginas

    while len(reviews) < max_reviews and page <= max_pages:
        print(f"📄 Página {page}...")

        try:
            # Esperar a que carguen las reviews
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-hook="review"]'))
            )

            # Extraer reviews
            review_elements = driver.find_elements(By.CSS_SELECTOR, '[data-hook="review"]')

            for elem in review_elements:
                if len(reviews) >= max_reviews:
                    break

                try:
                    # Rating
                    try:
                        rating_elem = elem.find_element(By.CSS_SELECTOR, '[data-hook="review-star-rating"]')
                        rating_text = rating_elem.text.strip()
                        rating = float(rating_text.split()[0])
                    except:
                        rating = 0

                    # Título
                    try:
                        title_elem = elem.find_element(By.CSS_SELECTOR, '[data-hook="review-title"] span:not([class])')
                        title = title_elem.text.strip()
                    except:
                        title = ""

                    # Texto
                    try:
                        text_elem = elem.find_element(By.CSS_SELECTOR, '[data-hook="review-body"] span')
                        text = text_elem.text.strip()
                    except:
                        text = ""

                    # Verificado
                    verified = len(elem.find_elements(By.CSS_SELECTOR, '[data-hook="avp-badge"]')) > 0

                    # Autor
                    try:
                        author_elem = elem.find_element(By.CSS_SELECTOR, '.a-profile-name')
                        author = author_elem.text.strip()
                    except:
                        author = ""

                    # Fecha
                    try:
                        date_elem = elem.find_element(By.CSS_SELECTOR, '[data-hook="review-date"]')
                        date = date_elem.text.strip()
                    except:
                        date = ""

                    if text:  # Solo agregar si tiene texto
                        reviews.append({
                            'rating': rating,
                            'title': title,
                            'text': text,
                            'verified': verified,
                            'author': author,
                            'date': date
                        })

                except Exception as e:
                    continue

            print(f"   ✅ {len(reviews)} reviews extraídas hasta ahora")

            # Ir a siguiente página
            if len(reviews) < max_reviews and page < max_pages:
                try:
                    next_button = driver.find_element(By.CSS_SELECTOR, '.a-pagination .a-last a')
                    next_button.click()
                    time.sleep(3)
                    page += 1
                except:
                    print("   ℹ️  No hay más páginas")
                    break
            else:
                break

        except Exception as e:
            print(f"   ⚠️  Error en página {page}: {e}")
            break

    return reviews


def extract_asin(input_str):
    """Extrae ASIN de un link de Amazon o retorna el ASIN directamente"""
    # Si es un link de Amazon
    if 'amazon.com' in input_str and '/dp/' in input_str:
        # Extraer ASIN del formato /dp/ASIN
        asin = input_str.split('/dp/')[1].split('?')[0].split('/')[0]
        return asin
    # Si ya es un ASIN directamente
    return input_str


def main():
    parser = argparse.ArgumentParser(description="Scraper de Amazon con login")
    parser.add_argument("--asin", required=True, help="ASIN del producto o link completo de Amazon")
    parser.add_argument("--login", action="store_true", help="Hacer login manual (primera vez)")
    parser.add_argument("--headless", action="store_true", help="Modo headless (sin ventana)")
    parser.add_argument("--output", help="Archivo de salida")
    parser.add_argument("--business", action="store_true", default=True, help="Amazon Business account (default: True)")

    args = parser.parse_args()

    # Extraer ASIN del input
    asin = extract_asin(args.asin)
    print(f"\n📋 ASIN: {asin}")

    print("\n" + "="*80)
    print("🕷️  AMAZON SCRAPER CON LOGIN")
    print("="*80 + "\n")

    # Setup driver
    driver = setup_driver(headless=args.headless and not args.login)

    try:
        # Login o cargar cookies
        if args.login or not COOKIES_FILE.exists():
            print("🔐 Login requerido...")
            if not manual_login(driver, is_business=args.business):
                print("❌ Login fallido")
                driver.quit()
                sys.exit(1)
        else:
            print("🍪 Cargando cookies guardadas...")
            if not load_cookies(driver):
                print("⚠️  Cookies inválidas, se requiere login")
                if not manual_login(driver, is_business=args.business):
                    driver.quit()
                    sys.exit(1)

        # Scrape reviews
        reviews = scrape_reviews(driver, asin, is_business=args.business)

        if not reviews:
            print("\n❌ No se obtuvieron reviews")
            print("\n💡 Intenta de nuevo con --login para renovar la sesión")
            driver.quit()
            sys.exit(1)

        # Mostrar resultados
        print(f"\n{'='*80}")
        print(f"✅ REVIEWS OBTENIDAS: {len(reviews)}")
        print(f"{'='*80}\n")

        # Estadísticas
        avg_rating = sum(r['rating'] for r in reviews) / len(reviews)
        verified_count = sum(1 for r in reviews if r['verified'])

        print("📊 ESTADÍSTICAS:")
        print(f"   Rating promedio: {avg_rating:.1f}/5.0")
        print(f"   Verificadas: {verified_count}/{len(reviews)}")

        # Muestra
        print(f"\n📝 MUESTRA (primeras 3):\n")
        for i, review in enumerate(reviews[:3], 1):
            print(f"{i}. {'⭐' * int(review['rating'])} ({review['rating']}/5) - {review['author']}")
            print(f"   {review['title']}")
            print(f"   {review['text'][:150]}...")
            print(f"   Verificada: {'✅' if review['verified'] else '❌'}")
            print(f"   Fecha: {review['date']}\n")

        # Guardar
        output_file = args.output or f"storage/reviews_{asin}.json"
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(reviews, f, indent=2, ensure_ascii=False)

        print(f"💾 Reviews guardadas en: {output_path}")

        print(f"\n✅ LISTO! Ahora puedes usar estas reviews con Claude:")
        print(f"   python3 scripts/research/product_qa_with_rag.py --asin {asin}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
