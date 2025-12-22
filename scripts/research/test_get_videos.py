#!/usr/bin/env python3
"""
Test script: Obtener videos de productos Amazon

Demuestra cómo usar la función get_product_videos() para extraer
videos de listing y customer videos de cualquier ASIN.
"""

import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from src.integrations.amazon_videos_api import get_product_videos
import json


def test_get_videos(asin: str):
    """Test completo de extracción de videos"""

    print("=" * 80)
    print(f"EXTRAYENDO VIDEOS DE ASIN: {asin}")
    print("=" * 80)
    print()

    # Obtener videos
    result = get_product_videos(asin)

    # Resultados
    print(f"📊 RESUMEN:")
    print(f"  Total videos: {result['total_videos']}")
    print(f"  Listing videos (del seller): {len(result['listing_videos'])}")
    print(f"  Customer videos: {len(result['customer_videos'])}")

    if result['error']:
        print(f"  ⚠️  Error: {result['error']}")
        return

    print()

    # Listing videos
    if result['listing_videos']:
        print("=" * 80)
        print("🎬 LISTING VIDEOS (del seller/brand)")
        print("=" * 80)
        for i, video in enumerate(result['listing_videos'], 1):
            print(f"\n{i}. {video['title']}")
            print(f"   Duración: {video['duration_seconds']}s ({video['duration_seconds']//60}min {video['duration_seconds']%60}s)")
            print(f"   URL: {video['url']}")
            print(f"   Thumbnail: {video['thumbnail']}")
            print(f"   Content ID: {video['content_id']}")

    # Customer videos
    if result['customer_videos']:
        print()
        print("=" * 80)
        print("👥 CUSTOMER VIDEOS")
        print("=" * 80)
        for i, video in enumerate(result['customer_videos'], 1):
            print(f"\n{i}. {video['title']}")
            print(f"   Duración: {video['duration_seconds']}s ({video['duration_seconds']//60}min {video['duration_seconds']%60}s)")
            print(f"   URL: {video['url']}")
            print(f"   Thumbnail: {video['thumbnail']}")
            print(f"   Content ID: {video['content_id']}")

    # Si no hay videos
    if result['total_videos'] == 0:
        print("\n❌ No se encontraron videos en este producto")

    print()
    print("=" * 80)

    # Guardar JSON completo
    output_file = f"/tmp/videos_{asin}.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"✅ JSON completo guardado en: {output_file}")
    print()


if __name__ == "__main__":
    import sys

    # ASINs de ejemplo para testear
    test_asins = [
        "B09X7MPX8L",  # SanDisk - tiene listing + customer videos
        "B0D1XD1ZV3",  # AirPods - tiene listing videos
    ]

    # Si se pasa un ASIN por argumento, usar ese
    if len(sys.argv) > 1:
        test_asins = [sys.argv[1]]

    # Test cada ASIN
    for asin in test_asins:
        test_get_videos(asin)
        print("\n\n")
