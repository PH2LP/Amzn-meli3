#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elimina TODOS los listings de MercadoLibre de todos los marketplaces.
Útil para limpiar antes de re-publicar con correcciones.
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

# Auto-activar venv
if sys.prefix == sys.base_prefix:
    venv_python = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
    if os.path.exists(venv_python):
        print(f"⚙️ Activando entorno virtual...")
        os.execv(venv_python, [venv_python] + sys.argv)

load_dotenv()

ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")
API = "https://api.mercadolibre.com"

def http_get(url):
    headers = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code >= 400:
        raise RuntimeError(f"GET {url} → {r.status_code} {r.text}")
    return r.json()

def http_put(url, data):
    headers = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}", "Content-Type": "application/json"}
    r = requests.put(url, json=data, headers=headers)
    if r.status_code >= 400:
        raise RuntimeError(f"PUT {url} → {r.status_code} {r.text}")
    return r.json()

def get_user_id():
    """Obtiene el user_id del vendedor."""
    return http_get(f"{API}/users/me").get("id")

def get_all_items(user_id):
    """Obtiene todos los items activos del vendedor."""
    all_items = []
    offset = 0
    limit = 50

    while True:
        url = f"{API}/users/{user_id}/items/search?status=active&offset={offset}&limit={limit}"
        response = http_get(url)
        results = response.get("results", [])

        if not results:
            break

        all_items.extend(results)
        offset += limit

        print(f"📦 Obtenidos {len(all_items)} items...")

        if len(results) < limit:
            break

    return all_items

def delete_item(item_id):
    """Cierra un item (lo pasa a closed/deleted)."""
    try:
        # Cambiar status a closed
        http_put(f"{API}/items/{item_id}", {"status": "closed", "deleted": True})
        return True
    except Exception as e:
        print(f"❌ Error eliminando {item_id}: {e}")
        return False

def main():
    print("=" * 60)
    print("🗑️  ELIMINADOR DE LISTINGS - MERCADOLIBRE CBT")
    print("=" * 60)

    if not ML_ACCESS_TOKEN:
        print("❌ ML_ACCESS_TOKEN no encontrado en .env")
        sys.exit(1)

    # Confirmar acción
    print("\n⚠️  ADVERTENCIA: Esta acción eliminará TODOS tus listings activos.")
    confirm = input("Escribe 'CONFIRMAR' para proceder: ")

    if confirm != "CONFIRMAR":
        print("❌ Operación cancelada.")
        sys.exit(0)

    print("\n🔍 Obteniendo user_id...")
    user_id = get_user_id()
    print(f"✅ User ID: {user_id}")

    print("\n📦 Obteniendo todos los items...")
    items = get_all_items(user_id)
    print(f"✅ Total de items activos: {len(items)}")

    if len(items) == 0:
        print("✅ No hay items para eliminar.")
        return

    print(f"\n🗑️  Eliminando {len(items)} items...")
    deleted = 0
    failed = 0

    for item_id in items:
        if delete_item(item_id):
            deleted += 1
            print(f"✅ [{deleted}/{len(items)}] Eliminado: {item_id}")
        else:
            failed += 1
            print(f"❌ [{failed} fallos] No se pudo eliminar: {item_id}")

    print("\n" + "=" * 60)
    print("📊 RESUMEN")
    print("=" * 60)
    print(f"✅ Items eliminados: {deleted}")
    print(f"❌ Items con error: {failed}")
    print("=" * 60)

if __name__ == "__main__":
    main()
