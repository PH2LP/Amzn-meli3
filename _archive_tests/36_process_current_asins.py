#!/usr/bin/env python3
"""
Procesa ASINs actuales de la DB con Browser Automation

Optimizado para ~1,000 productos: termina en 20-30 minutos

Instalación:
    pip install playwright beautifulsoup4
    playwright install chromium

Uso:
    python3 36_process_current_asins.py
"""

import os
import sys
import time
import random
import asyncio
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import re

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ ERROR: Playwright no instalado")
    print()
    print("Instalá con:")
    print("  pip install playwright beautifulsoup4")
    print("  playwright install chromium")
    print()
    sys.exit(1)

load_dotenv()

# Configuración
ZIPCODE = os.getenv('BUYER_ZIPCODE', '33172')
MAX_DELIVERY_DAYS = int(os.getenv('MAX_DELIVERY_DAYS', '2'))
DB_PATH = 'storage/listings_database.db'

# Para 1,000 productos: 6 browsers, delays cortos
NUM_BROWSERS = 6
DELAY_MIN = 1.0
DELAY_MAX = 2.0

print("=" * 80)
print("🚀 PROCESANDO ASINs ACTUALES - Browser Automation")
print("=" * 80)
print(f"Zipcode: {ZIPCODE}")
print(f"Max delivery days: {MAX_DELIVERY_DAYS}")
print(f"Browsers paralelos: {NUM_BROWSERS}")
print(f"Delays: {DELAY_MIN}-{DELAY_MAX}s")
print()


def get_asins_to_process():
    """Obtiene ASINs de la DB"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = """
        SELECT DISTINCT asin
        FROM listings
        WHERE asin IS NOT NULL
        AND asin != ''
        ORDER BY asin
    """

    cursor.execute(query)
    asins = [row[0] for row in cursor.fetchall()]
    conn.close()

    return asins


def extract_delivery_info(html_content):
    """Extrae delivery info del HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    delivery_block = soup.find(id='mir-layout-DELIVERY_BLOCK')

    if not delivery_block:
        return {'found': False, 'text': None, 'date': None, 'days': None}

    delivery_text = delivery_block.get_text(strip=True)
    date_pattern = r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\w+)\s+(\d+)'
    date_match = re.search(date_pattern, delivery_text)

    delivery_date = None
    days_until = None

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
                year = 2025 if month_num == 1 else datetime.now().year
                delivery_date = datetime(year, month_num, day)
                days_until = (delivery_date - datetime.now()).days
            except:
                pass

    return {
        'found': True,
        'text': delivery_text[:150],
        'date': delivery_date.strftime('%Y-%m-%d') if delivery_date else None,
        'days': days_until
    }


async def create_stealth_browser(playwright):
    """Crea browser con anti-detección"""
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
        ]
    )

    context = await browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    )

    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)

    return browser, context


async def validate_asin(asin, context, worker_id):
    """Valida un ASIN"""
    url = f"https://www.amazon.com/dp/{asin}"
    page = await context.new_page()

    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=25000)

        # Simular comportamiento humano
        await page.mouse.move(random.randint(100, 600), random.randint(100, 500))

        try:
            await page.wait_for_selector('#mir-layout-DELIVERY_BLOCK', timeout=8000)
        except:
            pass

        html_content = await page.content()
        await page.close()

        # Detectar CAPTCHA
        if 'captcha' in html_content.lower() or len(html_content) < 10000:
            return {
                'asin': asin,
                'worker_id': worker_id,
                'success': False,
                'error': 'CAPTCHA_DETECTED',
                'delivery_days': None,
                'passed_filter': False
            }

        delivery = extract_delivery_info(html_content)

        if not delivery['found'] or delivery['days'] is None:
            return {
                'asin': asin,
                'worker_id': worker_id,
                'success': False,
                'error': 'No delivery info',
                'delivery_days': None,
                'passed_filter': False
            }

        passed_filter = delivery['days'] <= MAX_DELIVERY_DAYS

        return {
            'asin': asin,
            'worker_id': worker_id,
            'success': True,
            'error': None,
            'delivery_days': delivery['days'],
            'delivery_date': delivery['date'],
            'delivery_text': delivery['text'],
            'passed_filter': passed_filter
        }

    except Exception as e:
        await page.close()
        return {
            'asin': asin,
            'worker_id': worker_id,
            'success': False,
            'error': str(e)[:100],
            'delivery_days': None,
            'passed_filter': False
        }


