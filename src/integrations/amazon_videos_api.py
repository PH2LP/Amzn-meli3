#!/usr/bin/env python3
"""
Amazon Videos Extractor

Extrae videos de productos Amazon (listing videos + customer videos)
usando HTML parsing del product page.
"""
import os
import re
import requests
import json
from typing import Dict, List
from html import unescape
from time import sleep


def get_product_videos(asin: str) -> Dict:
    """
    Obtiene TODOS los videos de un producto Amazon (listing + customers).

    Args:
        asin: ASIN del producto

    Returns:
        Dict con:
        {
            "asin": str,
            "total_videos": int,
            "listing_videos": List[Dict],  # Videos del seller/brand (groupType: IB_G1)
            "customer_videos": List[Dict],  # Videos de customers (groupType: IB_G2)
            "all_videos": List[Dict],  # Todos los videos combinados
            "error": str or None
        }

        Cada video tiene:
        {
            "title": str,
            "url": str,  # Video URL (HLS .m3u8 format)
            "duration_seconds": int,
            "thumbnail": str,
            "content_id": str,
            "group_type": str,  # IB_G1 (listing) o IB_G2 (customer)
            "creator_profile": dict,  # Info del creator si es customer video
        }
    """
    result = {
        "asin": asin,
        "total_videos": 0,
        "listing_videos": [],
        "customer_videos": [],
        "listing_horizontal": [],
        "listing_vertical": [],
        "customer_horizontal": [],
        "customer_vertical": [],
        "all_videos": [],
        "error": None
    }

    try:
        # Setup session con headers realistas para evitar CAPTCHA
        session = requests.Session()

        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        })

        # Paso 1: GET homepage para obtener cookies (evita CAPTCHA)
        session.get('https://www.amazon.com', timeout=30)
        sleep(1)

        # Paso 2: GET product page
        url = f'https://www.amazon.com/dp/{asin}'
        response = session.get(url, timeout=30)

        if response.status_code != 200:
            result["error"] = f"HTTP {response.status_code}"
            return result

        html = response.text

        # Verificar si hay CAPTCHA
        if 'captcha' in html.lower():
            result["error"] = "CAPTCHA detected"
            return result

        # Paso 3: Extraer videos del HTML
        # Amazon incluye un array JSON con todos los videos en el HTML
        # Formato: "videos": [{...}, {...}, ...]

        videos_pattern = r'"videos":\s*(\[[^\n]+\])'
        matches = re.findall(videos_pattern, html, re.DOTALL)

        if not matches:
            # No hay videos en este producto
            return result

        # Parsear el primer match (es el principal)
        try:
            # Unescape HTML entities y limpiar
            video_json = unescape(matches[0])
            video_json = video_json.replace('&quot;', '"')

            # Limpiar escape sequences inválidos
            # Reemplazar backslashes seguidos de caracteres no válidos
            video_json = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', video_json)

            videos = json.loads(video_json)

            # Procesar cada video
            for video in videos:
                video_url = video.get("url", "")

                # Detectar orientación basándose en la URL
                # URLs con "vertical" son verticales, el resto son horizontales
                is_vertical = "vertical" in video_url.lower()
                orientation = "vertical" if is_vertical else "horizontal"

                video_data = {
                    "title": video.get("title", ""),
                    "url": video_url,
                    "duration_seconds": video.get("durationSeconds", 0),
                    "thumbnail": video.get("thumb", ""),
                    "content_id": video.get("aciContentId", ""),
                    "group_type": video.get("groupType", ""),
                    "orientation": orientation,
                    "creator_profile": video.get("creatorProfile", {}),
                }

                # Clasificar por tipo (listing vs customer)
                if video.get("groupType") == "IB_G1":
                    # Video del listing (seller/brand)
                    result["listing_videos"].append(video_data)

                    # Subclasificar por orientación
                    if is_vertical:
                        result["listing_vertical"].append(video_data)
                    else:
                        result["listing_horizontal"].append(video_data)

                elif video.get("groupType") == "IB_G2":
                    # Video de customer
                    result["customer_videos"].append(video_data)

                    # Subclasificar por orientación
                    if is_vertical:
                        result["customer_vertical"].append(video_data)
                    else:
                        result["customer_horizontal"].append(video_data)

                result["all_videos"].append(video_data)

            result["total_videos"] = len(result["all_videos"])

        except json.JSONDecodeError as e:
            result["error"] = f"JSON parsing error: {e}"
        except Exception as e:
            result["error"] = f"Video extraction error: {e}"

        return result

    except Exception as e:
        result["error"] = str(e)
        return result


if __name__ == "__main__":
    import sys

    test_asin = sys.argv[1] if len(sys.argv) > 1 else "B09X7MPX8L"

    print("=" * 80)
    print(f"TEST: Extrayendo videos de Amazon")
    print(f"ASIN: {test_asin}")
    print("=" * 80)
    print()

    import time
    start = time.time()

    result = get_product_videos(test_asin)

    elapsed = time.time() - start

    print("Resultados:")
    print(f"  📹 Total videos: {result['total_videos']}")
    print(f"  🎬 Listing videos: {len(result['listing_videos'])}")
    print(f"  👥 Customer videos: {len(result['customer_videos'])}")
    print(f"  ⏱️  Tiempo: {elapsed:.1f}s")

    if result.get('error'):
        print(f"  ⚠️  Error: {result['error']}")

    print()

    # Mostrar primeros 3 listing videos
    if result['listing_videos']:
        print("=" * 80)
        print("LISTING VIDEOS (del seller/brand):")
        print("=" * 80)
        for i, video in enumerate(result['listing_videos'][:3]):
            print(f"\nVideo {i+1}:")
            print(f"  Título: {video['title']}")
            print(f"  Duración: {video['duration_seconds']}s")
            print(f"  URL: {video['url'][:80]}...")
            print(f"  Thumbnail: {video['thumbnail'][:80]}...")

    # Mostrar primeros 3 customer videos
    if result['customer_videos']:
        print()
        print("=" * 80)
        print("CUSTOMER VIDEOS:")
        print("=" * 80)
        for i, video in enumerate(result['customer_videos'][:3]):
            print(f"\nVideo {i+1}:")
            print(f"  Título: {video['title']}")
            print(f"  Duración: {video['duration_seconds']}s")
            print(f"  URL: {video['url'][:80]}...")
            print(f"  Creator: {video.get('creator_profile', {})}")

    print()
    print("✅ Función get_product_videos() lista para usar")
    print("   - Importar: from src.integrations.amazon_videos_api import get_product_videos")
    print("   - Usar: videos = get_product_videos('B09X7MPX8L')")
