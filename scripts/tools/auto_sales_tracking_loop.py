#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTO SALES TRACKING LOOP - DAEMON
==================================
Ejecuta tracking de ventas cada 1 hora y sube Excel a Dropbox.

Uso:
    python3 scripts/tools/auto_sales_tracking_loop.py
"""

import sys
import os
import time
import subprocess
from datetime import datetime

INTERVAL_HOURS = 1

def run_sales_tracking():
    """Ejecuta el tracking de ventas"""
    print("\n" + "="*80)
    print(f"🔄 EJECUTANDO TRACKING DE VENTAS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")

    try:
        result = subprocess.run(
            [sys.executable, "scripts/tools/track_sales.py"],
            timeout=300
        )

        if result.returncode == 0:
            print("\n✅ Tracking de ventas completado")
        else:
            print(f"\n⚠️  Tracking completado con código: {result.returncode}")

    except subprocess.TimeoutExpired:
        print("\n⚠️  Tracking timeout - continuando")
    except Exception as e:
        print(f"\n❌ Error en tracking: {e}")


def generate_and_upload_excel():
    """Genera Excel y lo sube a Dropbox"""
    print("\n" + "-"*80)
    print("📊 GENERANDO EXCEL Y SUBIENDO A DROPBOX")
    print("-"*80 + "\n")

    try:
        result = subprocess.run(
            [sys.executable, "scripts/tools/generate_excel_desktop.py"],
            timeout=120
        )

        if result.returncode == 0:
            print("\n✅ Excel generado y subido a Dropbox")
        else:
            print(f"\n⚠️  Excel con código: {result.returncode}")

    except Exception as e:
        print(f"\n❌ Error generando Excel: {e}")


def main():
    """Loop principal"""
    print("\n" + "╔" + "="*78 + "╗")
    print("║" + " "*25 + "SALES TRACKING DAEMON" + " "*32 + "║")
    print("╚" + "="*78 + "╝")
    print(f"\n⏱️  Intervalo: {INTERVAL_HOURS} hora(s)")
    print("💡 Para detener: Ctrl+C o kill -TERM <PID>")
    print("="*80 + "\n")

    iteration = 1

    while True:
        try:
            print("\n" + "="*80)
            print(f"ITERACIÓN {iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*80)

            # 1. Tracking de ventas
            run_sales_tracking()

            # 2. Generar Excel y subir a Dropbox
            generate_and_upload_excel()

            # Calcular próxima ejecución
            next_run = datetime.now()
            next_run = next_run.replace(
                hour=(next_run.hour + INTERVAL_HOURS) % 24,
                minute=0,
                second=0,
                microsecond=0
            )

            print("\n" + "="*80)
            print(f"✅ Ciclo completado")
            print(f"⏰ Próxima ejecución: {next_run.strftime('%Y-%m-%d %H:%M')}")
            print(f"💤 Durmiendo por {INTERVAL_HOURS} hora(s)...")
            print("="*80 + "\n")

            # Dormir
            time.sleep(INTERVAL_HOURS * 3600)
            iteration += 1

        except KeyboardInterrupt:
            print("\n\n🛑 Daemon detenido por el usuario")
            break
        except Exception as e:
            print(f"\n❌ Error inesperado: {e}")
            print("⏳ Esperando 5 minutos antes de reintentar...")
            time.sleep(300)


if __name__ == "__main__":
    main()
