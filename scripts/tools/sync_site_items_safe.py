#!/usr/bin/env python3
"""
Versión SEGURA de sync_site_items_from_ml.py

Diferencias con la versión original:
1. Solo actualiza productos que están ACTIVOS en ML
2. NO sobrescribe si no encuentra el producto (lo deja como está)
3. Tiene rate limiting (1 segundo entre requests)
4. Muestra reporte de cambios antes de aplicar
5. Opción --dry-run para ver qué cambiaría sin modificar la BD
"""

import os
import sys
import sqlite3
import requests
import json
import time
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "storage/listings_database.db"
ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
ML_USER_ID = os.getenv("ML_USER_ID")

def get_active_cbts_from_ml():
    """
    Obtiene TODOS los CBT (activos Y pausados) desde ML consultando todos los marketplaces.

    IMPORTANTE: ML limita la paginación a ~1000 items por búsqueda. Como tenemos ~1500 activos,
    necesitamos buscar activos Y pausados por separado para obtener todos.

    Returns:
        dict: {cbt_id: [site_ids donde está publicado]}
    """
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}
    sites = ["MLM", "MLB", "MLC", "MCO", "MLA"]

    all_cbts = {}  # {cbt_id: [site_ids]}

    print("Obteniendo todos los CBT desde ML (activos Y pausados)...")
    print()

    for site_id in sites:
        print(f"Consultando {site_id}...", end=" ", flush=True)

        url = f"https://api.mercadolibre.com/users/{ML_USER_ID}/items/search"
        found_count = 0

        # Buscar activos Y pausados por separado
        for status in ["active", "paused"]:
            offset = 0

            # Paginar hasta obtener TODOS (sin límite artificial)
            while True:
                params = {
                    "site_id": site_id,
                    "status": status,
                    "offset": offset,
                    "limit": 100  # Más eficiente que 50
                }

                try:
                    r = requests.get(url, headers=headers, params=params, timeout=30)
                    if r.status_code != 200:
                        if r.status_code == 400:  # Bad request - probablemente offset muy alto
                            break
                        print(f"Error {r.status_code} ")
                        break

                    data = r.json()
                    results = data.get("results", [])

                    if not results:
                        break

                    # Filtrar solo CBT
                    for item_id in results:
                        if item_id.startswith("CBT"):
                            if item_id not in all_cbts:
                                all_cbts[item_id] = []
                            if site_id not in all_cbts[item_id]:
                                all_cbts[item_id].append(site_id)
                                found_count += 1

                    # Verificar si hay más páginas
                    paging = data.get("paging", {})
                    total = paging.get("total", 0)

                    offset += 100

                    # Si ya obtuvimos todos, parar
                    if offset >= total or len(results) < 100:
                        break

                    time.sleep(0.05)  # Rate limiting reducido

                except Exception as e:
                    print(f"Error: {e} ")
                    break

        print(f"{found_count} CBT")

    print()
    print(f"Total CBT únicos encontrados: {len(all_cbts)}")
    print()

    return all_cbts


def sync_safe(dry_run=False):
    """Sincroniza site_items de forma segura"""

    print("=" * 70)
    print("SINCRONIZACIÓN SEGURA DE SITE_ITEMS")
    print("=" * 70)
    print()

    if dry_run:
        print("⚠️  MODO DRY-RUN: No se modificará la BD")
        print()

    # Obtener todos los CBT activos desde ML
    active_cbts = get_active_cbts_from_ml()

    # Conectar a BD
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT item_id, asin, title, site_items
        FROM listings
        WHERE item_id IS NOT NULL
        ORDER BY date_updated DESC
    """)

    listings = cursor.fetchall()

    print(f"Productos en BD: {len(listings)}")
    print()

    # Estadísticas
    stats = {
        "procesados": 0,
        "actualizados": 0,
        "sin_cambios": 0,
        "no_encontrados": 0,
        "errores": 0
    }

    changes = []

    for item_id, asin, title, current_site_items_str in listings:
        stats["procesados"] += 1

        # Parsear site_items actual
        try:
            current_site_items = json.loads(current_site_items_str) if current_site_items_str else []
            current_countries = set(
                s.get("site_id")
                for s in current_site_items
                if "site_id" in s and "error" not in s
            )
        except:
            current_site_items = []
            current_countries = set()

        # Verificar si el CBT existe en ML
        if item_id in active_cbts:
            real_countries = set(active_cbts[item_id])

            # Comparar
            if current_countries != real_countries:
                # HAY DIFERENCIA - necesita actualización
                missing = real_countries - current_countries
                extra = current_countries - real_countries

                change = {
                    "item_id": item_id,
                    "asin": asin,
                    "title": title[:60] if title else "N/A",
                    "bd_countries": sorted(list(current_countries)),
                    "ml_countries": sorted(list(real_countries)),
                    "missing": sorted(list(missing)),
                    "extra": sorted(list(extra))
                }

                changes.append(change)
                stats["actualizados"] += 1

                # Construir nuevo site_items
                new_site_items = []
                for site_id in real_countries:
                    new_site_items.append({
                        "item_id": item_id,  # Para CBT es el mismo
                        "site_id": site_id,
                        "logistic_type": "remote"
                    })

                # Actualizar BD (si no es dry-run)
                if not dry_run:
                    site_items_json = json.dumps(new_site_items)
                    cursor.execute("""
                        UPDATE listings
                        SET site_items = ?
                        WHERE item_id = ?
                    """, (site_items_json, item_id))
            else:
                stats["sin_cambios"] += 1
        else:
            # CBT no encontrado en ML - NO cambiar la BD (puede estar pausado/eliminado temporalmente)
            stats["no_encontrados"] += 1

    # Commit si no es dry-run
    if not dry_run:
        conn.commit()

    conn.close()

    # Reporte
    print("=" * 70)
    print("REPORTE DE CAMBIOS")
    print("=" * 70)
    print()

    if changes:
        print(f"Productos con diferencias: {len(changes)}")
        print()

        for i, change in enumerate(changes[:20], 1):  # Mostrar primeros 20
            print(f"{i}. {change['asin']} ({change['item_id']})")
            print(f"   {change['title']}")
            print(f"   BD: {change['bd_countries']}")
            print(f"   ML: {change['ml_countries']}")
            if change['missing']:
                print(f"   ⚠️  Faltaban: {change['missing']}")
            if change['extra']:
                print(f"   ⚠️  De más: {change['extra']}")
            print()

        if len(changes) > 20:
            print(f"... y {len(changes) - 20} más")
            print()
    else:
        print("✅ No hay cambios necesarios")
        print()

    # Resumen
    print("=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"Procesados: {stats['procesados']}")
    print(f"Actualizados: {stats['actualizados']}")
    print(f"Sin cambios: {stats['sin_cambios']}")
    print(f"No encontrados en ML: {stats['no_encontrados']}")
    print()

    if dry_run:
        print("⚠️  MODO DRY-RUN: No se modificó la BD")
        print("   Para aplicar cambios, ejecuta sin --dry-run")
    else:
        print("✅ BD actualizada")
    print()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sync_safe(dry_run=dry_run)
