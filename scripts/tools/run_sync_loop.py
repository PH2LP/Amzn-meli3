#!/usr/bin/env python3
"""
run_sync_loop.py
═══════════════════════════════════════════════════════════════════════════════
DAEMON DE SINCRONIZACIÓN AMAZON <-> MERCADOLIBRE
═══════════════════════════════════════════════════════════════════════════════

Ejecuta sync_amazon_ml.py en loop automático cada X horas (configurable).

- Sincroniza precios Amazon → MercadoLibre
- Pausa productos sin stock o que no cumplen Fast Fulfillment
- Reactiva productos que vuelven a estar disponibles

CONFIGURACIÓN (.env):
    SYNC_INTERVAL_HOURS=3  # Intervalo en horas (default: 3)

USO:
    python3 run_sync_loop.py

Para detener:
    python3 stop_sync_loop.py

Para ver logs:
    python3 view_sync_logs.py
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Cargar .env
load_dotenv()

# Configuración
PID_FILE = Path("storage/sync_loop.pid")
LOG_FILE = Path("logs/sync/sync_loop.log")
SYNC_INTERVAL_HOURS = float(os.getenv("SYNC_INTERVAL_HOURS", "3"))

# Colores para consola
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

def log_to_file(message):
    """Escribe en el archivo de log"""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {message}\n")

def log(message, color=Colors.NC, to_file=True):
    """Imprime en consola y archivo"""
    print(f"{color}{message}{Colors.NC}")
    if to_file:
        clean_msg = message
        for c in [Colors.RED, Colors.GREEN, Colors.YELLOW, Colors.BLUE, Colors.CYAN, Colors.NC]:
            clean_msg = clean_msg.replace(c, "")
        log_to_file(clean_msg)

# Variable global para rastrear proceso hijo
current_sync_process = None

def run_sync():
    """Ejecuta sync_amazon_ml.py"""
    global current_sync_process

    log("🔄 Iniciando sincronización Amazon → MercadoLibre...", Colors.CYAN)

    script_path = Path(__file__).parent / "sync_amazon_ml.py"

    if not script_path.exists():
        log(f"❌ Script no encontrado: {script_path}", Colors.RED)
        return False

    try:
        # Abrir archivo de log para escribir en tiempo real
        log_file_path = Path("logs/sync/sync_loop.log")

        # Ejecutar el script con output directo al log file
        with open(log_file_path, 'a') as log_file:
            log_to_file("═" * 80)
            log_to_file("INICIO DE SINCRONIZACIÓN")
            log_to_file("═" * 80)

            current_sync_process = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdout=log_file,
                stderr=subprocess.STDOUT,  # Redirigir stderr a stdout para verlo todo junto
                text=True
            )

            # Esperar a que termine (con timeout)
            try:
                returncode = current_sync_process.wait(timeout=3600)
            except subprocess.TimeoutExpired:
                log("❌ Timeout: La sincronización tardó más de 1 hora", Colors.RED)
                current_sync_process.kill()
                current_sync_process.wait()
                current_sync_process = None
                return False

        current_sync_process = None

        log_to_file("═" * 80)
        log_to_file("FIN DE SINCRONIZACIÓN")
        log_to_file("═" * 80)

        if returncode == 0:
            log("✅ Sincronización completada exitosamente", Colors.GREEN)
            return True
        else:
            log(f"❌ Sincronización falló (código: {returncode})", Colors.RED)
            return False

    except Exception as e:
        log(f"❌ Error ejecutando sincronización: {e}", Colors.RED)
        if current_sync_process:
            try:
                current_sync_process.kill()
                current_sync_process.wait()
            except:
                pass
            current_sync_process = None
        return False

def signal_handler(sig, frame):
    """Maneja Ctrl+C y señales de terminación"""
    global current_sync_process

    log("\n\n🛑 Daemon detenido (señal recibida)", Colors.YELLOW)

    # Si hay un proceso de sync corriendo, matarlo
    if current_sync_process:
        log("   Deteniendo proceso de sincronización...", Colors.YELLOW)
        try:
            current_sync_process.terminate()
            current_sync_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            current_sync_process.kill()
            current_sync_process.wait()
        except:
            pass

    # Limpiar PID file
    if PID_FILE.exists():
        PID_FILE.unlink()

    sys.exit(0)

def check_if_running():
    """Verifica si ya hay una instancia corriendo"""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            # Verificar si el proceso existe
            os.kill(pid, 0)
            return pid
        except (OSError, ValueError):
            # PID file existe pero proceso no
            PID_FILE.unlink()
            return None
    return None

def main():
    print()
    log("╔════════════════════════════════════════════════════════════════╗", Colors.BLUE)
    log("║        DAEMON DE SINCRONIZACIÓN AMAZON → MERCADOLIBRE         ║", Colors.BLUE)
    log("╚════════════════════════════════════════════════════════════════╝", Colors.BLUE)
    print()

    # Verificar si ya está corriendo
    existing_pid = check_if_running()
    if existing_pid:
        log(f"⚠️  Ya hay un daemon corriendo (PID: {existing_pid})", Colors.YELLOW)
        log(f"   Para detenerlo: python3 stop_sync_loop.py", Colors.YELLOW)
        sys.exit(1)

    # Crear directorios
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Guardar PID
    PID_FILE.write_text(str(os.getpid()))

    # Configurar handlers de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Información inicial
    log(f"🚀 Daemon iniciado (PID: {os.getpid()})", Colors.GREEN)
    log(f"⏱️  Intervalo: {SYNC_INTERVAL_HOURS} horas", Colors.CYAN)
    log(f"📝 Log: {LOG_FILE}", Colors.CYAN)
    print()
    log("💡 Para detener: python3 stop_sync_loop.py", Colors.YELLOW)
    log("💡 Para ver logs: python3 view_sync_logs.py", Colors.YELLOW)
    print()

    # Loop principal
    iteration = 0
    while True:
        iteration += 1
        log(f"═══════════════════════ ITERACIÓN {iteration} ═══════════════════════", Colors.BLUE)

        # Ejecutar sincronización
        success = run_sync()

        # Calcular próxima ejecución
        interval_seconds = int(SYNC_INTERVAL_HOURS * 3600)
        next_sync = datetime.now().timestamp() + interval_seconds
        next_sync_str = datetime.fromtimestamp(next_sync).strftime("%Y-%m-%d %H:%M:%S")

        log(f"⏰ Próxima sincronización: {next_sync_str}", Colors.CYAN)
        log(f"💤 Durmiendo por {SYNC_INTERVAL_HOURS} horas...", Colors.CYAN)
        print()

        # Esperar
        try:
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            signal_handler(None, None)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"\n❌ Error fatal: {e}", Colors.RED)
        import traceback
        traceback.print_exc()
        if PID_FILE.exists():
            PID_FILE.unlink()
        sys.exit(1)
