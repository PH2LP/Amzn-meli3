#!/usr/bin/env python3
"""
sync_mini_ml.py
────────────────────────────────────────────────────────────────────
Sincroniza archivos mini_ml.json locales al servidor
────────────────────────────────────────────────────────────────────
"""

import os
import subprocess
import sys
from pathlib import Path
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

LOCAL_DIR = "storage/logs/publish_ready"
REMOTE_DIR = f"{VPS_PATH}/storage/logs/publish_ready"

def main():
    print()
    print(f"{BLUE}═══════════════════════════════════════════════════════════════════{NC}")
    print(f"{BLUE}          SINCRONIZAR MINI_ML AL SERVIDOR{NC}")
    print(f"{BLUE}═══════════════════════════════════════════════════════════════════{NC}")
    print()

    # Contar archivos locales
    local_files = list(Path(LOCAL_DIR).glob("*_mini_ml.json"))
    print(f"{YELLOW}Archivos mini_ml locales: {len(local_files)}{NC}")
    print()

    if len(local_files) == 0:
        print(f"{RED}❌ No hay archivos mini_ml para sincronizar{NC}")
        return

    # Confirmar
    confirm = input("¿Sincronizar estos archivos al servidor? (s/N): ")
    if confirm.lower() != 's':
        print(f"{YELLOW}❌ Sincronización cancelada{NC}")
        return

    print()
    print(f"{YELLOW}Copiando archivos al servidor...{NC}")

    # Copiar archivos usando rsync (más eficiente que scp para muchos archivos)
    cmd = f"sshpass -p '{VPS_PASSWORD}' rsync -avz --progress {LOCAL_DIR}/*_mini_ml.json {VPS_USER}@{VPS_HOST}:{REMOTE_DIR}/"

    result = subprocess.run(cmd, shell=True)

    print()
    if result.returncode == 0:
        print(f"{GREEN}✅ Sincronización completada{NC}")
        print()
        print(f"{YELLOW}Los archivos mini_ml ahora están disponibles en el servidor{NC}")
        print(f"{YELLOW}El auto-answer los usará para responder preguntas{NC}")
    else:
        print(f"{RED}❌ Error en la sincronización{NC}")
        sys.exit(1)

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
