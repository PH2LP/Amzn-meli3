#!/usr/bin/env python3
"""
Verifica el estado de GTINs y seller_custom_field en los mini_ml files.
"""

import json
from pathlib import Path

def main():
    mini_ml_dir = Path("storage/logs/publish_ready")

    print("=" * 80)
    print("📊 VERIFICACIÓN DE GTINs Y SELLER_CUSTOM_FIELD")
    print("=" * 80)
    print()

    results = {
        "with_gtins": [],
        "without_gtins": [],
        "force_no_gtin": [],
        "total": 0
    }

    for file in sorted(mini_ml_dir.glob("*_mini_ml.json")):
        asin = file.stem.replace("_mini_ml", "")

        with open(file, 'r', encoding='utf-8') as f:
            mini_ml = json.load(f)

        results["total"] += 1

        gtins = mini_ml.get("gtins", [])
        force_no_gtin = mini_ml.get("force_no_gtin") or mini_ml.get("last_error") == "GTIN_REUSED"

        status_icon = "✅" if gtins and not force_no_gtin else "❌"

        print(f"{status_icon} {asin}")
        print(f"   GTINs: {gtins if gtins else 'NO'}")
        print(f"   force_no_gtin: {force_no_gtin}")
        print()

        if force_no_gtin:
            results["force_no_gtin"].append(asin)
        elif gtins:
            results["with_gtins"].append(asin)
        else:
            results["without_gtins"].append(asin)

    print("=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)
    print(f"Total productos: {results['total']}")
    print(f"Con GTINs válidos: {len(results['with_gtins'])} ✅")
    print(f"Sin GTINs: {len(results['without_gtins'])} ⚠️")
    print(f"Con force_no_gtin: {len(results['force_no_gtin'])} ❌")
    print()

    if results["force_no_gtin"]:
        print("🚫 Productos con GTIN bloqueado:")
        for asin in results["force_no_gtin"]:
            print(f"   - {asin}")
        print()

    if results["without_gtins"]:
        print("⚠️  Productos sin GTIN:")
        for asin in results["without_gtins"]:
            print(f"   - {asin}")
        print()

    return results

if __name__ == "__main__":
    main()
