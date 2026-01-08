#!/usr/bin/env python3
"""
Test para verificar si se genera deadline_text
"""
import sys
sys.path.insert(0, '/Users/felipemelucci/Desktop/revancha/scripts/tools')

from telegram_sales_notifier import format_sale_notification

# Simular venta real de MLM
order = {
    "pack_id": "2000010864008277",
    "date_created": "2026-01-05T00:46:17.058-05:00",  # Domingo 5 enero 00:46 Miami
    "context": {
        "site": "MLM"
    },
    "order_items": [
        {
            "item": {
                "id": "MLM2664238143",
                "title": "Base Cargadora Jsaux Para Steam Deck Hb0603 6-en-1 4k 100w",
            },
            "quantity": 1,
            "unit_price": 1000,
            "full_unit_price": 1000,
            "sale_fee": 100,
        }
    ],
    "payments": [
        {
            "total_paid_amount": 1000,
            "shipping_cost": 0,
        }
    ],
    "buyer": {
        "nickname": "VEMA1443094"
    },
}

# Datos de ASIN
asin_data = {
    "asin": "B0B7HVZNMB",
    "title": "Base Cargadora Jsaux",
    "brand": "None",
    "amazon_cost": 35.99,
    "marketplace": "MLM",
}

# Token de prueba (no se usará realmente)
ml_token = "TEST_TOKEN"

print("=" * 80)
print("TEST: VERIFICAR DEADLINE_TEXT")
print("=" * 80)
print()

try:
    main_msg, order_msg, asin_msg = format_sale_notification(order, asin_data, ml_token)

    print("MENSAJE PRINCIPAL:")
    print("-" * 80)
    print(main_msg)
    print()
    print("-" * 80)

    # Verificar si contiene "Despachar antes de"
    if "Despachar antes de" in main_msg:
        print("✅ El mensaje contiene la fecha de despacho")
    else:
        print("❌ El mensaje NO contiene la fecha de despacho")

    print()
    print("MENSAJE DE ORDEN:")
    print("-" * 80)
    print(order_msg)

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
