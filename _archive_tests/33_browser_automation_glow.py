#!/usr/bin/env python3
"""
Browser Automation con Playwright - Anti-bot Detection

Simula un usuario humano navegando Amazon para validar delivery times.
Amazon NO puede detectar que es bot porque:
- Ejecuta JavaScript real
- Simula movimientos de mouse
- Delays aleatorios (comportamiento humano)
- Browser fingerprint real

Ventajas vs proxies:
- GRATIS
- Delivery times EXACTOS (tu IP Miami)
- Muy difícil de detectar
- No requiere servicios externos

Desventajas:
- Más lento que requests directos (ejecuta JS)
- Usa más recursos (RAM, CPU)

Instalación:
    pip install playwright beautifulsoup4
    playwright install chromium

Uso:
    python3 33_browser_automation_glow.py
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

# Import Playwright (se instala con: playwright install chromium)
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ ERROR: Playwright no instalado")
    print()
    print("Instalá con:")
    print("  pip install playwright")
    print("  playwright install chromium")
    print()
    sys.exit(1)

load_dotenv()

# Configuración
ZIPCODE = os.getenv('BUYER_ZIPCODE', '33172')
MAX_DELIVERY_DAYS = int(os.getenv('MAX_DELIVERY_DAYS', '2'))
DB_PATH = 'storage/listings_database.db'

# Configuración de procesamiento
NUM_BROWSERS = 6  # Número de browsers paralelos (agresivo pero seguro)
DELAY_MIN = 1.0   # Delay mínimo entre requests (segundos)
DELAY_MAX = 2.5   # Delay máximo (simula humano)

print("=" * 80)
print("🤖 BROWSER AUTOMATION - Playwright Anti-Bot")
print("=" * 80)
print(f"Zipcode: {ZIPCODE}")
print(f"Max delivery days: {MAX_DELIVERY_DAYS}")
print(f"Browsers paralelos: {NUM_BROWSERS}")
print(f"Delay range: {DELAY_MIN}-{DELAY_MAX}s (comportamiento humano)")
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

    # Extraer fecha
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
    """
    Crea un browser con configuración anti-detección

    Técnicas stealth:
    - Disable automation flags
    - Real user agent
    - Real viewport size
    - Random fingerprint
    """
    browser = await playwright.chromium.launch(
        headless=True,  # Cambiar a False para debugging
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
        ]
    )

    context = await browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        locale='en-US',
        timezone_id='America/New_York',
    )

    # Inyectar scripts anti-detección
    await context.add_init_script("""
        // Ocultar que estamos en webdriver
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });

        // Ocultar automation flags
        window.navigator.chrome = {
            runtime: {},
        };

        // Mock permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """)

    return browser, context


async def simulate_human_behavior(page):
    """
    Simula comportamiento humano para evitar detección

    - Mouse movements aleatorios
    - Scroll aleatorio
    - Delays variables
    """
    # Simular movimiento de mouse
    await page.mouse.move(
        random.randint(100, 800),
        random.randint(100, 600)
    )

    # Scroll aleatorio
    await page.evaluate(f"window.scrollTo(0, {random.randint(100, 500)})")

    # Delay aleatorio
    await asyncio.sleep(random.uniform(0.5, 1.5))


