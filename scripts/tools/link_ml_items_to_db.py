#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCRIPT PARA VINCULAR PRODUCTOS DE MERCADOLIBRE CON LA BASE DE DATOS
====================================================================
Este script:
1. Obtiene todos los productos activos de MercadoLibre
2. Extrae el GTIN de cada producto
3. Busca el ASIN correspondiente en la BD usando el title match
4. Actualiza la BD con el item_id de MercadoLibre

Esto permite que sync_amazon_ml.py pueda sincronizar los productos.
"""

import os
import sys
import json
import sqlite3
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(override=True)

# Configuración
DB_PATH = "storage/listings_database.db"
ML_API = "https://api.mercadolibre.com"
ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
USER_ID = "2629793984"

# Logs
LOG_DIR = Path("logs/sync")
LOG_DIR.mkdir(parents=True, exist_ok=True)

def get_all_ml_items():
    """
    Obtiene todos los items activos de MercadoLibre.
    Retorna lista de item_ids.
    """
    print("📋 Obteniendo todos los productos de MercadoLibre...")

    url = f"{ML_API}/users/{USER_ID}/items/search"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    all_items = []
    offset = 0
    limit = 50

    while True:
        params = {
            "status": "active",
            "limit": limit,
            "offset": offset
        }

        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()

            items = data.get("results", [])
            if not items:
                break

            all_items.extend(items)

            total = data.get("paging", {}).get("total", 0)
            print(f"   Obtenidos {len(all_items)}/{total} productos...")

            if len(all_items) >= total:
                break

            offset += limit

        except Exception as e:
            print(f"⚠️ Error obteniendo items: {e}")
            break

    print(f"✅ Total de productos obtenidos: {len(all_items)}")
    return all_items


def get_item_details(item_id):
    """
    Obtiene los detalles de un item de MercadoLibre.
    Retorna dict con: item_id, title, gtin
    """
    url = f"{ML_API}/items/{item_id}"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()

        # Extraer GTIN de attributes
        gtin = None
        for attr in data.get("attributes", []):
            if attr.get("id") == "GTIN":
                gtin = attr.get("value_name")
                break

        return {
            "item_id": data.get("id"),
            "title": data.get("title"),
            "gtin": gtin,
            "price": data.get("price")
        }

    except Exception as e:
        print(f"⚠️ Error obteniendo detalles de {item_id}: {e}")
        return None


def find_asin_by_title(title):
    """
    Busca un ASIN en la BD usando el título.
    Hace match parcial del título.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Extraer palabras clave del título (primeras 5 palabras significativas)
    words = [w for w in title.split() if len(w) > 3][:5]

    # Buscar por coincidencia de palabras
    for word in words:
        cursor.execute("""
            SELECT asin, title
            FROM listings
            WHERE title LIKE ?
            LIMIT 1
        """, (f"%{word}%",))

        row = cursor.fetchone()
        if row:
            conn.close()
            return dict(row)

    conn.close()
    return None


def update_item_id_in_db(asin, item_id):
    """Actualiza el item_id en la base de datos para un ASIN"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Primero verificar si este item_id ya existe
        cursor.execute("SELECT asin FROM listings WHERE item_id = ?", (item_id,))
        existing = cursor.fetchone()

        if existing:
            existing_asin = existing[0]
            if existing_asin == asin:
                # Ya está vinculado correctamente
                conn.close()
                return False
            else:
                # El item_id pertenece a otro ASIN - skip
                conn.close()
                return False

        # Solo actualizar si el item_id está vacío
        cursor.execute("""
            UPDATE listings
            SET item_id = ?,
                date_updated = ?
            WHERE asin = ?
            AND (item_id IS NULL OR item_id = '')
        """, (item_id, datetime.now().isoformat(), asin))

        conn.commit()
        affected = cursor.rowcount
        conn.close()

        return affected > 0

    except sqlite3.IntegrityError:
        conn.close()
        return False


def main():
    """Función principal"""
    print("=" * 80)
    print("🔗 VINCULANDO PRODUCTOS DE MERCADOLIBRE CON BASE DE DATOS")
    print("=" * 80)
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Verificar BD
    if not os.path.exists(DB_PATH):
        print(f"❌ No se encontró la base de datos: {DB_PATH}")
        sys.exit(1)

    # Obtener todos los items de ML
    ml_items = get_all_ml_items()

    if not ml_items:
        print("⚠️ No se encontraron items en MercadoLibre")
        sys.exit(0)

    print()
    print("🔍 Procesando items y vinculando con BD...")
    print()

    # Estadísticas
    stats = {
        "total": len(ml_items),
        "linked": 0,
        "not_found": 0,
        "errors": 0
    }

    linked_items = []

    # Procesar cada item
    for i, item_id in enumerate(ml_items, 1):
        print(f"[{i}/{len(ml_items)}] Procesando {item_id}...", end=" ")

        # Obtener detalles del item
        details = get_item_details(item_id)

        if not details:
            print("❌ Error obteniendo detalles")
            stats["errors"] += 1
            continue

        title = details["title"]

        # Buscar ASIN correspondiente
        match = find_asin_by_title(title)

        if match:
            asin = match["asin"]

            # Actualizar BD
            if update_item_id_in_db(asin, item_id):
                print(f"✅ Vinculado con ASIN {asin}")
                stats["linked"] += 1

                linked_items.append({
                    "item_id": item_id,
                    "asin": asin,
                    "title": title[:60]
                })
            else:
                print(f"⚠️ Error actualizando BD para {asin}")
                stats["errors"] += 1
        else:
            print(f"⚠️ No encontrado en BD")
            stats["not_found"] += 1

    # Guardar log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"link_ml_{timestamp}.json"

    log_data = {
        "timestamp": datetime.now().isoformat(),
        "statistics": stats,
        "linked_items": linked_items
    }

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    # Resumen
    print()
    print("=" * 80)
    print("📊 RESUMEN DE VINCULACIÓN")
    print("=" * 80)
    print(f"Total procesados:     {stats['total']}")
    print(f"Vinculados exitosamente: {stats['linked']}")
    print(f"No encontrados en BD:    {stats['not_found']}")
    print(f"Errores:                 {stats['errors']}")
    print()
    print(f"📄 Log guardado en: {log_file}")
    print()
    print("✅ Proceso completado")
    print()
    print("Ahora puedes ejecutar sync_amazon_ml.py para sincronizar los productos.")


if __name__ == "__main__":
    main()
