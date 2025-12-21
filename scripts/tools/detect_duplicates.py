#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para detectar productos duplicados en MercadoLibre
Busca el mismo ASIN publicado múltiples veces en el mismo país

Uso:
    python3 scripts/tools/detect_duplicates.py
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
from collections import defaultdict

# Cargar .env
load_dotenv(override=True)
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")

if not ML_ACCESS_TOKEN:
    print("❌ Falta ML_ACCESS_TOKEN en .env")
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"}
API = "https://api.mercadolibre.com"


def get_user_id():
    """Obtiene el user ID del vendedor"""
    try:
        response = requests.get(f"{API}/users/me", headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json().get("id")
    except Exception as e:
        print(f"❌ Error obteniendo user ID: {e}")
        sys.exit(1)


def get_all_active_listings(user_id):
    """
    Obtiene todos los listings activos del vendedor
    Returns: dict {item_id: {...item_data...}}
    """
    print(f"🔍 Buscando listings activos del vendedor {user_id}...")

    all_items = {}
    offset = 0
    limit = 50

    while True:
        try:
            url = f"{API}/users/{user_id}/items/search"
            params = {
                "status": "active",
                "offset": offset,
                "limit": limit
            }

            response = requests.get(url, headers=HEADERS, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if not results:
                break

            print(f"   Descargando items {offset}-{offset + len(results)}...", end="\r")

            # Obtener detalles de cada item
            for item_id in results:
                try:
                    item_response = requests.get(f"{API}/items/{item_id}", headers=HEADERS, timeout=10)
                    item_response.raise_for_status()
                    item = item_response.json()

                    # Extraer ASIN del seller_custom_field
                    asin = item.get("seller_custom_field")
                    if asin:
                        all_items[item_id] = {
                            "item_id": item_id,
                            "asin": asin,
                            "title": item.get("title", ""),
                            "status": item.get("status", ""),
                            "permalink": item.get("permalink", ""),
                            "price": item.get("price", 0),
                            "available_quantity": item.get("available_quantity", 0),
                            "site_id": item_id[:3]  # Primeros 3 chars = site_id (MLM, MLB, etc)
                        }
                except Exception as e:
                    print(f"\n⚠️  Error obteniendo detalles de {item_id}: {e}")
                    continue

            offset += limit

            # Verificar si hay más resultados
            if offset >= data.get("paging", {}).get("total", 0):
                break

        except Exception as e:
            print(f"\n❌ Error en búsqueda: {e}")
            break

    print(f"\n✅ Total items activos encontrados: {len(all_items)}")
    return all_items


def find_duplicates(items_dict):
    """
    Encuentra duplicados: mismo ASIN publicado múltiples veces en el mismo país

    Returns:
        dict: {
            asin: {
                site_id: [item_id1, item_id2, ...]
            }
        }
    """
    # Agrupar por ASIN + site_id
    grouped = defaultdict(lambda: defaultdict(list))

    for item_id, item_data in items_dict.items():
        asin = item_data["asin"]
        site_id = item_data["site_id"]
        grouped[asin][site_id].append(item_data)

    # Filtrar solo los que tienen duplicados
    duplicates = {}
    for asin, sites in grouped.items():
        for site_id, items in sites.items():
            if len(items) > 1:
                if asin not in duplicates:
                    duplicates[asin] = {}
                duplicates[asin][site_id] = items

    return duplicates


def main():
    print("\n" + "="*70)
    print("🔍 DETECTOR DE DUPLICADOS EN MERCADOLIBRE")
    print("="*70 + "\n")

    # 1. Obtener user ID
    user_id = get_user_id()
    print(f"✅ User ID: {user_id}\n")

    # 2. Obtener todos los listings activos
    items = get_all_active_listings(user_id)

    if not items:
        print("\n❌ No se encontraron items activos")
        return

    # 3. Encontrar duplicados
    duplicates = find_duplicates(items)

    if not duplicates:
        print("\n✅ No se encontraron duplicados. Todo está limpio!")
        return

    # 4. Mostrar reporte de duplicados
    print("\n" + "="*70)
    print("⚠️  DUPLICADOS ENCONTRADOS")
    print("="*70 + "\n")

    total_duplicates = 0
    duplicate_report = []

    for asin, sites in sorted(duplicates.items()):
        print(f"\n📦 ASIN: {asin}")
        for site_id, items in sorted(sites.items()):
            print(f"   🌍 {site_id}: {len(items)} publicaciones")
            total_duplicates += len(items) - 1  # -1 porque 1 es la legítima

            for i, item in enumerate(items, 1):
                status_icon = "✅" if i == 1 else "❌"
                print(f"      {status_icon} {item['item_id']} - ${item['price']:.2f} - {item['title'][:50]}")
                print(f"         {item['permalink']}")

                duplicate_report.append({
                    "asin": asin,
                    "site_id": site_id,
                    "item_id": item['item_id'],
                    "title": item['title'],
                    "price": item['price'],
                    "permalink": item['permalink'],
                    "is_duplicate": i > 1  # El primero NO es duplicado, el resto SÍ
                })

    print("\n" + "="*70)
    print(f"📊 RESUMEN:")
    print(f"   • ASINs con duplicados: {len(duplicates)}")
    print(f"   • Total de publicaciones duplicadas: {total_duplicates}")
    print("="*70 + "\n")

    # 5. Guardar reporte en JSON
    report_path = Path("storage/logs/duplicates_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_items": len(items),
            "total_asins_with_duplicates": len(duplicates),
            "total_duplicate_items": total_duplicates,
            "duplicates": duplicate_report
        }, f, indent=2, ensure_ascii=False)

    print(f"💾 Reporte guardado en: {report_path}")
    print(f"\n💡 Para eliminar duplicados, ejecuta:")
    print(f"   python3 scripts/tools/clean_duplicates.py")


if __name__ == "__main__":
    main()
