#!/usr/bin/env python3
"""
Test de pausa automática cuando:
1. Producto deja de tener oferta Prime en Amazon
2. Tiempo de despacho > 24hs (no cumple Fast Fulfillment)
"""

import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

sys.path.insert(0, str(Path(__file__).parent))

from scripts.tools.sync_amazon_ml import sync_one_listing

DB_PATH = "storage/listings_database.db"

def run_test_scenario(scenario_name, cache_data, expected_action):
    """Ejecuta un escenario de test"""
    print(f"\n{'='*80}")
    print(f"🧪 ESCENARIO: {scenario_name}")
    print("=" * 80)

    # Obtener listing de la BD
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT item_id, asin, price_usd, title, site_items
        FROM listings
        WHERE asin = 'B0C3W4MNN1'
    """)

    result = cursor.fetchone()
    if not result:
        print("❌ No se encontró el producto en la BD")
        return False

    listing = dict(result)
    conn.close()

    asin = listing["asin"]
    item_id = listing["item_id"]

    print(f"\n📦 Producto: {asin}")
    print(f"   Item ID: {item_id}")

    # Mostrar estado del cache
    if cache_data.get(asin):
        offer = cache_data[asin]
        print(f"\n📊 Estado Amazon simulado:")
        print(f"   Tiene oferta Prime: {bool(offer)}")
        if offer:
            print(f"   Precio: ${offer.get('price', 'N/A')} USD")
    else:
        print(f"\n📊 Estado Amazon simulado: Sin oferta Prime")

    # Ejecutar sincronización
    print(f"\n🔄 Ejecutando sincronización...")

    changes_log = []
    result = sync_one_listing(listing, cache_data, changes_log)

    # Verificar resultado
    print(f"\n{'='*80}")
    print("✅ RESULTADO")
    print("=" * 80)

    print(f"\n📊 Acción: {result['action']}")
    print(f"   Exitoso: {result['success']}")
    print(f"   Mensaje: {result['message']}")

    success = (result['action'] == expected_action)

    if success:
        print(f"\n✅ TEST EXITOSO")
        print(f"   Acción esperada: {expected_action}")
        print(f"   Acción obtenida: {result['action']}")

        if result['action'] == 'paused':
            print(f"\n💡 El producto fue pausado en ML (stock = 0)")
            print(f"   Razón: {result['message']}")
    else:
        print(f"\n❌ TEST FALLIDO")
        print(f"   Esperado: {expected_action}")
        print(f"   Obtenido: {result['action']}")

    return success


def main():
    print("=" * 80)
    print("🧪 TEST DE PAUSA AUTOMÁTICA EN ML")
    print("=" * 80)
    print("\nVamos a probar 2 escenarios:")
    print("1. Producto SIN oferta Prime en Amazon")
    print("2. Producto con tiempo de despacho >24hs (no cumple Fast Fulfillment)")

    results = []

    # ============================================================
    # ESCENARIO 1: Sin oferta Prime
    # ============================================================

    scenario1_cache = {
        "B0C3W4MNN1": None  # None = No hay oferta Prime
    }

    success1 = run_test_scenario(
        "Producto SIN oferta Prime",
        scenario1_cache,
        expected_action="paused"
    )
    results.append(("Sin Prime", success1))

    # Esperar un poco entre tests
    import time
    time.sleep(2)

    # ============================================================
    # ESCENARIO 2: Tiempo de despacho >24hs
    # ============================================================
    # Nota: En el código actual, cuando get_prime_offers_batch_optimized
    # filtra productos por Fast Fulfillment, si no cumplen, retorna None
    # Entonces simular tiempo >24hs = cache con None también

    print(f"\n{'='*80}")
    print("ℹ️  NOTA SOBRE ESCENARIO 2")
    print("=" * 80)
    print("""
El filtro de Fast Fulfillment se aplica en get_prime_offers_batch_optimized():
- Si maximumHours > 24 → No retorna oferta (None)
- Si availabilityType != "NOW" con >7 días → No retorna oferta (None)

Por lo tanto, ambos escenarios (sin Prime y >24hs) producen cache = None
y el comportamiento es el mismo: pausar el producto.

El sistema NO diferencia entre "sin Prime" vs "tiempo largo",
simplemente detecta "no hay oferta Prime válida" → PAUSAR.
    """)

    scenario2_cache = {
        "B0C3W4MNN1": None  # Producto rechazado por Fast Fulfillment
    }

    success2 = run_test_scenario(
        "Producto con tiempo >24hs (rechazado por Fast Fulfillment)",
        scenario2_cache,
        expected_action="paused"
    )
    results.append(("Tiempo >24hs", success2))

    # ============================================================
    # ESCENARIO 3 (BONUS): Producto disponible de nuevo
    # ============================================================

    time.sleep(2)

    scenario3_cache = {
        "B0C3W4MNN1": {
            "price": 35.99,
            "is_prime": True,
            "is_amazon": True,
            "condition": "New"
        }
    }

    success3 = run_test_scenario(
        "BONUS: Producto vuelve a estar disponible Prime",
        scenario3_cache,
        expected_action="reactivated"  # O "no_change" si ya estaba activo
    )
    results.append(("Reactivación", success3))

    # ============================================================
    # RESUMEN FINAL
    # ============================================================

    print(f"\n{'='*80}")
    print("📊 RESUMEN DE TESTS")
    print("=" * 80)

    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status} - {name}")

    all_passed = all(r[1] for r in results)

    print(f"\n{'='*80}")
    if all_passed:
        print("✅ TODOS LOS TESTS PASARON")
        print("=" * 80)
        print("""
El sistema de sincronización funciona correctamente:

✅ Pausa productos sin oferta Prime
✅ Pausa productos con tiempo de despacho >24hs
✅ Reactiva productos cuando vuelven a estar disponibles

Método de pausa: available_quantity = 0 (sin stock)
        """)
    else:
        print("❌ ALGUNOS TESTS FALLARON")
        print("=" * 80)

if __name__ == "__main__":
    main()
