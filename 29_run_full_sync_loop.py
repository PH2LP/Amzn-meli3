#!/usr/bin/env python3
"""


Script para ejecutar el SYNC COMPLETO (Amazon → MercadoLibre)
EN LOOP INFINITO en horarios específicos.

CONFIGURACIÓN:
    - Horarios fijos: 00:10, 06:10, 12:10, 18:10
    - Descarga tokens del servidor antes de cada ejecución
    - Actualiza precios en MercadoLibre
    - Pausa/reactiva listings
    - Envía notificaciones Telegram

USO:
    python3 29_run_full_sync_loop.py

    # O dejarlo corriendo en background:
    nohup python3 29_run_full_sync_loop.py > logs/full_sync_loop.log 2>&1 &
"""

import subprocess
import sys
import time
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv, dotenv_values

load_dotenv()

# Configuración
SCHEDULED_TIMES = ['00:10', '06:10', '12:10', '18:10']
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


def download_env_from_server():
    """Descarga .env del servidor y carga tokens en memoria"""
    log_message("📥 Descargando tokens actualizados desde servidor...")

    vps_host = "138.197.32.67"
    vps_user = "root"
    vps_password = "koqven-1regka-nyfXiw"
    vps_path = "/opt/amz-ml-system/.env"
    temp_path = ".env.server_temp"

    cmd = [
        "sshpass", "-p", vps_password,
        "scp", "-o", "StrictHostKeyChecking=no",
        f"{vps_user}@{vps_host}:{vps_path}",
        temp_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            log_message("✅ Tokens descargados desde servidor")

            # Leer tokens del servidor
            server_env = dotenv_values(temp_path)

            # Actualizar .env LOCAL con los tokens del servidor
            # Así todos los load_dotenv() leerán el token correcto
            ml_tokens = ['ML_ACCESS_TOKEN', 'ML_REFRESH_TOKEN', 'ML_CLIENT_ID',
                        'ML_CLIENT_SECRET', 'ML_USER_ID']

            local_env_path = '.env'
            local_env = dotenv_values(local_env_path) if os.path.exists(local_env_path) else {}

            # Actualizar tokens ML del servidor en .env local
            for key in ml_tokens:
                if key in server_env:
                    local_env[key] = server_env[key]

            # Escribir .env actualizado
            with open(local_env_path, 'w') as f:
                for key, value in local_env.items():
                    f.write(f'{key}={value}\n')

            log_message(f"✅ Token ML actualizado en .env: {local_env.get('ML_ACCESS_TOKEN', 'N/A')[:30]}...")

            # Limpiar archivo temporal
            if os.path.exists(temp_path):
                os.remove(temp_path)

            return True
        else:
            log_message(f"⚠️  Error descargando: {result.stderr[:100]}")
            log_message("⚠️  Usando tokens locales")
            return False
    except Exception as e:
        log_message(f"⚠️  Error: {e}")
        log_message("⚠️  Usando tokens locales")
        return False


def run_full_sync():
    """Ejecuta el sync completo (Amazon → MercadoLibre)"""
    log_message("=" * 80)
    log_message("🚀 INICIANDO SYNC COMPLETO (Amazon → MercadoLibre)")
    log_message("=" * 80)

    # Descargar tokens del servidor antes de ejecutar
    download_env_from_server()
    log_message("")

    start_time = time.time()

    try:
        # Pasar variables de entorno actualizadas al subprocess
        # stdout=None permite ver el output en tiempo real
        # -u para unbuffered output (escribe inmediatamente al log)
        result = subprocess.run(
            [sys.executable, "-u", "scripts/tools/sync_amazon_ml_GLOW.py"],
            stdout=None,
            stderr=None,
            text=True,
            env=os.environ.copy()
        )

        elapsed = time.time() - start_time

        log_message("")
        log_message("=" * 80)
        if result.returncode == 0:
            log_message(f"✅ Sync completo exitoso en {elapsed/60:.1f} minutos")
        else:
            log_message(f"❌ Sync falló con código {result.returncode} después de {elapsed/60:.1f} minutos")
        log_message("=" * 80)
        log_message("")

        return result.returncode == 0

    except Exception as e:
        log_message(f"❌ Error ejecutando sync: {e}")
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
    log_message("🔄 SYNC COMPLETO - MODO LOOP CON HORARIOS FIJOS")
    log_message("=" * 80)
    log_message(f"Horarios programados: {', '.join(SCHEDULED_TIMES)}")
    log_message(f"Log file: {LOG_FILE}")
    log_message("")
    log_message("Acciones del sync:")
    log_message("  ✅ Valida delivery con Glow API")
    log_message("  ✅ Actualiza precios en MercadoLibre")
    log_message("  ✅ Pausa/reactiva listings")
    log_message("  ✅ Envía notificaciones Telegram")
    log_message("  ✅ Auto-descarga tokens del servidor")
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

            # Ejecutar sync completo
            success = run_full_sync()

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
