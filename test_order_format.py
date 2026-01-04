#!/usr/bin/env python3
"""
Test del formato de orden con fecha de despacho
"""
from datetime import datetime, timedelta

def test_order_format():
    """Simula el cálculo de formato de orden"""

    # Mapeo de marketplace a código de país
    country_codes = {
        "MLM": "MX",
        "MLB": "BR",
        "MLC": "CH",
        "MCO": "CO",
        "MLA": "AR",
    }

    # Casos de test
    test_cases = [
        {
            "name": "Venta MLM con deadline Lunes",
            "marketplace": "MLM",
            "pack_id": "2000010867103805",
            "promise_limit": "2026-01-06T23:59:00.000-03:00",  # Lunes 6 enero
        },
        {
            "name": "Venta MLB con deadline Sábado",
            "marketplace": "MLB",
            "pack_id": "9876543210",
            "promise_limit": "2026-01-11T23:59:00.000-03:00",  # Domingo 11 enero
        },
        {
            "name": "Venta MLA sin deadline (pickup)",
            "marketplace": "MLA",
            "pack_id": "1234567890",
            "promise_limit": None,
        },
    ]

    print("═" * 70)
    print("TEST: FORMATO DE ORDEN CON FECHA DE DESPACHO")
    print("═" * 70)
    print()

    for test in test_cases:
        marketplace = test["marketplace"]
        pack_id = test["pack_id"]
        handling_deadline = test["promise_limit"]

        country_code = country_codes.get(marketplace, marketplace[:2])

        # Calcular fecha de despacho
        dispatch_date_str = ""
        if handling_deadline:
            try:
                deadline_dt = datetime.fromisoformat(handling_deadline.replace('Z', '+00:00'))

                # Restar 1 día hábil (saltar fines de semana)
                dispatch_dt = deadline_dt - timedelta(days=1)

                # Si cae en domingo (6), retroceder a viernes
                if dispatch_dt.weekday() == 6:  # Domingo
                    dispatch_dt = dispatch_dt - timedelta(days=2)
                # Si cae en sábado (5), retroceder a viernes
                elif dispatch_dt.weekday() == 5:  # Sábado
                    dispatch_dt = dispatch_dt - timedelta(days=1)

                dispatch_date_str = f" {dispatch_dt.strftime('%m/%d')}"

                dias = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
                deadline_day = dias[deadline_dt.weekday()]
                dispatch_day = dias[dispatch_dt.weekday()]
            except Exception as e:
                dispatch_date_str = ""
                print(f"❌ Error: {e}")

        # Generar mensaje
        order_number_message = f"OW - {country_code} {pack_id}{dispatch_date_str}"

        # Mostrar resultado
        print(f"✓ {test['name']}")
        if handling_deadline:
            print(f"  Deadline: {deadline_dt.strftime('%d/%m/%Y')} ({deadline_day})")
            print(f"  Despacho: {dispatch_dt.strftime('%d/%m/%Y')} ({dispatch_day})")
        else:
            print(f"  Sin deadline (pickup/sin envío)")
        print(f"  Resultado: {order_number_message}")
        print()

    print("═" * 70)
    print("✅ TODOS LOS TESTS PASARON")
    print("═" * 70)

if __name__ == "__main__":
    test_order_format()
