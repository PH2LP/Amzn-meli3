#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
18_start_sales_tracking.py
═══════════════════════════════════════════════════════════════════════════════
INICIAR SALES TRACKING DAEMON EN SERVIDOR
═══════════════════════════════════════════════════════════════════════════════

Inicia el daemon de tracking de ventas en el servidor que:
- Trackea nuevas ventas cada 1 hora
- Genera Excel profesional con Dashboard
- Sube Excel a Dropbox
- Sube DB de ventas a Dropbox
- Sube DB de productos a Dropbox

Accede al Excel desde cualquier dispositivo en Dropbox:
    /VENTAS_MERCADOLIBRE.xlsx
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
    print(f"{Colors.BLUE}║          INICIAR SALES TRACKING DAEMON EN SERVIDOR           ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.NC}\n")

    print(f"{Colors.CYAN}🌐 Servidor: {VPS_HOST}{Colors.NC}")
    print(f"{Colors.CYAN}👤 Usuario: {VPS_USER}{Colors.NC}")
    print(f"{Colors.CYAN}📁 Path: {VPS_PATH}{Colors.NC}\n")

    # Comando para ejecutar en servidor
    daemon_script = f"{VPS_PATH}/scripts/server/sales_tracking_daemon.py"
    log_file = f"{VPS_PATH}/logs/sales_daemon.log"
    pid_file = f"{VPS_PATH}/logs/sales_daemon.pid"

    ssh_commands = f"""
        cd {VPS_PATH} && \
        mkdir -p logs && \
        nohup python3 {daemon_script} > {log_file} 2>&1 & \
        echo $! > {pid_file} && \
        sleep 2 && \
        if ps -p $(cat {pid_file}) > /dev/null 2>&1; then
            echo "DAEMON_STARTED_OK"
        else
            echo "DAEMON_START_FAILED"
        fi
    """

    print(f"{Colors.CYAN}🚀 Iniciando daemon en servidor...{Colors.NC}\n")

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

        if "DAEMON_STARTED_OK" in result.stdout:
            print(f"{Colors.GREEN}✅ Sales tracking daemon iniciado exitosamente{Colors.NC}\n")

            # Obtener PID
            get_pid_cmd = [
                "sshpass", "-p", VPS_PASSWORD,
                "ssh", "-o", "StrictHostKeyChecking=no",
                f"{VPS_USER}@{VPS_HOST}",
                f"cat {pid_file}"
            ]

            pid_result = subprocess.run(get_pid_cmd, capture_output=True, text=True)
            if pid_result.returncode == 0:
                pid = pid_result.stdout.strip()
                print(f"{Colors.CYAN}📌 PID del daemon: {pid}{Colors.NC}")

            print(f"\n{Colors.BLUE}{'─' * 64}{Colors.NC}")
            print(f"{Colors.CYAN}📊 El daemon ejecutará cada 1 hora:{Colors.NC}")
            print(f"   1. Track de nuevas ventas")
            print(f"   2. Generación de Excel profesional")
            print(f"   3. Upload a Dropbox:")
            print(f"      • /VENTAS_MERCADOLIBRE.xlsx")
            print(f"      • /sales_tracking.db")
            print(f"      • /listings_database.db")
            print(f"\n{Colors.GREEN}💡 Accede al Excel desde cualquier dispositivo en Dropbox{Colors.NC}")
            print(f"{Colors.BLUE}{'─' * 64}{Colors.NC}\n")

            print(f"{Colors.YELLOW}📝 Comandos útiles:{Colors.NC}")
            print(f"   Ver logs en vivo:  python3 19_view_sales_logs.py")
            print(f"   Detener daemon:    python3 20_stop_sales_tracking.py")
            print(f"   Estado:            python3 11_server_status.py")

        else:
            print(f"{Colors.RED}❌ Error iniciando daemon{Colors.NC}")
            if result.stderr:
                print(f"\n{Colors.RED}Error:{Colors.NC}")
                print(result.stderr)

    except subprocess.TimeoutExpired:
        print(f"{Colors.RED}❌ Timeout conectando al servidor{Colors.NC}")
    except FileNotFoundError:
        print(f"{Colors.RED}❌ Error: sshpass no instalado{Colors.NC}")
        print(f"{Colors.YELLOW}Instala: brew install sshpass{Colors.NC}")
    except Exception as e:
        print(f"{Colors.RED}❌ Error: {e}{Colors.NC}")


if __name__ == "__main__":
    main()
