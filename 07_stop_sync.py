#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 07_stop_sync.py - DETENER SYNC LOOP
# ═══════════════════════════════════════════════════════════════════════════════
# 
# ¿Qué hace?
#   Detiene el proceso de sync loop si está corriendo en background.
# 
# Comando:
#   python3 07_stop_sync.py
# 
# ═══════════════════════════════════════════════════════════════════════════════
import subprocess
import sys
import time

def main():
    print("=" * 80)
    print("🛑 DETENIENDO SYNC LOOP")
    print("=" * 80)
    print()

    # 1. Matar procesos de sync (loop Y sync)
    print("1️⃣  Matando procesos de sync...")

    # Matar el loop principal
    result1 = subprocess.run(["pkill", "-f", "29_run_full_sync_loop.py"], stderr=subprocess.DEVNULL)

    # Matar cualquier sync en progreso
    result2 = subprocess.run(["pkill", "-f", "sync_amazon_ml_GLOW.py"], stderr=subprocess.DEVNULL)

    time.sleep(2)
    print("   ✅ Comandos de kill enviados")
    print()

    # 2. Verificar que estén detenidos
    print("2️⃣  Verificando procesos...")
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True,
        text=True
    )

    sync_running = False
    for line in result.stdout.split('\n'):
        if ("29_run_full_sync_loop.py" in line or "sync_amazon_ml_GLOW.py" in line) and "grep" not in line:
            print(f"   ⚠️  Todavía corriendo: {line.split()[1]}")
            sync_running = True

    if not sync_running:
        print("   ✅ No hay procesos de sync corriendo")

    print()
    print("=" * 80)
    print("✅ SYNC DETENIDO")
    print("=" * 80)

if __name__ == "__main__":
    main()
