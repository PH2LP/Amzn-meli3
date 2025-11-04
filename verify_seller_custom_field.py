#!/usr/bin/env python3
"""
Verifica si las publicaciones YA tienen seller_custom_field (ASIN).
Si lo tienen, muestra el mapeo ASIN ↔ item_id.
Si no lo tienen, permite actualizarlas.
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import dotenv_values

# Cargar token del archivo .env
env = dotenv_values(".env")
ML_TOKEN = env.get("ML_ACCESS_TOKEN") or os.getenv("ML_TOKEN")

if not ML_TOKEN:
    print("❌ ML_TOKEN no encontrado")
    sys.exit(1)

API_BASE = "https://api.mercadolibre.com"

# Los 14 ASINs que nos importan
TARGET_ASINS = [
    "B092RCLKHN",   # GPS
    "B0BGQLZ921",   # LEGO Flowers
    "B0DRW69H11",   # LEGO Rhino
    "B0CYM126TT",   # LEGO Blocks
    "B0DRW8G3WK",   # LEGO Set
    "B0BXSLRQH7",   # Watch
    "B0D3H3NKBN",   # Nail Polish
    "B0DCYZJBYD",   # Basketball
    "B0CHLBDJYP",   # Leather Cleaner
    "B0CJQG4PMF",   # Earrings
    "B0CLC6NBBX",   # Headphones
    "B0D1Z99167",   # Personal Care
    "B081SRSNWW",   # Facial Mask
    "B0BRNY9HZB"    # Rock Painting
]

def get_user_id():
    """Obtiene el user_id del vendedor."""
    url = f"{API_BASE}/users/me"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        user = resp.json()
        return user.get("id")
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def search_user_items(user_id):
    """Busca todas las publicaciones activas."""
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
        print(f"❌ Error: {e}")
        return []

def get_item_details(item_id):
    """Obtiene detalles de un item."""
    url = f"{API_BASE}/items/{item_id}"
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return None

def main():
    print("=" * 80)
    print("🔍 VERIFICACIÓN DE SELLER_CUSTOM_FIELD EN TUS 14 PUBLICACIONES")
    print("=" * 80)
    print()

    user_id = get_user_id()
    if not user_id:
        return

    print(f"👤 User ID: {user_id}")
    print()

    print("🔎 Buscando todas tus publicaciones...")
    item_ids = search_user_items(user_id)
    print(f"✅ Encontradas {len(item_ids)} publicaciones totales")
    print()

    print(f"🎯 Filtrando por seller_custom_field (ASINs objetivo)...")
    print()

    found_asins = {}
    not_found_asins = TARGET_ASINS.copy()

    for i, item_id in enumerate(item_ids, 1):
        if i % 50 == 0:
            print(f"   Procesando {i}/{len(item_ids)}...")

        details = get_item_details(item_id)
        if not details:
            continue

        # Buscar seller_custom_field
        seller_custom_field = details.get("seller_custom_field")

        # También buscar en sites_to_sell
        sites_to_sell = details.get("sites_to_sell", [])
        if not seller_custom_field and sites_to_sell:
            seller_custom_field = sites_to_sell[0].get("seller_custom_field")

        if seller_custom_field and seller_custom_field in TARGET_ASINS:
            found_asins[seller_custom_field] = item_id
            if seller_custom_field in not_found_asins:
                not_found_asins.remove(seller_custom_field)

    print()
    print("=" * 80)
    print("📊 RESULTADOS")
    print("=" * 80)
    print()

    print(f"✅ ASINs encontrados con seller_custom_field: {len(found_asins)}/14")
    print(f"❌ ASINs NO encontrados: {len(not_found_asins)}/14")
    print()

    if found_asins:
        print("✅ Publicaciones con seller_custom_field:")
        for asin, item_id in sorted(found_asins.items()):
            print(f"   {asin} → {item_id}")
        print()

    if not_found_asins:
        print("❌ ASINs sin publicación encontrada (o sin seller_custom_field):")
        for asin in sorted(not_found_asins):
            print(f"   {asin}")
        print()

    # Guardar mapeo
    if found_asins:
        mapping_file = Path("storage/asin_to_itemid_mapping.json")
        mapping_file.parent.mkdir(parents=True, exist_ok=True)

        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(found_asins, f, indent=2, ensure_ascii=False)

        print(f"💾 Mapeo guardado en: {mapping_file}")
        print()

    # Resumen final
    if len(found_asins) == 14:
        print("🎉 ¡PERFECTO! Todas las 14 publicaciones tienen seller_custom_field configurado")
    elif len(found_asins) > 0:
        print(f"⚠️  Solo {len(found_asins)}/14 tienen seller_custom_field configurado")
        print(f"   Necesitas actualizar las {len(not_found_asins)} restantes")
    else:
        print("❌ Ninguna publicación tiene seller_custom_field configurado")
        print("   El sistema actual YA está enviando este campo al publicar")
        print("   Pero las publicaciones antiguas necesitan actualizarse manualmente")

if __name__ == "__main__":
    main()
