#!/usr/bin/env python3
"""
Captura sesión de Amazon usando Selenium

1. Abre el navegador
2. Te muestra la página de login de Amazon
3. VOS te logueas manualmente
4. El script captura las cookies automáticamente
5. Las guarda para usar en el scraper
"""
import json
import os
import time

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    print("❌ Selenium no está instalado")
    print()
    print("Instalando selenium...")
    import subprocess
    subprocess.check_call(["pip3", "install", "selenium"])
    print()
    print("✅ Selenium instalado - ejecutá el script de nuevo")
    exit(0)

COOKIES_FILE = "cache/amazon_session_cookies.json"

def capture_amazon_cookies():
    """Abre navegador para login y captura cookies"""

    print("=" * 80)
    print("CAPTURA DE SESIÓN DE AMAZON")
    print("=" * 80)
    print()

    # Configurar Chrome
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    # chrome_options.add_argument("--headless")  # Comentado - queremos ver el navegador

    # Intentar usar chromedriver del sistema
    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        print("❌ Error iniciando Chrome")
        print()
        print("Opciones:")
        print("  1. Instalar chromedriver:")
        print("     brew install chromedriver")
        print()
        print("  2. O usar Firefox (cambiá el código)")
        print()
        print(f"Error: {e}")
        return False

    try:
        print("🌐 Abriendo Amazon.com...")
        driver.get("https://www.amazon.com")
        time.sleep(3)

        print()
        print("=" * 80)
        print("⏸️  NAVEGADOR ABIERTO - LOGUÉATE AHORA")
        print("=" * 80)
        print()
        print("En el navegador que se abrió:")
        print()
        print("  1. Click en 'Sign in' (esquina superior derecha)")
        print("  2. Ingresa tu email y contraseña de Amazon Prime")
        print("  3. Completa 2FA o CAPTCHA si te pide")
        print("  4. Esperá a estar en la página principal")
        print()
        print("⚠️  NO CIERRES EL NAVEGADOR")
        print()
        print("=" * 80)
        input("👉 Cuando termines de loguearte, presiona ENTER aquí...")
        print()
        print("✅ Capturando cookies...")

        # Capturar cookies
        print()
        print("=" * 80)
        print("CAPTURANDO COOKIES")
        print("=" * 80)
        print()

        # Navegar a Amazon para asegurar que estamos en el dominio correcto
        driver.get("https://www.amazon.com")
        time.sleep(1)

        cookies_raw = driver.get_cookies()

        # Convertir a formato compatible con requests
        cookies = {}
        for cookie in cookies_raw:
            cookies[cookie['name']] = {
                'value': cookie['value'],
                'domain': cookie.get('domain', '.amazon.com'),
                'path': cookie.get('path', '/'),
                'secure': cookie.get('secure', False),
                'expires': cookie.get('expiry', None)
            }

        # Guardar cookies
        os.makedirs("cache", exist_ok=True)
        with open(COOKIES_FILE, 'w') as f:
            json.dump(cookies, f, indent=2)

        # Verificar cookies importantes
        important_cookies = ['session-id', 'ubid-main', 'session-token']
        found_important = [c for c in important_cookies if c in cookies]

        print(f"✅ Total cookies capturadas: {len(cookies)}")
        print(f"✅ Cookies importantes: {len(found_important)}/{len(important_cookies)}")
        print()

        if found_important:
            print("Cookies importantes encontradas:")
            for cookie_name in important_cookies:
                if cookie_name in cookies:
                    value = cookies[cookie_name]['value']
                    print(f"  ✅ {cookie_name}: {value[:20]}...")

        print()
        print(f"💾 Guardadas en: {COOKIES_FILE}")
        print()

        if len(found_important) >= 2:
            print("🎉 ¡Sesión de Amazon capturada exitosamente!")
            print()
            print("Ahora el scraper usará tu sesión Prime para obtener delivery times reales")
            success = True
        else:
            print("⚠️  Algunas cookies importantes no se encontraron")
            print("   El scraper puede no funcionar correctamente")
            success = False

        return success

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        print()
        print("Cerrando navegador en 5 segundos...")
        time.sleep(5)
        try:
            driver.quit()
            print("✅ Navegador cerrado")
        except:
            print("✅ Navegador ya cerrado")

if __name__ == "__main__":
    success = capture_amazon_cookies()

    print()
    print("=" * 80)

    if success:
        print("PRÓXIMOS PASOS")
        print("=" * 80)
        print()
        print("1. Probá el scraper:")
        print("   python3 src/integrations/amazon_glow_api_v2_advanced.py B0DX65SQXF 33172")
        print()
        print("2. Deberías ver: '🔐 Sesión Prime cargada'")
        print()
        print("3. Los delivery times deberían ser de Prime (1-3 días)")
    else:
        print("ERROR EN LA CAPTURA")
        print("=" * 80)
        print()
        print("Posibles soluciones:")
        print("  1. Asegurate de loguearte correctamente")
        print("  2. Completa cualquier verificación (2FA, CAPTCHA)")
        print("  3. Ejecuta el script de nuevo")

    print()
    print("=" * 80)
