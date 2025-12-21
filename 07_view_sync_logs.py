#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
07_view_sync_logs.py
═══════════════════════════════════════════════════════════════════════════════
VER LOGS DE SINCRONIZACIÓN LOCAL (MAC)
═══════════════════════════════════════════════════════════════════════════════

Muestra los logs guardados de sincronización en tu Mac local.

OPCIONES:
    -n NUM          Mostrar últimas NUM líneas del log más reciente (default: 50)
    --all           Mostrar todo el archivo del log más reciente
    --results       Mostrar últimos resultados JSON de sincronización
    --list          Listar todos los archivos de logs disponibles

USO:
    python3 07_view_sync_logs.py              # Últimas 50 líneas del log más reciente
    python3 07_view_sync_logs.py -n 100       # Últimas 100 líneas
    python3 07_view_sync_logs.py --all        # Todo el log más reciente
    python3 07_view_sync_logs.py --results    # Ver últimos resultados JSON
    python3 07_view_sync_logs.py --list       # Listar todos los logs disponibles

    Para ver logs en TIEMPO REAL usa: 07_view_sync_live.py
"""

import sys
import subprocess
import argparse
from pathlib import Path
import json
from datetime import datetime

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

def check_sync_status():
    """Verifica si el sync está corriendo localmente"""
    check_cmd = "ps aux | grep 'sync_amazon_ml' | grep -v grep | grep -v '07_view'"
    result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0 and result.stdout.strip():
        parts = result.stdout.strip().split('\n')[0].split()
        pid = parts[1] if len(parts) > 1 else "?"
        return pid
    return None

def show_latest_results(log_dir):
    """Muestra los últimos resultados JSON de sincronización local"""
    results_path = log_dir / "sync"

    if not results_path.exists():
        print(f"{Colors.YELLOW}⚠️  No se encontró el directorio de resultados: {results_path}{Colors.NC}")
        return

    # Listar archivos sync_*.json ordenados por fecha
    json_files = sorted(results_path.glob("sync_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)

    if not json_files:
        print(f"{Colors.YELLOW}⚠️  No se encontraron archivos de resultados{Colors.NC}")
        return

    print(f"{Colors.BLUE}📊 ÚLTIMOS RESULTADOS DE SINCRONIZACIÓN (LOCAL){Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 80}{Colors.NC}")
    print()

    # Mostrar los últimos 5 resultados
    for i, file_path in enumerate(json_files[:5], 1):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            timestamp = data.get("timestamp", "Desconocido")
            stats = data.get("statistics", {})

            print(f"{Colors.CYAN}{i}. {file_path.name}{Colors.NC}")
            print(f"   Fecha: {timestamp}")
            print(f"   Total procesados:      {stats.get('total', 0)}")
            print(f"   {Colors.YELLOW}Pausados:              {stats.get('paused', 0)}{Colors.NC}")
            print(f"   {Colors.GREEN}Precios actualizados:  {stats.get('price_updated', 0)}{Colors.NC}")
            print(f"   Sin cambios:           {stats.get('no_change', 0)}")
            print(f"   {Colors.RED}Errores:               {stats.get('errors', 0)}{Colors.NC}")
            print()
        except Exception as e:
            print(f"   {Colors.RED}❌ Error leyendo {file_path.name}: {e}{Colors.NC}")
            print()

    print(f"{Colors.YELLOW}💡 Archivos completos en: {results_path}{Colors.NC}")

def list_all_logs(log_dir):
    """Lista todos los archivos de logs disponibles"""
    log_files = sorted(log_dir.glob("sync_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)

    if not log_files:
        print(f"{Colors.YELLOW}⚠️  No se encontraron archivos de logs{Colors.NC}")
        return

    print(f"{Colors.BLUE}📋 ARCHIVOS DE LOGS DISPONIBLES{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 80}{Colors.NC}")
    print()

    for i, log_file in enumerate(log_files, 1):
        # Obtener info del archivo
        stat = log_file.stat()
        size = stat.st_size
        size_kb = size / 1024
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

        # Contar líneas
        try:
            result = subprocess.run(f"wc -l {log_file}", shell=True, capture_output=True, text=True)
            lines = result.stdout.strip().split()[0] if result.returncode == 0 else "?"
        except:
            lines = "?"

        print(f"{Colors.CYAN}{i}. {log_file.name}{Colors.NC}")
        print(f"   Fecha: {mtime}")
        print(f"   Tamaño: {size_kb:.1f} KB")
        print(f"   Líneas: {lines}")
        print()

def main():
    parser = argparse.ArgumentParser(
        description="Ver logs de sincronización local (Mac)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-n', '--lines', type=int, default=50,
                        help='Número de líneas a mostrar (default: 50)')
    parser.add_argument('--all', action='store_true',
                        help='Mostrar todo el archivo')
    parser.add_argument('--results', action='store_true',
                        help='Mostrar últimos resultados JSON')
    parser.add_argument('--list', action='store_true',
                        help='Listar todos los archivos de logs')

    args = parser.parse_args()

    project_dir = Path(__file__).parent
    log_dir = project_dir / "logs" / "sync_local"

    print()
    print(f"{Colors.BLUE}╔════════════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║       LOGS DE SINCRONIZACIÓN LOCAL - ARCHIVO COMPLETO        ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.NC}")
    print()
    print(f"💻 Modo: LOCAL")
    print(f"📂 Directorio de logs: {log_dir}")
    print()

    # Verificar estado del sync
    pid = check_sync_status()
    if pid:
        print(f"{Colors.GREEN}✅ Sync corriendo (PID: {pid}){Colors.NC}")
    else:
        print(f"{Colors.YELLOW}⚠️  Sync no está corriendo{Colors.NC}")

    print()

    # Crear directorio de logs si no existe
    log_dir.mkdir(parents=True, exist_ok=True)

    # Mostrar resultados JSON
    if args.results:
        show_latest_results(project_dir / "logs")
        return

    # Listar todos los logs
    if args.list:
        list_all_logs(log_dir)
        return

    # Buscar el log más reciente
    log_files = sorted(log_dir.glob("sync_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)

    if not log_files:
        print(f"{Colors.YELLOW}⚠️  No se encontraron archivos de log{Colors.NC}")
        print(f"{Colors.YELLOW}   Inicia el sync con: python3 05_start_sync_amzn_meli.py{Colors.NC}")
        print()
        return

    log_file = log_files[0]
    print(f"{Colors.CYAN}📝 Log más reciente: {log_file.name}{Colors.NC}")
    print()

    # Mostrar info del archivo
    stat = log_file.stat()
    size_kb = stat.st_size / 1024
    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

    result = subprocess.run(f"wc -l {log_file}", shell=True, capture_output=True, text=True)
    total_lines = result.stdout.strip().split()[0] if result.returncode == 0 else "?"

    print(f"{Colors.CYAN}📏 Total líneas: {total_lines}{Colors.NC}")
    print(f"{Colors.CYAN}📊 Tamaño: {size_kb:.1f} KB{Colors.NC}")
    print(f"{Colors.CYAN}🕒 Última modificación: {mtime}{Colors.NC}")
    print()

    # Mostrar todo el archivo
    if args.all:
        print(f"{Colors.CYAN}📄 Mostrando todo el archivo:{Colors.NC}")
        print()
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                print(f.read())
        except Exception as e:
            print(f"{Colors.RED}❌ Error leyendo archivo: {e}{Colors.NC}")
        return

    # Mostrar últimas N líneas
    num_lines = args.lines
    print(f"{Colors.CYAN}📄 Mostrando últimas {num_lines} líneas:{Colors.NC}")
    print()

    result = subprocess.run(f"tail -n {num_lines} {log_file}", shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"{Colors.RED}❌ Error leyendo archivo{Colors.NC}")

    print()
    print(f"{Colors.YELLOW}💡 Tip: usa 07_view_sync_live.py para seguir en tiempo real{Colors.NC}")
    print(f"{Colors.YELLOW}💡 Tip: usa --results para ver resultados de sincronización{Colors.NC}")
    print(f"{Colors.YELLOW}💡 Tip: usa --list para ver todos los logs disponibles{Colors.NC}")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Cancelado por usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}❌ Error: {e}{Colors.NC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
