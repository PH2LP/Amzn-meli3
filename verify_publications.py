#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar todas las publicaciones en MercadoLibre
- Confirma que estén en todos los marketplaces
- Verifica dimensiones contra Amazon
- Valida integridad de datos
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
API = "https://api.mercadolibre.com"
HEADERS = {"Authorization": f"Bearer {ML_TOKEN}"}

def get_cbt_items():
    """Obtiene todos los items CBT del seller"""
    try:
        # Obtener items del seller
        url = f"{API}/users/me/items/search"
        params = {"search_type": "scan", "limit": 50}
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)

        if r.status_code == 403:
            # Intentar endpoint alternativo
            uid = get_user_id()
            url = f"{API}/sites/CBT/search"
            params = {"seller_id": uid, "limit": 50}
            r = requests.get(url, params=params, timeout=30)

        r.raise_for_status()
        data = r.json()

        if "results" in data:
            return data["results"]
        elif "paging" in data:
            return data.get("results", [])

        return []
    except Exception as e:
        print(f"⚠️ Error obteniendo items: {e}")
        return []

def get_user_id():
    """Obtiene el user ID"""
    try:
        r = requests.get(f"{API}/users/me", headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json().get("id")
    except Exception as e:
        print(f"⚠️ Error obteniendo user ID: {e}")
        return None

def get_item_details(item_id):
    """Obtiene detalles completos de un item"""
    try:
        r = requests.get(f"{API}/items/{item_id}", headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"⚠️ Error obteniendo detalles de {item_id}: {e}")
        return None

def get_amazon_dimensions(asin):
    """Lee dimensiones del JSON de Amazon"""
    path = f"storage/asins_json/{asin}.json"
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Buscar dimensiones de paquete
        attrs = data.get("attributes", {})
        pkg_dims = attrs.get("item_package_dimensions", [{}])[0]
        pkg_weight = attrs.get("item_package_weight", [{}])[0]

        if isinstance(pkg_dims, dict):
            length = pkg_dims.get("length", {}).get("value")
            width = pkg_dims.get("width", {}).get("value")
            height = pkg_dims.get("height", {}).get("value")
            weight = pkg_weight.get("value") if isinstance(pkg_weight, dict) else None

            return {
                "length_cm": round(float(length), 2) if length else None,
                "width_cm": round(float(width), 2) if width else None,
                "height_cm": round(float(height), 2) if height else None,
                "weight_kg": round(float(weight), 3) if weight else None
            }
    except Exception as e:
        print(f"⚠️ Error leyendo dimensiones de Amazon para {asin}: {e}")

    return None

def check_marketplace_replication(item_id):
    """Verifica en qué marketplaces está publicado el item"""
    try:
        # Consultar el item en cada marketplace
        marketplaces = ["MLM", "MLB", "MLC", "MCO", "MLA"]
        replicated_in = []

        item = get_item_details(item_id)
        if not item:
            return []

        # CBT items tienen un campo sites_to_sell
        sites = item.get("sites_to_sell", [])
        if sites:
            for site in sites:
                if isinstance(site, dict):
                    replicated_in.append(site.get("site_id"))
                else:
                    replicated_in.append(site)

        # Fallback: el site_id del item
        if not replicated_in:
            site_id = item.get("site_id")
            if site_id:
                replicated_in.append(site_id)

        return replicated_in
    except Exception as e:
        print(f"⚠️ Error verificando replicación de {item_id}: {e}")
        return []

def main():
    print("=" * 80)
    print("🔍 VERIFICACIÓN COMPLETA DE PUBLICACIONES")
    print("=" * 80)
    print()

    # Obtener todos los items CBT
    print("📡 Consultando items publicados...")
    items = get_cbt_items()

    if not items:
        print("⚠️ No se encontraron items publicados o no se pudo acceder a la API")
        print("   Intentando método alternativo...")

        # Leer los mini_ml publicados exitosamente
        import glob
        mini_mls = glob.glob("storage/logs/publish_ready/*_mini_ml.json")
        print(f"📋 Encontrados {len(mini_mls)} mini_ml files locales")

        results = []
        for path in mini_mls:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    mini = json.load(f)

                asin = mini.get("asin")
                print(f"\n🔄 Verificando {asin}...")

                # Comparar dimensiones
                amazon_dims = get_amazon_dimensions(asin)
                ml_dims = mini.get("package", {})

                print(f"   📦 Dimensiones Amazon:")
                if amazon_dims:
                    print(f"      {amazon_dims['length_cm']} × {amazon_dims['width_cm']} × {amazon_dims['height_cm']} cm")
                    print(f"      Peso: {amazon_dims['weight_kg']} kg")
                else:
                    print("      No disponibles")

                print(f"   📦 Dimensiones ML (mini_ml):")
                print(f"      {ml_dims.get('length_cm')} × {ml_dims.get('width_cm')} × {ml_dims.get('height_cm')} cm")
                print(f"      Peso: {ml_dims.get('weight_kg')} kg")

                # Verificar coincidencia
                if amazon_dims and ml_dims:
                    match = (
                        abs(amazon_dims['length_cm'] - ml_dims.get('length_cm', 0)) < 0.1 and
                        abs(amazon_dims['width_cm'] - ml_dims.get('width_cm', 0)) < 0.1 and
                        abs(amazon_dims['height_cm'] - ml_dims.get('height_cm', 0)) < 0.1 and
                        abs(amazon_dims['weight_kg'] - ml_dims.get('weight_kg', 0)) < 0.01
                    )

                    if match:
                        print("   ✅ Dimensiones coinciden con Amazon")
                    else:
                        print("   ⚠️ Dimensiones NO coinciden exactamente")

                results.append({
                    "asin": asin,
                    "amazon_dims": amazon_dims,
                    "ml_dims": ml_dims,
                    "category": mini.get("category_id"),
                    "price": mini.get("price", {}).get("net_proceeds_usd")
                })

            except Exception as e:
                print(f"⚠️ Error procesando {path}: {e}")

        print("\n" + "=" * 80)
        print(f"📊 RESUMEN: {len(results)} productos verificados")
        print("=" * 80)

        # Guardar reporte
        with open("VERIFICACION_PUBLICACIONES.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print("✅ Reporte guardado en: VERIFICACION_PUBLICACIONES.json")
        return

    print(f"✅ Encontrados {len(items)} items publicados\n")

    # Verificar cada item
    report = []
    for idx, item_id in enumerate(items, 1):
        if isinstance(item_id, dict):
            item_id = item_id.get("id")

        print(f"[{idx}/{len(items)}] Verificando {item_id}...")

        item = get_item_details(item_id)
        if not item:
            continue

        # Extraer ASIN del seller_custom_field
        asin = item.get("seller_custom_field", "").strip()

        # Marketplaces
        marketplaces = check_marketplace_replication(item_id)

        # Dimensiones ML
        ml_dims = {
            "length": item.get("package_length"),
            "width": item.get("package_width"),
            "height": item.get("package_height"),
            "weight": item.get("package_weight")
        }

        # Dimensiones Amazon
        amazon_dims = get_amazon_dimensions(asin) if asin else None

        # Comparar
        dims_match = False
        if amazon_dims and all(ml_dims.values()):
            dims_match = (
                abs(amazon_dims['length_cm'] - ml_dims['length']) < 0.1 and
                abs(amazon_dims['width_cm'] - ml_dims['width']) < 0.1 and
                abs(amazon_dims['height_cm'] - ml_dims['height']) < 0.1 and
                abs(amazon_dims['weight_kg'] - ml_dims['weight']) < 0.01
            )

        report.append({
            "item_id": item_id,
            "asin": asin,
            "title": item.get("title"),
            "status": item.get("status"),
            "marketplaces": marketplaces,
            "marketplace_count": len(marketplaces),
            "amazon_dimensions": amazon_dims,
            "ml_dimensions": ml_dims,
            "dimensions_match": dims_match,
            "price": item.get("global_net_proceeds")
        })

        # Imprimir resumen
        print(f"   ASIN: {asin}")
        print(f"   Título: {item.get('title', '')[:60]}")
        print(f"   Marketplaces: {', '.join(marketplaces) if marketplaces else 'N/A'}")
        print(f"   Dimensiones coinciden: {'✅ Sí' if dims_match else '❌ No'}")
        print()

    # Guardar reporte
    with open("VERIFICACION_PUBLICACIONES.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("=" * 80)
    print("📊 RESUMEN FINAL")
    print("=" * 80)
    print(f"Total items verificados: {len(report)}")
    print(f"Items en todos los marketplaces (5): {sum(1 for r in report if r['marketplace_count'] == 5)}")
    print(f"Items con dimensiones correctas: {sum(1 for r in report if r['dimensions_match'])}")
    print()
    print("✅ Reporte completo guardado en: VERIFICACION_PUBLICACIONES.json")

if __name__ == "__main__":
    main()
