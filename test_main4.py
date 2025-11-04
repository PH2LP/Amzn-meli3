#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_main4.py - Script de prueba para main4.py

Prueba el sistema con un solo ASIN antes de ejecutar el batch completo.
"""

import os
import sys

# Auto-activar venv
if sys.prefix == sys.base_prefix:
    vpy = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
    if os.path.exists(vpy):
        print(f"⚙️ Activando entorno virtual: {vpy}")
        os.execv(vpy, [vpy] + sys.argv)

# Importar módulo principal
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from main4 import process_asin

def test_single_asin():
    """Prueba con un solo ASIN"""
    print("\n" + "="*80)
    print("🧪 TEST MODE - main4.py")
    print("="*80 + "\n")

    # ASIN de prueba (cambiar según necesidad)
    test_asin = "B0DRW69H11"  # Tercer ASIN de asins.txt

    print(f"🎯 ASIN de prueba: {test_asin}")
    print(f"📂 Buscando: storage/asins_json/{test_asin}.json")
    print()

    # Verificar que existe el JSON
    json_file = f"storage/asins_json/{test_asin}.json"
    if not os.path.exists(json_file):
        print(f"❌ ERROR: No existe {json_file}")
        print(f"   Por favor, coloca el JSON de Amazon en esa ubicación.")
        return False

    print(f"✅ JSON encontrado")
    print(f"🚀 Iniciando procesamiento...\n")

    # Procesar
    success = process_asin(test_asin)

    # Resultado
    print("\n" + "="*80)
    if success:
        print("✅ PRUEBA EXITOSA")
        print()
        print("El sistema funciona correctamente. Puedes ejecutar:")
        print("  python3 src/main4.py")
        print()
        print("Para procesar todos los ASINs de resources/asins.txt")
    else:
        print("❌ PRUEBA FALLIDA")
        print()
        print("Revisa los logs en:")
        print("  storage/logs/main4_publish.log")
        print()
        print("Y los errores en:")
        print("  storage/logs/main4_output/error_*.json")

    print("="*80 + "\n")

    return success


if __name__ == "__main__":
    test_single_asin()
