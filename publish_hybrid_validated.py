#!/usr/bin/env python3
"""
Publica los 11 ASINs validados con el sistema híbrido AI + Category Matcher
"""

import os
import sys
import json
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mainglobal import publish_item

def main():
    """
    Publica los 11 ASINs validados con el sistema híbrido.
    """

    # ASINs validados con sistema híbrido
    validated_asins = [
        "B092RCLKHN",  # GPS Navigation Systems
        "B0BGQLZ921",  # Doll Sets (LEGO Flowers)
        "B0DRW69H11",  # Building Toys
        "B0BXSLRQH7",  # Smartwatches
        "B0D3H3NKBN",  # Nail Polish
        "B0DCYZJBYD",  # Basketball
        "B0CJQG4PMF",  # Earrings
        "B0CLC6NBBX",  # Headphones
        "B0D1Z99167",  # Personal Care
        "B081SRSNWW",  # Facial Masks
        "B0BRNY9HZB"   # Diamond Painting Kits
    ]

    storage_dir = Path("/Users/felipemelucci/Desktop/revancha/storage")
    mini_ml_dir = storage_dir / "logs" / "publish_ready"

    ml_token = os.getenv("ML_TOKEN")
    if not ml_token:
        print("❌ ML_TOKEN no encontrado en variables de entorno")
        return

    results = {
        "published": [],
        "failed": []
    }

    print(f"\n{'='*70}")
    print(f"🚀 PUBLICANDO {len(validated_asins)} PRODUCTOS VALIDADOS CON SISTEMA HÍBRIDO")
    print(f"{'='*70}\n")

    for i, asin in enumerate(validated_asins, 1):
        print(f"\n{'='*70}")
        print(f"📦 [{i}/{len(validated_asins)}] Publicando {asin}")
        print(f"{'='*70}")

        mini_ml_path = mini_ml_dir / f"{asin}_mini_ml.json"

        if not mini_ml_path.exists():
            print(f"❌ No existe mini_ml para {asin}")
            results["failed"].append(asin)
            continue

        # Cargar el mini_ml
        with open(mini_ml_path, 'r', encoding='utf-8') as f:
            mini_ml = json.load(f)

        print(f"📂 Categoría: {mini_ml.get('category_id')} - {mini_ml.get('category_name')}")
        print(f"🏷️  Título: {mini_ml.get('title_ai', '')[:80]}...")

        try:
            # Publicar usando mainglobal
            result = publish_item(asin_json=mini_ml)

            if result and isinstance(result, dict):
                print(f"✅ PUBLICADO: {asin}")
                results["published"].append({
                    "asin": asin,
                    "category_id": mini_ml.get('category_id'),
                    "category_name": mini_ml.get('category_name'),
                    "result": result
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
    print(f"📊 RESUMEN DE PUBLICACIÓN")
    print(f"{'='*70}")
    print(f"✅ Publicados: {len(results['published'])}/{len(validated_asins)}")
    print(f"❌ Fallidos: {len(results['failed'])}/{len(validated_asins)}")

    if results['published']:
        print(f"\n✅ ASINs publicados:")
        for item in results['published']:
            print(f"  • {item['asin']}: {item['category_id']} - {item['category_name']}")

    if results['failed']:
        print(f"\n❌ ASINs que fallaron:")
        for asin in results['failed']:
            print(f"  • {asin}")

    # Guardar reporte
    report_path = storage_dir / "logs" / "hybrid_publication_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Reporte guardado en: {report_path}")

    return results


if __name__ == "__main__":
    main()
