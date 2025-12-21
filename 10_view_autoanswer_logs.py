#!/usr/bin/env python3
"""
view_auto_answer_logs.py
────────────────────────────────────────────────────────────────────
Visualiza los logs del sistema de respuestas automáticas
────────────────────────────────────────────────────────────────────
"""

import os
import subprocess
import sys
import argparse
from dotenv import load_dotenv

load_dotenv()

# Colores
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
RED = '\033[0;31m'
NC = '\033[0m'

# Configuración desde .env
VPS_HOST = os.getenv("REMOTE_DB_HOST", "138.197.32.67")
VPS_USER = os.getenv("REMOTE_DB_USER", "root")
VPS_PASSWORD = os.getenv("REMOTE_DB_PASSWORD")
VPS_PATH = "/opt/amz-ml-system"

def main():
    parser = argparse.ArgumentParser(description="Ver logs de auto-answer")
    parser.add_argument("--lines", "-n", type=int, default=100, help="Número de líneas a mostrar (default: 100)")
    parser.add_argument("--follow", "-f", action="store_true", help="Seguir el log en tiempo real")

    args = parser.parse_args()

    print()
    print(f"{BLUE}════════════════════════════════════════════════════════════════════{NC}")
    print(f"{BLUE}          LOGS DE AUTO-ANSWER{NC}")
    print(f"{BLUE}════════════════════════════════════════════════════════════════════{NC}")
    print()

    log_file = f"{VPS_PATH}/logs/auto_answer.log"

    if args.follow:
        print(f"{YELLOW}Siguiendo log en tiempo real...{NC}")
        print(f"{YELLOW}Presiona Ctrl+C para detener{NC}")
        print()

        cmd = f"sshpass -p '{VPS_PASSWORD}' ssh -o StrictHostKeyChecking=no {VPS_USER}@{VPS_HOST} 'tail -f {log_file}'"
    else:
        print(f"{YELLOW}Mostrando últimas {args.lines} líneas...{NC}")
        print()

        cmd = f"sshpass -p '{VPS_PASSWORD}' ssh -o StrictHostKeyChecking=no {VPS_USER}@{VPS_HOST} 'tail -n {args.lines} {log_file}'"

    try:
        subprocess.run(cmd, shell=True)
        print()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}⏸️  Detenido{NC}")
        print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}⏸️  Operación cancelada{NC}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{RED}❌ Error: {e}{NC}")
        sys.exit(1)
