#!/usr/bin/env python3
"""
python3 22_system_monitor.py
Sistema de monitoreo en tiempo real con colores dinámicos
Muestra: Temperatura, RAM/Pressure, Swap, Load Average, CPU Hogs, Scripts, Disco
"""

import psutil
import subprocess
import time
import sys
import os
from datetime import datetime

# Códigos de color ANSI
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    ORANGE = '\033[38;5;214m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    GRAY = '\033[90m'

def hide_cursor():
    """Oculta el cursor"""
    sys.stdout.write('\033[?25l')
    sys.stdout.flush()

def show_cursor():
    """Muestra el cursor"""
    sys.stdout.write('\033[?25h')
    sys.stdout.flush()

def move_cursor(row, col):
    """Mueve el cursor a una posición específica"""
    sys.stdout.write(f'\033[{row};{col}H')
    sys.stdout.flush()

def clear_screen():
    """Limpia la pantalla y mueve cursor al inicio"""
    sys.stdout.write('\033[2J\033[H')
    sys.stdout.flush()

def get_cpu_temperature():
    """Obtiene la temperatura de la CPU en macOS"""
    try:
        result = subprocess.run(['sysctl', '-n', 'machdep.xcpm.cpu_thermal_level'],
                              capture_output=True, text=True, timeout=1)
        if result.returncode == 0:
            level = int(result.stdout.strip())
            return 40 + (level * 0.55)
    except:
        pass

    try:
        result = subprocess.run(['osx-cpu-temp'], capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            temp = float(result.stdout.strip().replace('°C', ''))
            if temp > 0:
                return temp
    except:
        pass

    # Fallback: estimar por CPU usage
    cpu_percent = psutil.cpu_percent(interval=0.1)
    return 45 + (cpu_percent * 0.35)

def get_memory_pressure():
    """Calcula la presión de memoria real usando vm_stat de macOS"""
    try:
        # Obtener estadísticas de memoria de macOS
        result = subprocess.run(['vm_stat'], capture_output=True, text=True, timeout=2)
        if result.returncode != 0:
            # Fallback a psutil
            return psutil.virtual_memory().percent

        lines = result.stdout.strip().split('\n')
        stats = {}

        for line in lines[1:]:  # Skip header
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip().rstrip('.')
                try:
                    stats[key] = int(value)
                except ValueError:
                    continue

        # Obtener page size (típicamente 4096 bytes en macOS)
        page_size = 4096

        # Calcular presión de memoria
        pages_free = stats.get('Pages free', 0)
        pages_active = stats.get('Pages active', 0)
        pages_inactive = stats.get('Pages inactive', 0)
        pages_wired = stats.get('Pages wired down', 0)
        pages_compressed = stats.get('Pages occupied by compressor', 0)

        total_pages = pages_free + pages_active + pages_inactive + pages_wired + pages_compressed

        if total_pages == 0:
            return psutil.virtual_memory().percent

        # Cálculo de presión: páginas activas + wired + compressed / total
        pressure_pages = pages_active + pages_wired + pages_compressed
        pressure_percent = (pressure_pages / total_pages) * 100

        return pressure_percent

    except Exception:
        # Fallback a psutil si algo falla
        return psutil.virtual_memory().percent

def get_swap_usage():
    """Obtiene el uso de swap en porcentaje"""
    return psutil.swap_memory().percent

def get_load_average():
    """Obtiene el load average (1 min)"""
    load = os.getloadavg()[0]
    cpu_count = psutil.cpu_count()
    return (load / cpu_count) * 100

def get_cpu_hogs():
    """Obtiene los procesos que más CPU usan"""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            info = proc.info
            if info['cpu_percent'] and info['cpu_percent'] > 5:
                processes.append({
                    'name': info['name'][:20],
                    'cpu': info['cpu_percent']
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    processes.sort(key=lambda x: x['cpu'], reverse=True)
    return processes[:3]

def count_python_scripts():
    """Cuenta los scripts Python en ejecución"""
    count = 0
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if proc.info['name'] in ['python', 'python3', 'Python']:
                count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return count

def get_disk_usage():
    """Obtiene el uso de disco del directorio actual"""
    return psutil.disk_usage('/').percent

def get_color(value, thresholds):
    """Retorna el color según el valor y los umbrales"""
    if value <= thresholds[0]:
        return Colors.GREEN
    elif value <= thresholds[1]:
        return Colors.YELLOW
    elif value <= thresholds[2]:
        return Colors.ORANGE
    else:
        return Colors.RED

def get_range_text(thresholds):
    """Retorna el texto de rangos para mostrar"""
    return (f"{Colors.GRAY}[{Colors.GREEN}0-{thresholds[0]}{Colors.GRAY} bajo | "
            f"{Colors.YELLOW}{thresholds[0]+1}-{thresholds[1]}{Colors.GRAY} medio | "
            f"{Colors.ORANGE}{thresholds[1]+1}-{thresholds[2]}{Colors.GRAY} medio-alto | "
            f"{Colors.RED}{thresholds[2]+1}+{Colors.GRAY} alto]{Colors.RESET}")

def print_at(row, col, text):
    """Imprime texto en una posición específica sin mover el cursor al final"""
    move_cursor(row, col)
    sys.stdout.write(text)
    sys.stdout.flush()

def monitor_system():
    """Función principal de monitoreo"""
    hide_cursor()
    clear_screen()

    # Dibujar la estructura estática (solo una vez)
    print(f"{Colors.BOLD}{Colors.CYAN}=== Monitor del Sistema ==={Colors.RESET}")
    print(f"{Colors.GRAY}Presiona Ctrl+C para salir{Colors.RESET}\n")
    print(f"{Colors.BOLD}{'Temperatura CPU':20s}{Colors.RESET}")
    print(f"{Colors.BOLD}{'RAM / Pressure':20s}{Colors.RESET}")
    print(f"{Colors.BOLD}{'Swap Usage':20s}{Colors.RESET}")
    print(f"{Colors.BOLD}{'Load Average':20s}{Colors.RESET}")
    print(f"{Colors.BOLD}{'CPU Hogs':20s}{Colors.RESET}")
    print(f"{Colors.BOLD}{'Scripts Python':20s}{Colors.RESET}")
    print(f"{Colors.BOLD}{'Disco Usado':20s}{Colors.RESET}")
    print(f"\n{Colors.GRAY}Última actualización:{Colors.RESET}")
    print(f"\n{Colors.BOLD}Top 3 procesos CPU:{Colors.RESET}")
    print(f"  1.")
    print(f"  2.")
    print(f"  3.")

    try:
        while True:
            # === TEMPERATURA ===
            temp = get_cpu_temperature()
            temp_thresholds = (60, 70, 80, 100)
            color = get_color(temp, temp_thresholds)
            print_at(3, 1, f"{Colors.BOLD}{'Temperatura CPU':20s}{Colors.RESET} {color}{temp:6.1f}°C{Colors.RESET}  {get_range_text(temp_thresholds)}" + " " * 20)

            # === RAM PRESSURE ===
            ram_pressure = get_memory_pressure()
            ram_thresholds = (50, 70, 85, 100)
            color = get_color(ram_pressure, ram_thresholds)
            print_at(4, 1, f"{Colors.BOLD}{'RAM / Pressure':20s}{Colors.RESET} {color}{ram_pressure:6.1f}%{Colors.RESET}  {get_range_text(ram_thresholds)}" + " " * 20)

            # === SWAP ===
            swap = get_swap_usage()
            swap_thresholds = (10, 30, 60, 100)
            color = get_color(swap, swap_thresholds)
            print_at(5, 1, f"{Colors.BOLD}{'Swap Usage':20s}{Colors.RESET} {color}{swap:6.1f}%{Colors.RESET}  {get_range_text(swap_thresholds)}" + " " * 20)

            # === LOAD AVERAGE ===
            load = get_load_average()
            load_thresholds = (50, 80, 100, 150)
            color = get_color(load, load_thresholds)
            print_at(6, 1, f"{Colors.BOLD}{'Load Average':20s}{Colors.RESET} {color}{load:6.1f}%{Colors.RESET}  {get_range_text(load_thresholds)}" + " " * 20)

            # === CPU HOGS ===
            hogs = get_cpu_hogs()
            hogs_value = hogs[0]['cpu'] if hogs else 0
            hogs_text = f" ({hogs[0]['name']})" if hogs else " (ninguno)"
            hogs_thresholds = (30, 60, 80, 100)
            color = get_color(hogs_value, hogs_thresholds)
            print_at(7, 1, f"{Colors.BOLD}{'CPU Hogs':20s}{Colors.RESET} {color}{hogs_value:6.1f}%{hogs_text:25s}{Colors.RESET}  {get_range_text(hogs_thresholds)}" + " " * 20)

            # === SCRIPTS PYTHON ===
            scripts = count_python_scripts()
            scripts_thresholds = (5, 10, 15, 20)
            color = get_color(scripts, scripts_thresholds)
            print_at(8, 1, f"{Colors.BOLD}{'Scripts Python':20s}{Colors.RESET} {color}{scripts:6d}{Colors.RESET}  {get_range_text(scripts_thresholds)}" + " " * 20)

            # === DISCO ===
            disk = get_disk_usage()
            disk_free = 100 - disk
            disk_thresholds = (50, 70, 85, 100)
            color = get_color(disk, disk_thresholds)
            print_at(9, 1, f"{Colors.BOLD}{'Disco Usado':20s}{Colors.RESET} {color}{disk:6.1f}% (libre: {disk_free:.1f}%){Colors.RESET}  {get_range_text(disk_thresholds)}" + " " * 20)

            # === TIMESTAMP ===
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print_at(11, 1, f"{Colors.GRAY}Última actualización:{Colors.RESET} {timestamp}" + " " * 10)

            # === TOP 3 CPU HOGS ===
            print_at(13, 1, f"{Colors.BOLD}Top 3 procesos CPU:{Colors.RESET}" + " " * 50)
            if hogs:
                for i, proc in enumerate(hogs, 1):
                    color = get_color(proc['cpu'], hogs_thresholds)
                    print_at(13 + i, 3, f"{i}. {proc['name']:25s} {color}{proc['cpu']:5.1f}%{Colors.RESET}" + " " * 20)
            else:
                print_at(14, 3, f"{Colors.GRAY}No hay procesos con alto uso de CPU{Colors.RESET}" + " " * 30)
                print_at(15, 3, " " * 60)
                print_at(16, 3, " " * 60)

            # Esperar antes de la siguiente actualización
            time.sleep(2)

    except KeyboardInterrupt:
        show_cursor()
        move_cursor(20, 1)
        print(f"\n{Colors.CYAN}Monitor detenido.{Colors.RESET}\n")
        sys.exit(0)

if __name__ == "__main__":
    try:
        import psutil
    except ImportError:
        print(f"{Colors.RED}Error: psutil no está instalado{Colors.RESET}")
        print(f"Instala con: {Colors.CYAN}pip3 install --break-system-packages psutil{Colors.RESET}")
        sys.exit(1)

    try:
        monitor_system()
    except Exception as e:
        show_cursor()
        print(f"\n{Colors.RED}Error: {e}{Colors.RESET}\n")
        sys.exit(1)
