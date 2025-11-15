#!/usr/bin/env python3
# ============================================================
# 🔄 LOOP AUTOMÁTICO DE RENOVACIÓN DE TOKEN MERCADOLIBRE
# ============================================================
# Renueva el token cada 5.5 horas automáticamente
# Los tokens de ML duran 6 horas, renovamos a las 5.5 para seguridad
# ============================================================

import os
import sys
import time
import requests
from datetime import datetime
from pathlib import Path
from dotenv import dotenv_values

# Agregar el directorio raíz al path para imports
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

REFRESH_INTERVAL = 5.5 * 60 * 60  # 5.5 horas en segundos
ENV_PATH = ROOT_DIR / ".env"
LOG_FILE = ROOT_DIR / "logs" / "ml_token_refresh.log"

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
        log(f"   Próxima renovación en 5.5 horas")

        return True

    except requests.exceptions.RequestException as e:
        log(f"❌ Error de red al renovar token: {e}")
        return False
    except Exception as e:
        log(f"❌ Error inesperado al renovar token: {e}")
        return False

def run_loop():
    """
    Loop principal que renueva el token cada 5.5 horas
    """
    log("=" * 60)
    log("🚀 Iniciando loop automático de renovación ML Token")
    log(f"   Intervalo: 5.5 horas ({REFRESH_INTERVAL} segundos)")
    log(f"   Log: {LOG_FILE}")
    log("=" * 60)

    # Primera renovación inmediata
    refresh_ml_token()

    # Loop infinito
    iteration = 1
    while True:
        try:
            log(f"⏳ Esperando 5.5 horas hasta próxima renovación... (iteración #{iteration})")
            time.sleep(REFRESH_INTERVAL)

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
    run_loop()
