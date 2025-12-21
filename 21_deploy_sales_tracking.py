#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
21_deploy_sales_tracking.py
═══════════════════════════════════════════════════════════════════════════════
DEPLOY DE SALES TRACKING DAEMON AL SERVIDOR
═══════════════════════════════════════════════════════════════════════════════

Sube todos los archivos necesarios al servidor:
- scripts/server/sales_tracking_daemon.py
- scripts/tools/track_sales.py
- scripts/tools/generate_excel_desktop.py
- .env (variables de entorno)

Y opcionalmente inicia el daemon automáticamente.
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


def upload_file(local_path, remote_path):
    """
    Sube un archivo al servidor via SCP

    Args:
        local_path: Ruta local del archivo
        remote_path: Ruta remota en el servidor

    Returns:
        bool: True si se subió correctamente
    """
    import subprocess

    if not os.path.exists(local_path):
        print(f"{Colors.RED}   ❌ Archivo no existe: {local_path}{Colors.NC}")
        return False

    cmd = [
        "sshpass", "-p", VPS_PASSWORD,
        "scp", "-o", "StrictHostKeyChecking=no",
        local_path,
        f"{VPS_USER}@{VPS_HOST}:{remote_path}"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            filename = os.path.basename(local_path)
            print(f"{Colors.GREEN}   ✅ {filename}{Colors.NC}")
            return True
        else:
            print(f"{Colors.RED}   ❌ Error subiendo {local_path}{Colors.NC}")
            if result.stderr:
                print(f"      {result.stderr}")
            return False

    except Exception as e:
        print(f"{Colors.RED}   ❌ Error: {e}{Colors.NC}")
        return False


def create_remote_dirs():
    """Crea directorios necesarios en el servidor"""
    import subprocess

    dirs = [
        f"{VPS_PATH}/scripts/server",
        f"{VPS_PATH}/scripts/tools",
        f"{VPS_PATH}/logs",
        f"{VPS_PATH}/storage"
    ]

    cmd = [
        "sshpass", "-p", VPS_PASSWORD,
        "ssh", "-o", "StrictHostKeyChecking=no",
        f"{VPS_USER}@{VPS_HOST}",
        f"mkdir -p {' '.join(dirs)}"
    ]

    subprocess.run(cmd, capture_output=True, timeout=10)


def install_dependencies():
    """Instala dependencias de Python en el servidor"""
    print(f"\n{Colors.CYAN}📦 Instalando dependencias en servidor...{Colors.NC}")

    import subprocess

    deps = [
        "dropbox",
        "pandas",
        "openpyxl",
        "requests",
        "python-dotenv"
    ]

    cmd = [
        "sshpass", "-p", VPS_PASSWORD,
        "ssh", "-o", "StrictHostKeyChecking=no",
        f"{VPS_USER}@{VPS_HOST}",
        f"cd {VPS_PATH} && pip3 install {' '.join(deps)}"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode == 0:
            print(f"{Colors.GREEN}   ✅ Dependencias instaladas{Colors.NC}")
            return True
        else:
            print(f"{Colors.YELLOW}   ⚠️  Algunas dependencias pueden no haberse instalado{Colors.NC}")
            return False

    except Exception as e:
        print(f"{Colors.RED}   ❌ Error instalando dependencias: {e}{Colors.NC}")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Deploy sales tracking daemon al servidor")
    parser.add_argument("--start", action="store_true", help="Iniciar daemon después del deploy")
    args = parser.parse_args()

    print(f"{Colors.BLUE}╔════════════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║        DEPLOY SALES TRACKING DAEMON AL SERVIDOR               ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.NC}\n")

    print(f"{Colors.CYAN}🌐 Servidor: {VPS_HOST}{Colors.NC}")
    print(f"{Colors.CYAN}📁 Path: {VPS_PATH}{Colors.NC}\n")

    # Crear directorios
    print(f"{Colors.CYAN}📁 Creando directorios...{Colors.NC}")
    create_remote_dirs()
    print(f"{Colors.GREEN}   ✅ Directorios creados{Colors.NC}")

    # Subir archivos
    print(f"\n{Colors.CYAN}📤 Subiendo archivos...{Colors.NC}")

    files_to_upload = [
        ("scripts/server/sales_tracking_daemon.py", f"{VPS_PATH}/scripts/server/sales_tracking_daemon.py"),
        ("scripts/tools/track_sales.py", f"{VPS_PATH}/scripts/tools/track_sales.py"),
        ("scripts/tools/generate_excel_desktop.py", f"{VPS_PATH}/scripts/tools/generate_excel_desktop.py"),
        ("scripts/tools/dropbox_auth.py", f"{VPS_PATH}/scripts/tools/dropbox_auth.py"),
        ("scripts/tools/get_dropbox_refresh_token.py", f"{VPS_PATH}/scripts/tools/get_dropbox_refresh_token.py"),
        (".env", f"{VPS_PATH}/.env"),
    ]

    uploaded = 0
    for local_path, remote_path in files_to_upload:
        if upload_file(local_path, remote_path):
            uploaded += 1

    print(f"\n{Colors.GREEN}✅ {uploaded}/{len(files_to_upload)} archivos subidos{Colors.NC}")

    # Instalar dependencias
    install_dependencies()

    # Hacer ejecutable
    print(f"\n{Colors.CYAN}🔧 Configurando permisos...{Colors.NC}")
    import subprocess
    chmod_cmd = [
        "sshpass", "-p", VPS_PASSWORD,
        "ssh", "-o", "StrictHostKeyChecking=no",
        f"{VPS_USER}@{VPS_HOST}",
        f"chmod +x {VPS_PATH}/scripts/server/sales_tracking_daemon.py"
    ]
    subprocess.run(chmod_cmd, capture_output=True)
    print(f"{Colors.GREEN}   ✅ Permisos configurados{Colors.NC}")

    print(f"\n{Colors.GREEN}{'═' * 64}{Colors.NC}")
    print(f"{Colors.GREEN}✅ DEPLOY COMPLETADO EXITOSAMENTE{Colors.NC}")
    print(f"{Colors.GREEN}{'═' * 64}{Colors.NC}\n")

    # Iniciar si se solicitó
    if args.start:
        print(f"{Colors.CYAN}🚀 Iniciando daemon...{Colors.NC}\n")
        import subprocess
        subprocess.run(["python3", "18_start_sales_tracking.py"])
    else:
        print(f"{Colors.CYAN}💡 Para iniciar el daemon:{Colors.NC}")
        print(f"   python3 18_start_sales_tracking.py\n")


if __name__ == "__main__":
    main()
