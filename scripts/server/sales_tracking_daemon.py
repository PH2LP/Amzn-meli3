#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sales_tracking_daemon.py
═══════════════════════════════════════════════════════════════════════════════
DAEMON DE TRACKING DE VENTAS - PARA SERVIDOR
═══════════════════════════════════════════════════════════════════════════════

Ejecuta automáticamente cada hora:
1. Track de nuevas ventas en MercadoLibre
2. Genera Excel profesional con Dashboard
3. Sube Excel a Dropbox
4. Sube DB de ventas a Dropbox
5. Sube DB de productos a Dropbox

USO:
    # En servidor
    nohup python3 scripts/server/sales_tracking_daemon.py > logs/sales_daemon.log 2>&1 &

    # Localmente (testing)
    python3 scripts/server/sales_tracking_daemon.py
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import signal
import sqlite3
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(override=True)

# Configuración
CHECK_INTERVAL_HOURS = float(os.getenv("SALES_TRACKING_INTERVAL_HOURS", "1"))
DB_SALES_PATH = "storage/sales_tracking.db"
DB_LISTINGS_PATH = "storage/listings_database.db"
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


def track_sales():
    """
    Ejecuta el tracking de ventas

    Returns:
        bool: True si se ejecutó correctamente
    """
    print(f"\n{Colors.CYAN}📊 PASO 1: Tracking de ventas...{Colors.NC}", flush=True)

    try:
        from scripts.tools.track_sales import track_new_sales, init_database

        # Inicializar DB si no existe
        if not os.path.exists(DB_SALES_PATH):
            init_database()

        # Trackear ventas
        track_new_sales()

        print(f"{Colors.GREEN}   ✅ Tracking completado{Colors.NC}", flush=True)
        return True

    except Exception as e:
        print(f"{Colors.RED}   ❌ Error en tracking: {e}{Colors.NC}", flush=True)
        import traceback
        traceback.print_exc()
        return False


def generate_excel():
    """
    Genera Excel profesional con Dashboard

    Returns:
        str: Path del Excel generado o None
    """
    print(f"\n{Colors.CYAN}📈 PASO 2: Generando Excel profesional...{Colors.NC}", flush=True)

    try:
        from scripts.tools.generate_excel_desktop import create_professional_excel

        excel_path = create_professional_excel()

        print(f"{Colors.GREEN}   ✅ Excel generado: {excel_path}{Colors.NC}", flush=True)
        return excel_path

    except Exception as e:
        print(f"{Colors.RED}   ❌ Error generando Excel: {e}{Colors.NC}", flush=True)
        import traceback
        traceback.print_exc()
        return None


def upload_to_dropbox(local_path, dropbox_path):
    """
    Sube archivo a Dropbox

    Args:
        local_path: Ruta local del archivo
        dropbox_path: Ruta en Dropbox (debe empezar con /)

    Returns:
        bool: True si se subió correctamente
    """
    try:
        import dropbox

        access_token = os.getenv("DROPBOX_ACCESS_TOKEN")
        if not access_token:
            print(f"{Colors.YELLOW}   ⚠️  DROPBOX_ACCESS_TOKEN no configurado{Colors.NC}", flush=True)
            return False

        if not os.path.exists(local_path):
            print(f"{Colors.RED}   ❌ Archivo no existe: {local_path}{Colors.NC}", flush=True)
            return False

        # Conectar a Dropbox
        dbx = dropbox.Dropbox(access_token)

        # Leer archivo
        with open(local_path, 'rb') as f:
            file_data = f.read()

        # Subir (sobrescribir si existe)
        dbx.files_upload(
            file_data,
            dropbox_path,
            mode=dropbox.files.WriteMode.overwrite
        )

        file_size_kb = len(file_data) / 1024
        print(f"{Colors.GREEN}   ✅ Subido: {dropbox_path} ({file_size_kb:.1f} KB){Colors.NC}", flush=True)
        return True

    except ImportError:
        print(f"{Colors.YELLOW}   ⚠️  dropbox no instalado (pip install dropbox){Colors.NC}", flush=True)
        return False
    except Exception as e:
        print(f"{Colors.RED}   ❌ Error subiendo a Dropbox: {e}{Colors.NC}", flush=True)
        return False


