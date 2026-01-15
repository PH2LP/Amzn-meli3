#!/usr/bin/env python3
"""
16B_ml_token_loop.py

Loop automático de renovación de token MercadoLibre.
Renueva a las 00:00, 06:00, 12:00, 18:00 todos los días.

USO:
    python3 16B_ml_token_loop.py

    # En background:
    nohup python3 16B_ml_token_loop.py > logs/ml_token_refresh.log 2>&1 &
"""

import os
import sys
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import dotenv_values

ENV_PATH = Path(__file__).parent / ".env"
LOG_FILE = Path(__file__).parent / "logs" / "ml_token_refresh.log"

# Leer horarios programados desde .env
env_config = dotenv_values(ENV_PATH)
SCHEDULED_TIMES_STR = env_config.get("ML_TOKEN_REFRESH_SCHEDULED_TIMES", "00:00,06:00,12:00,18:00")
SCHEDULED_TIMES = [t.strip() for t in SCHEDULED_TIMES_STR.split(",")]

def log(msg):
    """Log con timestamp tanto a consola como a archivo"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

def refresh_ml_token():
    """
    Renueva el access token de MercadoLibre y actualiza el archivo .env
    """
    try:
        env = dotenv_values(ENV_PATH)

        client_id = env.get("ML_CLIENT_ID")
        client_secret = env.get("ML_CLIENT_SECRET")
        refresh_token = env.get("ML_REFRESH_TOKEN")

        if not all([client_id, client_secret, refresh_token]):
            log("❌ Error: Faltan credenciales ML en .env")
            return False

        log("🔄 Renovando access token de MercadoLibre...")

        url = "https://api.mercadolibre.com/oauth/token"
        payload = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token
        }

        r = requests.post(url, data=payload, timeout=10)
        r.raise_for_status()
        data = r.json()

        new_access_token = data["access_token"]
        new_refresh_token = data.get("refresh_token", refresh_token)

        # Actualizar archivo .env
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            if line.startswith("ML_ACCESS_TOKEN="):
                new_lines.append(f"ML_ACCESS_TOKEN={new_access_token}\n")
            elif line.startswith("ML_REFRESH_TOKEN="):
                new_lines.append(f"ML_REFRESH_TOKEN={new_refresh_token}\n")
            else:
                new_lines.append(line)

        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        log(f"✅ Token renovado exitosamente")
        log(f"   Access token: {new_access_token[:40]}...")
        log(f"   Refresh token: {new_refresh_token[:40]}...")

        return True

    except requests.exceptions.RequestException as e:
        log(f"❌ Error de red al renovar token: {e}")
        return False
    except Exception as e:
        log(f"❌ Error inesperado al renovar token: {e}")
        return False

def get_next_refresh_time():
    """
    Calcula la próxima hora de refresh basado en SCHEDULED_TIMES

    Returns:
        datetime: Próxima hora de refresh
    """
    now = datetime.now()
    upcoming_times = []

    # Parsear todos los horarios programados
    for time_str in SCHEDULED_TIMES:
        try:
            hour, minute = map(int, time_str.split(":"))
            next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # Si esta hora ya pasó hoy, programar para mañana
            if next_time <= now:
                next_time += timedelta(days=1)

            upcoming_times.append(next_time)
        except ValueError:
            log(f"⚠️  Formato de hora inválido: {time_str}")
            continue

    # Retornar el más cercano
    if upcoming_times:
        return min(upcoming_times)
    else:
        # Fallback: en 6 horas
        return now + timedelta(hours=6)

def main():
    """
    Loop principal que renueva el token en horarios fijos
    """
    log("=" * 60)
    log("🚀 Iniciando loop automático de renovación ML Token")
    log(f"   Horarios de refresh: {', '.join(SCHEDULED_TIMES)}")
    log(f"   Log: {LOG_FILE}")
    log("=" * 60)

    # Primera renovación inmediata
    log("🔄 Renovación inicial...")
    refresh_ml_token()

    # Loop infinito
    iteration = 1
    while True:
        try:
            # Calcular próxima ejecución
            next_run = get_next_refresh_time()
            now = datetime.now()

            log(f"⏰ Próxima renovación: {next_run.strftime('%Y-%m-%d %H:%M')}")

            # Countdown dinámico - esperar hasta que llegue el momento
            while True:
                now = datetime.now()
                remaining = (next_run - now).total_seconds()

                if remaining <= 0:
                    print()  # Nueva línea
                    break

                hours = int(remaining // 3600)
                minutes = int((remaining % 3600) // 60)
                seconds = int(remaining % 60)

                print(f"\r⏳ Esperando: {hours:02d}h {minutes:02d}m {seconds:02d}s (iteración #{iteration})    ", end='', flush=True)
                time.sleep(1)

            # Refrescar token SOLO cuando se cumple el tiempo
            log("🔄 Tiempo de renovación alcanzado...")
            refresh_ml_token()
            iteration += 1

        except KeyboardInterrupt:
            log("\n🛑 Loop detenido manualmente (Ctrl+C)")
            break
        except Exception as e:
            log(f"❌ Error en el loop: {e}")
            log("⏳ Reintentando en 5 minutos...")
            time.sleep(300)  # Esperar 5 minutos antes de reintentar

if __name__ == "__main__":
    main()
