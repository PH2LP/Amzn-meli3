#!/usr/bin/env python3
"""
Verifica el estado de items de MercadoLibre
Detecta items con categoría incorrecta, inactivos, pausados, etc.
"""

import os
import sys
import json
import requests
import time
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env
load_dotenv(override=True)

# Configuración
ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
ML_USER_ID = os.getenv("ML_USER_ID")

# Colores
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

def log(msg, color=Colors.NC):
    print(f"{color}{msg}{Colors.NC}")

def get_item_info(item_id: str) -> dict:
    """Obtiene información de un item de MercadoLibre"""
    try:
        url = f"https://api.mercadolibre.com/items/{item_id}"
        headers = {"Authorization": f"Bearer {ML_TOKEN}"}

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def check_category_issues(item_data: dict) -> dict:
    """
    Revisa si el item tiene problemas de categoría

    Returns:
        dict con {
            "has_issue": bool,
            "issue_type": str,
            "details": str
        }
    """
    result = {
        "has_issue": False,
        "issue_type": None,
        "details": None
    }

    # 1. Revisar status
    status = item_data.get("status")
    sub_status = item_data.get("sub_status", [])

    if status == "inactive":
        result["has_issue"] = True
        result["issue_type"] = "INACTIVE"
        result["details"] = f"Sub-status: {', '.join(sub_status) if sub_status else 'N/A'}"
        return result

    if status == "paused":
        result["has_issue"] = True
        result["issue_type"] = "PAUSED"
        result["details"] = f"Sub-status: {', '.join(sub_status) if sub_status else 'N/A'}"
        return result

    # 2. Revisar health (si existe)
    health = item_data.get("health")
    if health in ["warning", "unhealthy"]:
        result["has_issue"] = True
        result["issue_type"] = f"HEALTH_{health.upper()}"
        result["details"] = "Item con problemas de calidad/exposición"
        return result

    # 3. Revisar catalog_listing (si es false, puede tener problemas)
    catalog_listing = item_data.get("catalog_listing")
    if catalog_listing is False:
        result["has_issue"] = True
        result["issue_type"] = "NO_CATALOG"
        result["details"] = "Item no está en catálogo"

    # 4. Revisar warnings (pueden incluir problemas de categoría)
    warnings = item_data.get("warnings", [])
    if warnings:
        result["has_issue"] = True
        result["issue_type"] = "WARNINGS"
        result["details"] = f"{len(warnings)} advertencias"

    return result

