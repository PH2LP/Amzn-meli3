#!/usr/bin/env python3
"""
scrape_amazon_reviews.py
═══════════════════════════════════════════════════════════════════════════════
SCRAPER DE REVIEWS DE AMAZON
═══════════════════════════════════════════════════════════════════════════════

Obtiene reviews de productos de Amazon para usar con RAG/Claude.

MÉTODOS:
1. Requests directo (puede ser bloqueado)
2. Selenium (más robusto)
3. ScrapingBee API (pago pero confiable)

USO:
    python3 scrape_amazon_reviews.py --asin B0CYM126TT
    python3 scrape_amazon_reviews.py --asin B0CYM126TT --method selenium
    python3 scrape_amazon_reviews.py --asin B0CYM126TT --method api
"""

import sys
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict


def scrape_with_requests(asin: str) -> List[Dict]:
    """Método 1: Scraping con requests (simple pero puede ser bloqueado)"""
    import requests
    from bs4 import BeautifulSoup

    print(f"🔍 Método: Requests directo")

    reviews = []

    # Headers para simular navegador
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

    # URL de reviews
    url = f"https://www.amazon.com/product-reviews/{asin}/ref=cm_cr_dp_d_show_all_btm"

    try:
        print(f"📡 Obteniendo: {url}")
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 503:
            print("❌ Amazon bloqueó el request (503)")
            print("   Intenta con --method selenium o --method api")
            return []

        if response.status_code != 200:
            print(f"❌ Error: Status {response.status_code}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')

        # Buscar divs de reviews
        review_divs = soup.find_all('div', {'data-hook': 'review'})

        print(f"✅ Encontrados {len(review_divs)} reviews")

        for review_div in review_divs[:30]:  # Limitar a 30
            try:
                # Rating
                rating_elem = review_div.find('i', {'data-hook': 'review-star-rating'})
                rating = 0
                if rating_elem:
                    rating_text = rating_elem.get_text().strip()
                    rating = float(rating_text.split()[0])

                # Título
                title_elem = review_div.find('a', {'data-hook': 'review-title'})
                title = title_elem.get_text().strip() if title_elem else ""

                # Texto de la review
                text_elem = review_div.find('span', {'data-hook': 'review-body'})
                text = text_elem.get_text().strip() if text_elem else ""

                # Verificado
                verified = bool(review_div.find('span', {'data-hook': 'avp-badge'}))

                reviews.append({
                    'rating': rating,
                    'title': title,
                    'text': text,
                    'verified': verified
                })

            except Exception as e:
                print(f"⚠️  Error parseando review: {e}")
                continue

        return reviews

    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def scrape_with_selenium(asin: str) -> List[Dict]:
    """Método 2: Scraping con Selenium (más robusto)"""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        print("❌ Selenium no instalado")
        print("   Instala: pip3 install selenium")
        print("   Y descarga ChromeDriver: brew install chromedriver")
        return []

    print(f"🔍 Método: Selenium (headless Chrome)")

    # Configurar Chrome
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

    reviews = []

    try:
        driver = webdriver.Chrome(options=chrome_options)
        url = f"https://www.amazon.com/product-reviews/{asin}"

        print(f"📡 Abriendo: {url}")
        driver.get(url)

        # Esperar a que carguen las reviews
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-hook="review"]')))

        # Extraer reviews
        review_elements = driver.find_elements(By.CSS_SELECTOR, '[data-hook="review"]')

        print(f"✅ Encontrados {len(review_elements)} reviews")

        for elem in review_elements[:30]:
            try:
                # Rating
                rating_elem = elem.find_element(By.CSS_SELECTOR, '[data-hook="review-star-rating"]')
                rating_text = rating_elem.text.strip()
                rating = float(rating_text.split()[0])

                # Título
                title_elem = elem.find_element(By.CSS_SELECTOR, '[data-hook="review-title"]')
                title = title_elem.text.strip()

                # Texto
                text_elem = elem.find_element(By.CSS_SELECTOR, '[data-hook="review-body"]')
                text = text_elem.text.strip()

                # Verificado
                verified = len(elem.find_elements(By.CSS_SELECTOR, '[data-hook="avp-badge"]')) > 0

                reviews.append({
                    'rating': rating,
                    'title': title,
                    'text': text,
                    'verified': verified
                })

            except Exception as e:
                continue

        driver.quit()
        return reviews

    except Exception as e:
        print(f"❌ Error con Selenium: {e}")
        if 'driver' in locals():
            driver.quit()
        return []