def sync_to_dropbox(excel_path):
    """
    Sube Excel y DBs a Dropbox

    Args:
        excel_path: Path del Excel generado

    Returns:
        int: Cantidad de archivos subidos
    """
    print(f"\n{Colors.CYAN}☁️  PASO 3: Sincronizando a Dropbox...{Colors.NC}", flush=True)

    uploaded = 0

    # 1. Excel de ventas
    if excel_path and os.path.exists(excel_path):
        print(f"   📤 Subiendo Excel de ventas...", flush=True)
        if upload_to_dropbox(excel_path, "/VENTAS_MERCADOLIBRE.xlsx"):
            uploaded += 1

    # 2. DB de ventas
    if os.path.exists(DB_SALES_PATH):
        print(f"   📤 Subiendo DB de ventas...", flush=True)
        if upload_to_dropbox(DB_SALES_PATH, "/sales_tracking.db"):
            uploaded += 1

    # 3. DB de productos (listings)
    if os.path.exists(DB_LISTINGS_PATH):
        print(f"   📤 Subiendo DB de productos...", flush=True)
        if upload_to_dropbox(DB_LISTINGS_PATH, "/listings_database.db"):
            uploaded += 1

    print(f"\n{Colors.GREEN}   ✅ {uploaded} archivo(s) sincronizado(s) a Dropbox{Colors.NC}", flush=True)
    return uploaded


def show_stats():
    """Muestra estadísticas rápidas de ventas"""
    try:
        if not os.path.exists(DB_SALES_PATH):
            return

        conn = sqlite3.connect(DB_SALES_PATH)
        cursor = conn.cursor()

        # Stats básicas
        cursor.execute("""
            SELECT
                COUNT(*) as total_sales,
                SUM(profit) as total_profit,
                AVG(profit_margin) as avg_margin
            FROM sales
        """)

        row = cursor.fetchone()
        conn.close()

        if row and row[0] > 0:
            print(f"\n{Colors.BLUE}{'─' * 80}{Colors.NC}", flush=True)
            print(f"{Colors.CYAN}   📊 ESTADÍSTICAS:{Colors.NC}", flush=True)
            print(f"      Total ventas:      {row[0]}", flush=True)
            print(f"      Ganancia total:    ${row[1]:.2f}", flush=True)
            print(f"      Margen promedio:   {row[2]:.1f}%", flush=True)
            print(f"{Colors.BLUE}{'─' * 80}{Colors.NC}", flush=True)

    except Exception as e:
        pass  # Silent fail


def main():
    """Loop principal del daemon"""
    global LOOP_ACTIVE

    # Configurar handler de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"{Colors.BLUE}╔════════════════════════════════════════════════════════════════╗{Colors.NC}", flush=True)
    print(f"{Colors.BLUE}║      SALES TRACKING DAEMON - AMAZON → MERCADOLIBRE           ║{Colors.NC}", flush=True)
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.NC}", flush=True)
    print(f"{Colors.CYAN}⏱️  Intervalo: {CHECK_INTERVAL_HOURS} hora(s){Colors.NC}", flush=True)
    print(f"{Colors.CYAN}💾 DBs: ventas + productos{Colors.NC}", flush=True)
    print(f"{Colors.CYAN}☁️  Dropbox: Excel + DBs{Colors.NC}", flush=True)
    print(f"{Colors.CYAN}💡 Detener: Ctrl+C o kill -TERM <PID>{Colors.NC}", flush=True)
    print(f"{Colors.BLUE}{'═' * 80}{Colors.NC}\n", flush=True)

    iteration = 0

    while LOOP_ACTIVE:
        iteration += 1

        print(f"\n{Colors.BLUE}{'═' * 80}{Colors.NC}", flush=True)
        print(f"{Colors.BLUE}ITERACIÓN #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.NC}", flush=True)
        print(f"{Colors.BLUE}{'═' * 80}{Colors.NC}", flush=True)

        try:
            # PASO 1: Track sales
            track_sales()

            # PASO 2: Generar Excel
            excel_path = generate_excel()

            # PASO 3: Subir a Dropbox
            sync_to_dropbox(excel_path)

            # Mostrar stats
            show_stats()

            # Calcular próxima ejecución
            next_run = datetime.now()
            hours_to_add = int(CHECK_INTERVAL_HOURS)
            next_run = next_run.replace(
                hour=(next_run.hour + hours_to_add) % 24,
                minute=0,
                second=0,
                microsecond=0
            )

            print(f"\n{Colors.GREEN}✅ Ciclo completado exitosamente{Colors.NC}", flush=True)
            print(f"{Colors.CYAN}⏰ Próxima ejecución: {next_run.strftime('%Y-%m-%d %H:%M')}{Colors.NC}", flush=True)
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
