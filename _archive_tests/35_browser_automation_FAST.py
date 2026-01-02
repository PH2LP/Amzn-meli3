#!/usr/bin/env python3
"""
Browser Automation - MODO ULTRA RÁPIDO

Configuración agresiva para procesar 50k productos en ~2-3 horas.

ADVERTENCIA:
- Mayor riesgo de detección (pero aún bajo con browser real)
- Usa más recursos (10 browsers paralelos)
- Monitorear por CAPTCHAs en las primeras 500 requests

Si Amazon empieza a bloquear:
- Reducí NUM_BROWSERS
- Aumentá DELAY_MIN/MAX

Instalación:
    pip install playwright beautifulsoup4
    playwright install chromium

Uso:
    python3 35_browser_automation_FAST.py
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
    print("Ejecutá: pip install playwright && playwright install chromium")
    sys.exit(1)

load_dotenv()

# Configuración ULTRA RÁPIDA
ZIPCODE = os.getenv('BUYER_ZIPCODE', '33172')
MAX_DELIVERY_DAYS = int(os.getenv('MAX_DELIVERY_DAYS', '2'))
DB_PATH = 'storage/listings_database.db'

NUM_BROWSERS = 10     # 10 browsers paralelos (agresivo)
DELAY_MIN = 0.5       # Muy rápido
DELAY_MAX = 1.5       # Delays cortos

print("=" * 80)
print("🚀 BROWSER AUTOMATION - ULTRA FAST MODE")
print("=" * 80)
print(f"⚠️  MODO AGRESIVO: {NUM_BROWSERS} browsers, delays {DELAY_MIN}-{DELAY_MAX}s")
print(f"Zipcode: {ZIPCODE}")
print(f"Max delivery days: {MAX_DELIVERY_DAYS}")
print()
print("PROYECCIÓN:")
print(f"  Rate estimado: ~6-8 requests/segundo")
print(f"  50,000 productos: ~2-3 horas")
print()
print("⚠️  IMPORTANTE: Monitorear primeros 500 requests por CAPTCHAs")
print("=" * 80)
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
        return {
            'found': False,
            'text': None,
            'date': None,
            'days': None
        }

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
        await page.goto(url, wait_until='domcontentloaded', timeout=20000)

        # Minimal human simulation (para velocidad)
        await page.mouse.move(random.randint(100, 500), random.randint(100, 400))

        try:
            await page.wait_for_selector('#mir-layout-DELIVERY_BLOCK', timeout=5000)
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
            print(f"⚠️  Worker {worker_id}: CAPTCHA detectado ({captcha_count} total)")

            # Si muchos CAPTCHAs, pausar este worker
            if captcha_count >= 3:
                print(f"❌ Worker {worker_id}: Demasiados CAPTCHAs, pausando...")
                break

        # Log progreso
        if i % 50 == 0:
            successful = sum(1 for r in results_queue if r.get('worker_id') == worker_id and r['success'])
            print(f"Worker {worker_id}: {i}/{len(asins)} | Success: {successful} | CAPTCHAs: {captcha_count}")

        # Delay aleatorio
        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        await asyncio.sleep(delay)

    await context.close()
    await browser.close()

    print(f"✅ Worker {worker_id} completado - {len(asins)} ASINs procesados")


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

    # Dividir entre workers
    chunk_size = total_asins // NUM_BROWSERS
    asin_chunks = [all_asins[i:i + chunk_size] for i in range(0, total_asins, chunk_size)]

    print(f"🔀 Dividiendo en {len(asin_chunks)} chunks:")
    for i, chunk in enumerate(asin_chunks, 1):
        print(f"   Worker {i}: {len(chunk)} ASINs")
    print()

    print(f"🚀 Iniciando {NUM_BROWSERS} browsers paralelos...")
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
    print(f"CAPTCHAs detectados: {captchas}")
    print(f"Pasaron filtro (≤{MAX_DELIVERY_DAYS} días): {passed_filter:,} ({passed_filter/len(results_queue)*100:.1f}%)")
    print()
    print(f"Tiempo total: {elapsed_total/60:.1f} minutos ({elapsed_total/3600:.1f} horas)")
    print(f"Velocidad promedio: {len(results_queue)/elapsed_total:.2f} ASINs/segundo")
    print()

    if captchas > len(results_queue) * 0.05:  # >5% CAPTCHAs
        print("⚠️  MUCHOS CAPTCHAs DETECTADOS")
        print("Recomendación: Reducir NUM_BROWSERS o aumentar delays")
        print()

    # Guardar resultados
    print("💾 Guardando resultados en DB...")
    save_results_to_db(results_queue)
    print("✅ Resultados guardados")
    print()

    print("=" * 80)


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
        print("\n⚠️  Procesamiento interrumpido")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
