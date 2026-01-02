#!/usr/bin/env python3
"""
25_run_sync_manual.py

Script simple para ejecutar el sync manualmente y ver el progreso en tiempo real.

USO:
    python3 25_run_sync_manual.py
"""

import subprocess
import sys
from datetime import datetime

def main():
    print("=" * 80)
    print("🚀 EJECUTANDO SYNC MANUAL")
    print("=" * 80)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("⚠️  Presioná Ctrl+C para detener el sync en cualquier momento")
    print()
    print("=" * 80)
    print()

    # Ejecutar el sync mostrando todo el output en tiempo real
    try:
        result = subprocess.run(
            [sys.executable, "-B", "scripts/tools/sync_amazon_ml_GLOW.py"],
            # No capturar output - mostrarlo directamente en la terminal
            stdout=None,
            stderr=None,
            text=True
        )

        print()
        print("=" * 80)
        if result.returncode == 0:
            print("✅ Sync completado exitosamente")
        else:
            print(f"❌ Sync terminó con código de error: {result.returncode}")
        print(f"Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

    except KeyboardInterrupt:
        print()
        print()
        print("=" * 80)
        print("⏹️  Sync detenido por el usuario (Ctrl+C)")
        print("=" * 80)
        sys.exit(0)

if __name__ == "__main__":
    main()
