#!/usr/bin/env python3
"""
Corrige los pesos de paquete incorrectos en las publicaciones de ML
usando los datos correctos del JSON de Amazon.
"""

import sqlite3
import json
import os
import sys

def get_amazon_package_weight(asin):
    """Obtiene el peso del PAQUETE desde el JSON de Amazon"""
    json_path = f"storage/asins_json/{asin}.json"

    if not os.path.exists(json_path):
        return None

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'attributes' in data:
            attrs = data['attributes']

            # Buscar item_package_weight
            if 'item_package_weight' in attrs and len(attrs['item_package_weight']) > 0:
                weight_data = attrs['item_package_weight'][0]
                weight_value = weight_data.get('value')
                weight_unit = weight_data.get('unit', 'kilograms')

                # Convertir si está en pounds
                if weight_unit == 'pounds' and weight_value:
                    weight_value = weight_value * 0.453592

                return weight_value

        return None

    except Exception as e:
        print(f"Error al leer JSON {asin}: {e}")
        return None

def find_discrepancies():
    """Encuentra publicaciones con pesos incorrectos"""
    db_path = "storage/listings_database.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT asin, item_id, weight_kg
        FROM listings
        WHERE item_id IS NOT NULL
    """)

    discrepancies = []

    for asin, item_id, ml_weight in cursor.fetchall():
        amazon_weight = get_amazon_package_weight(asin)

        if amazon_weight is None:
            continue

        # Tolerancia de 0.01 kg
        if abs(ml_weight - amazon_weight) > 0.01:
            discrepancies.append({
                'asin': asin,
                'item_id': item_id,
                'ml_weight': ml_weight,
                'amazon_weight': amazon_weight
            })

    conn.close()
    return discrepancies

def update_weight_in_db(asin, correct_weight):
    """Actualiza el peso en la base de datos"""
    db_path = "storage/listings_database.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE listings
        SET weight_kg = ?
        WHERE asin = ?
    """, (correct_weight, asin))

    conn.commit()
    conn.close()

def main():
    print("=" * 80)
    print("CORRECCIÓN DE PESOS DE PAQUETE")
    print("=" * 80)
    print()

    print("Buscando discrepancias...")
    discrepancies = find_discrepancies()

    if not discrepancies:
        print("✅ No se encontraron discrepancias. Todos los pesos están correctos.")
        return

    print(f"Se encontraron {len(discrepancies)} publicaciones con pesos incorrectos:\n")

    for disc in discrepancies:
        print(f"ASIN: {disc['asin']}")
        print(f"  Item ID: {disc['item_id']}")
        print(f"  Peso actual (ML): {disc['ml_weight']} kg")
        print(f"  Peso correcto (Amazon): {disc['amazon_weight']} kg")
        print()

    # Confirmar corrección
    print("=" * 80)
    print("¿Desea corregir estos pesos en la base de datos? (y/n)")

    # Auto-confirmar basado en instrucciones del usuario
    response = 'y'
    print(f"Respuesta automática: {response}")

    if response.lower() == 'y':
        print("\nCorrigiendo pesos...")
        for disc in discrepancies:
            update_weight_in_db(disc['asin'], disc['amazon_weight'])
            print(f"✅ {disc['asin']}: {disc['ml_weight']} kg → {disc['amazon_weight']} kg")

        print(f"\n✅ Se corrigieron {len(discrepancies)} pesos en la base de datos.")
        print("\n⚠️  IMPORTANTE: Ahora debes actualizar estas publicaciones en Mercado Libre")
        print("para que reflejen los pesos correctos.")
    else:
        print("\n❌ Operación cancelada.")

if __name__ == "__main__":
    main()
