#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
07_view_sync_live.py
═══════════════════════════════════════════════════════════════════════════════
VER LOGS DE SYNC CRON EN TIEMPO REAL
═══════════════════════════════════════════════════════════════════════════════

Muestra los logs del sync ejecutado por cron en tiempo real

USO:
    python3 07_view_sync_live.py

    Presiona Ctrl+C para salir
═══════════════════════════════════════════════════════════════════════════════
"""

import subprocess
import sys
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
    log_file = project_dir / "logs" / "sync" / "sync_cron.log"

    print()
    print(f"{Colors.CYAN}╔════════════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.CYAN}║          SYNC CRON - MONITOREO EN TIEMPO REAL                ║{Colors.NC}")
    print(f"{Colors.CYAN}╚════════════════════════════════════════════════════════════════╝{Colors.NC}")
    print()

    if not log_file.exists():
        print(f"{Colors.YELLOW}⚠️  Esperando primera ejecución del cron...{Colors.NC}")
        print(f"   Log: {log_file}")
        print(f"   Próximas ejecuciones: 00:00, 06:00, 12:00, 18:00")
        print()
        print(f"{Colors.CYAN}   Monitoreando archivo (se actualizará cuando corra el cron)...{Colors.NC}")
        print()

    print(f"{Colors.GREEN}📝 Monitoreando: {log_file.name}{Colors.NC}")
    print(f"{Colors.YELLOW}👀 Mostrando logs en tiempo real (Ctrl+C para salir)...{Colors.NC}")
    print(f"{Colors.CYAN}{'─' * 64}{Colors.NC}")
    print()

    try:
        # Mostrar últimas 50 líneas si el archivo existe
        if log_file.exists():
            subprocess.run(f"tail -50 {log_file}", shell=True)
            print(f"{Colors.CYAN}{'─' * 64}{Colors.NC}")
            print(f"{Colors.GREEN}▼ LOGS EN VIVO{Colors.NC}")
            print(f"{Colors.CYAN}{'─' * 64}{Colors.NC}")
            print()

        # Seguir el archivo (tail -f espera si no existe)
        subprocess.run(f"tail -f {log_file}", shell=True)
    except KeyboardInterrupt:
        print()
        print(f"{Colors.YELLOW}✋ Detenido por el usuario{Colors.NC}")
        print()

if __name__ == "__main__":
    main()
