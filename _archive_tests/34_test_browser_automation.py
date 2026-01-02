#!/usr/bin/env python3
"""
TEST RÁPIDO: Browser Automation con Playwright

Prueba con 10 ASINs para verificar que:
1. Playwright está instalado correctamente
2. Browser automation funciona
3. Detecta delivery times correctamente
4. No hay bloqueos de Amazon

Instalación (si no lo hiciste):
    pip install playwright beautifulsoup4
    playwright install chromium

Uso:
    python3 34_test_browser_automation.py
"""

import sys
import asyncio
import random
import re
from datetime import datetime

try:
    from playwright.async_api import async_playwright
    from bs4 import BeautifulSoup
except ImportError:
    print("❌ ERROR: Falta instalar dependencias")
    print()
    print("Ejecutá:")
    print("  pip install playwright beautifulsoup4")
    print("  playwright install chromium")
    print()
    sys.exit(1)

# ASINs de prueba (productos reales)
TEST_ASINS = [
    "B0D9PK465N",  # El crítico que estabas probando
    "B0FGJ3G6V8",
    "B09P53JX4R",
    "B0CX23V2ZK",
    "B0D1XD1ZV3",
    "B0DBRVP21C",
    "B0CNL4M4YB",
    "B0D5RPS3TR",
    "B0C9KRG8YR",
    "B0BT9VM96Z",
]

print("=" * 80)
print("🧪 TEST RÁPIDO: Browser Automation")
print("=" * 80)
print(f"ASINs a probar: {len(TEST_ASINS)}")
print()
print("Esto va a:")
print("1. Abrir un browser Chromium headless")
print("2. Navegar a cada producto en Amazon")
print("3. Extraer delivery time")
print("4. Mostrar resultados")
print()
print("Tiempo estimado: ~1-2 minutos")
print()
print("=" * 80)
print()


def extract_delivery_info(html_content):
    """Extrae delivery info del HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    delivery_block = soup.find(id='mir-layout-DELIVERY_BLOCK')

    if not delivery_block:
        return None

    delivery_text = delivery_block.get_text(strip=True)

    # Extraer fecha
    date_pattern = r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\w+)\s+(\d+)'
    date_match = re.search(date_pattern, delivery_text)

    if not date_match:
        return None

    month_map = {
        'January': 1, 'February': 2, 'March': 3, 'April': 4,
        'May': 5, 'June': 6, 'July': 7, 'August': 8,
        'September': 9, 'October': 10, 'November': 11, 'December': 12
    }

    month_num = month_map.get(date_match.group(2))
    day = int(date_match.group(3))

    if not month_num:
        return None

    try:
        year = 2025 if month_num == 1 else datetime.now().year
        delivery_date = datetime(year, month_num, day)
        days_until = (delivery_date - datetime.now()).days

        return {
            'text': delivery_text[:100],
            'date': delivery_date.strftime('%Y-%m-%d'),
            'days': days_until
        }
    except:
        return None


async def test_asin(asin, context):
    """Prueba un ASIN con browser automation"""
    url = f"https://www.amazon.com/dp/{asin}"
    page = await context.new_page()

    try:
        print(f"📡 Testing {asin}...", end=" ", flush=True)

        # Navegar
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)

        # Simular comportamiento humano
        await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
        await asyncio.sleep(random.uniform(0.3, 0.8))

        # Esperar delivery block
        try:
            await page.wait_for_selector('#mir-layout-DELIVERY_BLOCK', timeout=5000)
        except:
            pass

        # Obtener HTML
        html = await page.content()

        # Cerrar página
        await page.close()

        # Extraer info
        delivery = extract_delivery_info(html)

        if delivery:
            print(f"✅ {delivery['days']} días ({delivery['date']})")
            return {
                'asin': asin,
                'success': True,
                'days': delivery['days'],
                'date': delivery['date'],
                'text': delivery['text']
            }
        else:
            print(f"⚠️  No delivery info")
            return {
                'asin': asin,
                'success': False,
                'error': 'No delivery info found'
            }

    except Exception as e:
        print(f"❌ Error: {str(e)[:50]}")
        await page.close()
        return {
            'asin': asin,
            'success': False,
            'error': str(e)[:100]
        }


async def main():
    """Main test"""

    print("🚀 Iniciando browser Chromium...")
    print()

    async with async_playwright() as playwright:
        # Crear browser con stealth
        browser = await playwright.chromium.launch(
            headless=True,  # Cambiar a False para ver el browser
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
            ]
        )

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        )

        # Anti-detección scripts
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        print("✅ Browser iniciado")
        print()

        # Procesar cada ASIN
        results = []
        for asin in TEST_ASINS:
            result = await test_asin(asin, context)
            results.append(result)

            # Delay entre requests
            delay = random.uniform(2.0, 4.0)
            await asyncio.sleep(delay)

        # Cerrar browser
        await context.close()
        await browser.close()

    # Mostrar resultados
    print()
    print("=" * 80)
    print("📊 RESULTADOS")
    print("=" * 80)
    print()

    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    print(f"Total: {len(results)}")
    print(f"Exitosos: {len(successful)} ({len(successful)/len(results)*100:.1f}%)")
    print(f"Fallidos: {len(failed)}")
    print()

    if successful:
        print("DELIVERY TIMES DETECTADOS:")
        print("-" * 80)
        for r in successful:
            print(f"  {r['asin']}: {r['days']} días ({r['date']})")
            print(f"    → {r['text'][:80]}")
        print()

    if failed:
        print("ERRORES:")
        print("-" * 80)
        for r in failed:
            print(f"  {r['asin']}: {r.get('error', 'Unknown error')}")
        print()

    print("=" * 80)
    print("✅ TEST COMPLETADO")
    print("=" * 80)
    print()

    if len(successful) >= 8:  # 80% éxito
        print("✅ TODO FUNCIONANDO CORRECTAMENTE")
        print()
        print("Próximo paso:")
        print("  python3 33_browser_automation_glow.py")
        print()
        print("Para procesar todos los ASINs de la DB")
    else:
        print("⚠️  MUCHOS ERRORES")
        print()
        print("Posibles causas:")
        print("1. Playwright no instalado correctamente")
        print("2. Amazon bloqueando requests (poco probable)")
        print("3. Problemas de conectividad")
        print()
        print("Probá:")
        print("  playwright install chromium")

    print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrumpido")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
