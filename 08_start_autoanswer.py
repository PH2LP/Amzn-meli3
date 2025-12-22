#!/usr/bin/env python3
"""
08_start_autoanswer.py
────────────────────────────────────────────────────────────────────
¿Qué hace?
    Inicia el bot de respuestas automáticas en el servidor

USO:
    python3 08_start_autoanswer.py

Inicia el sistema de respuestas automáticas en el servidor VPS
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
NC = '\033[0m'

# Configuración desde .env
VPS_HOST = os.getenv("REMOTE_DB_HOST", "138.197.32.67")
VPS_USER = os.getenv("REMOTE_DB_USER", "root")
VPS_PASSWORD = os.getenv("REMOTE_DB_PASSWORD")
VPS_PATH = "/opt/amz-ml-system"

def main():
    print()
    print(f"{BLUE}════════════════════════════════════════════════════════════════════{NC}")
    print(f"{BLUE}          INICIAR AUTO-ANSWER EN SERVIDOR{NC}")
    print(f"{BLUE}════════════════════════════════════════════════════════════════════{NC}")
    print()

    # Verificar si ya está corriendo
    print(f"{YELLOW}Verificando si auto-answer ya está activo...{NC}")
    check_cmd = f"sshpass -p '{VPS_PASSWORD}' ssh -o StrictHostKeyChecking=no {VPS_USER}@{VPS_HOST} 'ps aux | grep auto_answer_questions.py | grep -v grep'"

    result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0 and result.stdout.strip():
        print(f"{YELLOW}⚠️  Auto-answer ya está corriendo en el servidor{NC}")
        print(f"{YELLOW}   Si querés reiniciarlo, primero ejecutá: python3 stop_auto_answer.py{NC}")
        print()
        return

    # Iniciar auto-answer en background
    print(f"{YELLOW}Conectando a {VPS_HOST}...{NC}")
    start_cmd = f"sshpass -p '{VPS_PASSWORD}' ssh -o StrictHostKeyChecking=no {VPS_USER}@{VPS_HOST} 'cd {VPS_PATH} && nohup ./start_auto_answer.sh > /dev/null 2>&1 &'"

    subprocess.run(start_cmd, shell=True)

    # Esperar un momento y verificar
    import time
    time.sleep(2)

    result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0 and result.stdout.strip():
        print(f"{GREEN}✅ Auto-answer iniciado correctamente{NC}")
        print()
        print(f"📊 {BLUE}Sistema activo:{NC}")
        print(f"   • Revisa preguntas cada 60 segundos")
        print(f"   • Responde automáticamente con IA")
        print(f"   • Log: {VPS_PATH}/logs/auto_answer.log")
        print()
        print(f"{YELLOW}Para ver el log en tiempo real:{NC}")
        print(f"   python3 view_auto_answer_logs.py")
        print()
        print(f"{YELLOW}Para detenerlo:{NC}")
        print(f"   python3 stop_auto_answer.py")
        print()
    else:
        print(f"{YELLOW}⚠️  No se pudo verificar si el proceso inició correctamente{NC}")
        print(f"{YELLOW}   Revisá el log manualmente: python3 view_auto_answer_logs.py{NC}")
        print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}⏸️  Operación cancelada{NC}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{YELLOW}❌ Error: {e}{NC}")
        sys.exit(1)
