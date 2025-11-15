#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTO-SYNC: Sincroniza automáticamente productos de ML con la BD
================================================================
Este script:
1. Obtiene productos nuevos/actualizados de MercadoLibre (últimos 7 días)
2. Los vincula con ASINs en la BD usando coincidencia de título
3. Guarda el item_id para que sync_amazon_ml.py pueda sincronizarlos

Se ejecuta automáticamente cada 1 hora para detectar nuevos productos.
"""

import os
import sys
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# Configuración
DB_PATH = "storage/listings_database.db"
ML_API = "https://api.mercadolibre.com"
ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
USER_ID = "2629793984"

LOG_DIR = Path("logs/sync")
LOG_DIR.mkdir(parents=True, exist_ok=True)

def get_recent_ml_items(days=7):
    """
    Obtiene items de ML actualizados en los últimos N días.
    Esto permite detectar nuevos productos sin procesar los 961 existentes.
    """
    print(f"📋 Buscando productos actualizados en los últimos {days} días...")

    url = f"{ML_API}/users/{USER_ID}/items/search"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    # Ordenar por última actualización (más recientes primero)
    params = {
        "status": "active",
        "limit": 50,
        "offset": 0,
        "order": "last_updated_desc"
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        items = data.get("results", [])
        print(f"✅ Encontrados {len(items)} productos recientes")
        return items

    except Exception as e:
        print(f"⚠️ Error obteniendo items: {e}")
        return []


def get_item_details(item_id):
    """Obtiene detalles de un item de ML"""
    url = f"{ML_API}/items/{item_id}"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()

        # Extraer GTIN
        gtin = None
        for attr in data.get("attributes", []):
            if attr.get("id") == "GTIN":
                gtin = attr.get("value_name")
                break

        # Verificar si fue actualizado recientemente
        last_updated = data.get("last_updated")

        return {
            "item_id": data.get("id"),
            "title": data.get("title"),
            "gtin": gtin,
            "price": data.get("price"),
            "last_updated": last_updated
        }

    except Exception as e:
        print(f"⚠️ Error obteniendo {item_id}: {e}")
        return None


def find_asin_by_title_smart(title):
    """
    Busca ASIN en la BD usando título.
    Estrategia: extraer palabras clave y buscar coincidencias.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Limpiar título y extraer palabras significativas
    import re
    # Remover caracteres especiales y split
    clean_title = re.sub(r'[^\w\s]', ' ', title)
    words = [w for w in clean_title.split() if len(w) > 3][:6]

    # Intentar match con múltiples palabras (mejor precisión)
    for num_words in range(min(4, len(words)), 0, -1):
        search_words = words[:num_words]
        pattern = '%'.join(search_words)

        cursor.execute("""
            SELECT asin, title, item_id
            FROM listings
            WHERE title LIKE ?
            LIMIT 1
        """, (f"%{pattern}%",))

        row = cursor.fetchone()
        if row:
            conn.close()
            return dict(row)

    conn.close()
    return None


def check_if_already_linked(item_id):
    """Verifica si un item_id ya está en la BD"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT asin FROM listings WHERE item_id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()

    return row is not None


def link_item_to_db(asin, item_id):
    """
    Vincula un item_id con un ASIN en la BD.
    Solo actualiza si no hay item_id previo.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
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
        # El item_id ya existe en otro registro
        conn.close()
        return False


def main():
    """Función principal"""
    print("=" * 80)
    print("🔄 AUTO-SYNC: MercadoLibre → Base de Datos")
    print("=" * 80)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Verificar BD
    if not os.path.exists(DB_PATH):
        print(f"❌ No existe BD: {DB_PATH}")
        sys.exit(1)

    # Obtener items recientes (últimos 7 días)
    ml_items = get_recent_ml_items(days=7)

    if not ml_items:
        print("✅ No hay items nuevos para procesar")
        sys.exit(0)

    print()
    print("🔍 Procesando items...")
    print()

    stats = {
        "total": len(ml_items),
        "linked": 0,
        "already_linked": 0,
        "not_found": 0,
        "errors": 0
    }

    linked_items = []

    for i, item_id in enumerate(ml_items, 1):
        print(f"[{i}/{len(ml_items)}] {item_id}...", end=" ")

        # Verificar si ya está vinculado
        if check_if_already_linked(item_id):
            print("⏭️  Ya vinculado")
            stats["already_linked"] += 1
            continue

        # Obtener detalles
        details = get_item_details(item_id)
        if not details:
            print("❌ Error")
            stats["errors"] += 1
            continue

        title = details["title"]

        # Buscar ASIN
        match = find_asin_by_title_smart(title)

        if match:
            asin = match["asin"]

            # Vincular
            if link_item_to_db(asin, item_id):
                print(f"✅ → {asin}")
                stats["linked"] += 1

                linked_items.append({
                    "item_id": item_id,
                    "asin": asin,
                    "title": title[:60],
                    "timestamp": datetime.now().isoformat()
                })
            else:
                print(f"⚠️ Ya existe")
                stats["already_linked"] += 1
        else:
            print(f"⚠️ No encontrado")
            stats["not_found"] += 1

    # Log
    if stats["linked"] > 0:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"auto_sync_{timestamp}.json"

        log_data = {
            "timestamp": datetime.now().isoformat(),
            "statistics": stats,
            "linked_items": linked_items
        }

        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

        print()
        print(f"📄 Log: {log_file}")

    # Resumen
    print()
    print("📊 RESUMEN")
    print("─" * 40)
    print(f"Total procesados:    {stats['total']}")
    print(f"Nuevos vinculados:   {stats['linked']}")
    print(f"Ya vinculados:       {stats['already_linked']}")
    print(f"No encontrados:      {stats['not_found']}")
    print(f"Errores:             {stats['errors']}")
    print()

    if stats["linked"] > 0:
        print(f"✅ {stats['linked']} productos nuevos sincronizados")
    else:
        print("✅ Todo al día")


if __name__ == "__main__":
    main()
