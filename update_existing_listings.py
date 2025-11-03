#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script INDEPENDIENTE para actualizar listings existentes en MercadoLibre.
NO modifica el pipeline principal (mainglobal.py).

Este script:
1. Busca todos los listings publicados por ASIN (seller_custom_field)
2. Identifica duplicados (mismo ASIN con diferentes item_ids)
3. Actualiza el listing más reciente con datos corregidos del mini_ml
4. Opcionalmente pausa/elimina listings duplicados antiguos
"""

import os
import sys
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
API = "https://api.mercadolibre.com"
HEADERS = {"Authorization": f"Bearer {ML_TOKEN}"}

def http_get(url, params=None):
    """GET request con manejo de errores"""
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"⚠️ Error GET {url}: {e}")
        return None

def http_put(url, body):
    """PUT request para actualizar items"""
    try:
        r = requests.put(url, headers=HEADERS, json=body, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"⚠️ Error PUT {url}: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"   Response: {e.response.text}")
        return None

def get_user_id():
    """Obtiene el user ID del seller"""
    user = http_get(f"{API}/users/me")
    if user:
        return user.get("id")
    return None

def get_all_listings():
    """
    Obtiene TODOS los listings del seller.
    Intenta varios métodos porque la API de ML es restrictiva.
    """
    listings = []

    # Método 1: /users/me/items/search
    print("📡 Intentando método 1: /users/me/items/search...")
    try:
        url = f"{API}/users/me/items/search"
        params = {"search_type": "scan", "limit": 50, "offset": 0}

        while True:
            data = http_get(url, params)
            if not data or "results" not in data:
                break

            results = data.get("results", [])
            if not results:
                break

            listings.extend(results)
            print(f"   Encontrados {len(results)} items (total: {len(listings)})")

            # Paginación
            paging = data.get("paging", {})
            if paging.get("offset", 0) + paging.get("limit", 0) >= paging.get("total", 0):
                break

            params["offset"] += params["limit"]

        if listings:
            print(f"✅ Método 1 exitoso: {len(listings)} listings encontrados")
            return listings
    except Exception as e:
        print(f"⚠️ Método 1 falló: {e}")

    # Método 2: Buscar en CBT site
    print("\n📡 Intentando método 2: Búsqueda por seller_id en CBT...")
    try:
        user_id = get_user_id()
        if not user_id:
            print("⚠️ No se pudo obtener user_id")
            return []

        url = f"{API}/sites/CBT/search"
        params = {"seller_id": user_id, "limit": 50}
        data = http_get(url, params)

        if data and "results" in data:
            listings = data["results"]
            print(f"✅ Método 2 exitoso: {len(listings)} listings encontrados")
            return listings
    except Exception as e:
        print(f"⚠️ Método 2 falló: {e}")

    return []

def get_item_details(item_id):
    """Obtiene detalles completos de un item"""
    return http_get(f"{API}/items/{item_id}")

def load_mini_ml(asin):
    """Carga el mini_ml corregido para un ASIN"""
    path = f"storage/logs/publish_ready/{asin}_mini_ml.json"
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Error cargando mini_ml para {asin}: {e}")
        return None

def build_update_body(item_details, mini_ml):
    """
    Construye el body para actualizar un item existente.
    Solo actualiza campos específicos sin romper el listing.
    """
    body = {}

    # Actualizar dimensiones del paquete
    pkg = mini_ml.get("package", {})
    if pkg:
        body["package_length"] = pkg.get("length_cm")
        body["package_width"] = pkg.get("width_cm")
        body["package_height"] = pkg.get("height_cm")
        body["package_weight"] = pkg.get("weight_kg")

    # Actualizar precio (net_proceeds)
    price = mini_ml.get("price", {})
    if price and price.get("net_proceeds_usd"):
        body["global_net_proceeds"] = {
            "amount": price["net_proceeds_usd"],
            "currency_id": "USD"
        }

    # Actualizar atributos (solo los válidos del schema)
    if mini_ml.get("attributes"):
        body["attributes"] = mini_ml["attributes"]

    return body

def group_by_asin(listings):
    """
    Agrupa listings por ASIN (seller_custom_field).
    Devuelve: {asin: [item_id1, item_id2, ...]}
    """
    groups = {}

    for item_id in listings:
        # Si es un dict, extraer el id
        if isinstance(item_id, dict):
            item_id = item_id.get("id")

        if not item_id:
            continue

        # Obtener detalles del item
        item = get_item_details(item_id)
        if not item:
            continue

        # Extraer ASIN del seller_custom_field
        asin = item.get("seller_custom_field", "").strip()
        if not asin:
            continue

        if asin not in groups:
            groups[asin] = []

        groups[asin].append({
            "item_id": item_id,
            "date_created": item.get("date_created"),
            "status": item.get("status"),
            "package": {
                "length": item.get("package_length"),
                "width": item.get("package_width"),
                "height": item.get("package_height"),
                "weight": item.get("package_weight")
            }
        })

    return groups

def main():
    print("=" * 80)
    print("🔄 ACTUALIZACIÓN DE LISTINGS EXISTENTES")
    print("=" * 80)
    print()

    # 1. Obtener todos los listings
    print("📋 PASO 1: Obtener todos los listings publicados...")
    listings = get_all_listings()

    if not listings:
        print("❌ No se encontraron listings. Verifica el access token.")
        return

    print(f"✅ Encontrados {len(listings)} listings totales\n")

    # 2. Agrupar por ASIN
    print("📋 PASO 2: Agrupar listings por ASIN...")
    groups = group_by_asin(listings)

    print(f"✅ Agrupados en {len(groups)} ASINs únicos\n")

    # 3. Identificar duplicados
    duplicates = {asin: items for asin, items in groups.items() if len(items) > 1}

    if duplicates:
        print(f"⚠️ Encontrados {len(duplicates)} ASINs con listings duplicados:")
        for asin, items in duplicates.items():
            print(f"   {asin}: {len(items)} listings")
        print()

    # 4. Actualizar listings
    print("📋 PASO 3: Actualizar listings con datos corregidos...\n")

    updated = 0
    errors = 0

    for asin, items in groups.items():
        print(f"🔄 Procesando {asin}...")

        # Cargar mini_ml corregido
        mini_ml = load_mini_ml(asin)
        if not mini_ml:
            print(f"   ⚠️ No se encontró mini_ml para {asin}")
            errors += 1
            continue

        # Ordenar por fecha (más reciente primero)
        items_sorted = sorted(items, key=lambda x: x.get("date_created", ""), reverse=True)

        # Actualizar el listing más reciente
        latest = items_sorted[0]
        item_id = latest["item_id"]

        print(f"   Item ID: {item_id}")
        print(f"   Status: {latest['status']}")

        # Mostrar cambio de dimensiones
        old_pkg = latest["package"]
        new_pkg = mini_ml.get("package", {})

        print(f"   Dimensiones ANTES: {old_pkg.get('length')} × {old_pkg.get('width')} × {old_pkg.get('height')} cm")
        print(f"   Dimensiones DESPUÉS: {new_pkg.get('length_cm')} × {new_pkg.get('width_cm')} × {new_pkg.get('height_cm')} cm")

        # Obtener detalles completos para construir update
        item_details = get_item_details(item_id)
        if not item_details:
            print(f"   ❌ Error obteniendo detalles del item")
            errors += 1
            continue

        # Construir body de actualización
        update_body = build_update_body(item_details, mini_ml)

        # Actualizar el item
        result = http_put(f"{API}/items/{item_id}", update_body)

        if result:
            print(f"   ✅ Actualizado exitosamente")
            updated += 1
        else:
            print(f"   ❌ Error actualizando")
            errors += 1

        # Si hay duplicados, reportar
        if len(items_sorted) > 1:
            print(f"   ⚠️ {len(items_sorted) - 1} listings duplicados encontrados:")
            for dup in items_sorted[1:]:
                print(f"      - {dup['item_id']} (creado: {dup['date_created']})")

        print()

    # Resumen
    print("=" * 80)
    print("📊 RESUMEN FINAL")
    print("=" * 80)
    print(f"Total ASINs procesados: {len(groups)}")
    print(f"Listings actualizados: {updated}")
    print(f"Errores: {errors}")

    if duplicates:
        print(f"\n⚠️ {len(duplicates)} ASINs tienen listings duplicados")
        print("   Considera eliminar manualmente los duplicados antiguos desde el panel de ML")

    print("\n✅ Proceso completado")

if __name__ == "__main__":
    main()
