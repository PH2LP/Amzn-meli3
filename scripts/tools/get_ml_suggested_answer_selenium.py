#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obtiene la respuesta sugerida de MercadoLibre usando Selenium.
Este script automatiza el navegador para hacer click en "Ver respuesta sugerida"
y extraer el texto generado por la IA de ML.
"""

import os
import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from dotenv import load_dotenv

load_dotenv()


def get_ml_suggested_answer_selenium(question_id, headless=True):
    """
    Obtiene la respuesta sugerida de ML usando Selenium (automatización del navegador).

    Args:
        question_id: ID de la pregunta en ML
        headless: Si True, ejecuta el navegador en modo invisible

    Returns:
        str: Texto de la respuesta sugerida o None si falla
    """

    # Configurar Chrome en modo headless
    chrome_options = Options()
    if headless:
        chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')

    # Agregar User-Agent
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = None

    try:
        print(f"🌐 Iniciando navegador...")
        driver = webdriver.Chrome(options=chrome_options)

        # Ir a la página de login de ML
        print(f"🔐 Accediendo a MercadoLibre...")
        driver.get('https://www.mercadolibre.com.ar/gz/login')

        # Aquí necesitarías automatizar el login
        # Por ahora, vamos a intentar usar cookies guardadas

        # Cargar cookies si existen
        cookies_file = "storage/ml_session_cookies.json"
        if os.path.exists(cookies_file):
            print(f"🍪 Cargando cookies de sesión...")
            with open(cookies_file, 'r') as f:
                cookies = json.load(f)
                for cookie in cookies:
                    driver.add_cookie(cookie)
        else:
            print(f"⚠️  No hay cookies guardadas. Necesitas hacer login manual.")
            print(f"   1. El navegador se abrirá")
            print(f"   2. Hace login en MercadoLibre")
            print(f"   3. Presiona Enter aquí cuando hayas hecho login")
            input("   Presiona Enter cuando estés logueado...")

            # Guardar cookies para la próxima vez
            cookies = driver.get_cookies()
            with open(cookies_file, 'w') as f:
                json.dump(cookies, f)
            print(f"   ✅ Cookies guardadas en {cookies_file}")

        # Ir a la página de preguntas
        print(f"📩 Navegando a la pregunta {question_id}...")
        driver.get('https://global-selling.mercadolibre.com/questions')

        time.sleep(2)  # Esperar que cargue

        # Buscar la pregunta específica (esto puede variar según la UI)
        # Por ahora, vamos a intentar hacer una llamada directa a la API desde el navegador

        # Ejecutar JavaScript para llamar a la API de sugerencias
        print(f"🤖 Obteniendo respuesta sugerida...")

        script = f"""
        return fetch('https://global-selling.mercadolibre.com/preguntas/vendedor/api/suggestion/{question_id}?reAnswer=on_demand', {{
            method: 'GET',
            headers: {{
                'Accept': 'application/json, text/plain, */*',
                'x-csrf-token': document.cookie.match(/(_csrf)=([^;]*)/)?.[2] || ''
            }},
            credentials: 'include'
        }})
        .then(response => response.json())
        .then(data => data)
        .catch(error => ({{error: error.toString()}}));
        """

        result = driver.execute_script(script)

        # Esperar un poco para que se complete la llamada
        time.sleep(3)

        # El resultado debería estar en result
        if isinstance(result, dict):
            if 'error' in result:
                print(f"❌ Error: {result['error']}")
                return None

            # Buscar el campo de la respuesta sugerida
            # (la estructura exacta depende de la respuesta de la API)
            suggested_answer = result.get('suggestion') or result.get('answer') or result.get('text')

            if suggested_answer:
                print(f"✅ Respuesta sugerida obtenida!")
                return suggested_answer
            else:
                print(f"⚠️  Respuesta recibida pero sin campo de sugerencia:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return None
        else:
            print(f"⚠️  Respuesta inesperada: {result}")
            return None

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        if driver:
            driver.quit()


def get_ml_suggested_answer_api(question_id):
    """
    Intenta obtener la respuesta usando requests + cookies guardadas.
    Más rápido que Selenium si funciona.
    """
    import requests

    cookies_file = "storage/ml_session_cookies.json"

    if not os.path.exists(cookies_file):
        print("⚠️  No hay cookies guardadas. Ejecuta primero con Selenium.")
        return None

    # Cargar cookies
    with open(cookies_file, 'r') as f:
        cookies_list = json.load(f)

    # Convertir a formato requests
    cookies_dict = {c['name']: c['value'] for c in cookies_list}

    # Extraer CSRF token
    csrf_token = cookies_dict.get('_csrf', '')

    url = f'https://global-selling.mercadolibre.com/preguntas/vendedor/api/suggestion/{question_id}'

    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://global-selling.mercadolibre.com/questions',
        'x-csrf-token': csrf_token,
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    params = {'reAnswer': 'on_demand'}

    try:
        r = requests.get(url, headers=headers, cookies=cookies_dict, params=params, timeout=30)

        if r.status_code in [200, 206]:
            data = r.json()
            return data.get('suggestion') or data.get('answer') or data.get('text')
        else:
            print(f"Error {r.status_code}: {r.text[:200]}")
            return None

    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == "__main__":
    # Ejemplo de uso
    question_id = 13488833889

    print("=" * 80)
    print("🤖 OBTENER RESPUESTA SUGERIDA DE MERCADOLIBRE")
    print("=" * 80)
    print()

    # Opción 1: Intentar con API + cookies (rápido)
    print("📡 Intentando con API + cookies guardadas...")
    answer = get_ml_suggested_answer_api(question_id)

    if not answer:
        # Opción 2: Usar Selenium (más lento pero más confiable)
        print("\n🌐 Intentando con Selenium...")
        answer = get_ml_suggested_answer_selenium(question_id, headless=False)

    if answer:
        print("\n" + "=" * 80)
        print("✅ RESPUESTA SUGERIDA:")
        print("=" * 80)
        print(answer)
    else:
        print("\n❌ No se pudo obtener la respuesta sugerida")
