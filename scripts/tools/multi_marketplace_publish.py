#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
multi_marketplace_publish.py
═══════════════════════════════════════════════════════════════════════════════
PUBLICACIÓN MASIVA MULTI-MARKETPLACE
═══════════════════════════════════════════════════════════════════════════════

Publica automáticamente todos los productos en todos los marketplaces donde no están.

Usa la API de Global Listing de MercadoLibre para agregar marketplaces a items CBT.

Features:
- Detecta productos que no están en todos los marketplaces
- Publica masivamente en marketplaces faltantes
- Actualiza la base de datos con los nuevos item IDs
- Reporta éxitos y errores

Uso:
    python3 multi_marketplace_publish.py
"""

import os
import sys
import time
import json
import requests
import sqlite3
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env
load_dotenv(override=True)

# Configuración
ML_API = "https://api.mercadolibre.com"
ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
LOG_DIR = Path("logs/multi_marketplace")
LOG_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path("storage/listings_database.db")

# Marketplaces disponibles
ALL_MARKETPLACES = {"MLM", "MLB", "MLC", "MCO", "MLA"}

# Colores
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'


def log(msg, color=Colors.NC):
    """Print con color"""
    print(f"{color}{msg}{Colors.NC}")


def get_items_missing_marketplaces(limit=None):
    """
    Obtiene items de la DB que NO están en todos los marketplaces.

    Args:
        limit: Límite de items a procesar (None = todos)

    Returns:
        list: Lista de (item_id, marketplaces_faltantes, site_items)
    """
    log("\n📋 Analizando items en base de datos...", Colors.CYAN)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = "SELECT item_id, site_items FROM listings WHERE item_id IS NOT NULL"
    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)

    items_to_publish = []

    for row in cursor.fetchall():
        item_id = row[0]
        site_items_str = row[1]

        # Si no hay site_items, necesita publicarse en todos
        if not site_items_str:
            items_to_publish.append((item_id, ALL_MARKETPLACES, []))
            continue

        try:
            site_items = json.loads(site_items_str)

            # Extraer marketplaces donde YA está publicado (sin errores)
            published_sites = {
                item.get('site_id')
                for item in site_items
                if 'site_id' in item and 'error' not in item and item.get('item_id')
            }

            # Calcular marketplaces faltantes
            missing = ALL_MARKETPLACES - published_sites

            if missing:
                items_to_publish.append((item_id, missing, site_items))

        except Exception as e:
            log(f"⚠️  Error parseando site_items de {item_id}: {e}", Colors.YELLOW)
            continue

    conn.close()

    log(f"✅ Items analizados: {cursor.rowcount if cursor.rowcount > 0 else 'N/A'}", Colors.GREEN)
    log(f"✅ Items que necesitan publicación: {len(items_to_publish)}", Colors.GREEN)

    return items_to_publish


def publish_to_marketplace(item_id, site_id, logistic_type="remote"):
    """
    Publica un item CBT en un marketplace específico.

    Args:
        item_id: ID del item CBT (ej: CBT123456)
        site_id: Marketplace destino (MLM, MLB, etc)
        logistic_type: Tipo logístico (remote/fulfillment)

    Returns:
        dict: Resultado con success, new_item_id, error
    """
    url = f"{ML_API}/global/items/{item_id}"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    body = {
        "sites_to_sell": [
            {
                "site_id": site_id,
                "logistic_type": logistic_type,
                "listing_type_id": "gold_pro"  # Premium listing
            }
        ]
    }

    try:
        r = requests.post(url, headers=headers, json=body, timeout=60)

        if r.status_code == 200:
            data = r.json()

            # La respuesta incluye el array site_items (NO sites_to_sell)
            site_items = data.get("site_items", [])

            # Buscar el resultado para este site_id
            for site in site_items:
                if site.get("site_id") == site_id and site.get("logistic_type") == logistic_type:
                    # Verificar si hay error
                    if "error" in site:
                        error = site.get("error", {})
                        error_msg = error.get("message", "Unknown error")

                        # Extraer mensaje más específico si existe
                        causes = error.get("cause", [])
                        if causes and len(causes) > 0:
                            specific_msg = causes[0].get("message", "")
                            error_code = causes[0].get("code", "")
                            if specific_msg:
                                error_msg = f"{error_msg}: {specific_msg} ({error_code})"

                        return {
                            "success": False,
                            "error": error_msg
                        }

                    # Si no hay error, debe tener item_id
                    new_item_id = site.get("item_id")
                    if new_item_id:
                        return {
                            "success": True,
                            "item_id": new_item_id,
                            "seller_id": site.get("seller_id"),
                            "site_id": site_id,
                            "logistic_type": logistic_type
                        }

            return {
                "success": False,
                "error": "Site no encontrado en la respuesta"
            }
        else:
            error_data = r.json() if r.text else {}
            error_msg = error_data.get("message", r.text[:200])
            return {
                "success": False,
                "error": f"HTTP {r.status_code}: {error_msg}"
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def update_database_with_new_item(global_item_id, new_site_data):
    """
    Actualiza la DB con un nuevo marketplace item.

    Args:
        global_item_id: ID del item global CBT
        new_site_data: Dict con {item_id, seller_id, site_id, logistic_type}

    Returns:
        bool: True si se actualizó correctamente
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Obtener site_items actual
        cursor.execute("SELECT site_items FROM listings WHERE item_id = ?", (global_item_id,))
        row = cursor.fetchone()

        if not row:
            log(f"⚠️  {global_item_id}: No encontrado en DB", Colors.YELLOW)
            return False

        # Parsear site_items actual
        current_site_items = []
        if row[0]:
            try:
                current_site_items = json.loads(row[0])
            except:
                current_site_items = []

        # Verificar si ya existe este site_id + logistic_type
        existing = False
        for item in current_site_items:
            if (item.get("site_id") == new_site_data["site_id"] and
                item.get("logistic_type") == new_site_data["logistic_type"]):
                # Actualizar
                item["item_id"] = new_site_data["item_id"]
                item["seller_id"] = new_site_data["seller_id"]
                # Remover error si existía
                if "error" in item:
                    del item["error"]
                existing = True
                break

        # Si no existe, agregar
        if not existing:
            current_site_items.append({
                "item_id": new_site_data["item_id"],
                "seller_id": new_site_data["seller_id"],
                "site_id": new_site_data["site_id"],
                "logistic_type": new_site_data["logistic_type"]
            })

        # Actualizar DB
        site_items_json = json.dumps(current_site_items)
        cursor.execute("""
            UPDATE listings
            SET site_items = ?,
                date_updated = ?
            WHERE item_id = ?
        """, (site_items_json, datetime.now().isoformat(), global_item_id))

        conn.commit()
        return True

    except Exception as e:
        log(f"❌ Error actualizando DB para {global_item_id}: {e}", Colors.RED)
        return False
    finally:
        conn.close()


