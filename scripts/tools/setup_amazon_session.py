#!/usr/bin/env python3
"""
Setup de sesión de Amazon Prime - MÉTODO MANUAL

Este script te guía para copiar las cookies desde el navegador
"""
import json
import os

COOKIES_FILE = "cache/amazon_session_cookies.json"

print("=" * 80)
print("SETUP: Amazon Prime Session")
print("=" * 80)
print()
print("PASO 1: Abre tu navegador")
print()
print("  1. Abre Chrome (o el navegador que uses)")
print("  2. Ve a: https://www.amazon.com")
print("  3. Loguéate con tu cuenta de Amazon Prime")
print()
input("Presiona ENTER cuando estés logueado en Amazon...")
print()

print("=" * 80)
print("PASO 2: Abre las Developer Tools")
print("=" * 80)
print()
print("  1. En la página de Amazon, presiona: Cmd+Option+I (Mac)")
print("     O click derecho → Inspeccionar")
print("  2. Ve a la pestaña 'Application' (o 'Aplicación')")
print("  3. En el panel izquierdo, expande 'Cookies'")
print("  4. Selecciona 'https://www.amazon.com'")
print()
input("Presiona ENTER cuando veas las cookies...")
print()

print("=" * 80)
print("PASO 3: Copia estas cookies IMPORTANTES")
print("=" * 80)
print()

cookies_to_get = {
    'session-id': None,
    'ubid-main': None,
    'session-token': None,
    'at-main': None,
    'sess-at-main': None,
    'x-main': None
}

print("Voy a pedirte cada cookie. En la tabla de cookies, buscá el 'Name'")
print("y copiá el 'Value' (doble click en el valor, Cmd+C)")
print()

for cookie_name in cookies_to_get.keys():
    print(f"🔍 Buscá la cookie: {cookie_name}")
    value = input(f"   Pegá el valor aquí (o ENTER si no existe): ").strip()
    if value:
        cookies_to_get[cookie_name] = {
            'value': value,
            'domain': '.amazon.com',
            'path': '/',
            'secure': True
        }
        print(f"   ✅ Cookie guardada: {value[:20]}...")
    else:
        print(f"   ⚠️  Cookie omitida")
    print()

# Filtrar solo las cookies que existen
cookies_final = {k: v for k, v in cookies_to_get.items() if v is not None}

if len(cookies_final) == 0:
    print("❌ No se guardó ninguna cookie!")
    print("   Intentá de nuevo asegurándote de copiar los valores correctos")
    exit(1)

# Guardar cookies
os.makedirs("cache", exist_ok=True)
with open(COOKIES_FILE, 'w') as f:
    json.dump(cookies_final, f, indent=2)

print("=" * 80)
print("✅ COOKIES GUARDADAS EXITOSAMENTE")
print("=" * 80)
print(f"Total cookies: {len(cookies_final)}")
print(f"Archivo: {COOKIES_FILE}")
print()

important = ['session-id', 'session-token']
has_important = all(c in cookies_final for c in important)

if has_important:
    print("✅ Cookies importantes presentes - Sesión Prime lista!")
else:
    print("⚠️  Faltan cookies importantes:")
    for c in important:
        if c not in cookies_final:
            print(f"    - {c}")
    print()
    print("El scraper puede funcionar pero sin beneficios de Prime")

print()
print("Próximo paso:")
print("  python3 src/integrations/amazon_glow_api_v2_advanced.py B0DX65SQXF 33172")
print()
