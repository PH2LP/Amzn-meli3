#!/usr/bin/env python3
"""
Extrae cookies de Amazon desde Chrome y las guarda para usar en el scraper

Uso:
    python3 scripts/tools/extract_amazon_cookies.py

IMPORTANTE:
    1. Asegurate de estar logueado en Amazon.com en Chrome
    2. Cierra Chrome antes de ejecutar este script (Chrome bloquea la DB)
    3. Las cookies se guardan en: cache/amazon_session_cookies.json
"""
import sqlite3
import json
import os
import shutil
from pathlib import Path

# Path de cookies de Chrome en macOS
CHROME_COOKIES_PATH = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome/Default/Cookies"
)

# Archivo donde guardaremos las cookies
OUTPUT_FILE = "cache/amazon_session_cookies.json"

def extract_amazon_cookies():
    """Extrae cookies de Amazon desde Chrome"""

    if not os.path.exists(CHROME_COOKIES_PATH):
        print(f"❌ No se encontró la base de datos de cookies de Chrome")
        print(f"   Buscado en: {CHROME_COOKIES_PATH}")
        return False

    # Crear directorio cache si no existe
    os.makedirs("cache", exist_ok=True)

    # Copiar DB temporalmente (Chrome la bloquea si está abierto)
    temp_db = "/tmp/chrome_cookies_temp.db"
    try:
        shutil.copyfile(CHROME_COOKIES_PATH, temp_db)
    except Exception as e:
        print(f"❌ Error copiando DB de cookies: {e}")
        print(f"   Asegurate de cerrar Chrome antes de ejecutar este script")
        return False

    # Conectar a la DB
    try:
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Buscar cookies de amazon.com
        cursor.execute("""
            SELECT name, value, host_key, path, expires_utc, is_secure
            FROM cookies
            WHERE host_key LIKE '%amazon.com%'
        """)

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            print(f"❌ No se encontraron cookies de Amazon")
            print(f"   Asegurate de estar logueado en Amazon.com en Chrome")
            return False

        # Convertir a formato dict
        cookies = {}
        important_cookies = ['session-id', 'ubid-main', 'at-main', 'sess-at-main', 'x-main', 'session-token']

        for row in rows:
            name, value, host, path, expires, secure = row
            cookies[name] = {
                'value': value,
                'domain': host,
                'path': path,
                'expires': expires,
                'secure': bool(secure)
            }

        # Guardar cookies
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(cookies, f, indent=2)

        # Verificar que tenemos las cookies importantes
        found_important = [c for c in important_cookies if c in cookies]

        print("=" * 80)
        print("✅ Cookies de Amazon extraídas exitosamente")
        print("=" * 80)
        print(f"Total cookies: {len(cookies)}")
        print(f"Cookies importantes encontradas: {len(found_important)}/{len(important_cookies)}")
        print()
        print("Cookies importantes:")
        for cookie_name in important_cookies:
            if cookie_name in cookies:
                value = cookies[cookie_name]['value']
                print(f"  ✅ {cookie_name}: {value[:20]}..." if len(value) > 20 else f"  ✅ {cookie_name}: {value}")
            else:
                print(f"  ⚠️  {cookie_name}: NO ENCONTRADA")
        print()
        print(f"Guardado en: {OUTPUT_FILE}")
        print("=" * 80)

        # Limpiar temp
        os.remove(temp_db)

        return True

    except Exception as e:
        print(f"❌ Error leyendo cookies: {e}")
        return False

if __name__ == "__main__":
    print("=" * 80)
    print("Extractor de Cookies de Amazon desde Chrome")
    print("=" * 80)
    print()
    print("INSTRUCCIONES:")
    print("  1. Asegurate de estar logueado en Amazon.com en Chrome")
    print("  2. CIERRA Chrome completamente")
    print("  3. Ejecuta este script")
    print()
    input("Presiona ENTER cuando hayas cerrado Chrome...")
    print()

    success = extract_amazon_cookies()

    if success:
        print()
        print("🎉 Listo! El scraper ahora usará tu sesión de Amazon Prime")
        print()
        print("Próximos pasos:")
        print("  - Ejecuta el sync normalmente")
        print("  - Debería detectar delivery times de Prime (1-3 días)")
    else:
        print()
        print("❌ Error extrayendo cookies")
        print()
        print("Soluciones:")
        print("  1. Asegurate de cerrar Chrome completamente")
        print("  2. Verifica estar logueado en amazon.com")
        print("  3. Reinicia Chrome y vuelve a intentar")
