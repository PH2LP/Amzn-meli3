#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 05_sync_once.py - SYNC COMPLETO (1 VEZ)
# ═══════════════════════════════════════════════════════════════════════════════
# 
# ¿Qué hace?
#   Ejecuta sincronización completa UNA VEZ:
#   - Valida delivery con Glow API
#   - Actualiza precios en MercadoLibre
#   - Pausa/reactiva listings según disponibilidad
#   - Envía notificaciones por Telegram
# 
# Comando:
#   python3 05_sync_once.py
# 
# ═══════════════════════════════════════════════════════════════════════════════
import subprocess
import sys
import os
import shutil
from datetime import datetime
from dotenv import dotenv_values

def backup_local_env():
    """Hace backup del .env local"""
    if os.path.exists('.env'):
        shutil.copy('.env', '.env.local_backup')
        print("💾 Backup del .env local creado")
        return True
    return False


def restore_local_env():
    """Restaura el .env local desde el backup"""
    if os.path.exists('.env.local_backup'):
        shutil.copy('.env.local_backup', '.env')
        print("♻️  .env local restaurado desde backup")
        return True
    return False


def download_env_from_server():
    """Descarga .env del servidor y SOBRESCRIBE el .env local"""
    print("📥 Descargando .env completo desde servidor...")

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
            print("✅ .env del servidor descargado y aplicado")
            print("   (Todos los imports usarán configuración del servidor)")
            return True
        else:
            print(f"⚠️  Error descargando: {result.stderr[:100]}")
            print("⚠️  Usando .env local")
            return False
    except Exception as e:
        print(f"⚠️  Error: {e}")
        print("⚠️  Usando .env local")
        return False


def main():
    print("=" * 80)
    print("🚀 EJECUTANDO SYNC COMPLETO (Amazon → MercadoLibre)")
    print("=" * 80)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    print("📖 Usando .env local")
    print()

    print("Este sync hace:")
    print("  ✅ Valida delivery con Glow API")
    print("  ✅ Actualiza precios en MercadoLibre")
    print("  ✅ Pausa/reactiva listings")
    print("  ✅ Envía notificaciones Telegram")
    print()
    print("⚠️  Presioná Ctrl+C para detener el sync en cualquier momento")
    print()
    print("=" * 80)
    print()

    try:
        # Ejecutar el sync completo (lee .env local)
        result = subprocess.run(
            [sys.executable, "scripts/tools/sync_amazon_ml_GLOW.py"],
            stdout=None,
            stderr=None,
            text=True
        )

        print()
        print("=" * 80)
        if result.returncode == 0:
            print("✅ Sync completado exitosamente")
        else:
            print(f"❌ Sync terminó con código de error: {result.returncode}")
        print(f"Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

    except KeyboardInterrupt:
        print()
        print()
        print("=" * 80)
        print("⏹️  Sync detenido por el usuario (Ctrl+C)")
        print("=" * 80)

if __name__ == "__main__":
    main()