async def validate_asin_with_browser(asin, context, worker_id):
    """
    Valida un ASIN usando browser automation

    Args:
        asin: Amazon ASIN
        context: Playwright browser context
        worker_id: ID del worker (para logging)

    Returns:
        dict con resultado
    """
    url = f"https://www.amazon.com/dp/{asin}"
    page = await context.new_page()

    try:
        # Navegar a la página del producto
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)

        # Simular comportamiento humano
        await simulate_human_behavior(page)

        # Esperar a que cargue el delivery block
        try:
            await page.wait_for_selector('#mir-layout-DELIVERY_BLOCK', timeout=10000)
        except:
            # Si no aparece, puede ser que el producto no esté disponible
            pass

        # Obtener HTML completo
        html_content = await page.content()

        # Cerrar página
        await page.close()

        # Extraer delivery info
        delivery = extract_delivery_info(html_content)

        if not delivery['found'] or delivery['days'] is None:
            return {
                'asin': asin,
                'worker_id': worker_id,
                'success': False,
                'error': 'No delivery info found',
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
    """
    Worker que procesa ASINs con su propio browser

    Args:
        worker_id: ID del worker
        asins: Lista de ASINs a procesar
        playwright: Playwright instance
        results_queue: Queue para guardar resultados
    """
    print(f"🚀 Worker {worker_id} iniciado - {len(asins)} ASINs")

    # Crear browser stealth
    browser, context = await create_stealth_browser(playwright)

    for i, asin in enumerate(asins, 1):
        # Procesar ASIN
        result = await validate_asin_with_browser(asin, context, worker_id)
        results_queue.append(result)

        # Log progreso
        if i % 10 == 0:
            successful = sum(1 for r in results_queue if r.get('worker_id') == worker_id and r['success'])
            print(f"Worker {worker_id}: {i}/{len(asins)} | Success: {successful}")

        # Delay aleatorio entre requests (comportamiento humano)
        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        await asyncio.sleep(delay)

    # Cerrar browser
    await context.close()
    await browser.close()

    print(f"✅ Worker {worker_id} completado - {len(asins)} ASINs procesados")


async def main():
    """Main execution"""

    # 1. Obtener ASINs
    print("📦 Cargando ASINs desde DB...")
    all_asins = get_asins_to_process()
    total_asins = len(all_asins)

    if total_asins == 0:
        print("❌ No hay ASINs para procesar")
        return

    print(f"✅ {total_asins:,} ASINs encontrados")
    print()

    # 2. Dividir ASINs entre workers
    chunk_size = total_asins // NUM_BROWSERS
    asin_chunks = [
        all_asins[i:i + chunk_size]
        for i in range(0, total_asins, chunk_size)
    ]

    print(f"🔀 Dividiendo en {len(asin_chunks)} chunks:")
    for i, chunk in enumerate(asin_chunks, 1):
        print(f"   Worker {i}: {len(chunk)} ASINs")
    print()

    # 3. Procesar con Playwright
    print(f"🚀 Iniciando {NUM_BROWSERS} browsers paralelos...")
    print()

    start_time = time.time()
    results_queue = []

    async with async_playwright() as playwright:
        # Crear tasks para cada worker
        tasks = [
            worker_browser(i+1, chunk, playwright, results_queue)
            for i, chunk in enumerate(asin_chunks)
        ]

        # Ejecutar todos los workers en paralelo
        await asyncio.gather(*tasks)

    elapsed_total = time.time() - start_time

    print()
    print("=" * 80)
    print("✅ PROCESAMIENTO COMPLETO")
    print("=" * 80)
    print()

    # 4. Estadísticas
    successful = sum(1 for r in results_queue if r['success'])
    failed = len(results_queue) - successful
    passed_filter = sum(1 for r in results_queue if r.get('passed_filter', False))

    print(f"Total procesados: {len(results_queue):,}")
    print(f"Exitosos: {successful:,} ({successful/len(results_queue)*100:.1f}%)")
    print(f"Fallidos: {failed:,}")
    print(f"Pasaron filtro (≤{MAX_DELIVERY_DAYS} días): {passed_filter:,} ({passed_filter/len(results_queue)*100:.1f}%)")
    print()
    print(f"Tiempo total: {elapsed_total/60:.1f} minutos ({elapsed_total/3600:.1f} horas)")
    print(f"Velocidad promedio: {len(results_queue)/elapsed_total:.2f} ASINs/segundo")
    print()

    # 5. Proyección para 50k
    if total_asins < 50000:
        rate = len(results_queue) / elapsed_total
        time_for_50k = 50000 / rate
        print("=" * 80)
        print("📊 PROYECCIÓN PARA 50,000 PRODUCTOS")
        print("=" * 80)
        print(f"Velocidad actual: {rate:.2f} ASINs/segundo")
        print(f"Tiempo estimado: {time_for_50k/3600:.1f} horas")
        print()

    # 6. Guardar resultados
    print("💾 Guardando resultados en DB...")
    save_results_to_db(results_queue)
    print("✅ Resultados guardados")
    print()

    # 7. Ejemplos
    print("=" * 80)
    print(f"📦 EJEMPLOS DE ASINs QUE PASARON EL FILTRO (≤{MAX_DELIVERY_DAYS} días)")
    print("=" * 80)

    passed_examples = [r for r in results_queue if r.get('passed_filter', False)][:10]

    if passed_examples:
        for result in passed_examples:
            print(f"✅ {result['asin']} → {result['delivery_days']} días ({result.get('delivery_date', 'N/A')})")
    else:
        print("⚠️  No hay ASINs que pasen el filtro")

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
        print("\n⚠️  Procesamiento interrumpido por usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
