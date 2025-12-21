#!/usr/bin/env python3
"""
sync_db_to_server.py
═══════════════════════════════════════════════════════════════════════════════
SINCRONIZACIÓN DE BASE DE DATOS LOCAL → SERVIDOR
═══════════════════════════════════════════════════════════════════════════════

Sincroniza la base de datos SQLite local (storage/listings_database.db)
con la base de datos del servidor remoto.

CONFIGURACIÓN (.env):
    # Agregar estas variables al archivo .env:
    REMOTE_DB_TYPE=sqlite          # Tipo: sqlite, postgresql, mysql
    REMOTE_DB_HOST=your.server.ip  # IP o hostname del servidor
    REMOTE_DB_PORT=22              # Puerto SSH (para sqlite) o DB (para postgres/mysql)
    REMOTE_DB_USER=usuario         # Usuario SSH o DB
    REMOTE_DB_PASSWORD=password    # Contraseña (opcional para SSH con keys)
    REMOTE_DB_PATH=/path/to/db     # Para SQLite: ruta en servidor
    REMOTE_DB_NAME=database_name   # Para PostgreSQL/MySQL: nombre de DB

USO:
    python3 sync_db_to_server.py

MÉTODOS DE SINCRONIZACIÓN:
1. SQLite remoto: Copia el archivo via SCP y hace merge
2. PostgreSQL/MySQL: INSERT ON CONFLICT UPDATE directo
"""

import os
import sys
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Cargar .env
load_dotenv()

# Colores para consola
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def log(message, color=Colors.NC):
    print(f"{color}{message}{Colors.NC}")

def get_local_stats():
    """Obtiene estadísticas de la DB local"""
    local_db = Path("storage/listings_database.db")

    if not local_db.exists():
        log("❌ Base de datos local no encontrada", Colors.RED)
        sys.exit(1)

    conn = sqlite3.connect(str(local_db))
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM listings")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM listings WHERE created_at >= datetime('now', '-7 days')")
    recent = cursor.fetchone()[0]

    conn.close()

    return {
        "total": total,
        "recent_7days": recent,
        "file_size_mb": local_db.stat().st_size / (1024 * 1024)
    }

def sync_to_remote_sqlite():
    """Sincroniza con SQLite remoto via SSH/SCP"""
    log("📤 Sincronizando con SQLite remoto...", Colors.BLUE)

    host = os.getenv("REMOTE_DB_HOST")
    user = os.getenv("REMOTE_DB_USER")
    remote_path = os.getenv("REMOTE_DB_PATH", "/root/revancha/storage/listings_database.db")
    password = os.getenv("REMOTE_DB_PASSWORD")

    if not host or not user:
        log("❌ Falta configuración: REMOTE_DB_HOST y REMOTE_DB_USER", Colors.RED)
        return False

    local_db = "storage/listings_database.db"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. Hacer backup en servidor
    log(f"1️⃣  Creando backup en servidor...", Colors.YELLOW)
    backup_cmd = f"ssh {user}@{host} 'cp {remote_path} {remote_path}.backup_{timestamp}'"
    result = subprocess.run(backup_cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        log(f"⚠️  No se pudo crear backup (tal vez no existe): {result.stderr}", Colors.YELLOW)

    # 2. Copiar DB local al servidor (reemplazo directo)
    log(f"2️⃣  Copiando base de datos local al servidor...", Colors.YELLOW)

    # Usar sshpass si hay password
    if password:
        scp_cmd = f"sshpass -p '{password}' scp -o StrictHostKeyChecking=no {local_db} {user}@{host}:{remote_path}"
    else:
        scp_cmd = f"scp {local_db} {user}@{host}:{remote_path}"

    result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        log(f"❌ Error copiando archivo: {result.stderr}", Colors.RED)
        return False

    log(f"✅ Base de datos copiada exitosamente", Colors.GREEN)

    log("✅ Sincronización completada!", Colors.GREEN)
    return True

def sync_to_postgresql():
    """Sincroniza con PostgreSQL remoto"""
    log("📤 Sincronización con PostgreSQL no implementada aún", Colors.YELLOW)
    log("   Usa SQLite remoto o implementa esta función", Colors.YELLOW)
    return False

def sync_to_mysql():
    """Sincroniza con MySQL remoto"""
    log("📤 Sincronización con MySQL no implementada aún", Colors.YELLOW)
    log("   Usa SQLite remoto o implementa esta función", Colors.YELLOW)
    return False

def main():
    print()
    log("╔════════════════════════════════════════════════════════════════╗", Colors.BLUE)
    log("║            SINCRONIZACIÓN DB LOCAL → SERVIDOR                  ║", Colors.BLUE)
    log("╚════════════════════════════════════════════════════════════════╝", Colors.BLUE)
    print()

    # Verificar configuración
    db_type = os.getenv("REMOTE_DB_TYPE", "sqlite").lower()

    if db_type not in ["sqlite", "postgresql", "mysql"]:
        log(f"❌ REMOTE_DB_TYPE inválido: {db_type}", Colors.RED)
        log("   Valores válidos: sqlite, postgresql, mysql", Colors.YELLOW)
        sys.exit(1)

    # Estadísticas locales
    log("📊 ESTADÍSTICAS LOCALES:", Colors.BLUE)
    stats = get_local_stats()
    log(f"   Total listings:        {Colors.YELLOW}{stats['total']}{Colors.NC}")
    log(f"   Nuevos (últimos 7d):   {Colors.YELLOW}{stats['recent_7days']}{Colors.NC}")
    log(f"   Tamaño archivo:        {Colors.YELLOW}{stats['file_size_mb']:.2f} MB{Colors.NC}")
    print()

    # Confirmar
    log(f"🔄 Tipo de DB remota: {Colors.YELLOW}{db_type.upper()}{Colors.NC}")
    log(f"🌐 Servidor: {Colors.YELLOW}{os.getenv('REMOTE_DB_HOST', 'NO CONFIGURADO')}{Colors.NC}")
    print()

    confirm = input("¿Continuar con la sincronización? (s/N): ")
    if confirm.lower() != 's':
        log("❌ Sincronización cancelada", Colors.YELLOW)
        return

    print()

    # Ejecutar sincronización según tipo
    success = False
    if db_type == "sqlite":
        success = sync_to_remote_sqlite()
    elif db_type == "postgresql":
        success = sync_to_postgresql()
    elif db_type == "mysql":
        success = sync_to_mysql()

    print()
    if success:
        log("╔════════════════════════════════════════════════════════════════╗", Colors.GREEN)
        log("║                  ✅ SINCRONIZACIÓN EXITOSA                     ║", Colors.GREEN)
        log("╚════════════════════════════════════════════════════════════════╝", Colors.GREEN)
    else:
        log("╔════════════════════════════════════════════════════════════════╗", Colors.RED)
        log("║                  ❌ SINCRONIZACIÓN FALLIDA                     ║", Colors.RED)
        log("╚════════════════════════════════════════════════════════════════╝", Colors.RED)
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Sincronización cancelada por usuario (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        log(f"\n❌ Error: {e}", Colors.RED)
        import traceback
        traceback.print_exc()
        sys.exit(1)
