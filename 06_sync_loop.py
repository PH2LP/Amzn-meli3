#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 06_sync_loop.py - SYNC COMPLETO (LOOP INFINITO)
# ═══════════════════════════════════════════════════════════════════════════════
# 
# ¿Qué hace?
#   Ejecuta sync completo en LOOP INFINITO cada 6 horas (00:10, 06:10, 12:10, 18:10).
#   Mismas acciones que 05_sync_once.py pero automático y continuo.
# 
# Comando:
#   python3 06_sync_loop.py
# 
# Ctrl+C para detener
# ═══════════════════════════════════════════════════════════════════════════════
import subprocess
import sys
import time
import os
import shutil
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


def backup_local_env():
    """Hace backup del .env local"""
    if os.path.exists('.env'):
        shutil.copy('.env', '.env.local_backup')
        log_message("💾 Backup del .env local creado")
        return True
    return False


def restore_local_env():
    """Restaura el .env local desde el backup"""
    if os.path.exists('.env.local_backup'):
        shutil.copy('.env.local_backup', '.env')
        log_message("♻️  .env local restaurado desde backup")
        return True
    return False


def download_env_from_server():
    """Descarga .env del servidor y SOBRESCRIBE el .env local"""
    log_message("📥 Descargando .env completo desde servidor...")

    vps_host = "138.197.32.67"
    vps_user = "root"
    vps_password = "koqven-1regka-nyfXiw"
    vps_path = "/opt/amz-ml-system/.env"
    local_env_path = ".env"

    cmd = [
        "sshpass", "-p", vps_password,
        "scp", "-o", "StrictHostKeyChecking=no",
        f"{vps_user}@{vps_host}:{vps_path}",
        local_env_path  # Sobrescribir .env local directamente
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            log_message("✅ .env del servidor descargado y aplicado")
            log_message("   (Todos los imports usarán configuración del servidor)")
            return True
        else:
            log_message(f"⚠️  Error descargando: {result.stderr[:100]}")
            log_message("⚠️  Usando .env local")
            return False
    except Exception as e:
        log_message(f"⚠️  Error: {e}")
        log_message("⚠️  Usando .env local")
        return False


def run_full_sync():
    """Ejecuta el sync completo (Amazon → MercadoLibre)"""
    log_message("=" * 80)
    log_message("🚀 INICIANDO SYNC COMPLETO (Amazon → MercadoLibre)")
    log_message("=" * 80)

    start_time = time.time()

    try:
        # Ejecutar sync completo (lee .env local)
        log_message("📖 Usando .env local")
        log_message("")

        result = subprocess.run(
            [sys.executable, "-u", "scripts/tools/sync_amazon_ml_GLOW.py"],
            stdout=None,
            stderr=None,
            text=True
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
    log_message("  ✅ Usa configuración del .env local")
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
