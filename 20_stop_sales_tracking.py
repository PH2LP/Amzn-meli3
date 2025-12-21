#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
20_stop_sales_tracking.py
═══════════════════════════════════════════════════════════════════════════════
DETENER SALES TRACKING DAEMON EN SERVIDOR
═══════════════════════════════════════════════════════════════════════════════

Detiene el daemon de sales tracking que se ejecuta en el servidor.
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
    print(f"{Colors.BLUE}╔════════════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║           DETENER SALES TRACKING DAEMON                       ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.NC}\n")

    pid_file = f"{VPS_PATH}/logs/sales_daemon.pid"

    # Comando para detener daemon
    ssh_commands = f"""
        if [ -f {pid_file} ]; then
            PID=$(cat {pid_file})
            if ps -p $PID > /dev/null 2>&1; then
                kill -TERM $PID
                sleep 2
                if ps -p $PID > /dev/null 2>&1; then
                    kill -9 $PID
                    echo "DAEMON_FORCE_KILLED"
                else
                    echo "DAEMON_STOPPED_OK"
                fi
                rm -f {pid_file}
            else
                echo "DAEMON_NOT_RUNNING"
                rm -f {pid_file}
            fi
        else
            echo "PID_FILE_NOT_FOUND"
        fi
    """

    print(f"{Colors.CYAN}🛑 Deteniendo daemon en servidor...{Colors.NC}\n")

    # Ejecutar via SSH
    import subprocess

    cmd = [
        "sshpass", "-p", VPS_PASSWORD,
        "ssh", "-o", "StrictHostKeyChecking=no",
        f"{VPS_USER}@{VPS_HOST}",
        ssh_commands
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        output = result.stdout.strip()

        if "DAEMON_STOPPED_OK" in output:
            print(f"{Colors.GREEN}✅ Sales tracking daemon detenido exitosamente{Colors.NC}\n")
        elif "DAEMON_FORCE_KILLED" in output:
            print(f"{Colors.YELLOW}⚠️  Daemon detenido forzadamente (kill -9){Colors.NC}\n")
        elif "DAEMON_NOT_RUNNING" in output:
            print(f"{Colors.YELLOW}⚠️  El daemon no estaba ejecutándose{Colors.NC}\n")
        elif "PID_FILE_NOT_FOUND" in output:
            print(f"{Colors.YELLOW}⚠️  No se encontró el archivo PID (daemon no iniciado){Colors.NC}\n")
        else:
            print(f"{Colors.RED}❌ Respuesta inesperada:{Colors.NC}")
            print(output)

        print(f"{Colors.CYAN}💡 Para reiniciar: python3 18_start_sales_tracking.py{Colors.NC}")

    except FileNotFoundError:
        print(f"{Colors.RED}❌ Error: sshpass no instalado{Colors.NC}")
        print(f"{Colors.YELLOW}Instala: brew install sshpass{Colors.NC}")
    except Exception as e:
        print(f"{Colors.RED}❌ Error: {e}{Colors.NC}")


if __name__ == "__main__":
    main()
