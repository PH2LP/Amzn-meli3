#!/usr/bin/env python3
"""
41_run_full_sync_once.py

Script para ejecutar el SYNC COMPLETO (Amazon → MercadoLibre) UNA SOLA VEZ
y ver el progreso en tiempo real.

Este sync COMPLETO hace:
- ✅ Obtiene precio y delivery de Amazon (usando V2 Advanced anti-detección)
- ✅ Actualiza precios en MercadoLibre
- ✅ Pausa/reactiva listings según disponibilidad
- ✅ Envía notificaciones por Telegram
- ✅ Guarda logs de todos los cambios

USO:
    python3 41_run_full_sync_once.py
"""

import subprocess
import sys
from datetime import datetime

def main():
    print("=" * 80)
    print("🚀 EJECUTANDO SYNC COMPLETO AMAZON → MERCADOLIBRE (V2 ADVANCED)")
    print("=" * 80)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("Features del sistema V2 Advanced:")
    print("  ✅ Session Rotation (nueva sesión cada 100 requests)")
    print("  ✅ Exponential Backoff con Jitter")
    print("  ✅ Rate Limiting Inteligente (~0.5 req/sec)")
    print("  ✅ User-Agent Rotation")
    print("  ✅ Actualización automática de precios en ML")
    print("  ✅ Pausa/reactiva listings según disponibilidad")
    print("  ✅ Notificaciones Telegram")
    print()
    print("⚠️  Presioná Ctrl+C para detener el sync en cualquier momento")
    print()
    print("=" * 80)
    print()

    # Ejecutar el sync mostrando todo el output en tiempo real
    try:
        result = subprocess.run(
            [sys.executable, "scripts/tools/sync_amazon_ml_GLOW.py"],
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
