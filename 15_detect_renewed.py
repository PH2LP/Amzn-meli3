#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 15_detect_renewed.py - DETECTOR DE PRODUCTOS RENOVADOS
# ═══════════════════════════════════════════════════════════════════════════════
#
# ¿Qué hace?
#   Lee todos los ASINs de la DB, consulta Amazon y detecta productos renovados,
#   reacondicionados, usados, etc.
#
# Comando:
#   python3 15_detect_renewed.py              # Solo detectar
#   python3 15_detect_renewed.py --export     # Detectar y exportar a CSV
#
# ═══════════════════════════════════════════════════════════════════════════════
import subprocess
import sys

# Colores
class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

def main():
    print(f"{Colors.BLUE}╔════════════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║          DETECTOR DE PRODUCTOS RENOVADOS                    ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.NC}\n")

    # Pasar argumentos al script real
    args = ["python3", "scripts/tools/detect_renewed_products.py"] + sys.argv[1:]

    try:
        subprocess.run(args)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}🛑 Detenido por usuario{Colors.NC}")

if __name__ == "__main__":
    main()
