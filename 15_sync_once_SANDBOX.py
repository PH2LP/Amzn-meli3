#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 15_sync_once_SANDBOX.py - SYNC CON VERSIÓN SANDBOX (FALLBACK DE VARIANTES)
# ═══════════════════════════════════════════════════════════════════════════════
#
# ¿Qué hace?
#   Ejecuta sincronización completa UNA VEZ usando VERSIÓN SANDBOX de Glow API:
#   - Usa amazon_glow_api_v2_advanced_SANDBOX.py
#   - Incluye FALLBACK de variantes (detecta productos con Size/Color)
#   - Detección mejorada de bloqueos de Amazon
#   - Valida delivery con Glow API
#   - Actualiza precios en MercadoLibre
#   - Pausa/reactiva listings según disponibilidad
#   - Envía notificaciones por Telegram
#
# DIFERENCIAS vs 05_sync_once.py:
#   ✅ Fallback de variantes: detecta productos con variantes y consulta ASIN específico
#   ✅ Mejor detección de bloqueos: detecta "automated access" de Amazon
#   ✅ Menos falsos "No disponible" en productos con variantes
#
# Comando:
#   python3 15_sync_once_SANDBOX.py
#
# ═══════════════════════════════════════════════════════════════════════════════
import subprocess
import sys
import os
from datetime import datetime

def main():
    print("=" * 80)
    print("🧪 SYNC SANDBOX - CON FALLBACK DE VARIANTES")
    print("=" * 80)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    print("📦 Usando versión SANDBOX de Glow API")
    print("   → amazon_glow_api_v2_advanced_SANDBOX.py")
    print()

    print("🆕 MEJORAS EN ESTA VERSIÓN:")
    print("  ✅ Fallback de variantes (productos con Size/Color)")
    print("  ✅ Detección mejorada de bloqueos de Amazon")
    print("  ✅ Menos productos marcados como 'No disponible' incorrectamente")
    print()

    print("Este sync hace:")
    print("  ✅ Valida delivery con Glow API (versión SANDBOX)")
    print("  ✅ Actualiza precios en MercadoLibre")
    print("  ✅ Pausa/reactiva listings")
    print("  ✅ Envía notificaciones Telegram")
    print()
    print("⚠️  Presioná Ctrl+C para detener el sync en cualquier momento")
    print()
    print("=" * 80)
    print()

    try:
        # Ejecutar el sync SANDBOX
        result = subprocess.run(
            [sys.executable, "scripts/tools/sync_amazon_ml_GLOW_SANDBOX.py"],
            stdout=None,
            stderr=None,
            text=True
        )

        print()
        print("=" * 80)
        if result.returncode == 0:
            print("✅ Sync SANDBOX completado exitosamente")
        else:
            print(f"❌ Sync terminó con código de error: {result.returncode}")
        print(f"Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

    except KeyboardInterrupt:
        print()
        print()
        print("=" * 80)
        print("⏹️  Sync SANDBOX detenido por el usuario (Ctrl+C)")
        print("=" * 80)

if __name__ == "__main__":
    main()
