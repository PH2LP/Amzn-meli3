#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
05_start_sync_amzn_meli.py
═══════════════════════════════════════════════════════════════════════════════
INICIAR DAEMON DE SYNC EN SERVIDOR VPS
═══════════════════════════════════════════════════════════════════════════════

Inicia el daemon de sincronización Amazon → MercadoLibre en el servidor VPS

USO:
    python3 05_start_sync_amzn_meli.py
═════════════════════════════════════════════════════════════════════════no puede ver ══════
"""

import os
import sys
import subprocess
import time
from dotenv import load_dotenv

load_dotenv(override=True)

# Colores
class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def main():
    host = os.getenv("VPS_HOST", "138.197.32.67")
    user = os.getenv("VPS_USER", "root")
    password = os.getenv("REMOTE_DB_PASSWORD")
    vps_path = os.getenv("VPS_PATH", "/opt/amz-ml-system")

    print()
    print(f"{Colors.BLUE}╔════════════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║        INICIAR DAEMON DE SINCRONIZACIÓN EN SERVIDOR          ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.NC}")
    print()
    print(f"🌐 Servidor: {host}")
    print()

    # Verificar si ya está corriendo
    check_cmd = f"sshpass -p '{password}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 {user}@{host} 'ps aux | grep run_sync_loop.py | grep -v grep'"
    result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, timeout=15)

    if result.returncode == 0 and result.stdout.strip():
        print(f"{Colors.YELLOW}⚠️  El daemon ya está corriendo en el servidor{Colors.NC}")
        print()
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            pid = parts[1] if len(parts) > 1 else "?"
            print(f"   PID: {pid}")
        print()
        print(f"{Colors.YELLOW}   Usa 06_stop_sync_amzn_meli.py para detenerlo primero{Colors.NC}")
        print()
        return

    # Iniciar daemon
    print(f"{Colors.YELLOW}🚀 Iniciando daemon en servidor...{Colors.NC}")

    # Ejecutar comando en background y desconectar inmediatamente
    start_cmd = f"sshpass -p '{password}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 {user}@{host} 'cd {vps_path} && nohup python3 scripts/tools/run_sync_loop.py > /dev/null 2>&1 & echo STARTED'"

    try:
        result = subprocess.run(start_cmd, shell=True, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        # Timeout es esperado a veces, verificar si se inició de todos modos
        result = None

    # Esperar 2 segundos para que el proceso se inicie
    time.sleep(2)

    # Verificar si está corriendo
    check_cmd = f"sshpass -p '{password}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 {user}@{host} 'ps aux | grep run_sync_loop.py | grep -v grep'"
    verify = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, timeout=10)

    if verify.returncode == 0 and verify.stdout.strip():
        # Obtener PID
        parts = verify.stdout.strip().split()
        pid = parts[1] if len(parts) > 1 else "?"

        print(f"{Colors.GREEN}✅ Daemon iniciado exitosamente{Colors.NC}")
        print(f"   PID: {pid}")
        print()
        print(f"{Colors.BLUE}💡 Comandos útiles:{Colors.NC}")
        print(f"   • Ver estado: python3 11_server_status.py")
        print(f"   • Ver logs:   python3 07_view_sync_live.py")
        print(f"   • Detener:    python3 06_stop_sync_amzn_meli.py")
        print()
    else:
        print(f"{Colors.RED}❌ Error al iniciar daemon{Colors.NC}")
        if result and result.stderr:
            print(f"   {result.stderr}")
        sys.exit(1)

if __name__ == "__main__":
    main()
