#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 19_capture_amazon_session.py - CAPTURA SESIÓN DE AMAZON PRIME
# ═══════════════════════════════════════════════════════════════════════════════
#
# ¿Qué hace?
#   Captura cookies de tu sesión de Amazon Prime para que el scraper pueda
#   obtener delivery times precisos usando tu cuenta.
#
#   - Abre navegador con Amazon.com
#   - Te logueas manualmente
#   - Captura cookies automáticamente
#   - Guarda en cache/amazon_session_cookies.json
#
# ¿Cuándo ejecutar?
#   - Primera vez que configuras el sistema
#   - Cuando las cookies expiren (cada ~1 mes)
#   - Si el scraper detecta que no está logueado
#
# Comando:
#   python3 19_capture_amazon_session.py
#
# ═══════════════════════════════════════════════════════════════════════════════

import sys
import os

# Agregar directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar y ejecutar el script de captura
from scripts.tools.capture_amazon_session import capture_amazon_cookies

if __name__ == "__main__":
    print()
    print("═" * 80)
    print("19 - CAPTURA SESIÓN DE AMAZON PRIME")
    print("═" * 80)
    print()

    success = capture_amazon_cookies()

    print()
    print("═" * 80)

    if success:
        print("✅ SESIÓN CAPTURADA EXITOSAMENTE")
        print("═" * 80)
        print()
        print("Las cookies se guardaron en: cache/amazon_session_cookies.json")
        print()
        print("Ahora el scraper (06_sync_loop.py) usará tu sesión Prime automáticamente")
        print()
        print("Próximos pasos:")
        print("  - Ejecuta el sync: python3 06_sync_loop.py")
        print("  - Verifica delivery times precisos (4-5 días)")
    else:
        print("❌ ERROR CAPTURANDO SESIÓN")
        print("═" * 80)
        print()
        print("Posibles soluciones:")
        print("  1. Asegurate de loguearte correctamente en Amazon")
        print("  2. Completa cualquier verificación (2FA, CAPTCHA)")
        print("  3. Ejecuta el script de nuevo")
        print()
        print("Si el problema persiste, contacta soporte")

    print()
    print("═" * 80)