def main():
    if not ML_TOKEN:
        log("❌ Error: ML_ACCESS_TOKEN no encontrado en .env", Colors.RED)
        sys.exit(1)

    # Leer items desde test.txt
    items_file = Path("test.txt")

    if not items_file.exists():
        log("❌ Error: test.txt no encontrado", Colors.RED)
        sys.exit(1)

    with open(items_file, 'r') as f:
        asins = [line.strip() for line in f if line.strip()]

    if not asins:
        log("❌ Error: test.txt está vacío", Colors.RED)
        sys.exit(1)

    log(f"\n{'='*80}", Colors.BLUE)
    log(f"VERIFICACIÓN DE ESTADO DE ITEMS", Colors.BLUE)
    log(f"{'='*80}\n", Colors.BLUE)

    log(f"📊 Total de ASINs a revisar: {len(asins)}\n", Colors.CYAN)

    # Primero obtener todos los items del usuario
    log("🔍 Obteniendo items de MercadoLibre...", Colors.CYAN)

    try:
        url = f"https://api.mercadolibre.com/users/{ML_USER_ID}/items/search"
        headers = {"Authorization": f"Bearer {ML_TOKEN}"}

        all_item_ids = []
        offset = 0
        limit = 100

        while True:
            params = {"offset": offset, "limit": limit}
            response = requests.get(url, headers=headers, params=params, timeout=15)

            if response.status_code != 200:
                log(f"⚠️  Error obteniendo items: HTTP {response.status_code}", Colors.YELLOW)
                break

            data = response.json()
            results = data.get("results", [])

            if not results:
                break

            all_item_ids.extend(results)

            total = data.get("paging", {}).get("total", 0)
            log(f"   Obtenidos {len(all_item_ids)}/{total} items...", Colors.CYAN)

            if len(all_item_ids) >= total:
                break

            offset += limit

            # Evitar rate limiting
            time.sleep(0.5)

        log(f"✅ Total items encontrados: {len(all_item_ids)}\n", Colors.GREEN)

    except Exception as e:
        log(f"❌ Error: {e}", Colors.RED)
        sys.exit(1)

    # Crear mapeo de ASIN -> Item ID
    log("🔗 Buscando items por SKU...\n", Colors.CYAN)

    asin_to_item_id = {}

    for asin in asins:
        # Buscar item por SKU
        try:
            url = f"https://api.mercadolibre.com/users/{ML_USER_ID}/items/search"
            params = {"seller_sku": asin}
            headers = {"Authorization": f"Bearer {ML_TOKEN}"}

            response = requests.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                if results:
                    asin_to_item_id[asin] = results[0]  # Tomar el primero

            time.sleep(0.3)  # Rate limiting

        except Exception as e:
            log(f"⚠️  Error buscando {asin}: {e}", Colors.YELLOW)

    log(f"✅ Mapeados {len(asin_to_item_id)}/{len(asins)} ASINs\n", Colors.GREEN)

    # Revisar estado de cada item
    stats = {
        "total": 0,
        "ok": 0,
        "category_error": 0,
        "inactive": 0,
        "paused": 0,
        "warnings": 0,
        "not_found": 0
    }

    items_con_problemas = []

    for i, asin in enumerate(asins, 1):
        stats["total"] += 1

        if asin not in asin_to_item_id:
            log(f"[{i}/{len(asins)}] ❌ {asin} - NO ENCONTRADO EN ML", Colors.RED)
            stats["not_found"] += 1
            continue

        item_id = asin_to_item_id[asin]

        # Obtener info del item
        item_data = get_item_info(item_id)

        if "error" in item_data:
            log(f"[{i}/{len(asins)}] ❌ {asin} ({item_id}) - Error: {item_data['error']}", Colors.RED)
            stats["not_found"] += 1
            continue

        # Revisar problemas
        issue_check = check_category_issues(item_data)

        status = item_data.get("status", "unknown")
        title = item_data.get("title", "N/A")[:50]

        if issue_check["has_issue"]:
            issue_type = issue_check["issue_type"]
            details = issue_check["details"]

            color = Colors.RED if issue_type == "INACTIVE" else Colors.YELLOW

            log(f"[{i}/{len(asins)}] {color}⚠️  {asin} ({item_id})", Colors.NC)
            log(f"         Título: {title}", color)
            log(f"         Estado: {status}", color)
            log(f"         Problema: {issue_type} - {details}", color)

            items_con_problemas.append({
                "asin": asin,
                "item_id": item_id,
                "title": title,
                "status": status,
                "issue_type": issue_type,
                "details": details
            })

            if issue_type == "INACTIVE":
                stats["inactive"] += 1
            elif issue_type == "PAUSED":
                stats["paused"] += 1
            elif "CATEGORY" in issue_type:
                stats["category_error"] += 1
            else:
                stats["warnings"] += 1
        else:
            log(f"[{i}/{len(asins)}] ✅ {asin} ({item_id}) - {status.upper()}", Colors.GREEN)
            stats["ok"] += 1

        # Rate limiting
        time.sleep(0.3)

    # Resumen
    print()
    log("="*80, Colors.BLUE)
    log("RESUMEN", Colors.BLUE)
    log("="*80, Colors.BLUE)
    log(f"Total revisados:      {stats['total']}")
    log(f"✅ Sin problemas:     {stats['ok']}", Colors.GREEN)
    log(f"⚠️  Inactivos:         {stats['inactive']}", Colors.RED)
    log(f"⏸️  Pausados:          {stats['paused']}", Colors.YELLOW)
    log(f"⚠️  Advertencias:      {stats['warnings']}", Colors.YELLOW)
    log(f"❌ No encontrados:    {stats['not_found']}", Colors.RED)
    log("="*80, Colors.BLUE)

    # Guardar items con problemas
    if items_con_problemas:
        output_file = "items_con_problemas.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(items_con_problemas, f, indent=2, ensure_ascii=False)

        log(f"\n💾 Items con problemas guardados en: {output_file}", Colors.CYAN)

    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Proceso cancelado (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        log(f"\n❌ Error: {e}", Colors.RED)
        import traceback
        traceback.print_exc()
        sys.exit(1)
