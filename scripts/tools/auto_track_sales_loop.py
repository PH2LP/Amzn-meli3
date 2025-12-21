#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_track_sales_loop.py
═══════════════════════════════════════════════════════════════════════════════
DAEMON DE TRACKING DE VENTAS
═══════════════════════════════════════════════════════════════════════════════

Monitorea ventas de MercadoLibre cada N horas automáticamente.

USO:
    python3 scripts/tools/auto_track_sales_loop.py      # Ejecutar daemon

    En servidor:
    nohup python3 scripts/tools/auto_track_sales_loop.py > logs/sales_tracking.log 2>&1 &
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import signal
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.tools.track_sales import track_new_sales, init_database

# Configuración
CHECK_INTERVAL_HOURS = float(os.getenv("SALES_TRACKING_INTERVAL_HOURS", "1"))  # Cada 1 hora
LOOP_ACTIVE = True

# Colores
class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'


def signal_handler(sig, frame):
    """Maneja señales de terminación"""
    global LOOP_ACTIVE
    print(f"\n\n{Colors.YELLOW}🛑 Daemon detenido (señal recibida){Colors.NC}", flush=True)
    LOOP_ACTIVE = False
    sys.exit(0)


def main():
    global LOOP_ACTIVE

    # Configurar handler de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"{Colors.BLUE}╔════════════════════════════════════════════════════════════════╗{Colors.NC}", flush=True)
    print(f"{Colors.BLUE}║         DAEMON DE TRACKING DE VENTAS - MERCADOLIBRE          ║{Colors.NC}", flush=True)
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.NC}", flush=True)
    print(f"{Colors.CYAN}⏱️  Intervalo: {CHECK_INTERVAL_HOURS} hora(s){Colors.NC}", flush=True)
    print(f"{Colors.CYAN}💡 Para detener: Ctrl+C o kill -TERM <PID>{Colors.NC}", flush=True)
    print(f"{Colors.BLUE}{'═' * 80}{Colors.NC}\n", flush=True)

    # Inicializar DB
    init_database()

    iteration = 0

    while LOOP_ACTIVE:
        iteration += 1

        print(f"{Colors.BLUE}{'═' * 80}{Colors.NC}", flush=True)
        print(f"{Colors.BLUE}ITERACIÓN {iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.NC}", flush=True)
        print(f"{Colors.BLUE}{'═' * 80}{Colors.NC}\n", flush=True)

        try:
            # Trackear ventas
            track_new_sales()

            # Generar Excel en Desktop automáticamente
            print(f"\n{Colors.CYAN}📊 Generando Excel en Desktop...{Colors.NC}", flush=True)
            try:
                import subprocess
                result = subprocess.run(
                    ["python3", "scripts/tools/generate_excel_desktop.py"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    print(f"{Colors.GREEN}   ✅ Excel actualizado en Desktop{Colors.NC}", flush=True)
                else:
                    print(f"{Colors.YELLOW}   ⚠️  Error generando Excel{Colors.NC}", flush=True)
            except Exception as e:
                print(f"{Colors.YELLOW}   ⚠️  No se pudo generar Excel: {e}{Colors.NC}", flush=True)

            # Calcular próxima ejecución
            next_run = datetime.now().replace(microsecond=0)
            next_run = next_run.replace(second=0, minute=0)

            # Redondear a la siguiente hora
            next_run = next_run.replace(hour=next_run.hour + int(CHECK_INTERVAL_HOURS))

            print(f"\n{Colors.GREEN}✅ Tracking completado{Colors.NC}", flush=True)
            print(f"{Colors.CYAN}⏰ Próxima revisión: {next_run.strftime('%Y-%m-%d %H:%M')}{Colors.NC}", flush=True)
            print(f"{Colors.YELLOW}💤 Durmiendo por {CHECK_INTERVAL_HOURS} hora(s)...{Colors.NC}\n", flush=True)

            # Dormir
            time.sleep(CHECK_INTERVAL_HOURS * 3600)

        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}🛑 Detenido por usuario{Colors.NC}", flush=True)
            break

        except Exception as e:
            print(f"\n{Colors.RED}❌ Error en iteración {iteration}: {e}{Colors.NC}", flush=True)
            import traceback
            traceback.print_exc()

            # Esperar 5 minutos antes de reintentar
            print(f"{Colors.YELLOW}⏳ Reintentando en 5 minutos...{Colors.NC}\n", flush=True)
            time.sleep(300)


if __name__ == "__main__":
    main()