async def worker_browser(worker_id, asins, playwright, results_queue):
    """Worker que procesa ASINs"""
    print(f"🚀 Worker {worker_id} iniciado - {len(asins)} ASINs")

    browser, context = await create_stealth_browser(playwright)
    captcha_count = 0

    for i, asin in enumerate(asins, 1):
        result = await validate_asin(asin, context, worker_id)
        results_queue.append(result)

        # Detectar CAPTCHAs
        if result.get('error') == 'CAPTCHA_DETECTED':
            captcha_count += 1
            print(f"⚠️  Worker {worker_id}: CAPTCHA detectado (total: {captcha_count})")

            if captcha_count >= 3:
                print(f"❌ Worker {worker_id}: Demasiados CAPTCHAs, parando...")
                break

        # Log cada 20 ASINs
        if i % 20 == 0:
            successful = sum(1 for r in results_queue if r.get('worker_id') == worker_id and r['success'])
            passed = sum(1 for r in results_queue if r.get('worker_id') == worker_id and r.get('passed_filter', False))
            print(f"Worker {worker_id}: {i}/{len(asins)} | OK: {successful} | Passed filter: {passed}")

        # Delay aleatorio
        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        await asyncio.sleep(delay)

    await context.close()
    await browser.close()

    print(f"✅ Worker {worker_id} completado")


async def main():
    """Main execution"""

    print("📦 Cargando ASINs desde DB...")
    all_asins = get_asins_to_process()
    total_asins = len(all_asins)

    if total_asins == 0:
        print("❌ No hay ASINs para procesar")
        return

    print(f"✅ {total_asins:,} ASINs encontrados")
    print()

    # Calcular tiempo estimado
    avg_delay = (DELAY_MIN + DELAY_MAX) / 2
    rate_per_browser = 1 / avg_delay
    total_rate = rate_per_browser * NUM_BROWSERS
    estimated_time = total_asins / total_rate

    print(f"📊 Estimación:")
    print(f"   Rate: ~{total_rate:.1f} ASINs/segundo")
    print(f"   Tiempo estimado: {estimated_time/60:.1f} minutos")
    print()

    # Dividir entre workers
    chunk_size = (total_asins + NUM_BROWSERS - 1) // NUM_BROWSERS
    asin_chunks = [all_asins[i:i + chunk_size] for i in range(0, total_asins, chunk_size)]

    print(f"🔀 Dividiendo en {len(asin_chunks)} workers:")
    for i, chunk in enumerate(asin_chunks, 1):
        print(f"   Worker {i}: {len(chunk)} ASINs")
    print()

    print(f"🚀 Iniciando {NUM_BROWSERS} browsers...")
    print()

    start_time = time.time()
    results_queue = []

    async with async_playwright() as playwright:
        tasks = [
            worker_browser(i+1, chunk, playwright, results_queue)
            for i, chunk in enumerate(asin_chunks)
        ]
        await asyncio.gather(*tasks)

    elapsed_total = time.time() - start_time

    print()
    print("=" * 80)
    print("✅ PROCESAMIENTO COMPLETO")
    print("=" * 80)
    print()

    successful = sum(1 for r in results_queue if r['success'])
    failed = len(results_queue) - successful
    passed_filter = sum(1 for r in results_queue if r.get('passed_filter', False))
    captchas = sum(1 for r in results_queue if r.get('error') == 'CAPTCHA_DETECTED')

    print(f"Total procesados: {len(results_queue):,}")
    print(f"Exitosos: {successful:,} ({successful/len(results_queue)*100:.1f}%)")
    print(f"Fallidos: {failed:,}")
    print(f"CAPTCHAs: {captchas}")
    print(f"Pasaron filtro (≤{MAX_DELIVERY_DAYS} días): {passed_filter:,} ({passed_filter/successful*100:.1f}% de exitosos)")
    print()
    print(f"⏱️  Tiempo total: {elapsed_total/60:.1f} minutos")
    print(f"📊 Velocidad: {len(results_queue)/elapsed_total:.2f} ASINs/segundo")
    print()

    # Guardar resultados
    print("💾 Guardando resultados en DB...")
    save_results_to_db(results_queue)
    print("✅ Resultados guardados en delivery_validations")
    print()

    # Mostrar ejemplos
    print("=" * 80)
    print(f"📦 EJEMPLOS - ASINs que PASARON filtro (≤{MAX_DELIVERY_DAYS} días)")
    print("=" * 80)

    passed_examples = [r for r in results_queue if r.get('passed_filter', False)][:15]

    if passed_examples:
        for r in passed_examples:
            print(f"✅ {r['asin']} → {r['delivery_days']} días ({r.get('delivery_date', 'N/A')})")
    else:
        print("⚠️  No hay ASINs que pasen el filtro")

    print()
    print("=" * 80)
    print("📊 PARA VER RESULTADOS COMPLETOS:")
    print("=" * 80)
    print()
    print("sqlite3 storage/listings_database.db")
    print("SELECT * FROM delivery_validations WHERE passed_filter = 1;")
    print()


def save_results_to_db(results):
    """Guarda resultados en DB"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS delivery_validations (
            asin TEXT PRIMARY KEY,
            delivery_days INTEGER,
            delivery_date TEXT,
            passed_filter BOOLEAN,
            validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    for result in results:
        if result['success']:
            cursor.execute("""
                INSERT OR REPLACE INTO delivery_validations
                (asin, delivery_days, delivery_date, passed_filter)
                VALUES (?, ?, ?, ?)
            """, (
                result['asin'],
                result['delivery_days'],
                result.get('delivery_date'),
                result['passed_filter']
            ))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Interrumpido por usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
