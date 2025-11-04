#!/usr/bin/env python3
"""
Actualiza las publicaciones existentes en MercadoLibre para:
1. Asegurar que seller_custom_field (SKU) esté presente en sites_to_sell
2. Agregar GTIN visible en attributes si no está
3. Poblar item_ids en la base de datos

IMPORTANTE: Necesitas un token ML válido para ejecutar este script.

Para renovar tu token:
1. Ve a https://developers.mercadolibre.com/
2. Obtén un nuevo access_token usando tu refresh_token
3. Actualiza la variable ML_TOKEN
"""

import os
import sys
import json
import requests
import sqlite3
from pathlib import Path
from dotenv import dotenv_values

# Cargar token del archivo .env (renovado automáticamente)
env = dotenv_values(".env")
ML_TOKEN = env.get("ML_ACCESS_TOKEN") or os.getenv("ML_TOKEN")
if not ML_TOKEN:
    print("❌ ML_TOKEN no encontrado en variables de entorno")
    print()
    print("Para obtener un nuevo token:")
    print("1. Ve a https://developers.mercadolibre.com/")
    print("2. Usa tu refresh_token para obtener un nuevo access_token")
    print("3. export ML_TOKEN='tu_nuevo_token'")
    print("4. Ejecuta este script de nuevo")
    sys.exit(1)

API_BASE = "https://api.mercadolibre.com"
DB_PATH = Path("storage/listings_database.db")
MINI_ML_DIR = Path("storage/logs/publish_ready")

def get_user_id():
    """Obtiene el user_id del vendedor autenticado."""
    url = f"{API_BASE}/users/me"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        user = resp.json()
        print(f"✅ Autenticado como: {user.get('nickname')} (ID: {user.get('id')})")
        return user.get("id")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("❌ Token expirado o inválido")
            print()
            print("Para renovar tu token:")
            print("curl -X POST https://api.mercadolibre.com/oauth/token \\")
            print("  -H 'Content-Type: application/x-www-form-urlencoded' \\")
            print("  -d 'grant_type=refresh_token&client_id=TU_CLIENT_ID&client_secret=TU_CLIENT_SECRET&refresh_token=TU_REFRESH_TOKEN'")
        else:
            print(f"❌ Error obteniendo user_id: {e}")
        return None
    except Exception as e:
        print(f"❌ Error obteniendo user_id: {e}")
        return None

def search_user_items(user_id):
    """Busca todas las publicaciones activas del vendedor."""
    url = f"{API_BASE}/users/{user_id}/items/search"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}
    params = {"status": "active", "limit": 50}

    all_items = []

    try:
        while True:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            all_items.extend(results)

            paging = data.get("paging", {})
            if paging.get("offset", 0) + paging.get("limit", 0) >= paging.get("total", 0):
                break

            params["offset"] = paging["offset"] + paging["limit"]

        return all_items
    except Exception as e:
        print(f"❌ Error buscando publicaciones: {e}")
        return []

def get_item_details(item_id):
    """Obtiene detalles completos de un item."""
    url = f"{API_BASE}/items/{item_id}"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"⚠️  Error obteniendo detalles de {item_id}: {e}")
        return None

