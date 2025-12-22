#!/usr/bin/env python3
"""
09_stop_autoanswer.py
────────────────────────────────────────────────────────────────────
¿Qué hace?
    Detiene el bot de respuestas automáticas

USO:
    python3 09_stop_autoanswer.py

Detiene el sistema de respuestas automáticas en el servidor VPS
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
    print(f"{BLUE}════════════════════════════════════════════════════════════════════{NC}")
    print(f"{BLUE}          DETENER AUTO-ANSWER EN SERVIDOR{NC}")
    print(f"{BLUE}════════════════════════════════════════════════════════════════════{NC}")
    print()

    # Verificar si está corriendo
    print(f"{YELLOW}Verificando procesos de auto-answer...{NC}")
    check_cmd = f"sshpass -p '{VPS_PASSWORD}' ssh -o StrictHostKeyChecking=no {VPS_USER}@{VPS_HOST} 'ps aux | grep auto_answer_questions.py | grep -v grep'"

    result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0 or not result.stdout.strip():
        print(f"{YELLOW}ℹ️  Auto-answer no está corriendo en el servidor{NC}")
        print()
        return

    # Mostrar procesos encontrados
    print(f"{YELLOW}Procesos encontrados:{NC}")
    for line in result.stdout.strip().split('\n'):
        print(f"   {line}")
    print()

    # Detener procesos
    print(f"{YELLOW}Deteniendo auto-answer...{NC}")
    stop_cmd = f"sshpass -p '{VPS_PASSWORD}' ssh -o StrictHostKeyChecking=no {VPS_USER}@{VPS_HOST} 'pkill -f auto_answer_questions.py && pkill -f start_auto_answer.sh'"

    subprocess.run(stop_cmd, shell=True)

    # Verificar que se detuvo
    import time
    time.sleep(2)

    result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0 or not result.stdout.strip():
        print(f"{GREEN}✅ Auto-answer detenido correctamente{NC}")
        print()
        print(f"📊 {BLUE}Sistema inactivo:{NC}")
        print(f"   • No se responderán preguntas automáticamente")
        print(f"   • El log se mantiene en: {VPS_PATH}/logs/auto_answer.log")
        print()
        print(f"{YELLOW}Para reiniciarlo:{NC}")
        print(f"   python3 start_auto_answer.py")
        print()
    else:
        print(f"{RED}⚠️  Algunos procesos no se pudieron detener{NC}")
        print(f"{YELLOW}   Intentá detenerlos manualmente con SSH{NC}")
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
