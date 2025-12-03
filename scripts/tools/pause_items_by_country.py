#!/usr/bin/env python3
"""
Script para PAUSAR todas las publicaciones de un país específico
(versión segura que permite reactivar después)

Uso:
    python3 pause_items_by_country.py MLA  # Argentina
    python3 pause_items_by_country.py MLB  # Brasil
    python3 pause_items_by_country.py MCO  # Colombia

Diferencia con delete_items_by_country.py:
- PAUSAR: Oculta las publicaciones pero permite reactivarlas después
- CERRAR: Elimina permanentemente (no se pueden reactivar, solo republicar)
"""

import os
import sys
import time
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# Cargar variables de entorno
load_dotenv(override=True)

ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")
ML_API = "https://api.mercadolibre.com"

if not ML_ACCESS_TOKEN:
    print("❌ Error: ML_ACCESS_TOKEN no encontrado en .env")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {ML_ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Site IDs disponibles
SITE_IDS = {
    "MLA": "Argentina",
    "MLB": "Brasil",
    "MCO": "Colombia",
    "MLC": "Chile",
    "MLM": "México",
    "MLU": "Uruguay",
    "MEC": "Ecuador",
    "MPE": "Perú",
    "MLV": "Venezuela",
    "MBO": "Bolivia",
    "MPA": "Panamá",
    "MRD": "República Dominicana",
    "MCR": "Costa Rica",
    "MHN": "Honduras",
    "MNI": "Nicaragua",
    "MSV": "El Salvador",
    "MGT": "Guatemala",
    "MPY": "Paraguay"
}

def get_user_id():
    """Obtiene el user_id del token actual"""
    try:
        response = requests.get(f"{ML_API}/users/me", headers=HEADERS, timeout=10)
        response.raise_for_status()
        user_data = response.json()
        return user_data["id"]
    except Exception as e:
        print(f"❌ Error obteniendo user_id: {e}")
        sys.exit(1)

def get_all_user_items(user_id, status="active"):
    """Obtiene TODOS los items del usuario usando paginación"""
    all_items = []
    offset = 0
    limit = 100

    print(f"\n📋 Obteniendo items con status='{status}'...")

    while True:
        try:
            url = f"{ML_API}/users/{user_id}/items/search"
            params = {
                "status": status,
                "limit": limit,
                "offset": offset
            }

            response = requests.get(url, headers=HEADERS, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])

            if not results:
                break

            all_items.extend(results)

            total = data.get("paging", {}).get("total", len(all_items))
            print(f"   📦 Obtenidos: {len(all_items)}/{total} items", end="\r")

            if len(results) < limit:
                break

            offset += limit
            time.sleep(0.5)

        except Exception as e:
            print(f"\n⚠️  Error obteniendo items (offset={offset}): {e}")
            break

    print(f"\n✅ Total items obtenidos: {len(all_items)}")
    return all_items

def get_item_details(item_id):
    """Obtiene detalles de un item específico"""
    try:
        response = requests.get(f"{ML_API}/items/{item_id}", headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️  Error obteniendo detalles de {item_id}: {e}")
        return None

def pause_item(item_id):
    """Pausa un item cambiando su status a 'paused'"""
    try:
        url = f"{ML_API}/items/{item_id}"
        payload = {"status": "paused"}

        response = requests.put(url, headers=HEADERS, json=payload, timeout=15)
        response.raise_for_status()

        return True

    except requests.exceptions.HTTPError as e:
        error_msg = e.response.text if hasattr(e.response, 'text') else str(e)
        print(f"\n⚠️  Error HTTP pausando {item_id}: {error_msg}")
        return False
    except Exception as e:
        print(f"\n⚠️  Error pausando {item_id}: {e}")
        return False

def filter_items_by_site(items, target_site_id):
    """Filtra items por site_id"""
    filtered_items = []

    print(f"\n🔍 Filtrando items por site_id={target_site_id}...")

    for i, item_id in enumerate(items, 1):
        print(f"   Verificando {i}/{len(items)}: {item_id}", end="\r")

        details = get_item_details(item_id)

        if details and details.get("site_id") == target_site_id:
            filtered_items.append(item_id)

        time.sleep(0.3)

    print(f"\n✅ Items encontrados en {target_site_id}: {len(filtered_items)}")
    return filtered_items

def main():
    if len(sys.argv) < 2:
        print("\n❌ Uso: python3 pause_items_by_country.py <SITE_ID>")
        print("\nSite IDs disponibles:")
        for site_id, country in sorted(SITE_IDS.items()):
            print(f"  {site_id} - {country}")
        sys.exit(1)

    target_site = sys.argv[1].upper()

    if target_site not in SITE_IDS:
        print(f"\n❌ Site ID inválido: {target_site}")
        print("\nSite IDs disponibles:")
        for site_id, country in sorted(SITE_IDS.items()):
            print(f"  {site_id} - {country}")
        sys.exit(1)

    country_name = SITE_IDS[target_site]

    print("\n" + "="*60)
    print(f"⏸️  PAUSAR PUBLICACIONES - {country_name} ({target_site})")
    print("="*60)

    print(f"\nℹ️  Este script PAUSARÁ todas las publicaciones de {country_name}")
    print("   Las publicaciones pausadas pueden reactivarse después")
    print("   (Para eliminar permanentemente usa delete_items_by_country.py)")

    confirm = input(f"\n¿Continuar? (si/no): ")

    if confirm.lower() != "si":
        print("\n❌ Operación cancelada")
        sys.exit(0)

    # Obtener user_id
    user_id = get_user_id()
    print(f"\n👤 User ID: {user_id}")

    # Crear directorio de logs
    log_dir = Path("logs/pause_items")
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"pause_{target_site}_{timestamp}.json"

    # Obtener todos los items activos
    all_items = get_all_user_items(user_id, status="active")

    if not all_items:
        print(f"\n✅ No hay items activos para procesar")
        sys.exit(0)

    # Filtrar por site_id
    target_items = filter_items_by_site(all_items, target_site)

    if not target_items:
        print(f"\n✅ No hay items en {country_name} ({target_site})")
        sys.exit(0)

    # Pausar items
    print(f"\n⏸️  Pausando {len(target_items)} items...")

    results = {
        "site_id": target_site,
        "country": country_name,
        "timestamp": timestamp,
        "total_items": len(target_items),
        "success": [],
        "failed": []
    }

    for i, item_id in enumerate(target_items, 1):
        print(f"\n[{i}/{len(target_items)}] Pausando {item_id}...", end=" ")

        if pause_item(item_id):
            print("✅")
            results["success"].append(item_id)
        else:
            print("❌")
            results["failed"].append(item_id)

        time.sleep(0.5)

    # Guardar resultados
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Resumen final
    print("\n" + "="*60)
    print("📊 RESUMEN")
    print("="*60)
    print(f"País: {country_name} ({target_site})")
    print(f"Total items procesados: {len(target_items)}")
    print(f"✅ Pausados exitosamente: {len(results['success'])}")
    print(f"❌ Errores: {len(results['failed'])}")
    print(f"\n📄 Log guardado en: {log_file}")
    print("\nℹ️  Para reactivar estos items, usa reactivate_items_by_country.py")
    print("="*60)

if __name__ == "__main__":
    main()
