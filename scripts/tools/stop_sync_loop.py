#!/usr/bin/env python3
"""
stop_sync_loop.py
═══════════════════════════════════════════════════════════════════════════════
DETENER DAEMON DE SINCRONIZACIÓN AMAZON → MERCADOLIBRE
═══════════════════════════════════════════════════════════════════════════════

Detiene el daemon de sincronización automática.

USO:
    python3 stop_sync_loop.py
"""

import os
import sys
import signal
from pathlib import Path

# Configuración
PID_FILE = Path("storage/sync_loop.pid")

# Colores para consola
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def log(message, color=Colors.NC):
    print(f"{color}{message}{Colors.NC}")

def main():
    print()
    log("╔════════════════════════════════════════════════════════════════╗", Colors.BLUE)
    log("║       DETENER DAEMON DE SINCRONIZACIÓN AMAZON → ML            ║", Colors.BLUE)
    log("╚════════════════════════════════════════════════════════════════╝", Colors.BLUE)
    print()

    # Verificar si existe el PID file
    if not PID_FILE.exists():
        log("⚠️  No hay daemon corriendo", Colors.YELLOW)
        log("   (No se encontró archivo PID)", Colors.YELLOW)
        return

    # Leer PID
    try:
        pid = int(PID_FILE.read_text().strip())
    except ValueError:
        log("❌ Error: PID file corrupto", Colors.RED)
        PID_FILE.unlink()
        return

    # Verificar si el proceso existe
    try:
        os.kill(pid, 0)  # Signal 0 solo verifica existencia
    except OSError:
        log(f"⚠️  El proceso {pid} ya no existe", Colors.YELLOW)
        log("   Limpiando PID file...", Colors.YELLOW)
        PID_FILE.unlink()
        return

    # Detener el proceso
    log(f"🛑 Deteniendo daemon (PID: {pid})...", Colors.YELLOW)

    try:
        # Enviar SIGTERM (señal de terminación elegante)
        os.kill(pid, signal.SIGTERM)

        # Esperar hasta 10 segundos para que termine
        import time
        max_wait = 10
        for i in range(max_wait * 2):  # Chequear cada 0.5s
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except OSError:
                # Proceso terminó
                break

        # Verificar si se detuvo
        try:
            os.kill(pid, 0)
            # Si llegamos aquí, el proceso sigue vivo después de 10s
            log("⚠️  El proceso no se detuvo con SIGTERM después de 10s, usando SIGKILL...", Colors.YELLOW)
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)  # Esperar un poco después de SIGKILL
        except OSError:
            # Proceso ya terminó
            pass

        # Limpiar PID file
        if PID_FILE.exists():
            PID_FILE.unlink()

        log("✅ Daemon detenido exitosamente", Colors.GREEN)

    except Exception as e:
        log(f"❌ Error deteniendo daemon: {e}", Colors.RED)
        sys.exit(1)

    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Cancelado por usuario")
        sys.exit(0)
    except Exception as e:
        log(f"\n❌ Error: {e}", Colors.RED)
        sys.exit(1)