def update_item(item_id, updates):
    """Actualiza un item en MercadoLibre."""
    url = f"{API_BASE}/items/{item_id}"
    headers = {
        "Authorization": f"Bearer {ML_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.put(url, headers=headers, json=updates, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        error_data = e.response.json() if e.response.content else {}
        print(f"⚠️  Error actualizando {item_id}: {error_data}")
        return None
    except Exception as e:
        print(f"⚠️  Error actualizando {item_id}: {e}")
        return None

def find_asin_for_title(title):
    """Busca el ASIN correspondiente al título en los mini_ml files."""
    for file in MINI_ML_DIR.glob("*_mini_ml.json"):
        with open(file, 'r', encoding='utf-8') as f:
            mini_ml = json.load(f)
            if mini_ml.get("title_ai", "").lower() in title.lower():
                return mini_ml.get("asin")
    return None

def get_gtin_from_mini_ml(asin):
    """Obtiene el GTIN del mini_ml file."""
    file_path = MINI_ML_DIR / f"{asin}_mini_ml.json"

    if not file_path.exists():
        return None

    with open(file_path, 'r', encoding='utf-8') as f:
        mini_ml = json.load(f)

        # Verificar si force_no_gtin está activo
        if mini_ml.get("force_no_gtin") or mini_ml.get("last_error") == "GTIN_REUSED":
            return None

        gtins = mini_ml.get("gtins", [])
        return gtins[0] if gtins else None

def update_database_with_item_id(asin, item_id):
    """Actualiza la base de datos con el item_id."""
    if not DB_PATH.exists():
        print("⚠️  Base de datos no existe, creando...")
        from save_listing_data import init_database
        init_database()

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Actualizar item_id para todas las entradas con este ASIN
        cursor.execute("""
            UPDATE listings
            SET item_id = ?
            WHERE asin = ?
        """, (item_id, asin))

        conn.commit()
        conn.close()

        print(f"   💾 Base de datos actualizada: {asin} → {item_id}")
    except Exception as e:
        print(f"   ⚠️  Error actualizando DB: {e}")

def main():
    print("=" * 80)
    print("🔧 ACTUALIZACIÓN DE PUBLICACIONES: SKU Y GTIN")
    print("=" * 80)
    print()

    # Obtener user_id
    user_id = get_user_id()
    if not user_id:
        return

    print()

    # Buscar publicaciones
    print("🔎 Buscando publicaciones activas...")
    item_ids = search_user_items(user_id)

    if not item_ids:
        print("⚠️  No se encontraron publicaciones activas")
        return

    print(f"✅ Encontradas {len(item_ids)} publicaciones activas")
    print()

    # Verificar y actualizar cada publicación
    results = {
        "updated": [],
        "already_ok": [],
        "failed": []
    }

    for i, item_id in enumerate(item_ids, 1):
        print(f"[{i}/{len(item_ids)}] Procesando {item_id}...")

        details = get_item_details(item_id)
        if not details:
            results["failed"].append(item_id)
            continue

        title = details.get("title", "")
        print(f"   Título: {title[:60]}...")

        # Identificar ASIN
        asin = find_asin_for_title(title)
        if not asin:
            print(f"   ⚠️  No se pudo identificar ASIN para este producto")
            results["failed"].append(item_id)
            continue

        print(f"   ASIN: {asin}")

        # Verificar estado actual
        seller_custom_field = details.get("seller_custom_field")
        sites_to_sell = details.get("sites_to_sell", [])

        attributes = details.get("attributes", [])
        has_gtin = any(attr.get("id") == "GTIN" for attr in attributes)

        needs_update = False
        updates = {}

        # 1. Verificar seller_custom_field
        if not seller_custom_field:
            print(f"   ⚠️  Falta seller_custom_field, agregando...")
            updates["seller_custom_field"] = asin
            needs_update = True
        else:
            print(f"   ✅ seller_custom_field: {seller_custom_field}")

        # 2. Verificar seller_custom_field en sites_to_sell
        if sites_to_sell:
            needs_sites_update = False
            for site in sites_to_sell:
                if not site.get("seller_custom_field"):
                    site["seller_custom_field"] = asin
                    needs_sites_update = True

            if needs_sites_update:
                print(f"   ⚠️  Actualizando seller_custom_field en sites_to_sell...")
                updates["sites_to_sell"] = sites_to_sell
                needs_update = True

        # 3. Verificar GTIN
        if not has_gtin:
            gtin = get_gtin_from_mini_ml(asin)
            if gtin:
                print(f"   ⚠️  Falta GTIN, agregando: {gtin}")

                # Agregar GTIN a attributes
                if "attributes" not in updates:
                    updates["attributes"] = attributes.copy()

                updates["attributes"].append({
                    "id": "GTIN",
                    "value_name": str(gtin)
                })
                needs_update = True
            else:
                print(f"   ⚠️  No hay GTIN disponible para este producto")
        else:
            gtin_value = next((attr.get("value_name") for attr in attributes if attr.get("id") == "GTIN"), None)
            print(f"   ✅ GTIN: {gtin_value}")

        # Actualizar si es necesario
        if needs_update:
            print(f"   🔧 Actualizando publicación...")
            result = update_item(item_id, updates)

            if result:
                print(f"   ✅ Actualización exitosa")
                results["updated"].append(item_id)
            else:
                print(f"   ❌ Falló la actualización")
                results["failed"].append(item_id)
        else:
            print(f"   ✅ Ya está OK, no necesita actualización")
            results["already_ok"].append(item_id)

        # Actualizar base de datos con item_id
        update_database_with_item_id(asin, item_id)

        print()

    # Resumen final
    print("=" * 80)
    print("📊 RESUMEN FINAL")
    print("=" * 80)
    print(f"Total procesados: {len(item_ids)}")
    print(f"Actualizados: {len(results['updated'])} ✅")
    print(f"Ya estaban OK: {len(results['already_ok'])} ✅")
    print(f"Fallidos: {len(results['failed'])} ❌")
    print()

    # Guardar reporte
    report_path = Path("storage/update_listings_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"💾 Reporte guardado en: {report_path}")

if __name__ == "__main__":
    main()
