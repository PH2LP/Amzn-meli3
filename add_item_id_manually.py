#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para agregar item_ids manualmente a la base de datos.

Uso:
    python3 add_item_id_manually.py MLM123456 B0ABC123XYZ
    python3 add_item_id_manually.py --file item_ids.txt
    python3 add_item_id_manually.py --interactive

Formato del archivo (item_ids.txt):
    MLM123456 B0ABC123XYZ
    MLM789012 B0DEF456GHI
    ...
"""

import os
import sys
import sqlite3
from pathlib import Path

DB_PATH = "storage/listings_database.db"


def update_item_id(item_id, asin):
    """Actualiza el item_id para un ASIN en la BD"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Base de datos no encontrada: {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Verificar si existe el ASIN
    cursor.execute("SELECT id, title FROM listings WHERE asin = ?", (asin,))
    row = cursor.fetchone()

    if not row:
        print(f"❌ ASIN no encontrado en BD: {asin}")
        conn.close()
        return False

    # Actualizar item_id
    cursor.execute("""
        UPDATE listings
        SET item_id = ?
        WHERE asin = ?
    """, (item_id, asin))

    conn.commit()
    conn.close()

    print(f"✅ {asin} → {item_id}")
    return True


def interactive_mode():
    """Modo interactivo para agregar item_ids"""
    print("=" * 80)
    print("📝 MODO INTERACTIVO - Agregar Item IDs")
    print("=" * 80)
    print()
    print("Ingresa los datos solicitados (o 'q' para salir)")
    print()

    while True:
        print("-" * 80)
        item_id = input("Item ID de MercadoLibre (ej: MLM123456): ").strip()

        if item_id.lower() == 'q':
            break

        if not item_id:
            print("⚠️ Item ID vacío, intenta de nuevo")
            continue

        asin = input("ASIN de Amazon (ej: B0ABC123XYZ): ").strip().upper()

        if asin.lower() == 'q':
            break

        if not asin or len(asin) != 10:
            print("⚠️ ASIN inválido (debe tener 10 caracteres)")
            continue

        update_item_id(item_id, asin)
        print()

    print("\n✅ Modo interactivo finalizado")


def from_file(filepath):
    """Lee item_ids desde un archivo"""
    if not os.path.exists(filepath):
        print(f"❌ Archivo no encontrado: {filepath}")
        return

    print(f"📄 Leyendo desde: {filepath}")
    print()

    updated = 0
    errors = 0

    with open(filepath, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # Saltar líneas vacías o comentarios
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) != 2:
                print(f"⚠️ Línea {line_num}: formato inválido (se esperan 2 columnas)")
                errors += 1
                continue

            item_id, asin = parts
            asin = asin.upper()

            if update_item_id(item_id, asin):
                updated += 1
            else:
                errors += 1

    print()
    print(f"📊 Resumen: {updated} actualizados, {errors} errores")


def main():
    if len(sys.argv) == 1 or sys.argv[1] == "--interactive":
        # Modo interactivo
        interactive_mode()

    elif sys.argv[1] == "--file":
        # Desde archivo
        if len(sys.argv) < 3:
            print("❌ Falta el path del archivo")
            print("Uso: python3 add_item_id_manually.py --file item_ids.txt")
            sys.exit(1)

        from_file(sys.argv[2])

    elif len(sys.argv) == 3:
        # Desde argumentos de línea de comando
        item_id = sys.argv[1]
        asin = sys.argv[2].upper()

        if len(asin) != 10:
            print(f"❌ ASIN inválido: {asin} (debe tener 10 caracteres)")
            sys.exit(1)

        if update_item_id(item_id, asin):
            print("\n✅ Item ID actualizado exitosamente")
        else:
            sys.exit(1)

    else:
        print("Uso:")
        print("  python3 add_item_id_manually.py MLM123456 B0ABC123XYZ")
        print("  python3 add_item_id_manually.py --file item_ids.txt")
        print("  python3 add_item_id_manually.py --interactive")
        sys.exit(1)


if __name__ == "__main__":
    main()
