#!/usr/bin/env python3
"""
Interceptar las llamadas AJAX internas de Amazon
para descubrir cómo obtienen delivery dates con zipcode
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import time
import json

asin = "B0FDWT3MXK"
zipcode = "33172"

# Habilitar logging de network requests
chrome_options = Options()
chrome_options.add_argument('--headless=new')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
chrome_options.add_experimental_option('perfLoggingPrefs', {
    'enableNetwork': True,
    'enablePage': False,
})

driver = webdriver.Chrome(options=chrome_options)

print("="*80)
print("INTERCEPTANDO LLAMADAS AJAX DE AMAZON")
print("="*80)

try:
    # Ir a Amazon
    print("\n1️⃣ Abriendo Amazon.com...")
    driver.get("https://www.amazon.com")
    time.sleep(2)

    # Cambiar zipcode
    print(f"2️⃣ Configurando zipcode {zipcode}...")
    try:
        deliver_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "nav-global-location-popover-link"))
        )
        deliver_button.click()
        time.sleep(1)

        zipcode_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "GLUXZipUpdateInput"))
        )
        zipcode_input.clear()
        zipcode_input.send_keys(zipcode)

        apply_button = driver.find_element(By.CSS_SELECTOR, "input[aria-labelledby='GLUXZipUpdate-announce']")
        apply_button.click()
        time.sleep(2)

        print(f"   ✅ Zipcode configurado")
    except Exception as e:
        print(f"   ⚠️  Error configurando zipcode: {e}")

    # Ir al producto
    print(f"\n3️⃣ Navegando a producto {asin}...")
    driver.get(f"https://www.amazon.com/dp/{asin}")
    time.sleep(3)

    # Obtener network logs
    print("\n4️⃣ Analizando llamadas de red...")
    logs = driver.get_log('performance')

    ajax_calls = []

    for entry in logs:
        try:
            log = json.loads(entry['message'])['message']

            if log['method'] == 'Network.responseReceived':
                response = log['params']['response']
                url = response['url']

                # Buscar llamadas AJAX relacionadas con delivery/pricing
                keywords = [
                    'delivery', 'ajax', 'glow', 'address', 'zipcode',
                    'pricing', 'availability', 'offer', 'buybox'
                ]

                if any(kw in url.lower() for kw in keywords):
                    ajax_calls.append({
                        'url': url,
                        'status': response.get('status'),
                        'method': response.get('requestMethod', 'GET'),
                        'headers': response.get('headers', {})
                    })
        except:
            pass

    print(f"\n📡 Encontradas {len(ajax_calls)} llamadas AJAX relevantes:\n")

    for i, call in enumerate(ajax_calls, 1):
        print(f"{i}. {call['method']} {call['status']}")
        print(f"   URL: {call['url'][:120]}...")

        # Mostrar headers importantes
        important_headers = ['content-type', 'anti-csrftoken-a2z']
        for header in important_headers:
            if header in call['headers']:
                print(f"   {header}: {call['headers'][header]}")
        print()

    # Guardar URLs completas
    with open('/tmp/amazon_ajax_calls.json', 'w') as f:
        json.dump(ajax_calls, f, indent=2)

    print(f"💾 URLs completas guardadas en /tmp/amazon_ajax_calls.json")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    driver.quit()

print("\n" + "="*80)
