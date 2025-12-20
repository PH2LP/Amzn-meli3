#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
05_start_sync_amzn_meli.py
═══════════════════════════════════════════════════════════════════════════════
INICIAR SYNC LOCAL (MAC)
═══════════════════════════════════════════════════════════════════════════════

Inicia la sincronización Amazon → MercadoLibre en tu Mac local

USO:
    python3 05_start_sync_amzn_meli.py
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# Colores
class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def main():
    # Obtener ruta del proyecto
    project_dir = Path(__file__).parent

    print()
    print(f"{Colors.BLUE}╔════════════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║           INICIAR SINCRONIZACIÓN LOCAL (MAC)                 ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.NC}")
    print()
    print(f"💻 Modo: LOCAL (loop automático cada 6 horas)")
    print(f"📂 Directorio: {project_dir}")
    print()

    # Verificar si ya está corriendo
    check_cmd = "ps aux | grep 'sync_amazon_ml' | grep -v grep | grep -v '05_start'"
    result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0 and result.stdout.strip():
        print(f"{Colors.YELLOW}⚠️  El sync ya está corriendo{Colors.NC}")
        print()
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            pid = parts[1] if len(parts) > 1 else "?"
            cmd = ' '.join(parts[10:])[:60] if len(parts) > 10 else ""
            print(f"   PID: {pid} - {cmd}")
        print()
        print(f"{Colors.YELLOW}   Usa 06_stop_sync_amzn_meli.py para detenerlo primero{Colors.NC}")
        print()
        return

    # Refrescar token de MercadoLibre antes de iniciar
    print(f"{Colors.YELLOW}🔄 Refrescando token de MercadoLibre...{Colors.NC}")
    sys.path.insert(0, str(project_dir / 'src' / 'integrations'))
    try:
        from mainglobal import refresh_ml_token
        if refresh_ml_token(force=True):
            print(f"{Colors.GREEN}   ✅ Token actualizado{Colors.NC}")
        else:
            print(f"{Colors.YELLOW}   ⚠️  No se pudo actualizar token (usando token actual){Colors.NC}")
    except Exception as e:
        print(f"{Colors.YELLOW}   ⚠️  Error refrescando token: {e}{Colors.NC}")
        print(f"{Colors.YELLOW}   Continuando con token actual...{Colors.NC}")
    print()

    # Crear directorio de logs
    log_dir = project_dir / "logs" / "sync_local"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Nombre del log con timestamp
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"sync_{timestamp}.log"

    print(f"{Colors.YELLOW}🚀 Iniciando sync en background...{Colors.NC}")
    print(f"📝 Log: {log_file}")
    print()

    # Iniciar sync LOOP (cada 6 horas) en background
    sync_script = project_dir / "scripts" / "tools" / "sync_amazon_ml_LOOP.py"

    start_cmd = f"cd {project_dir} && nohup python3 {sync_script} > {log_file} 2>&1 &"

    try:
        subprocess.run(start_cmd, shell=True, timeout=5)
    except subprocess.TimeoutExpired:
        pass  # Es normal, el proceso corre en background

    # Esperar 2 segundos para que se inicie
    time.sleep(2)

    # Verificar si está corriendo
    check_cmd = "ps aux | grep 'sync_amazon_ml' | grep -v grep | grep -v '05_start'"
    verify = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

    if verify.returncode == 0 and verify.stdout.strip():
        # Obtener PID
        parts = verify.stdout.strip().split()
        pid = parts[1] if len(parts) > 1 else "?"

        print(f"{Colors.GREEN}✅ Sync iniciado exitosamente{Colors.NC}")
        print(f"   PID: {pid}")
        print()
        print(f"{Colors.BLUE}💡 Comandos útiles:{Colors.NC}")
        print(f"   • Ver logs en vivo:  python3 07_view_sync_live.py")
        print(f"   • Ver logs archivo:  python3 07_view_sync_logs.py")
        print(f"   • Detener sync:      python3 06_stop_sync_amzn_meli.py")
        print()
    else:
        print(f"{Colors.RED}❌ Error al iniciar sync{Colors.NC}")
        print(f"   Verifica el archivo de log: {log_file}")
        print()
        sys.exit(1)

if __name__ == "__main__":
    main()
