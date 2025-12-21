#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para limpiar productos duplicados en MercadoLibre
Elimina publicaciones duplicadas dejando solo 1 por ASIN+país

IMPORTANTE: Este script BORRA publicaciones permanentemente.
Asegúrate de revisar el reporte de duplicados antes de ejecutar.

Uso:
    # 1. Detectar duplicados primero
    python3 scripts/tools/detect_duplicates.py

    # 2. Revisar el reporte: storage/logs/duplicates_report.json

    # 3. Limpiar duplicados (modo interactivo)
    python3 scripts/tools/clean_duplicates.py

    # 4. Limpiar duplicados (modo automático - PELIGROSO)
    python3 scripts/tools/clean_duplicates.py --auto
"""

import os
import sys
import json
import time
import requests
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env
load_dotenv(override=True)
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")

if not ML_ACCESS_TOKEN:
    print("❌ Falta ML_ACCESS_TOKEN en .env")
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"}
API = "https://api.mercadolibre.com"


def delete_item(item_id):
    """
    Elimina un item de MercadoLibre (cambia status a closed)

    Returns:
        bool: True si se eliminó exitosamente
    """
    try:
        url = f"{API}/items/{item_id}"
        payload = {
            "status": "closed",
            "deleted": True
        }

        response = requests.put(url, headers=HEADERS, json=payload, timeout=10)
        response.raise_for_status()

        # Verificar que se cerró correctamente
        result = response.json()
        if result.get("status") == "closed":
            return True
        else:
            print(f"⚠️  {item_id}: status = {result.get('status')} (esperaba 'closed')")
            return False

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"⚠️  {item_id}: Item no encontrado (ya fue eliminado?)")
            return True  # Considerar como éxito si ya no existe
        else:
            print(f"❌ {item_id}: Error HTTP {e.response.status_code}")
            print(f"   {e.response.text}")
            return False
    except Exception as e:
        print(f"❌ {item_id}: Error eliminando - {e}")
        return False


def load_duplicates_report():
    """
    Carga el reporte de duplicados generado por detect_duplicates.py

    Returns:
        dict: Reporte de duplicados o None si no existe
    """
    report_path = Path("storage/logs/duplicates_report.json")

    if not report_path.exists():
        print(f"❌ No se encontró el reporte de duplicados en: {report_path}")
        print(f"\n💡 Ejecuta primero: python3 scripts/tools/detect_duplicates.py")
        return None

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error leyendo reporte: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Limpia productos duplicados en MercadoLibre")
    parser.add_argument("--auto", action="store_true", help="Modo automático (sin confirmación)")
    parser.add_argument("--dry-run", action="store_true", help="Simular eliminación sin ejecutar")
    args = parser.parse_args()

    print("\n" + "="*70)
    print("🧹 LIMPIADOR DE DUPLICADOS EN MERCADOLIBRE")
    print("="*70 + "\n")

    # 1. Cargar reporte de duplicados
    report = load_duplicates_report()
    if not report:
        sys.exit(1)

    duplicates = [d for d in report["duplicates"] if d["is_duplicate"]]

    if not duplicates:
        print("✅ No hay duplicados para eliminar")
        return

    # 2. Mostrar resumen
    print(f"📊 RESUMEN DEL REPORTE:")
    print(f"   • Total items: {report['total_items']}")
    print(f"   • ASINs con duplicados: {report['total_asins_with_duplicates']}")
    print(f"   • Items duplicados a eliminar: {len(duplicates)}")
    print()

    # 3. Mostrar items a eliminar
    print("🗑️  ITEMS QUE SERÁN ELIMINADOS:")
    print("-" * 70)
    for dup in duplicates:
        print(f"   {dup['item_id']} ({dup['site_id']}) - {dup['asin']}")
        print(f"      {dup['title'][:60]}")
        print(f"      {dup['permalink']}")
        print()

    # 4. Confirmación (a menos que sea modo auto)
    if not args.auto and not args.dry_run:
        print("="*70)
        print("⚠️  ADVERTENCIA: Esta acción es PERMANENTE")
        print("   Los items eliminados NO se pueden recuperar")
        print("="*70)
        confirm = input(f"\n¿Eliminar {len(duplicates)} items duplicados? (escribe 'SI' para confirmar): ")

        if confirm.strip() != "SI":
            print("\n❌ Operación cancelada por el usuario")
            return

    # 5. Eliminar duplicados
    print("\n" + "="*70)
    print("🗑️  ELIMINANDO DUPLICADOS...")
    print("="*70 + "\n")

    deleted_count = 0
    failed_count = 0
    deleted_items = []
    failed_items = []

    for i, dup in enumerate(duplicates, 1):
        item_id = dup["item_id"]
        print(f"[{i}/{len(duplicates)}] Eliminando {item_id}...", end=" ")

        if args.dry_run:
            print("(DRY-RUN - no eliminado)")
            deleted_count += 1
            deleted_items.append(item_id)
        else:
            if delete_item(item_id):
                print("✅ Eliminado")
                deleted_count += 1
                deleted_items.append(item_id)
            else:
                print("❌ Error")
                failed_count += 1
                failed_items.append(item_id)

            # Rate limiting: esperar 0.5s entre eliminaciones
            time.sleep(0.5)

    # 6. Resumen final
    print("\n" + "="*70)
    print("📊 RESUMEN FINAL:")
    print(f"   ✅ Eliminados exitosamente: {deleted_count}")
    if failed_count > 0:
        print(f"   ❌ Errores: {failed_count}")
        print(f"\n   Items con error:")
        for item_id in failed_items:
            print(f"      • {item_id}")
    print("="*70 + "\n")

    # 7. Guardar log de eliminación
    cleanup_log_path = Path("storage/logs/cleanup_log.json")
    cleanup_log_path.parent.mkdir(parents=True, exist_ok=True)

    cleanup_log = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "dry-run" if args.dry_run else "real",
        "total_deleted": deleted_count,
        "total_failed": failed_count,
        "deleted_items": deleted_items,
        "failed_items": failed_items
    }

    with open(cleanup_log_path, "w", encoding="utf-8") as f:
        json.dump(cleanup_log, f, indent=2, ensure_ascii=False)

    print(f"💾 Log guardado en: {cleanup_log_path}")

    if not args.dry_run and deleted_count > 0:
        print(f"\n✅ Limpieza completada exitosamente")
        print(f"💡 Ejecuta de nuevo detect_duplicates.py para verificar que no quedan duplicados")


if __name__ == "__main__":
    main()
