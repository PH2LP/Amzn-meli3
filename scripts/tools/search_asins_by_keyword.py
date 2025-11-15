#!/usr/bin/env python3
# ============================================================
# search_asins_by_keyword.py
# ✅ Buscar productos en Amazon por keyword y extraer ASINs
# ✅ Obtener BSR (Best Sellers Rank) y ordenar resultados
# ✅ Alternativa gratis a Helium 10 usando SP-API directamente
# ============================================================

import os
import sys
import json
import requests
import time
from pathlib import Path
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# Agregar src al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
from integrations.amazon_api import get_amazon_access_token

load_dotenv()

SPAPI_BASE = "https://sellingpartnerapi-na.amazon.com"
MARKETPLACE_ID = "ATVPDKIKX0DER"  # US marketplace

# -------------------------------------------------------------
# 🔍 Buscar productos por keyword
# -------------------------------------------------------------

def search_products_by_keyword(keyword: str, max_pages: int = 10, log_callback=None):
    """
    Busca productos en Amazon por keyword usando SP-API searchCatalogItems.

    Args:
        keyword: Palabra clave a buscar (ej: "lego", "wireless keyboard")
        max_pages: Máximo de páginas a obtener (cada página = ~10 ASINs)
        log_callback: Función opcional para loguear progreso (default: print)

    Returns:
        list: Lista de ASINs encontrados
    """
    log = log_callback if log_callback else print

    log(f"\n🔍 Buscando productos para keyword: '{keyword}'")
    log(f"📊 Máximo de páginas: {max_pages} (~{max_pages * 10} ASINs potenciales)\n")

    token = get_amazon_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "x-amz-access-token": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    all_asins = []
    next_token = None
    page = 1

    while page <= max_pages:
        url = f"{SPAPI_BASE}/catalog/2022-04-01/items"

        params = {
            "marketplaceIds": MARKETPLACE_ID,
            "keywords": keyword,
            "pageSize": 10,  # Máximo permitido por Amazon
            "includedData": "summaries"  # Solo lo básico para ser eficiente
        }

        if next_token:
            params["pageToken"] = next_token

        try:
            log(f"   📥 Descargando página {page}/{max_pages}...")
            r = requests.get(url, headers=headers, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()

            # Extraer ASINs de esta página
            items = data.get("items", [])
            page_asins = [item.get("asin") for item in items if item.get("asin")]

            all_asins.extend(page_asins)

            log(f"   ✅ Página {page}: {len(page_asins)} ASINs (total acumulado: {len(all_asins)})")

            # Verificar si hay más páginas
            pagination = data.get("pagination", {})
            next_token = pagination.get("nextToken")

            if not next_token:
                log(f"   ✅ Última página alcanzada ({page})")
                break

            page += 1

            # Rate limiting: Amazon permite ~2 requests/segundo para este endpoint
            # Aumentado a 2s para evitar conflictos con otros procesos que usan la misma API
            time.sleep(2.0)

        except requests.exceptions.HTTPError as e:
            if r.status_code == 403:
                log(f"   ❌ Error 403: Sin permisos para el endpoint de búsqueda")
                log("      Verificá que tu cuenta tenga acceso a Catalog Items API 2022-04-01")
                break
            elif r.status_code == 429:
                log(f"   ⏱️ Rate limit alcanzado, esperando 2 segundos...")
                time.sleep(2)
                continue
            else:
                log(f"   ❌ Error HTTP {r.status_code}: {r.text}")
                break
        except requests.exceptions.RequestException as e:
            log(f"   ❌ Error de conexión: {e}")
            break

    return all_asins

# -------------------------------------------------------------
# 📊 Obtener BSR (Best Sellers Rank) de un ASIN
# -------------------------------------------------------------

def get_bsr_for_asin(asin: str, token: str):
    """
    Obtiene el BSR (Best Sellers Rank) de un ASIN usando SP-API.

    Returns:
        dict: {"asin": str, "bsr": int or None, "category": str or None}
    """

    url = f"{SPAPI_BASE}/catalog/2022-04-01/items/{asin}"

    headers = {
        "Authorization": f"Bearer {token}",
        "x-amz-access-token": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    params = {
        "marketplaceIds": MARKETPLACE_ID,
        "includedData": "salesRanks"
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        # Extraer el BSR más bajo (mejor ranking)
        sales_ranks = data.get("salesRanks", [])

        if not sales_ranks:
            return {"asin": asin, "bsr": None, "category": None}

        # Obtener el BSR de la categoría principal (displayGroupRanks[0])
        best_bsr = None
        best_category = None

        for rank_data in sales_ranks:
            display_group_ranks = rank_data.get("displayGroupRanks", [])
            if display_group_ranks:
                rank_info = display_group_ranks[0]
                rank = rank_info.get("rank")
                if rank and (best_bsr is None or rank < best_bsr):
                    best_bsr = rank
                    best_category = rank_info.get("title", "Unknown")

        return {
            "asin": asin,
            "bsr": best_bsr,
            "category": best_category
        }

    except Exception as e:
        # Si hay error, devolver sin BSR
        return {"asin": asin, "bsr": None, "category": None, "error": str(e)}

# -------------------------------------------------------------
# 📊 Obtener BSR para múltiples ASINs (paralelo)
# -------------------------------------------------------------

def get_bsr_for_asins(asins: list, max_workers: int = 5):
    """
    Obtiene BSR para múltiples ASINs en paralelo.

    Args:
        asins: Lista de ASINs
        max_workers: Número de threads paralelos (default: 5 para no exceder rate limits)

    Returns:
        list: Lista de dicts con {asin, bsr, category}
    """

    print(f"\n📊 Obteniendo BSR para {len(asins)} ASINs...")
    print(f"⚙️  Usando {max_workers} threads paralelos\n")

    token = get_amazon_access_token()
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(get_bsr_for_asin, asin, token): asin for asin in asins}

        completed = 0
        for future in as_completed(futures):
            completed += 1
            try:
                result = future.result()
                results.append(result)

                bsr_str = f"BSR: {result['bsr']:,}" if result.get('bsr') else "BSR: N/A"
                print(f"✅ [{completed}/{len(asins)}] {result['asin']} - {bsr_str}")

            except Exception as e:
                asin = futures[future]
                print(f"❌ [{completed}/{len(asins)}] {asin} - Error: {e}")
                results.append({"asin": asin, "bsr": None, "category": None, "error": str(e)})

            # Rate limiting: pequeña pausa entre requests
            time.sleep(0.2)

    return results

# -------------------------------------------------------------
# 🎯 Ordenar por BSR y filtrar top N
# -------------------------------------------------------------

def filter_top_asins_by_bsr(asin_data: list, top_n: int):
    """
    Ordena ASINs por BSR (menor = mejor) y retorna los top N.

    Args:
        asin_data: Lista de dicts con {asin, bsr, category}
        top_n: Número de ASINs a retornar

    Returns:
        list: Top N ASINs ordenados por BSR
    """

    # Filtrar solo los que tienen BSR
    with_bsr = [x for x in asin_data if x.get('bsr') is not None]
    without_bsr = [x for x in asin_data if x.get('bsr') is None]

    print(f"\n📊 Estadísticas:")
    print(f"   ✅ Con BSR: {len(with_bsr)}")
    print(f"   ⚠️  Sin BSR: {len(without_bsr)}")

    # Ordenar por BSR (menor primero)
    sorted_data = sorted(with_bsr, key=lambda x: x['bsr'])

    # Tomar top N
    top_data = sorted_data[:top_n]

    print(f"\n🏆 Top {len(top_data)} ASINs por BSR:")
    for i, item in enumerate(top_data[:10], 1):
        print(f"   {i}. {item['asin']} - BSR: {item['bsr']:,} ({item.get('category', 'N/A')})")

    if len(top_data) > 10:
        print(f"   ... y {len(top_data) - 10} más")

    return top_data

# -------------------------------------------------------------
# 💾 Guardar ASINs en archivo
# -------------------------------------------------------------

def save_asins_to_file(asins: list, output_file: str = None, append: bool = False, interactive: bool = True, asin_data: list = None):
    """
    Guarda los ASINs en un archivo de texto (uno por línea).

    Args:
        asins: Lista de ASINs (para compatibilidad)
        output_file: Ruta del archivo de salida (default: asins.txt)
        append: Si es True, agrega al final del archivo (default: False = reemplazar)
        interactive: Si es True, pregunta al usuario (default: True)
        asin_data: Lista de dicts con {asin, bsr, category} para guardar JSON detallado (opcional)
    """

    if output_file is None:
        output_file = "asins.txt"

    output_path = Path(output_file)

    # Si el archivo ya existe, preguntar si queremos append o reemplazar
    mode = 'a' if append else 'w'

    if output_path.exists() and interactive:
        print(f"\n⚠️  El archivo {output_file} ya existe")
        choice = input("   ¿Querés (a)gregar al final o (r)eemplazar? [a/r]: ").strip().lower()
        if choice == 'a':
            mode = 'a'
        else:
            mode = 'w'

    # Guardar archivo TXT con ASINs
    with open(output_path, mode, encoding='utf-8') as f:
        for asin in asins:
            f.write(f"{asin}\n")

    action = "agregados" if mode == 'a' else "guardados"
    print(f"\n✅ {len(asins)} ASINs {action} en {output_file}")

    # Si hay datos detallados, guardar JSON
    if asin_data:
        json_file = output_path.with_suffix('.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(asin_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Datos detallados guardados en {json_file}")

# -------------------------------------------------------------
# 🎯 Modo interactivo
# -------------------------------------------------------------

def interactive_mode():
    """
    Modo interactivo: permite buscar por keyword y guardar resultados.
    """

    print("\n" + "="*60)
    print("🔍 BÚSQUEDA DE ASINs POR KEYWORD - Amazon SP-API")
    print("="*60)

    keyword = input("\n📝 Ingresá la keyword (ej: 'lego', 'keyboard'): ").strip()

    if not keyword:
        print("❌ Keyword vacía, saliendo...")
        return

    max_results = input("📊 ¿Cuántos ASINs querés obtener? (ej: 100, 500, 1000): ").strip()

    try:
        max_results = int(max_results)
        max_pages = (max_results + 9) // 10  # Redondear hacia arriba
    except ValueError:
        print("⚠️  Número inválido, usando default de 100 ASINs")
        max_pages = 10

    # Buscar ASINs
    asins = search_products_by_keyword(keyword, max_pages=max_pages)

    if not asins:
        print("\n❌ No se encontraron ASINs")
        return

    print(f"\n📋 Primeros 10 ASINs encontrados:")
    for i, asin in enumerate(asins[:10], 1):
        print(f"   {i}. {asin}")

    if len(asins) > 10:
        print(f"   ... y {len(asins) - 10} más")

    # Guardar en archivo
    save_choice = input("\n💾 ¿Querés guardar estos ASINs? [s/n]: ").strip().lower()

    if save_choice == 's':
        output_file = input("   📁 Nombre del archivo (default: asins.txt): ").strip()
        if not output_file:
            output_file = "asins.txt"

        save_asins_to_file(asins, output_file)
    else:
        print("\n✅ ASINs no guardados (solo mostrados en pantalla)")

# -------------------------------------------------------------
# 🧪 CLI Mode
# -------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        # Modo CLI: python search_asins_by_keyword.py "lego" 1500 500 [output_file] [--append]
        # Args: keyword, max_results, top_n, output_file
        keyword = sys.argv[1]
        max_results = int(sys.argv[2]) if len(sys.argv) >= 3 else 100
        top_n = int(sys.argv[3]) if len(sys.argv) >= 4 else max_results
        output_file = sys.argv[4] if len(sys.argv) >= 5 else "asins.txt"
        append = "--append" in sys.argv

        print(f"\n{'='*60}")
        print(f"🔍 Búsqueda de ASINs por Keyword con BSR")
        print(f"{'='*60}")
        print(f"📝 Keyword: {keyword}")
        print(f"📊 ASINs a buscar: {max_results}")
        print(f"🏆 Top ASINs a guardar (por BSR): {top_n}")
        print(f"💾 Archivo salida: {output_file}")
        print(f"{'='*60}\n")

        # Paso 1: Buscar ASINs
        max_pages = (max_results + 9) // 10
        asins = search_products_by_keyword(keyword, max_pages=max_pages)

        if not asins:
            print("\n❌ No se encontraron ASINs")
            sys.exit(1)

        print(f"\n✅ Total ASINs encontrados: {len(asins)}")

        # Paso 2: Obtener BSR para todos los ASINs
        asin_data = get_bsr_for_asins(asins, max_workers=5)

        # Paso 3: Ordenar por BSR y obtener top N
        top_data = filter_top_asins_by_bsr(asin_data, top_n)

        # Paso 4: Guardar resultados
        top_asins = [x['asin'] for x in top_data]
        save_asins_to_file(top_asins, output_file, append=append, interactive=False, asin_data=top_data)

        print(f"\n{'='*60}")
        print(f"✅ Proceso completado exitosamente")
        print(f"{'='*60}")

    else:
        # Modo interactivo
        try:
            interactive_mode()
        except KeyboardInterrupt:
            print("\n\n👋 Búsqueda cancelada")
            sys.exit(0)