def main():
    log("=" * 80, Colors.BLUE)
    log("🚀 PUBLICACIÓN MASIVA MULTI-MARKETPLACE", Colors.BLUE)
    log("=" * 80, Colors.BLUE)
    log(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", Colors.CYAN)

    # Paso 1: Obtener items que necesitan publicación
    items_to_publish = get_items_missing_marketplaces()

    if not items_to_publish:
        log("\n✅ Todos los items ya están publicados en todos los marketplaces!", Colors.GREEN)
        return

    # Mostrar resumen
    log("\n" + "=" * 80, Colors.BLUE)
    log("📊 RESUMEN", Colors.BLUE)
    log("=" * 80, Colors.BLUE)

    total_publications = sum(len(missing) for _, missing, _ in items_to_publish)

    marketplaces_count = {}
    for _, missing, _ in items_to_publish:
        for site in missing:
            marketplaces_count[site] = marketplaces_count.get(site, 0) + 1

    log(f"Items a procesar:               {len(items_to_publish)}", Colors.CYAN)
    log(f"Total publicaciones nuevas:     {total_publications}", Colors.CYAN)
    log(f"\nPor marketplace:", Colors.CYAN)
    for site_id, count in sorted(marketplaces_count.items()):
        log(f"  {site_id}: {count}", Colors.CYAN)

    # Confirmar
    log("\n" + "=" * 80, Colors.YELLOW)
    log("⚠️  IMPORTANTE", Colors.YELLOW)
    log("=" * 80, Colors.YELLOW)
    log(f"Se van a crear {total_publications} nuevas publicaciones.", Colors.YELLOW)
    log("Esto puede tomar varios minutos.", Colors.YELLOW)

    confirm = input("\n¿Continuar? (s/n): ").strip().lower()
    if confirm != 's':
        log("\n❌ Operación cancelada", Colors.RED)
        return

    # Paso 2: Publicar
    log("\n" + "=" * 80, Colors.CYAN)
    log("📤 PUBLICANDO...", Colors.CYAN)
    log("=" * 80, Colors.CYAN)

    successful = 0
    errors = 0
    db_updated = 0

    for item_id, missing_sites, _ in items_to_publish:
        log(f"\n📦 {item_id}", Colors.BLUE)
        log(f"   Marketplaces faltantes: {', '.join(sorted(missing_sites))}", Colors.CYAN)

        for site_id in missing_sites:
            log(f"   → Publicando en {site_id}...", Colors.CYAN)

            result = publish_to_marketplace(item_id, site_id)

            if result["success"]:
                new_item_id = result["item_id"]
                log(f"   ✅ {site_id}: {new_item_id}", Colors.GREEN)
                successful += 1

                # Actualizar DB
                if update_database_with_new_item(item_id, result):
                    db_updated += 1

                # Rate limiting
                time.sleep(0.5)
            else:
                error_msg = result["error"]
                log(f"   ❌ {site_id}: {error_msg}", Colors.RED)
                errors += 1

    # Resumen final
    log("\n" + "=" * 80, Colors.BLUE)
    log("📈 RESUMEN FINAL", Colors.BLUE)
    log("=" * 80, Colors.BLUE)
    log(f"Publicaciones exitosas:         {successful}", Colors.GREEN)
    log(f"Errores:                        {errors}", Colors.RED)
    log(f"Items actualizados en DB:       {db_updated}", Colors.GREEN)

    if successful > 0:
        success_rate = (successful / total_publications) * 100
        log(f"Tasa de éxito:                  {success_rate:.1f}%", Colors.CYAN)

    # Guardar log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"multi_marketplace_{timestamp}.json"

    log_data = {
        "timestamp": timestamp,
        "total_items": len(items_to_publish),
        "total_publications": total_publications,
        "successful": successful,
        "errors": errors,
        "db_updated": db_updated
    }

    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    log(f"\n📄 Log guardado: {log_file}", Colors.CYAN)
    log("\n✅ Proceso completado", Colors.GREEN)

    if db_updated > 0:
        log(f"✅ El sync ahora puede actualizar precios en todos los marketplaces", Colors.GREEN)


if __name__ == "__main__":
    main()
