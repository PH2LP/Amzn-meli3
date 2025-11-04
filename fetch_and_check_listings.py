#!/usr/bin/env python3
"""
Busca las publicaciones existentes en MercadoLibre y verifica:
1. Si tienen seller_custom_field (SKU/ASIN)
2. Si tienen GTIN visible en attributes
3. Obtiene los item_ids para actualizar la base de datos
"""

import os
import sys
import json
import requests
from pathlib import Path

ML_TOKEN = os.getenv("ML_TOKEN")
if not ML_TOKEN:
    print("❌ ML_TOKEN no encontrado en variables de entorno")
    sys.exit(1)

API_BASE = "https://api.mercadolibre.com"

def get_user_id():
    """Obtiene el user_id del vendedor autenticado."""
    url = f"{API_BASE}/users/me"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json().get("id")
    except Exception as e:
        print(f"❌ Error obteniendo user_id: {e}")
        return None

def search_user_items(user_id):
    """Busca todas las publicaciones activas del vendedor."""
    url = f"{API_BASE}/users/{user_id}/items/search"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}
    params = {
        "status": "active",
        "limit": 50  # Máximo por página
    }

    all_items = []

    try:
        while True:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            all_items.extend(results)

            # Paginación
            paging = data.get("paging", {})
            if paging.get("offset", 0) + paging.get("limit", 0) >= paging.get("total", 0):
                break

            params["offset"] = paging["offset"] + paging["limit"]

        return all_items
    except Exception as e:
        print(f"❌ Error buscando publicaciones: {e}")
        return []

def get_item_details(item_id):
    """Obtiene detalles completos de un item incluyendo seller_custom_field y attributes."""
    url = f"{API_BASE}/items/{item_id}"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"⚠️  Error obteniendo detalles de {item_id}: {e}")
        return None

def check_gtin_in_attributes(attributes):
    """Busca GTIN en la lista de atributos."""
    for attr in attributes:
        if attr.get("id") == "GTIN":
            return attr.get("value_name") or attr.get("value_id")
    return None

def main():
    print("=" * 80)
    print("🔍 BÚSQUEDA Y VERIFICACIÓN DE PUBLICACIONES EN MERCADOLIBRE")
    print("=" * 80)
    print()

    # Obtener user_id
    user_id = get_user_id()
    if not user_id:
        return

    print(f"👤 User ID: {user_id}")
    print()

    # Buscar publicaciones
    print("🔎 Buscando publicaciones activas...")
    item_ids = search_user_items(user_id)

    if not item_ids:
        print("⚠️  No se encontraron publicaciones activas")
        return

    print(f"✅ Encontradas {len(item_ids)} publicaciones activas")
    print()

    # Verificar cada publicación
    results = []

    for i, item_id in enumerate(item_ids, 1):
        print(f"[{i}/{len(item_ids)}] Verificando {item_id}...")

        details = get_item_details(item_id)
        if not details:
            continue

        # Extraer información relevante
        title = details.get("title", "")
        seller_custom_field = details.get("seller_custom_field")
        attributes = details.get("attributes", [])
        gtin = check_gtin_in_attributes(attributes)

        # También verificar si está en sites_to_sell
        sites_to_sell = details.get("sites_to_sell", [])
        seller_custom_field_in_sites = None
        if sites_to_sell:
            seller_custom_field_in_sites = sites_to_sell[0].get("seller_custom_field")

        result = {
            "item_id": item_id,
            "title": title[:60],
            "seller_custom_field": seller_custom_field,
            "seller_custom_field_in_sites": seller_custom_field_in_sites,
            "gtin": gtin,
            "has_sku": bool(seller_custom_field or seller_custom_field_in_sites),
            "has_gtin": bool(gtin)
        }

        results.append(result)

        # Mostrar resultado
        sku_icon = "✅" if result["has_sku"] else "❌"
        gtin_icon = "✅" if result["has_gtin"] else "❌"

        print(f"   {sku_icon} SKU: {seller_custom_field or seller_custom_field_in_sites or 'NO'}")
        print(f"   {gtin_icon} GTIN: {gtin or 'NO'}")
        print()

    # Resumen final
    print("=" * 80)
    print("📊 RESUMEN FINAL")
    print("=" * 80)

    with_sku = sum(1 for r in results if r["has_sku"])
    with_gtin = sum(1 for r in results if r["has_gtin"])

    print(f"Total publicaciones: {len(results)}")
    print(f"Con seller_custom_field (SKU): {with_sku}/{len(results)} ({with_sku*100//len(results) if results else 0}%)")
    print(f"Con GTIN: {with_gtin}/{len(results)} ({with_gtin*100//len(results) if results else 0}%)")
    print()

    if results:
        print("❌ Publicaciones SIN seller_custom_field:")
        for r in results:
            if not r["has_sku"]:
                print(f"   - {r['item_id']}: {r['title']}")
        print()

        print("❌ Publicaciones SIN GTIN:")
        for r in results:
            if not r["has_gtin"]:
                print(f"   - {r['item_id']}: {r['title']}")
        print()

    # Guardar resultados
    report_path = Path("storage/listings_check_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"💾 Reporte guardado en: {report_path}")

if __name__ == "__main__":
    main()
