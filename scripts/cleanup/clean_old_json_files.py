#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Limpia archivos JSON de ASINs que ya están guardados en la base de datos.

Esto ahorra espacio en disco:
- 50,000 ASINs × 50KB = 2.5 GB innecesarios

El sistema de auto-answer descargará temporalmente si necesita el JSON.
"""

import os
import sqlite3
import glob
from pathlib import Path

DB_PATH = "storage/listings_database.db"
ASINS_JSON_DIR = "storage/asins_json"
MINI_ML_DIR = "storage/logs/publish_ready"

def get_asins_from_db():
    """Obtiene todos los ASINs que están en la base de datos"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT asin FROM listings WHERE mini_ml_data IS NOT NULL")
        asins = [row[0] for row in cursor.fetchall()]

        conn.close()
        return set(asins)

    except Exception as e:
        print(f"❌ Error leyendo DB: {e}")
        return set()

def clean_json_files(dry_run=False):
    """
    Elimina archivos JSON de ASINs que ya están en DB.

    Args:
        dry_run: Si es True, solo muestra qué archivos se eliminarían
    """
    print("🔍 Obteniendo ASINs de la base de datos...")
    db_asins = get_asins_from_db()

    if not db_asins:
        print("⚠️  No hay ASINs en la base de datos")
        return

    print(f"✅ Encontrados {len(db_asins)} ASINs en DB")

    # 1. Limpiar asins_json/
    print(f"\n🧹 Limpiando {ASINS_JSON_DIR}...")

    asins_json_pattern = f"{ASINS_JSON_DIR}/*.json"
    asins_json_files = glob.glob(asins_json_pattern)

    deleted_asins = 0
    saved_space_asins = 0

    for file_path in asins_json_files:
        filename = os.path.basename(file_path)
        asin = filename.replace(".json", "")

        if asin in db_asins:
            file_size = os.path.getsize(file_path)

            if dry_run:
                print(f"   [DRY-RUN] Eliminaría: {filename} ({file_size / 1024:.1f} KB)")
            else:
                os.remove(file_path)
                deleted_asins += 1
                saved_space_asins += file_size

    # 2. Limpiar mini_ml files
    print(f"\n🧹 Limpiando {MINI_ML_DIR}...")

    mini_ml_pattern = f"{MINI_ML_DIR}/*_mini_ml.json"
    mini_ml_files = glob.glob(mini_ml_pattern)

    deleted_mini = 0
    saved_space_mini = 0

    for file_path in mini_ml_files:
        filename = os.path.basename(file_path)
        asin = filename.replace("_mini_ml.json", "")

        if asin in db_asins:
            file_size = os.path.getsize(file_path)

            if dry_run:
                print(f"   [DRY-RUN] Eliminaría: {filename} ({file_size / 1024:.1f} KB)")
            else:
                os.remove(file_path)
                deleted_mini += 1
                saved_space_mini += file_size

    # 3. Resumen
    print("\n" + "="*60)
    print("📊 RESUMEN DE LIMPIEZA")
    print("="*60)

    if dry_run:
        print("🧪 MODO DRY-RUN (no se eliminó nada)")

    print(f"\nASINs JSON:")
    print(f"   Archivos: {deleted_asins} eliminados")
    print(f"   Espacio: {saved_space_asins / (1024*1024):.1f} MB liberados")

    print(f"\nMini ML JSON:")
    print(f"   Archivos: {deleted_mini} eliminados")
    print(f"   Espacio: {saved_space_mini / (1024*1024):.1f} MB liberados")

    total_space = (saved_space_asins + saved_space_mini) / (1024*1024)
    print(f"\n💾 TOTAL LIBERADO: {total_space:.1f} MB")
    print("="*60)

    if not dry_run:
        print("\n✅ Limpieza completada")
        print("ℹ️  El auto-answer descargará temporalmente si necesita un JSON")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Limpiar archivos JSON de productos en DB")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué se eliminaría")
    parser.add_argument("--force", action="store_true", help="Eliminar sin confirmar")

    args = parser.parse_args()

    if args.dry_run:
        print("🧪 MODO DRY-RUN - No se eliminará nada\n")
        clean_json_files(dry_run=True)
    else:
        if not args.force:
            print("⚠️  Esta operación eliminará archivos JSON de productos ya en DB")
            print("   (El auto-answer los descargará temporalmente si los necesita)")
            confirm = input("\n¿Continuar? (yes/no): ")

            if confirm.lower() != "yes":
                print("❌ Operación cancelada")
                exit(0)

        clean_json_files(dry_run=False)
