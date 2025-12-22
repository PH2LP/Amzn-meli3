#!/usr/bin/env python3
"""
11_server_status.py
────────────────────────────────────────────────────────────────────
¿Qué hace?
    Muestra el estado de todos los procesos en el servidor

USO:
    python3 11_server_status.py

Verifica el estado del sync de Amazon-ML en el servidor VPS
────────────────────────────────────────────────────────────────────
"""

import os
import subprocess
import sys
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
    print()
    print(f"{BLUE}═══════════════════════════════════════════════════════════════════{NC}")
    print(f"{BLUE}                    SERVER STATUS{NC}")
    print(f"{BLUE}═══════════════════════════════════════════════════════════════════{NC}")
    print()

    # Verificar si sync_amazon_ml.py está corriendo
    print(f"{YELLOW}Verificando procesos de sync...{NC}")
    check_cmd = f"sshpass -p '{VPS_PASSWORD}' ssh -o StrictHostKeyChecking=no {VPS_USER}@{VPS_HOST} 'ps aux | grep sync_amazon_ml.py | grep -v grep'"

    result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0 and result.stdout.strip():
        print(f"{GREEN}● Active (running){NC}")
        print()
        print(f"Procesos encontrados:")
        for line in result.stdout.strip().split('\n'):
            print(f"   {line[:120]}")
        print()
    else:
        print(f"{YELLOW}○ Inactive (stopped){NC}")
        print(f"{YELLOW}   El sync no está corriendo en el servidor{NC}")
        print()

    # Ver último sync en el log
    print(f"{YELLOW}Últimas líneas del log de sync:{NC}")
    log_cmd = f"sshpass -p '{VPS_PASSWORD}' ssh -o StrictHostKeyChecking=no {VPS_USER}@{VPS_HOST} 'tail -20 {VPS_PATH}/logs/sync/sync_loop.log 2>/dev/null || echo \"No log file found\"'"

    result = subprocess.run(log_cmd, shell=True, capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout)
    else:
        print(f"{YELLOW}   No hay logs disponibles{NC}")

    print()
    print(f"{BLUE}Server: {VPS_USER}@{VPS_HOST}{NC}")
    print(f"{BLUE}Path: {VPS_PATH}{NC}")
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
