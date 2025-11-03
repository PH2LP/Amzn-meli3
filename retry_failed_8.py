#!/usr/bin/env python3
"""
Reintenta publicar los 8 productos que fallaron con las validaciones ahora relajadas.
"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from mainglobal import publish_item

def main():
    """Reintenta publicar los 8 ASINs fallidos."""

    failed_asins = [
        "B092RCLKHN",   # GPS - Blocked by dimensions
        "B0BGQLZ921",   # LEGO Flowers - Blocked by dimensions
        "B0BXSLRQH7",   # Watch - Blocked by dimensions
        "B0DCYZJBYD",   # Basketball - Blocked by dimensions + Non-leaf category
        "B0CJQG4PMF",   # Earrings - Blocked by dimensions
        "B0CLC6NBBX",   # Headphones - Missing BRAND
        "B0D1Z99167",   # Personal Care - GTIN duplicate + Missing BRAND
        "B0BRNY9HZB"    # Rock Painting - Blocked by dimensions
    ]

    storage_dir = Path("/Users/felipemelucci/Desktop/revancha/storage")
    mini_ml_dir = storage_dir / "logs" / "publish_ready"

    ml_token = os.getenv("ML_TOKEN")
    if not ml_token:
        print("❌ ML_TOKEN no encontrado")
        return

    results = {
        "published": [],
        "failed": []
    }

    print(f"\n{'='*70}")
    print(f"🔄 REINTENTANDO PUBLICACIÓN DE 8 PRODUCTOS FALLIDOS")
    print(f"{'='*70}\n")

    for i, asin in enumerate(failed_asins, 1):
        print(f"\n{'='*70}")
        print(f"📦 [{i}/8] Publicando {asin}")
        print(f"{'='*70}")

        mini_ml_path = mini_ml_dir / f"{asin}_mini_ml.json"

        if not mini_ml_path.exists():
            print(f"❌ No existe mini_ml para {asin}")
            results["failed"].append(asin)
            continue

        with open(mini_ml_path, 'r', encoding='utf-8') as f:
            mini_ml = json.load(f)

        print(f"📂 Categoría: {mini_ml.get('category_id')} - {mini_ml.get('category_name')}")
        print(f"🏷️  Título: {mini_ml.get('title_ai', '')[:80]}...")

        try:
            result = publish_item(asin_json=mini_ml)

            if result and isinstance(result, dict):
                item_id = result.get("item_id") or result.get("id")
                print(f"✅ PUBLICADO: {asin} → {item_id}")
                results["published"].append({
                    "asin": asin,
                    "item_id": item_id,
                    "category": f"{mini_ml.get('category_id')} - {mini_ml.get('category_name')}"
                })
            else:
                print(f"❌ FALLÓ: {asin}")
                results["failed"].append(asin)

        except Exception as e:
            print(f"❌ Error publicando {asin}: {e}")
            import traceback
            traceback.print_exc()
            results["failed"].append(asin)

    # Resumen final
    print(f"\n{'='*70}")
    print(f"📊 RESUMEN FINAL")
    print(f"{'='*70}")
    print(f"✅ Publicados: {len(results['published'])}/8")
    print(f"❌ Fallidos: {len(results['failed'])}/8")

    if results['published']:
        print(f"\n✅ ASINs publicados exitosamente:")
        for item in results['published']:
            print(f"  • {item['asin']}: {item.get('item_id', 'N/A')} ({item['category']})")

    if results['failed']:
        print(f"\n❌ ASINs que aún fallan:")
        for asin in results['failed']:
            print(f"  • {asin}")

    # Guardar reporte
    report_path = storage_dir / "logs" / "retry_8_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Reporte guardado en: {report_path}")

    # Calcular total publicados (6 anteriores + nuevos)
    total_published = 6 + len(results['published'])
    print(f"\n{'='*70}")
    print(f"🎯 TOTAL PUBLICADOS: {total_published}/14 ({total_published*100//14}%)")
    print(f"{'='*70}")

    return results


if __name__ == "__main__":
    main()
