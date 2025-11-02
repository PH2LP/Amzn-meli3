#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verificar_publicaciones.py
Verifica qué productos se publicaron exitosamente en MercadoLibre
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")
API = "https://api.mercadolibre.com"
HEADERS = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"}

def get_user_id():
    """Obtiene el user_id de ML"""
    r = requests.get(f"{API}/users/me", headers=HEADERS)
    if r.ok:
        return r.json()["id"]
    return None

def get_user_items(user_id, status="active"):
    """Obtiene todos los items del usuario"""
    items = []
    offset = 0
    limit = 50

    while True:
        url = f"{API}/users/{user_id}/items/search"
        params = {"status": status, "offset": offset, "limit": limit}

        r = requests.get(url, headers=HEADERS, params=params)
        if not r.ok:
            break

        data = r.json()
        results = data.get("results", [])
        if not results:
            break

        items.extend(results)
        offset += limit

        if offset >= data.get("paging", {}).get("total", 0):
            break

    return items

def get_item_details(item_id):
    """Obtiene detalles de un item"""
    r = requests.get(f"{API}/items/{item_id}", headers=HEADERS)
    if r.ok:
        return r.json()
    return None

def main():
    print("\n" + "="*60)
    print("🔍 VERIFICANDO PUBLICACIONES EN MERCADOLIBRE")
    print("="*60 + "\n")

    user_id = get_user_id()
    if not user_id:
        print("❌ No se pudo obtener user_id")
        sys.exit(1)

    print(f"✅ User ID: {user_id}\n")
    print("📦 Obteniendo items activos...")

    items = get_user_items(user_id, "active")

    print(f"\n📊 TOTAL DE ITEMS ACTIVOS: {len(items)}\n")
    print("="*60)

    # Buscar items recientes (últimas 24 horas)
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    recent_items = []

    for item_id in items:
        details = get_item_details(item_id)
        if not details:
            continue

        # Parsear fecha de creación
        try:
            date_created = datetime.datetime.fromisoformat(
                details["date_created"].replace("Z", "+00:00")
            )

            age_hours = (now - date_created).total_seconds() / 3600

            if age_hours < 24:  # Últimas 24 horas
                recent_items.append({
                    "id": details["id"],
                    "title": details["title"][:60],
                    "price": details["price"],
                    "currency": details["currency_id"],
                    "site": details["site_id"],
                    "permalink": details["permalink"],
                    "seller_custom_field": details.get("seller_custom_field", "N/A"),
                    "created": date_created.strftime("%Y-%m-%d %H:%M:%S")
                })
        except Exception as e:
            print(f"⚠️  Error procesando {item_id}: {e}")
            continue

    print(f"\n🆕 ITEMS PUBLICADOS EN LAS ÚLTIMAS 24 HORAS: {len(recent_items)}\n")

    for item in recent_items:
        print(f"{'='*60}")
        print(f"📦 Item ID: {item['id']}")
        print(f"   Título: {item['title']}")
        print(f"   Precio: {item['currency']} ${item['price']}")
        print(f"   Sitio: {item['site']}")
        print(f"   ASIN (seller_custom_field): {item['seller_custom_field']}")
        print(f"   Creado: {item['created']}")
        print(f"   🔗 {item['permalink']}")
        print()

    # Guardar reporte
    report = {
        "total_active": len(items),
        "recent_24h": len(recent_items),
        "items": recent_items,
        "generated_at": now.isoformat()
    }

    report_path = Path("logs/verification_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"{'='*60}")
    print(f"📄 Reporte guardado en: {report_path}")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
