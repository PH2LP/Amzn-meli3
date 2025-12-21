#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
19_view_sales_logs.py
═══════════════════════════════════════════════════════════════════════════════
VER LOGS DEL SALES TRACKING DAEMON EN TIEMPO REAL
═══════════════════════════════════════════════════════════════════════════════

Muestra los logs del daemon de sales tracking ejecutándose en el servidor.

USO:
    python3 19_view_sales_logs.py          # Ver últimas 50 líneas
    python3 19_view_sales_logs.py --live   # Ver en tiempo real (tail -f)
    python3 19_view_sales_logs.py --full   # Ver archivo completo
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv(override=True)

# Configuración SSH
VPS_HOST = os.getenv("VPS_HOST", "138.197.32.67")
VPS_USER = os.getenv("VPS_USER", "root")
VPS_PASSWORD = os.getenv("REMOTE_DB_PASSWORD", "koqven-1regka-nyfXiw")
VPS_PATH = os.getenv("VPS_PATH", "/opt/amz-ml-system")

# Colores
class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Ver logs de sales tracking daemon")
    parser.add_argument("--live", action="store_true", help="Ver en tiempo real (tail -f)")
    parser.add_argument("--full", action="store_true", help="Ver archivo completo")
    args = parser.parse_args()

    print(f"{Colors.BLUE}╔════════════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║            LOGS DE SALES TRACKING DAEMON                      ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.NC}\n")

    log_file = f"{VPS_PATH}/logs/sales_daemon.log"

    # Construir comando
    if args.live:
        print(f"{Colors.CYAN}📡 Mostrando logs en tiempo real (Ctrl+C para salir)...{Colors.NC}\n")
        tail_cmd = f"tail -f {log_file}"
    elif args.full:
        print(f"{Colors.CYAN}📄 Mostrando archivo completo...{Colors.NC}\n")
        tail_cmd = f"cat {log_file}"
    else:
        print(f"{Colors.CYAN}📄 Mostrando últimas 50 líneas...{Colors.NC}\n")
        tail_cmd = f"tail -n 50 {log_file}"

    # SSH command
    import subprocess

    cmd = [
        "sshpass", "-p", VPS_PASSWORD,
        "ssh", "-o", "StrictHostKeyChecking=no",
        f"{VPS_USER}@{VPS_HOST}",
        tail_cmd
    ]

    try:
        # Ejecutar (streaming)
        if args.live:
            subprocess.run(cmd)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                print(result.stdout)
            else:
                print(f"{Colors.RED}❌ Error leyendo logs{Colors.NC}")
                if result.stderr:
                    print(result.stderr)

    except FileNotFoundError:
        print(f"{Colors.RED}❌ Error: sshpass no instalado{Colors.NC}")
        print(f"{Colors.YELLOW}Instala: brew install sshpass{Colors.NC}")
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}🛑 Detenido por usuario{Colors.NC}")
    except Exception as e:
        print(f"{Colors.RED}❌ Error: {e}{Colors.NC}")


if __name__ == "__main__":
    main()
