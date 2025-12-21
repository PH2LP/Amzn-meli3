#!/usr/bin/env python3
"""
view_sync_logs.py
═══════════════════════════════════════════════════════════════════════════════
VER LOGS DE SINCRONIZACIÓN AMAZON → MERCADOLIBRE
═══════════════════════════════════════════════════════════════════════════════

Muestra los logs del daemon de sincronización automática.

OPCIONES:
    -f, --follow    Seguir el archivo en tiempo real (como tail -f)
    -n NUM          Mostrar últimas NUM líneas (default: 50)
    --all           Mostrar todo el archivo
    --results       Mostrar últimos resultados JSON de sincronización

USO:
    python3 view_sync_logs.py              # Últimas 50 líneas
    python3 view_sync_logs.py -n 100       # Últimas 100 líneas
    python3 view_sync_logs.py --all        # Todo el archivo
    python3 view_sync_logs.py -f           # Seguir en tiempo real
    python3 view_sync_logs.py --results    # Ver últimos resultados JSON
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from datetime import datetime

# Configuración
LOG_FILE = Path("logs/sync/sync_loop.log")
RESULTS_DIR = Path("logs/sync")
PID_FILE = Path("storage/sync_loop.pid")

# Colores para consola
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    MAGENTA = '\033[0;35m'
    NC = '\033[0m'

def log(message, color=Colors.NC):
    print(f"{color}{message}{Colors.NC}")

def colorize_line(line):
    """Aplica colores a las líneas del log"""
    if "✅" in line or "completada exitosamente" in line or "Sincronización completada" in line:
        return f"{Colors.GREEN}{line}{Colors.NC}"
    elif "❌" in line or "Error" in line or "falló" in line or "STDERR:" in line:
        return f"{Colors.RED}{line}{Colors.NC}"
    elif "⚠️" in line or "Warning" in line or "Timeout" in line:
        return f"{Colors.YELLOW}{line}{Colors.NC}"
    elif "🔄" in line or "Iniciando sincronización" in line or "Sincronizando:" in line:
        return f"{Colors.CYAN}{line}{Colors.NC}"
    elif "═══" in line or "ITERACIÓN" in line or "RESUMEN" in line:
        return f"{Colors.BLUE}{line}{Colors.NC}"
    elif "💰" in line or "Precio" in line:
        return f"{Colors.MAGENTA}{line}{Colors.NC}"
    return line

def check_daemon_status():
    """Verifica si el daemon está corriendo"""
    if not PID_FILE.exists():
        return None

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)  # Verifica existencia
        return pid
    except (OSError, ValueError):
        return None

def tail_file(file_path, num_lines):
    """Muestra las últimas N líneas de un archivo"""
    if not file_path.exists():
        return []

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    return lines[-num_lines:] if len(lines) > num_lines else lines

def follow_file(file_path):
    """Sigue un archivo en tiempo real (como tail -f)"""
    if not file_path.exists():
        log("⏳ Esperando a que se cree el archivo de log...", Colors.YELLOW)
        while not file_path.exists():
            time.sleep(1)

    with open(file_path, 'r', encoding='utf-8') as f:
        # Ir al final del archivo
        f.seek(0, 2)

        log("👀 Siguiendo logs en tiempo real (Ctrl+C para salir)...", Colors.CYAN)
        print()

        while True:
            line = f.readline()
            if line:
                print(colorize_line(line.rstrip()))
            else:
                time.sleep(0.1)

def show_latest_results():
    """Muestra los últimos resultados JSON de sincronización"""
    if not RESULTS_DIR.exists():
        log("❌ Directorio de resultados no existe", Colors.RED)
        return

    # Buscar archivos sync_*.json
    json_files = sorted(RESULTS_DIR.glob("sync_*.json"), reverse=True)

    if not json_files:
        log("⚠️ No se encontraron archivos de resultados", Colors.YELLOW)
        return

    # Mostrar los 5 más recientes
    log("📊 ÚLTIMOS RESULTADOS DE SINCRONIZACIÓN", Colors.BLUE)
    log("═" * 80, Colors.BLUE)
    print()

    for i, json_file in enumerate(json_files[:5], 1):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            timestamp = data.get("timestamp", "Desconocido")
            stats = data.get("statistics", {})

            log(f"{i}. {json_file.name}", Colors.CYAN)
            log(f"   Fecha: {timestamp}", Colors.NC)
            log(f"   Total procesados:      {stats.get('total', 0)}", Colors.NC)
            log(f"   Pausados:              {stats.get('paused', 0)}", Colors.YELLOW)
            log(f"   Precios actualizados:  {stats.get('price_updated', 0)}", Colors.GREEN)
            log(f"   Sin cambios:           {stats.get('no_change', 0)}", Colors.NC)
            log(f"   Errores:               {stats.get('errors', 0)}", Colors.RED)
            print()

        except Exception as e:
            log(f"   ❌ Error leyendo archivo: {e}", Colors.RED)

    log(f"💡 Archivos completos en: {RESULTS_DIR}", Colors.YELLOW)

def main():
    parser = argparse.ArgumentParser(
        description="Ver logs de sincronización Amazon → MercadoLibre",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-f', '--follow', action='store_true',
                        help='Seguir el archivo en tiempo real')
    parser.add_argument('-n', '--lines', type=int, default=50,
                        help='Número de líneas a mostrar (default: 50)')
    parser.add_argument('--all', action='store_true',
                        help='Mostrar todo el archivo')
    parser.add_argument('--results', action='store_true',
                        help='Mostrar últimos resultados JSON')

    args = parser.parse_args()

    print()
    log("╔════════════════════════════════════════════════════════════════╗", Colors.BLUE)
    log("║         LOGS DE SINCRONIZACIÓN AMAZON → MERCADOLIBRE          ║", Colors.BLUE)
    log("╚════════════════════════════════════════════════════════════════╝", Colors.BLUE)
    print()

    # Verificar estado del daemon
    pid = check_daemon_status()
    if pid:
        log(f"✅ Daemon corriendo (PID: {pid})", Colors.GREEN)
    else:
        log("⚠️  Daemon no está corriendo", Colors.YELLOW)

    print()

    # Mostrar resultados JSON
    if args.results:
        show_latest_results()
        return

    log(f"📝 Log: {LOG_FILE}", Colors.CYAN)
    print()

    # Verificar si existe el archivo
    if not LOG_FILE.exists():
        log("❌ Archivo de log no existe", Colors.RED)
        log("   El daemon aún no se ha ejecutado", Colors.YELLOW)
        return

    # Mostrar info del archivo
    file_size = LOG_FILE.stat().st_size
    file_size_str = f"{file_size / 1024:.2f} KB" if file_size > 1024 else f"{file_size} bytes"
    log(f"📊 Tamaño: {file_size_str}", Colors.CYAN)

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        total_lines = sum(1 for _ in f)
    log(f"📏 Total líneas: {total_lines}", Colors.CYAN)
    print()

    # Seguir en tiempo real
    if args.follow:
        try:
            follow_file(LOG_FILE)
        except KeyboardInterrupt:
            print("\n")
            log("👋 Dejando de seguir el archivo", Colors.YELLOW)
            return

    # Mostrar todo el archivo
    if args.all:
        log("📄 Mostrando todo el archivo:", Colors.CYAN)
        print()
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                print(colorize_line(line.rstrip()))
        return

    # Mostrar últimas N líneas
    num_lines = args.lines
    log(f"📄 Mostrando últimas {num_lines} líneas:", Colors.CYAN)
    print()

    lines = tail_file(LOG_FILE, num_lines)
    for line in lines:
        print(colorize_line(line.rstrip()))

    print()
    log(f"💡 Tip: usa -f para seguir en tiempo real, --results para ver resultados", Colors.YELLOW)
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Cancelado por usuario")
        sys.exit(0)
    except Exception as e:
        log(f"\n❌ Error: {e}", Colors.RED)
        import traceback
        traceback.print_exc()
        sys.exit(1)
