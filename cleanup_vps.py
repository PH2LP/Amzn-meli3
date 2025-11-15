#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLEANUP VPS - Limpieza de Archivos Obsoletos
==============================================
Limpia archivos del VPS que ya no se usan porque ahora todo
el pipeline de publicación se ejecuta desde Mac.

El VPS ahora solo tiene servicios autónomos:
- ML Token Loop (renovación de tokens)
- Auto-Answer (respuestas automáticas)
- Telegram Sales (notificaciones de ventas)

Uso:
    python3 cleanup_vps.py --dry-run    # Ver qué se borraría (sin borrar)
    python3 cleanup_vps.py              # Ejecutar limpieza real
"""

import sys
import subprocess
from datetime import datetime

# Configuración VPS
VPS_HOST = "138.197.32.67"
VPS_USER = "root"
VPS_PASSWORD = "koqven-1regka-nyfXiw"
VPS_PATH = "/opt/amz-ml-system"

# Colores
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'=' * 70}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'=' * 70}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

def ssh_command(command):
    """Ejecuta un comando SSH en el VPS"""
    full_cmd = f"sshpass -p '{VPS_PASSWORD}' ssh -o StrictHostKeyChecking=no {VPS_USER}@{VPS_HOST} '{command}'"

    try:
        result = subprocess.run(
            full_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e)
        }

# Archivos y directorios a eliminar
FILES_TO_DELETE = [
    # Scripts de pipeline obsoletos (ahora en Mac)
    "pipeline.py",
    "main.py",  # Si existe viejo

    # Scripts autónomos de búsqueda/publicación (pausados)
    "scripts/autonomous/autonomous_search_and_publish.py",

    # Scripts de fix/retry que ya no se usan
    "fix_all_errors.py",
    "fix_categories.py",
    "fix_categories_manual.py",
    "republish_failed.py",
    "retry_failed_8.py",
    "delete_all_listings.py",

    # Scripts de categorías híbridos (ahora category_matcher_v2)
    "ai_hybrid_categorizer.py",
    "find_category_with_ai_ml_hybrid.py",
    "find_correct_categories_with_ai.py",
    "find_flexible_category.py",

    # Scripts de sincronización (ahora en Mac)
    "sync_amazon_ml.py",

    # Scripts de templates globales (no se usan)
    "ml_global_templates.py",

    # Scripts de preguntas específicas (ahora auto_answer genérico)
    "answer_specific_question.py",

    # Scripts de características (se genera desde Mac)
    "generate_product_characteristics.py",

    # Scripts de datos de listings (se maneja desde Mac)
    "save_listing_data.py",

    # Archivos de texto de búsqueda
    "lego_top500.txt",
    "asins_reintentar.txt",

    # Loops de publicación obsoletos
    "autonomous_loop.sh",
    "auto_monitor.sh",

    # Scripts de regeneración (no necesarios)
    "regenerate_all_miniml.sh",

    # Reportes viejos
    "CAMBIOS_AUTOMATICOS.md",
    "MEJORAS_APLICADAS.md",
    "REPORTE_CALIDAD_FINAL.md",
    "REPORTE_PROGRESO.md",
    "STATUS_PARA_FELIPE.md",
]

DIRS_TO_DELETE = [
    # Directorio de cache viejo (se mantiene solo tokens)
    # "cache/",  # NO BORRAR - contiene tokens

    # Outputs viejos
    "outputs/",

    # Docs viejos
    "docs/",

    # Config viejo
    "config.yml",
]

# Archivos de logs viejos a limpiar
LOGS_TO_CLEAN = [
    "logs/pipeline.log",
    "logs/main2_*.log",
    "logs/test_*.log",
    "logs/sync_*.log",
    "logs/fix_*.log",
    "logs/final_publish_*.log",
]

def get_file_size(filepath):
    """Obtiene el tamaño de un archivo en el VPS"""
    result = ssh_command(f"cd {VPS_PATH} && du -sh {filepath} 2>/dev/null")
    if result["success"] and result["stdout"]:
        return result["stdout"].split()[0]
    return "N/A"

def check_files_exist():
    """Verifica qué archivos existen en el VPS"""
    print_header("VERIFICANDO ARCHIVOS EXISTENTES EN VPS")

    existing_files = []
    existing_dirs = []
    total_size = 0

    # Verificar archivos
    print(f"{Colors.BOLD}Archivos:{Colors.END}")
    for filepath in FILES_TO_DELETE:
        result = ssh_command(f"cd {VPS_PATH} && test -f {filepath} && echo 'EXISTS'")
        if result["success"] and "EXISTS" in result["stdout"]:
            size = get_file_size(filepath)
            existing_files.append((filepath, size))
            print(f"  ✓ {filepath} ({size})")
        else:
            print(f"  ✗ {filepath} (no existe)")

    # Verificar directorios
    print(f"\n{Colors.BOLD}Directorios:{Colors.END}")
    for dirpath in DIRS_TO_DELETE:
        result = ssh_command(f"cd {VPS_PATH} && test -d {dirpath} && echo 'EXISTS'")
        if result["success"] and "EXISTS" in result["stdout"]:
            size = get_file_size(dirpath)
            existing_dirs.append((dirpath, size))
            print(f"  ✓ {dirpath}/ ({size})")
        else:
            print(f"  ✗ {dirpath}/ (no existe)")

    return existing_files, existing_dirs

def delete_files(files, dry_run=False):
    """Elimina archivos del VPS"""
    print_header("ELIMINANDO ARCHIVOS")

    if dry_run:
        print_warning("MODO DRY-RUN - No se eliminará nada realmente\n")

    deleted_count = 0

    for filepath, size in files:
        if dry_run:
            print(f"  [DRY-RUN] Borraría: {filepath} ({size})")
            deleted_count += 1
        else:
            result = ssh_command(f"cd {VPS_PATH} && rm -f {filepath}")
            if result["success"]:
                print_success(f"Eliminado: {filepath} ({size})")
                deleted_count += 1
            else:
                print_error(f"Error eliminando: {filepath}")

    return deleted_count

def delete_directories(dirs, dry_run=False):
    """Elimina directorios del VPS"""
    print_header("ELIMINANDO DIRECTORIOS")

    if dry_run:
        print_warning("MODO DRY-RUN - No se eliminará nada realmente\n")

    deleted_count = 0

    for dirpath, size in dirs:
        if dry_run:
            print(f"  [DRY-RUN] Borraría: {dirpath}/ ({size})")
            deleted_count += 1
        else:
            result = ssh_command(f"cd {VPS_PATH} && rm -rf {dirpath}")
            if result["success"]:
                print_success(f"Eliminado: {dirpath}/ ({size})")
                deleted_count += 1
            else:
                print_error(f"Error eliminando: {dirpath}/")

    return deleted_count

def clean_old_logs(dry_run=False):
    """Limpia logs viejos (mayores a 30 días)"""
    print_header("LIMPIANDO LOGS VIEJOS (>30 días)")

    if dry_run:
        print_warning("MODO DRY-RUN - No se eliminará nada realmente\n")

    # Encontrar logs viejos
    result = ssh_command(
        f"cd {VPS_PATH} && find logs/ -type f -name '*.log' -mtime +30 2>/dev/null"
    )

    if result["success"] and result["stdout"]:
        old_logs = result["stdout"].split('\n')
        print_info(f"Encontrados {len(old_logs)} logs viejos")

        if dry_run:
            for log in old_logs[:5]:  # Mostrar solo primeros 5
                print(f"  [DRY-RUN] Borraría: {log}")
            if len(old_logs) > 5:
                print(f"  [DRY-RUN] ... y {len(old_logs) - 5} más")
        else:
            # Eliminar logs viejos
            result = ssh_command(
                f"cd {VPS_PATH} && find logs/ -type f -name '*.log' -mtime +30 -delete"
            )
            if result["success"]:
                print_success(f"Eliminados {len(old_logs)} logs viejos")
            else:
                print_error("Error eliminando logs viejos")

        return len(old_logs)
    else:
        print_info("No se encontraron logs viejos para eliminar")
        return 0

def create_backup(dry_run=False):
    """Crea backup antes de limpiar"""
    print_header("CREANDO BACKUP ANTES DE LIMPIAR")

    if dry_run:
        print_warning("MODO DRY-RUN - No se creará backup\n")
        return True

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_before_cleanup_{timestamp}.tar.gz"

    # Crear backup de archivos importantes
    print_info("Creando backup de archivos críticos...")

    result = ssh_command(
        f"cd {VPS_PATH} && tar -czf /tmp/{backup_name} "
        f".env storage/listings_database.db storage/pipeline_state.db "
        f"cache/amazon_token.json 2>/dev/null"
    )

    if result["success"]:
        print_success(f"Backup creado: /tmp/{backup_name}")
        return True
    else:
        print_error("Error creando backup")
        return False

def show_summary(files_count, dirs_count, logs_count, dry_run=False):
    """Muestra resumen final"""
    print_header("RESUMEN DE LIMPIEZA")

    print(f"{Colors.BOLD}Archivos eliminados:{Colors.END} {files_count}")
    print(f"{Colors.BOLD}Directorios eliminados:{Colors.END} {dirs_count}")
    print(f"{Colors.BOLD}Logs viejos eliminados:{Colors.END} {logs_count}")
    print(f"{Colors.BOLD}Total de items:{Colors.END} {files_count + dirs_count + logs_count}")

    if dry_run:
        print_warning("\nEsto fue una simulación (--dry-run)")
        print_info("Ejecutá sin --dry-run para hacer la limpieza real")
    else:
        print_success("\n✅ Limpieza completada exitosamente")

        # Verificar espacio liberado
        result = ssh_command("df -h / | tail -1")
        if result["success"] and result["stdout"]:
            parts = result["stdout"].split()
            if len(parts) >= 5:
                print(f"\n{Colors.BOLD}Espacio en disco:{Colors.END}")
                print(f"  Disponible: {parts[3]}")
                print(f"  Usado: {parts[4]}")

def main():
    """Función principal"""
    dry_run = "--dry-run" in sys.argv

    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}CLEANUP VPS - Limpieza de Archivos Obsoletos{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")
    print(f"{Colors.WHITE}Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}")
    print(f"{Colors.WHITE}VPS: {VPS_USER}@{VPS_HOST}{Colors.END}")

    if dry_run:
        print(f"{Colors.YELLOW}Modo: DRY-RUN (simulación){Colors.END}")
    else:
        print(f"{Colors.RED}Modo: REAL (eliminará archivos){Colors.END}")

    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}\n")

    # Verificar conexión
    print_info("Verificando conexión al VPS...")
    result = ssh_command("echo 'OK'")
    if not result["success"] or "OK" not in result["stdout"]:
        print_error("No se pudo conectar al VPS")
        sys.exit(1)
    print_success("Conexión OK\n")

    # Verificar archivos existentes
    existing_files, existing_dirs = check_files_exist()

    if not existing_files and not existing_dirs:
        print_warning("\nNo hay archivos para eliminar. El VPS ya está limpio!")
        sys.exit(0)

    # Confirmar si no es dry-run
    if not dry_run:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️  ADVERTENCIA{Colors.END}")
        print(f"{Colors.RED}Esta operación eliminará {len(existing_files)} archivos y {len(existing_dirs)} directorios{Colors.END}")
        print(f"{Colors.YELLOW}¿Estás seguro? (escribe 'SI' para continuar){Colors.END}")

        confirmation = input("> ")
        if confirmation != "SI":
            print_warning("\nOperación cancelada por el usuario")
            sys.exit(0)

        # Crear backup
        if not create_backup(dry_run):
            print_error("\nNo se pudo crear backup. Abortando limpieza.")
            sys.exit(1)

    # Ejecutar limpieza
    files_deleted = delete_files(existing_files, dry_run)
    dirs_deleted = delete_directories(existing_dirs, dry_run)
    logs_deleted = clean_old_logs(dry_run)

    # Mostrar resumen
    show_summary(files_deleted, dirs_deleted, logs_deleted, dry_run)

    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠️  Operación interrumpida por el usuario{Colors.END}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}❌ Error inesperado: {e}{Colors.END}\n")
        sys.exit(1)
