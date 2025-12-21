#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
07_view_sync_live.py
═══════════════════════════════════════════════════════════════════════════════
VER LOGS DE SYNC LOCAL EN TIEMPO REAL
═══════════════════════════════════════════════════════════════════════════════

Muestra los logs del sync local en tiempo real

USO:
    python3 07_view_sync_live.py

    Presiona Ctrl+C para salir
═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import subprocess
from pathlib import Path

# Colores
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

def main():
    project_dir = Path(__file__).parent
    log_dir = project_dir / "logs" / "sync_local"

    print()
    print(f"{Colors.CYAN}╔════════════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.CYAN}║        LOGS DE SINCRONIZACIÓN LOCAL - TIEMPO REAL            ║{Colors.NC}")
    print(f"{Colors.CYAN}╚════════════════════════════════════════════════════════════════╝{Colors.NC}")
    print()

    # Verificar si hay sync corriendo
    check_cmd = "ps aux | grep 'sync_amazon_ml' | grep -v grep | grep -v '07_view'"
    result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0 or not result.stdout.strip():
        print(f"{Colors.RED}❌ No hay sync corriendo{Colors.NC}")
        print(f"{Colors.YELLOW}   Inicialo con: python3 05_start_sync_amzn_meli.py{Colors.NC}")
        print()
        sys.exit(1)

    # Obtener PID
    parts = result.stdout.strip().split()
    pid = parts[1] if len(parts) > 1 else "?"
    print(f"{Colors.GREEN}✅ Sync corriendo (PID: {pid}){Colors.NC}")

    # Buscar el log más reciente
    log_files = sorted(log_dir.glob("sync_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)

    if not log_files:
        print(f"{Colors.YELLOW}⚠️  No se encontraron archivos de log en {log_dir}{Colors.NC}")
        print()
        sys.exit(1)

    log_file = log_files[0]
    print(f"📝 Log: {log_file.name}")
    print()
    print(f"{Colors.CYAN}{'─' * 64}{Colors.NC}")
    print(f"{Colors.YELLOW}👀 Mostrando logs en tiempo real (Ctrl+C para salir)...{Colors.NC}")
    print(f"{Colors.CYAN}{'─' * 64}{Colors.NC}")
    print()

    try:
        # Mostrar últimas 30 líneas
        subprocess.run(f"tail -30 {log_file}", shell=True)

        print(f"{Colors.CYAN}{'─' * 64}{Colors.NC}")
        print(f"{Colors.GREEN}▼ LOGS EN VIVO{Colors.NC}")
        print(f"{Colors.CYAN}{'─' * 64}{Colors.NC}")

        # Seguir el archivo
        subprocess.run(f"tail -f {log_file}", shell=True)
    except KeyboardInterrupt:
        print()
        print(f"{Colors.YELLOW}✋ Detenido por el usuario{Colors.NC}")
        print()

if __name__ == "__main__":
    main()
