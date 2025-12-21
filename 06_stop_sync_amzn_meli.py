#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06_stop_sync_amzn_meli.py
═══════════════════════════════════════════════════════════════════════════════
DETENER SYNC LOCAL (MAC)
═══════════════════════════════════════════════════════════════════════════════

Detiene la sincronización Amazon → MercadoLibre en tu Mac local

USO:
    python3 06_stop_sync_amzn_meli.py
═══════════════════════════════════════════════════════════════════════════════
"""

import subprocess
import sys
import time

# Colores
class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def main():
    print()
    print(f"{Colors.BLUE}╔════════════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║            DETENER SINCRONIZACIÓN LOCAL (MAC)                ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.NC}")
    print()

    # Buscar procesos de sync
    check_cmd = "ps aux | grep 'sync_amazon_ml' | grep -v grep | grep -v '06_stop'"
    result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0 or not result.stdout.strip():
        print(f"{Colors.GREEN}✅ No hay sync corriendo{Colors.NC}")
        print()
        return

    # Mostrar procesos encontrados
    print(f"{Colors.YELLOW}📦 Procesos de sync encontrados:{Colors.NC}")
    print()

    pids = []
    for line in result.stdout.strip().split('\n'):
        parts = line.split()
        if len(parts) > 1:
            pid = parts[1]
            pids.append(pid)
            cmd = ' '.join(parts[10:])[:60] if len(parts) > 10 else ""
            print(f"   PID: {pid} - {cmd}")

    print()
    print(f"{Colors.YELLOW}🛑 Deteniendo procesos...{Colors.NC}")

    # Detener cada proceso
    for pid in pids:
        try:
            subprocess.run(f"kill {pid}", shell=True, timeout=5)
            print(f"   ✅ Proceso {pid} detenido")
        except Exception as e:
            print(f"   ⚠️  Error deteniendo {pid}: {e}")

    # Esperar 2 segundos
    time.sleep(2)

    # Verificar que se detuvieron
    check_cmd = "ps aux | grep 'sync_amazon_ml' | grep -v grep | grep -v '06_stop'"
    verify = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

    if verify.returncode != 0 or not verify.stdout.strip():
        print()
        print(f"{Colors.GREEN}✅ Sync detenido exitosamente{Colors.NC}")
        print()
    else:
        print()
        print(f"{Colors.YELLOW}⚠️  Algunos procesos aún están corriendo. Forzando...{Colors.NC}")

        for pid in pids:
            try:
                subprocess.run(f"kill -9 {pid}", shell=True, timeout=5)
            except:
                pass

        time.sleep(1)
        print(f"{Colors.GREEN}✅ Procesos forzados a detenerse{Colors.NC}")
        print()

if __name__ == "__main__":
    main()