def scrape_with_api(asin: str) -> List[Dict]:
    """Método 3: Usar API de ScrapingBee (pago pero muy confiable)"""
    import requests
    import os

    api_key = os.getenv("SCRAPINGBEE_API_KEY")

    if not api_key:
        print("❌ SCRAPINGBEE_API_KEY no configurada en .env")
        print("   Obtén una key gratis en: https://www.scrapingbee.com/")
        print("   1000 requests gratis al mes")
        return []

    print(f"🔍 Método: ScrapingBee API")

    url = f"https://www.amazon.com/product-reviews/{asin}"

    params = {
        'api_key': api_key,
        'url': url,
        'render_js': 'true',
        'premium_proxy': 'true',
        'country_code': 'us'
    }

    try:
        print(f"📡 Request a ScrapingBee...")
        response = requests.get('https://app.scrapingbee.com/api/v1/', params=params, timeout=60)

        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            return []

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')

        review_divs = soup.find_all('div', {'data-hook': 'review'})

        print(f"✅ Encontrados {len(review_divs)} reviews")

        reviews = []
        for review_div in review_divs[:30]:
            try:
                rating_elem = review_div.find('i', {'data-hook': 'review-star-rating'})
                rating = float(rating_elem.get_text().split()[0]) if rating_elem else 0

                title_elem = review_div.find('a', {'data-hook': 'review-title'})
                title = title_elem.get_text().strip() if title_elem else ""

                text_elem = review_div.find('span', {'data-hook': 'review-body'})
                text = text_elem.get_text().strip() if text_elem else ""

                verified = bool(review_div.find('span', {'data-hook': 'avp-badge'}))

                reviews.append({
                    'rating': rating,
                    'title': title,
                    'text': text,
                    'verified': verified
                })
            except:
                continue

        return reviews

    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Scraper de reviews de Amazon")
    parser.add_argument("--asin", required=True, help="ASIN del producto")
    parser.add_argument("--method", choices=['requests', 'selenium', 'api'],
                       default='requests', help="Método de scraping")
    parser.add_argument("--output", help="Archivo de salida (JSON)")

    args = parser.parse_args()

    print(f"\n{'='*80}")
    print(f"🕷️  AMAZON REVIEWS SCRAPER")
    print(f"{'='*80}\n")
    print(f"ASIN: {args.asin}")
    print(f"Método: {args.method}\n")

    # Scrape según método
    if args.method == 'requests':
        reviews = scrape_with_requests(args.asin)
    elif args.method == 'selenium':
        reviews = scrape_with_selenium(args.asin)
    elif args.method == 'api':
        reviews = scrape_with_api(args.asin)

    if not reviews:
        print("\n❌ No se obtuvieron reviews")
        print("\n💡 Prueba otro método:")
        if args.method == 'requests':
            print("   python3 scrape_amazon_reviews.py --asin", args.asin, "--method selenium")
        sys.exit(1)

    # Mostrar muestra
    print(f"\n{'='*80}")
    print(f"✅ REVIEWS OBTENIDAS: {len(reviews)}")
    print(f"{'='*80}\n")

    print("📊 ESTADÍSTICAS:")
    avg_rating = sum(r['rating'] for r in reviews) / len(reviews)
    verified_count = sum(1 for r in reviews if r['verified'])
    print(f"   Rating promedio: {avg_rating:.1f}/5.0")
    print(f"   Verificadas: {verified_count}/{len(reviews)}")

    print(f"\n📝 MUESTRA (primeras 3):\n")
    for i, review in enumerate(reviews[:3], 1):
        print(f"{i}. {'⭐' * int(review['rating'])} ({review['rating']}/5)")
        print(f"   {review['title']}")
        print(f"   {review['text'][:150]}...")
        print(f"   Verificada: {'✅' if review['verified'] else '❌'}\n")

    # Guardar
    output_file = args.output or f"storage/reviews_{args.asin}.json"
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(reviews, f, indent=2, ensure_ascii=False)

    print(f"💾 Reviews guardadas en: {output_path}")
    print(f"\n💡 Ahora puedes usar estas reviews con Claude:")
    print(f"   python3 scripts/research/product_qa_with_rag.py --asin {args.asin} --question '¿Es bueno?'")


if __name__ == "__main__":
    main()
