#!/usr/bin/env python3
"""
Test del fix de alternative category finder para productos sin GTIN válido
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from main2 import Main2Pipeline

# ASINs que fallaron por categoria requiere GTIN pero no tenemos válido
TEST_ASINS = [
    "B092RCLKHN",  # Error 7810
    "B0BXSLRQH7",  # Error 7810
    "B0CLC6NBBX",  # Error 7810 (probable)
    "B081SRSNWW",  # Error 7810
]

if __name__ == "__main__":
    print("=" * 70)
    print("🧪 TEST: Alternative Category Finder Fix")
    print("=" * 70)
    print(f"📦 Testing {len(TEST_ASINS)} ASINs that require GTIN")
    print("=" * 70)
    print()

    pipeline = Main2Pipeline()
    pipeline.dry_run = False

    success = []
    failed = []

    for i, asin in enumerate(TEST_ASINS, 1):
        print(f"\n{'=' * 70}")
        print(f"📦 [{i}/{len(TEST_ASINS)}] Testing: {asin}")
        print('=' * 70)

        try:
            result = pipeline.execute(asin)
            if result:
                success.append(asin)
                print(f"✅ {asin}: PUBLICADO ({result})")
            else:
                failed.append(asin)
                print(f"❌ {asin}: FALLÓ")
        except Exception as e:
            failed.append(asin)
            print(f"❌ {asin}: ERROR - {e}")

    print("\n" + "=" * 70)
    print("📊 RESULTADOS FINALES")
    print("=" * 70)
    print(f"✅ Exitosos: {len(success)}/{len(TEST_ASINS)}")
    if success:
        for asin in success:
            print(f"   - {asin}")

    print(f"\n❌ Fallidos: {len(failed)}/{len(TEST_ASINS)}")
    if failed:
        for asin in failed:
            print(f"   - {asin}")

    print("=" * 70)
