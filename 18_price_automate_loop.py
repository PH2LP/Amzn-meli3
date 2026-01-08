#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 18_price_automate_loop.py - AUTOMATIZACIÓN DE PRECIOS ML (LOOP INFINITO)
# ═══════════════════════════════════════════════════════════════════════════════
#
# ¿Qué hace?
#   Ejecuta automatización de precios ML en LOOP INFINITO en horarios configurables.
#   Configura min_price (15% markup) y max_price (100% markup) para competencia automática.
#
# Comando:
#   python3 18_price_automate_loop.py
#
# Ctrl+C para detener
# ═══════════════════════════════════════════════════════════════════════════════
import subprocess
import sys
import time
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Configuración
# Leer horarios del .env o usar default
PRICE_AUTOMATE_SCHEDULED_TIMES = os.getenv('PRICE_AUTOMATE_SCHEDULED_TIMES', '01:00,07:00,13:00,19:00')
SCHEDULED_TIMES = [time.strip() for time in PRICE_AUTOMATE_SCHEDULED_TIMES.split(',')]
LOG_FILE = 'logs/price_automate_loop.log'

# Crear directorio de logs si no existe
os.makedirs('logs', exist_ok=True)

def log_message(message):
    """Escribe mensaje en consola y en log file"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    full_message = f"[{timestamp}] {message}"
    print(full_message)

    # Escribir en log file
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(full_message + '\n')
    except:
        pass


def get_next_scheduled_time():
    """Calcula el próximo horario programado"""
    now = datetime.now()

    # Convertir horarios programados a datetime de hoy
    today_times = []
    for time_str in SCHEDULED_TIMES:
        hour, minute = map(int, time_str.split(':'))
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        today_times.append(scheduled)

    # Encontrar el próximo horario
    for scheduled in today_times:
        if scheduled > now:
            return scheduled

    # Si no hay más horarios hoy, tomar el primero de mañana
    hour, minute = map(int, SCHEDULED_TIMES[0].split(':'))
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)


def run_price_automation():
    """Ejecuta la automatización de precios ML"""
    log_message("=" * 80)
    log_message("🤖 INICIANDO AUTOMATIZACIÓN DE PRECIOS ML")
    log_message("=" * 80)

    start_time = time.time()

    try:
        # Ejecutar script 17 con input automático 's' para confirmar
        log_message("📖 Ejecutando script de automatización...")
        log_message("")

        # Crear proceso con input 's' para autoconfirmar
        process = subprocess.Popen(
            [sys.executable, "-u", "17_price_automate.py"],
            stdin=subprocess.PIPE,
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True
        )

        # Enviar 's' para confirmar automáticamente
        process.communicate(input='s\n')

        elapsed = time.time() - start_time

        log_message("")
        log_message("=" * 80)
        if process.returncode == 0:
            log_message(f"✅ Automatización de precios exitosa en {elapsed/60:.1f} minutos")
        else:
            log_message(f"❌ Automatización falló con código {process.returncode} después de {elapsed/60:.1f} minutos")
        log_message("=" * 80)
        log_message("")

        return process.returncode == 0

    except Exception as e:
        log_message(f"❌ Error ejecutando automatización: {e}")
        return False


def wait_until_scheduled_time(next_run):
    """Espera hasta el horario programado mostrando countdown"""
    while True:
        now = datetime.now()
        remaining = (next_run - now).total_seconds()

        if remaining <= 0:
            break

        # Convertir a horas, minutos, segundos
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)

        # Mostrar countdown en la misma línea
        print(f"\r⏳ Esperando... {hours:02d}:{minutes:02d}:{seconds:02d} restantes", end='', flush=True)

        time.sleep(1)

    print()  # Nueva línea al terminar


def main():
    """Main loop"""

    log_message("")
    log_message("=" * 80)
    log_message("🤖 AUTOMATIZACIÓN DE PRECIOS ML - MODO LOOP CON HORARIOS FIJOS")
    log_message("=" * 80)
    log_message(f"Horarios programados: {', '.join(SCHEDULED_TIMES)}")
    log_message(f"Log file: {LOG_FILE}")
    log_message("")
    log_message("Acciones del script:")
    log_message("  ✅ Lee precios de la DB")
    log_message("  ✅ Configura min_price (15% markup)")
    log_message("  ✅ Configura max_price (100% markup)")
    log_message("  ✅ Activa competencia automática (INT)")
    log_message("  ✅ Procesa CBT y items locales")
    log_message("")
    log_message("⚠️  Presioná Ctrl+C para detener el loop")
    log_message("=" * 80)
    log_message("")

    execution_count = 0

    try:
        while True:
            # Calcular próximo horario programado
            next_run = get_next_scheduled_time()

            log_message("=" * 80)
            log_message(f"⏰ Próxima ejecución programada: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            log_message("=" * 80)

            # Esperar con countdown hasta el horario programado
            wait_until_scheduled_time(next_run)

            execution_count += 1

            # Ejecutar automatización
            success = run_price_automation()

            log_message("")
            log_message("=" * 80)
            log_message(f"📊 Ejecución #{execution_count} completada")
            log_message("=" * 80)
            log_message("")

    except KeyboardInterrupt:
        print()  # Nueva línea si se interrumpe durante countdown
        log_message("")
        log_message("=" * 80)
        log_message("⏹️  Loop detenido por el usuario (Ctrl+C)")
        log_message(f"Total ejecuciones: {execution_count}")
        log_message("=" * 80)
        sys.exit(0)


if __name__ == "__main__":
    main()
