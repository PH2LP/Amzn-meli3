#!/usr/bin/env python3
"""
27_run_full_sync_loop.py

Script para ejecutar el SYNC COMPLETO (Amazon → MercadoLibre) a HORAS ESPECÍFICAS.

Ejecuta sync_amazon_ml_GLOW.py automáticamente a las:
- 00:10
- 06:10
- 12:10
- 18:10

Este sync COMPLETO hace:
- ✅ Obtiene precio y delivery de Amazon (usando V2 Advanced anti-detección)
- ✅ Actualiza precios en MercadoLibre
- ✅ Pausa/reactiva listings según disponibilidad
- ✅ Envía notificaciones por Telegram
- ✅ Guarda logs de todos los cambios

USO:
    python3 27_run_full_sync_loop.py

    # O dejarlo corriendo en background:
    nohup python3 27_run_full_sync_loop.py > logs/full_sync_loop.log 2>&1 &
"""

import subprocess
import sys
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Configuración
SYNC_TIMES = ['00:10', '06:10', '12:10', '18:10']  # Horas específicas para ejecutar
SYNC_SCRIPT = 'scripts/tools/sync_amazon_ml_GLOW.py'
LOG_FILE = 'logs/full_sync_loop.log'

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


def get_next_sync_time():
    """Calcula la próxima hora de ejecución"""
    now = datetime.now()

    # Convertir horas de sync a datetime de hoy
    today_syncs = []
    for sync_time in SYNC_TIMES:
        hour, minute = map(int, sync_time.split(':'))
        sync_datetime = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        today_syncs.append(sync_datetime)

    # Encontrar la próxima ejecución
    for sync_dt in today_syncs:
        if sync_dt > now:
            return sync_dt

    # Si ya pasaron todas las horas de hoy, usar la primera de mañana
    hour, minute = map(int, SYNC_TIMES[0].split(':'))
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)


def run_sync():
    """Ejecuta el sync completo una vez"""
    log_message("=" * 80)
    log_message("🚀 INICIANDO SYNC COMPLETO AMAZON → MERCADOLIBRE")
    log_message("=" * 80)

    start_time = time.time()

    try:
        result = subprocess.run(
            [sys.executable, SYNC_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        elapsed = time.time() - start_time

        # Mostrar últimas 30 líneas del output
        output_lines = result.stdout.strip().split('\n')
        for line in output_lines[-30:]:
            log_message(f"  {line}")

        log_message("")
        log_message("=" * 80)
        if result.returncode == 0:
            log_message(f"✅ Sync completado exitosamente en {elapsed/60:.1f} minutos")
        else:
            log_message(f"❌ Sync falló con código {result.returncode} después de {elapsed/60:.1f} minutos")
        log_message("=" * 80)
        log_message("")

        return result.returncode == 0

    except Exception as e:
        log_message(f"❌ Error ejecutando sync: {e}")
        return False


def main():
    """Main loop"""

    log_message("")
    log_message("=" * 80)
    log_message("🔄 SYNC COMPLETO AMAZON → ML - HORARIOS PROGRAMADOS")
    log_message("=" * 80)
    log_message(f"Horarios de ejecución: {', '.join(SYNC_TIMES)}")
    log_message(f"Script: {SYNC_SCRIPT}")
    log_message(f"Log file: {LOG_FILE}")
    log_message("")
    log_message("Features del sistema V2 Advanced:")
    log_message("  ✅ Session Rotation (nueva sesión cada 100 requests)")
    log_message("  ✅ Exponential Backoff con Jitter")
    log_message("  ✅ Rate Limiting Inteligente (~0.5 req/sec)")
    log_message("  ✅ User-Agent Rotation")
    log_message("  ✅ Actualización automática de precios en ML")
    log_message("  ✅ Pausa/reactiva listings según disponibilidad")
    log_message("  ✅ Notificaciones Telegram")
    log_message("")
    log_message("⚠️  Presioná Ctrl+C para detener el loop")
    log_message("=" * 80)
    log_message("")

    execution_count = 0

    try:
        while True:
            # Calcular próxima ejecución
            next_run = get_next_sync_time()
            now = datetime.now()
            wait_seconds = (next_run - now).total_seconds()

            log_message(f"⏰ Próxima ejecución: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            log_message(f"⏳ Esperando {wait_seconds/60:.0f} minutos...")
            log_message("")

            # Esperar hasta la próxima ejecución
            time.sleep(wait_seconds)

            # Ejecutar sync
            execution_count += 1
            log_message(f"📊 Ejecución #{execution_count}")
            success = run_sync()

    except KeyboardInterrupt:
        log_message("")
        log_message("=" * 80)
        log_message("⏹️  Loop detenido por el usuario (Ctrl+C)")
        log_message(f"Total ejecuciones: {execution_count}")
        log_message("=" * 80)
        sys.exit(0)


if __name__ == "__main__":
    main()
