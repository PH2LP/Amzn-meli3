#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 13_get_videos.py - OBTENER VIDEOS DE PRODUCTOS
# ═══════════════════════════════════════════════════════════════════════════════
#
# ¿Qué hace?
#   Descarga videos de productos de Amazon para incluirlos en listings de ML.
#
# Comando:
#   python3 13_get_videos.py
# 
# ═══════════════════════════════════════════════════════════════════════════════
import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.integrations.amazon_videos_api import get_product_videos


def format_duration(seconds: int) -> str:
    """Formatea segundos a formato legible"""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def main():
    if len(sys.argv) < 2:
        print("=" * 80)
        print("GET PRODUCT VIDEOS - Extrae videos de productos Amazon")
        print("=" * 80)
        print()
        print("Uso:")
        print("  python3 22_get_product_videos.py <ASIN>")
        print("  python3 22_get_product_videos.py <ASIN> --json")
        print("  python3 22_get_product_videos.py <ASIN> --download")
        print()
        print("Ejemplos:")
        print("  python3 22_get_product_videos.py B09X7MPX8L")
        print("  python3 22_get_product_videos.py B0CLC6NBBX --json")
        print()
        sys.exit(1)

    asin = sys.argv[1].strip().upper()
    output_json = "--json" in sys.argv
    download = "--download" in sys.argv

    print("=" * 80)
    print(f"EXTRAYENDO VIDEOS - ASIN: {asin}")
    print("=" * 80)
    print()

    # Obtener videos
    import time
    start = time.time()

    result = get_product_videos(asin)

    elapsed = time.time() - start

    # Verificar error
    if result.get('error'):
        print(f"❌ ERROR: {result['error']}")
        print()
        sys.exit(1)

    # Mostrar resultados
    print(f"✅ Videos encontrados: {result['total_videos']}")
    print(f"   📹 Listing videos: {len(result['listing_videos'])}")
    print(f"      📱 Vertical: {len(result['listing_vertical'])}")
    print(f"      🖥️  Horizontal: {len(result['listing_horizontal'])}")
    print(f"   👥 Customer videos: {len(result['customer_videos'])}")
    print(f"      📱 Vertical: {len(result['customer_vertical'])}")
    print(f"      🖥️  Horizontal: {len(result['customer_horizontal'])}")
    print(f"   ⏱️  Tiempo: {elapsed:.1f}s")
    print()

    if result['total_videos'] == 0:
        print("❌ Este producto no tiene videos")
        print()
        sys.exit(0)

    # Opción JSON
    if output_json:
        output_file = f"videos_{asin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"💾 JSON guardado en: {output_file}")
        print()
        sys.exit(0)

    # Mostrar listing videos - Horizontal
    if result['listing_horizontal']:
        print("=" * 80)
        print("🎬 LISTING VIDEOS - HORIZONTAL (del seller/brand)")
        print("=" * 80)
        print()
        for i, video in enumerate(result['listing_horizontal'], 1):
            print(f"{i}. {video['title']}")
            print(f"   ⏱️  Duración: {format_duration(video['duration_seconds'])}")
            print(f"   📐 Orientación: 🖥️  Horizontal")
            print(f"   🔗 URL: {video['url']}")
            print(f"   🖼️  Thumbnail: {video['thumbnail']}")
            print()

    # Mostrar listing videos - Vertical
    if result['listing_vertical']:
        print("=" * 80)
        print("🎬 LISTING VIDEOS - VERTICAL (del seller/brand)")
        print("=" * 80)
        print()
        for i, video in enumerate(result['listing_vertical'], 1):
            print(f"{i}. {video['title']}")
            print(f"   ⏱️  Duración: {format_duration(video['duration_seconds'])}")
            print(f"   📐 Orientación: 📱 Vertical")
            print(f"   🔗 URL: {video['url']}")
            print(f"   🖼️  Thumbnail: {video['thumbnail']}")
            print()

    # Mostrar customer videos - Horizontal
    if result['customer_horizontal']:
        print("=" * 80)
        print("👥 CUSTOMER VIDEOS - HORIZONTAL")
        print("=" * 80)
        print()
        for i, video in enumerate(result['customer_horizontal'], 1):
            print(f"{i}. {video['title']}")
            print(f"   ⏱️  Duración: {format_duration(video['duration_seconds'])}")
            print(f"   📐 Orientación: 🖥️  Horizontal")
            print(f"   🔗 URL: {video['url']}")
            print(f"   🖼️  Thumbnail: {video['thumbnail']}")
            print()

    # Mostrar customer videos - Vertical
    if result['customer_vertical']:
        print("=" * 80)
        print("👥 CUSTOMER VIDEOS - VERTICAL")
        print("=" * 80)
        print()
        for i, video in enumerate(result['customer_vertical'], 1):
            print(f"{i}. {video['title']}")
            print(f"   ⏱️  Duración: {format_duration(video['duration_seconds'])}")
            print(f"   📐 Orientación: 📱 Vertical")
            print(f"   🔗 URL: {video['url']}")
            print(f"   🖼️  Thumbnail: {video['thumbnail']}")
            print()

    # Opción download
    if download:
        print("=" * 80)
        print("📥 INSTRUCCIONES PARA DESCARGAR")
        print("=" * 80)
        print()
        print("Los videos están en formato HLS (.m3u8)")
        print("Para descargarlos, usa ffmpeg:")
        print()

        for i, video in enumerate(result['all_videos'], 1):
            tipo = "listing" if video['group_type'] == 'IB_G1' else "customer"
            filename = f"{asin}_{tipo}_{i}.mp4"
            print(f'{i}. ffmpeg -i "{video["url"]}" -c copy "{filename}"')

        print()
        print("O copia las URLs y ábrelas en un navegador/reproductor HLS")
        print()

    # Guardar archivo con URLs
    urls_file = f"videos_{asin}_urls.txt"
    with open(urls_file, 'w', encoding='utf-8') as f:
        f.write(f"Videos de ASIN: {asin}\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total: {result['total_videos']} videos\n")
        f.write(f"  Listing: {len(result['listing_videos'])} (H:{len(result['listing_horizontal'])}, V:{len(result['listing_vertical'])})\n")
        f.write(f"  Customer: {len(result['customer_videos'])} (H:{len(result['customer_horizontal'])}, V:{len(result['customer_vertical'])})\n")
        f.write("=" * 80 + "\n\n")

        if result['listing_horizontal']:
            f.write("LISTING VIDEOS - HORIZONTAL:\n")
            f.write("-" * 80 + "\n")
            for i, video in enumerate(result['listing_horizontal'], 1):
                f.write(f"{i}. {video['title']}\n")
                f.write(f"   Duración: {format_duration(video['duration_seconds'])}\n")
                f.write(f"   Orientación: Horizontal\n")
                f.write(f"   URL: {video['url']}\n")
                f.write(f"   Thumbnail: {video['thumbnail']}\n\n")

        if result['listing_vertical']:
            f.write("\nLISTING VIDEOS - VERTICAL:\n")
            f.write("-" * 80 + "\n")
            for i, video in enumerate(result['listing_vertical'], 1):
                f.write(f"{i}. {video['title']}\n")
                f.write(f"   Duración: {format_duration(video['duration_seconds'])}\n")
                f.write(f"   Orientación: Vertical\n")
                f.write(f"   URL: {video['url']}\n")
                f.write(f"   Thumbnail: {video['thumbnail']}\n\n")

        if result['customer_horizontal']:
            f.write("\nCUSTOMER VIDEOS - HORIZONTAL:\n")
            f.write("-" * 80 + "\n")
            for i, video in enumerate(result['customer_horizontal'], 1):
                f.write(f"{i}. {video['title']}\n")
                f.write(f"   Duración: {format_duration(video['duration_seconds'])}\n")
                f.write(f"   Orientación: Horizontal\n")
                f.write(f"   URL: {video['url']}\n")
                f.write(f"   Thumbnail: {video['thumbnail']}\n\n")

        if result['customer_vertical']:
            f.write("\nCUSTOMER VIDEOS - VERTICAL:\n")
            f.write("-" * 80 + "\n")
            for i, video in enumerate(result['customer_vertical'], 1):
                f.write(f"{i}. {video['title']}\n")
                f.write(f"   Duración: {format_duration(video['duration_seconds'])}\n")
                f.write(f"   Orientación: Vertical\n")
                f.write(f"   URL: {video['url']}\n")
                f.write(f"   Thumbnail: {video['thumbnail']}\n\n")

    print(f"💾 URLs guardadas en: {urls_file}")
    print()

    print("=" * 80)
    print("✅ COMPLETADO")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
