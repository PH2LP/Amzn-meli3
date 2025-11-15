#!/usr/bin/env python3
"""
============================================================
fetch_popular_keywords.py
Obtiene las keywords más populares de Amazon usando DataForSEO API
============================================================
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATAFORSEO_BULK_VOLUME_URL = "https://api.dataforseo.com/v3/dataforseo_labs/amazon/bulk_search_volume/live"
DATAFORSEO_RELATED_KW_URL = "https://api.dataforseo.com/v3/dataforseo_labs/amazon/related_keywords/live"
DATAFORSEO_LOGIN = os.getenv("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.getenv("DATAFORSEO_PASSWORD")

# Archivo de salida
MASTER_KEYWORDS_FILE = Path(__file__).parent.parent.parent / "config" / "master_keywords.json"


def discover_related_keywords(seed_keywords: list, depth: int = 2, location_code: int = 2840):
    """
    Descubre keywords relacionadas a partir de keywords semilla usando DataForSEO.

    Args:
        seed_keywords: Lista de keywords semilla (ej: ["phone case", "bluetooth headphones"])
        depth: Profundidad de búsqueda (1-3, mayor = más keywords)
        location_code: Código de ubicación (2840 = United States)

    Returns:
        list: Lista de keywords descubiertas con sus datos
    """

    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        print("❌ Error: Falta configurar DATAFORSEO_LOGIN y DATAFORSEO_PASSWORD en .env")
        return []

    all_keywords = []
    total_cost = 0

    print(f"\n🔍 Descubriendo keywords relacionadas desde {len(seed_keywords)} semillas...")
    print(f"   Profundidad: {depth} (cada profundidad descubre ~100-200 keywords por semilla)")

    for i, seed in enumerate(seed_keywords, 1):
        print(f"\n📥 Semilla {i}/{len(seed_keywords)}: '{seed}'")

        payload = [{
            "location_code": location_code,
            "language_name": "English",
            "keyword": seed,
            "depth": depth,
            "include_seed_keyword": True,
            "include_serp_info": False
        }]

        try:
            response = requests.post(
                DATAFORSEO_RELATED_KW_URL,
                json=payload,
                auth=(DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD),
                timeout=60
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status_code") != 20000:
                print(f"   ❌ Error: {data.get('status_message')}")
                continue

            tasks = data.get("tasks", [])
            if not tasks or not tasks[0].get("result"):
                print(f"   ⚠️  No se encontraron keywords relacionadas")
                continue

            result = tasks[0]["result"]
            items = result[0].get("items", []) if result and len(result) > 0 else []

            # Extraer keywords con search volume
            if not items:
                print(f"   ⚠️  No hay items en la respuesta")
                continue

            for item in items:
                kw_data = item.get("keyword_data", {})
                keyword = kw_data.get("keyword")
                keyword_info = kw_data.get("keyword_info", {})
                search_volume = keyword_info.get("search_volume")

                if keyword and search_volume:
                    all_keywords.append({
                        "keyword": keyword,
                        "search_volume": search_volume,
                        "competition": kw_data.get("competition"),
                        "cpc": kw_data.get("cpc")
                    })

            cost = data.get("cost", 0)
            total_cost += cost

            print(f"   ✅ {len(items)} keywords descubiertas (costo: ${cost})")

        except requests.exceptions.RequestException as e:
            print(f"   ❌ Error: {e}")
            continue

    # Eliminar duplicados
    unique_keywords = {}
    for kw in all_keywords:
        keyword_str = kw["keyword"]
        if keyword_str not in unique_keywords:
            unique_keywords[keyword_str] = kw

    all_keywords = list(unique_keywords.values())

    # Ordenar por search volume
    all_keywords.sort(key=lambda x: x.get("search_volume", 0), reverse=True)

    print(f"\n✅ Total keywords únicas descubiertas: {len(all_keywords)}")
    print(f"💰 Costo total: ${total_cost:.3f}")

    return all_keywords


def get_popular_keywords_from_dataforseo(keywords: list, location_code: int = 2840):
    """
    Obtiene datos de keywords (incluyendo search volume) desde DataForSEO.

    Args:
        keywords: Lista de keywords a consultar
        location_code: Código de ubicación (2840 = United States)

    Returns:
        list: Lista de keywords con sus datos (search_volume, competition, etc)
    """

    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        print("❌ Error: Falta configurar DATAFORSEO_LOGIN y DATAFORSEO_PASSWORD en .env")
        return None

    # Preparar payload
    payload = [{
        "location_code": location_code,
        "keywords": keywords
    }]

    print(f"📡 Consultando DataForSEO API para {len(keywords)} keywords...")

    try:
        response = requests.post(
            DATAFORSEO_API_URL,
            json=payload,
            auth=(DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD),
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        # Verificar respuesta exitosa
        if data.get("status_code") != 20000:
            print(f"❌ Error en la respuesta de DataForSEO: {data.get('status_message')}")
            return None

        # Extraer resultados
        tasks = data.get("tasks", [])
        if not tasks or not tasks[0].get("result"):
            print("❌ No se obtuvieron resultados de DataForSEO")
            return None

        results = tasks[0]["result"]

        # Calcular costo
        cost = data.get("cost", 0)
        print(f"✅ Datos obtenidos exitosamente")
        print(f"💰 Costo: ${cost}")

        return results

    except requests.exceptions.RequestException as e:
        print(f"❌ Error al consultar DataForSEO API: {e}")
        return None


def fetch_and_save_popular_keywords(seed_keywords: list = None, use_discovery: bool = True, depth: int = 2, output_file: Path = None):
    """
    Obtiene keywords populares y las guarda en master_keywords.json.

    Args:
        seed_keywords: Lista de keywords semilla para descubrimiento (opcional)
        use_discovery: Si True, usa discovery automático; si False, solo obtiene search volume
        depth: Profundidad de descubrimiento (1-3, mayor = más keywords)
        output_file: Archivo donde guardar (default: config/master_keywords.json)
    """

    if output_file is None:
        output_file = MASTER_KEYWORDS_FILE

    # Si no se proporcionan keywords, usar las del archivo actual
    if seed_keywords is None:
        # Prioridad 1: seed_keywords.json (keywords curadas del usuario)
        keywords_config_file = Path(__file__).parent.parent.parent / "config" / "seed_keywords.json"

        if not keywords_config_file.exists():
            # Prioridad 2: keywords_extended.json
            keywords_config_file = Path(__file__).parent.parent.parent / "config" / "keywords_extended.json"

        if not keywords_config_file.exists():
            # Prioridad 3: keywords.json
            keywords_config_file = Path(__file__).parent.parent.parent / "config" / "keywords.json"

        if keywords_config_file.exists():
            with open(keywords_config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                seed_keywords = [k["keyword"] for k in config.get("keywords", [])]
        else:
            # Keywords semilla por defecto (fallback)
            seed_keywords = [
                "phone case", "wireless headphones", "bluetooth speaker",
                "laptop stand", "usb cable", "power bank", "led lights",
                "yoga mat", "water bottle", "backpack"
            ]

    print(f"\n{'='*70}")
    print("🔍 SISTEMA DE DESCUBRIMIENTO AUTOMÁTICO DE KEYWORDS")
    print(f"{'='*70}\n")
    print(f"Keywords semilla: {len(seed_keywords)}")
    print(f"Modo: {'DISCOVERY (expandir automáticamente)' if use_discovery else 'VOLUME ONLY'}")
    if use_discovery:
        print(f"Profundidad: {depth} (estimado: {len(seed_keywords) * 100 * depth} keywords)")
    print(f"Archivo de salida: {output_file}")

    # Descubrir keywords automáticamente o solo obtener search volume
    if use_discovery:
        print(f"\n🚀 Descubriendo keywords relacionadas...")
        keywords_data_raw = discover_related_keywords(seed_keywords, depth=depth)
    else:
        print(f"\n📊 Obteniendo search volume de keywords...")
        results = get_popular_keywords_from_dataforseo(seed_keywords)
        keywords_data_raw = results if results else []

    if not keywords_data_raw:
        print("❌ No se obtuvieron keywords")
        return False

    # Procesar resultados y crear lista ordenada
    keywords_data = []

    for item in keywords_data_raw:
        keyword = item.get("keyword")
        search_volume = item.get("search_volume", 0)

        # Filtrar keywords de baja calidad (< 50 búsquedas/mes)
        if search_volume < 50:
            continue

        keywords_data.append({
            "keyword": keyword,
            "search_volume": search_volume,
            "competition": item.get("competition", 0),
            "cpc": item.get("cpc", 0),
            "processed": False,
            "asins_published": 0,
            "last_processed": None
        })

    # Ordenar por search volume (mayor a menor)
    keywords_data.sort(key=lambda x: x["search_volume"], reverse=True)

    # Crear estructura completa
    from datetime import datetime
    master_data = {
        "comment": "Master list de keywords populares descubiertas automáticamente y ordenadas por search volume",
        "version": "2.0",
        "last_updated": datetime.now().isoformat(),
        "discovery_enabled": use_discovery,
        "discovery_depth": depth if use_discovery else 0,
        "total_keywords": len(keywords_data),
        "total_publications_target": 50000,
        "total_publications_current": 0,
        "keywords": keywords_data
    }

    # Guardar archivo
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(master_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Master keywords guardadas en {output_file}")
    print(f"\n📊 ESTADÍSTICAS:")
    print(f"   Total keywords: {len(keywords_data)}")
    print(f"   Rango de search volume: {keywords_data[-1]['search_volume']:,} - {keywords_data[0]['search_volume']:,}")
    print(f"\n🏆 TOP 10 KEYWORDS MÁS POPULARES:")
    for i, kw in enumerate(keywords_data[:10], 1):
        print(f"   {i:2d}. {kw['keyword']:35s} → {kw['search_volume']:,} búsquedas/mes")

    return True


def update_keyword_progress(keyword: str, asins_published: int):
    """
    Actualiza el progreso de una keyword en master_keywords.json.

    Args:
        keyword: Keyword procesada
        asins_published: Cantidad de ASINs publicados
    """

    if not MASTER_KEYWORDS_FILE.exists():
        print(f"⚠️  Archivo {MASTER_KEYWORDS_FILE} no existe")
        return False

    with open(MASTER_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Buscar keyword y actualizar
    for kw in data["keywords"]:
        if kw["keyword"] == keyword:
            kw["processed"] = True
            kw["asins_published"] = asins_published

            from datetime import datetime
            kw["last_processed"] = datetime.now().isoformat()

            # Actualizar totales
            data["total_publications_current"] = sum(k["asins_published"] for k in data["keywords"])
            data["last_updated"] = datetime.now().isoformat()

            break

    # Guardar cambios
    with open(MASTER_KEYWORDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return True


def get_next_keyword():
    """
    Obtiene la siguiente keyword NO procesada de master_keywords.json.

    Returns:
        dict: Datos de la keyword o None si no hay más
    """

    if not MASTER_KEYWORDS_FILE.exists():
        print(f"⚠️  Archivo {MASTER_KEYWORDS_FILE} no existe")
        return None

    with open(MASTER_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Buscar primera keyword no procesada
    for kw in data["keywords"]:
        if not kw.get("processed", False):
            return kw

    return None


def get_progress_stats():
    """
    Obtiene estadísticas del progreso actual.

    Returns:
        dict: Estadísticas de progreso
    """

    if not MASTER_KEYWORDS_FILE.exists():
        return None

    with open(MASTER_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total_keywords = len(data["keywords"])
    processed_keywords = sum(1 for k in data["keywords"] if k.get("processed", False))
    total_publications = data.get("total_publications_current", 0)
    target_publications = data.get("total_publications_target", 10000)

    return {
        "total_keywords": total_keywords,
        "processed_keywords": processed_keywords,
        "pending_keywords": total_keywords - processed_keywords,
        "total_publications": total_publications,
        "target_publications": target_publications,
        "progress_percentage": (total_publications / target_publications * 100) if target_publications > 0 else 0
    }


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sistema de descubrimiento automático de keywords con DataForSEO")
    parser.add_argument("--fetch", action="store_true", help="Descubrir keywords desde DataForSEO")
    parser.add_argument("--no-discovery", action="store_true", help="Solo obtener search volume (sin discovery)")
    parser.add_argument("--depth", type=int, default=2, choices=[1,2,3], help="Profundidad de discovery (1-3, default: 2)")
    parser.add_argument("--stats", action="store_true", help="Mostrar estadísticas de progreso")
    parser.add_argument("--next", action="store_true", help="Mostrar siguiente keyword a procesar")

    args = parser.parse_args()

    if args.fetch:
        use_discovery = not args.no_discovery
        fetch_and_save_popular_keywords(use_discovery=use_discovery, depth=args.depth)
    elif args.stats:
        stats = get_progress_stats()
        if stats:
            print(f"\n{'='*60}")
            print("📊 ESTADÍSTICAS DE PROGRESO")
            print(f"{'='*60}")
            print(f"Keywords totales:     {stats['total_keywords']}")
            print(f"Keywords procesadas:  {stats['processed_keywords']}")
            print(f"Keywords pendientes:  {stats['pending_keywords']}")
            print(f"Publicaciones:        {stats['total_publications']:,} / {stats['target_publications']:,}")
            print(f"Progreso:             {stats['progress_percentage']:.1f}%")
            print(f"{'='*60}\n")
        else:
            print("❌ No se pudo obtener estadísticas")
    elif args.next:
        next_kw = get_next_keyword()
        if next_kw:
            print(f"\n🎯 Siguiente keyword: {next_kw['keyword']}")
            print(f"   Search volume: {next_kw['search_volume']:,}")
        else:
            print("\n✅ No hay más keywords pendientes")
    else:
        parser.print_help()
