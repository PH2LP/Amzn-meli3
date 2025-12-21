#!/usr/bin/env python3
"""
Verifica que las medidas del paquete en ML coincidan con las del JSON de Amazon.
Asegura que se estén usando medidas de PAQUETE y no del producto.
"""

import sqlite3
import json
import os
from pathlib import Path

def get_active_listings():
    """Obtiene todas las publicaciones con item_id de la BD"""
    db_path = "storage/listings_database.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT asin, item_id, length_cm, width_cm, height_cm, weight_kg
        FROM listings
        WHERE item_id IS NOT NULL
    """)

    listings = cursor.fetchall()
    conn.close()
    return listings

def get_amazon_package_dimensions(asin):
    """Obtiene las medidas del PAQUETE desde el JSON de Amazon"""
    json_path = f"storage/asins_json/{asin}.json"

    if not os.path.exists(json_path):
        return None

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Buscar dimensiones del PAQUETE en attributes
        package_dims = {}

        if 'attributes' in data:
            attrs = data['attributes']

            # Buscar item_package_dimensions
            if 'item_package_dimensions' in attrs and len(attrs['item_package_dimensions']) > 0:
                pkg = attrs['item_package_dimensions'][0]

                # Extraer dimensiones
                if 'length' in pkg:
                    package_dims['length_cm'] = pkg['length'].get('value')
                if 'width' in pkg:
                    package_dims['width_cm'] = pkg['width'].get('value')
                if 'height' in pkg:
                    package_dims['height_cm'] = pkg['height'].get('value')

            # Buscar item_package_weight
            if 'item_package_weight' in attrs and len(attrs['item_package_weight']) > 0:
                weight_data = attrs['item_package_weight'][0]
                weight_value = weight_data.get('value')
                weight_unit = weight_data.get('unit', 'kilograms')

                # Convertir si está en pounds
                if weight_unit == 'pounds' and weight_value:
                    weight_value = weight_value * 0.453592

                package_dims['weight_kg'] = weight_value

        # Si no encontramos datos, retornar None
        if not package_dims:
            return None

        return package_dims

    except Exception as e:
        print(f"Error al leer JSON {asin}: {e}")
        return None

def compare_dimensions(ml_dims, amazon_dims):
    """Compara dimensiones con tolerancia de 0.1 cm y 0.01 kg"""
    if not amazon_dims:
        return None, "No hay datos de Amazon"

    issues = []

    # Comparar cada dimensión
    dims_to_check = ['length_cm', 'width_cm', 'height_cm', 'weight_kg']

    for dim in dims_to_check:
        ml_val = ml_dims.get(dim)
        amz_val = amazon_dims.get(dim)

        if ml_val is None or amz_val is None:
            continue

        # Tolerancia
        tolerance = 0.1 if 'cm' in dim else 0.01

        if abs(ml_val - amz_val) > tolerance:
            issues.append(f"{dim}: ML={ml_val}, Amazon={amz_val}")

    if issues:
        return False, "; ".join(issues)

    return True, "OK"

def main():
    print("=" * 80)
    print("VERIFICACIÓN DE MEDIDAS DE PAQUETE: ML vs AMAZON")
    print("=" * 80)
    print()

    listings = get_active_listings()
    print(f"Total de publicaciones a verificar: {len(listings)}\n")

    discrepancies = []
    no_amazon_data = []
    correct = []

    for asin, item_id, length_cm, width_cm, height_cm, weight_kg in listings:
        ml_dims = {
            'length_cm': length_cm,
            'width_cm': width_cm,
            'height_cm': height_cm,
            'weight_kg': weight_kg
        }

        amazon_dims = get_amazon_package_dimensions(asin)

        if amazon_dims is None:
            no_amazon_data.append((asin, item_id))
            continue

        match, message = compare_dimensions(ml_dims, amazon_dims)

        if match is None:
            no_amazon_data.append((asin, item_id))
        elif match:
            correct.append((asin, item_id))
        else:
            discrepancies.append((asin, item_id, message, ml_dims, amazon_dims))

    # Reporte de discrepancias
    if discrepancies:
        print(f"\n🚨 DISCREPANCIAS ENCONTRADAS: {len(discrepancies)}")
        print("=" * 80)
        for asin, item_id, message, ml_dims, amz_dims in discrepancies:
            print(f"\nASIN: {asin}")
            print(f"Item ID: {item_id}")
            print(f"Problemas: {message}")
            print(f"ML: L={ml_dims['length_cm']} W={ml_dims['width_cm']} H={ml_dims['height_cm']} Weight={ml_dims['weight_kg']}")
            print(f"Amazon: L={amz_dims.get('length_cm')} W={amz_dims.get('width_cm')} H={amz_dims.get('height_cm')} Weight={amz_dims.get('weight_kg')}")
            print("-" * 80)

    # Reporte de sin datos
    if no_amazon_data:
        print(f"\n⚠️  SIN DATOS DE AMAZON: {len(no_amazon_data)}")
        print("=" * 80)
        for asin, item_id in no_amazon_data[:10]:  # Mostrar solo los primeros 10
            print(f"ASIN: {asin}, Item ID: {item_id}")
        if len(no_amazon_data) > 10:
            print(f"... y {len(no_amazon_data) - 10} más")

    # Resumen
    print(f"\n{'=' * 80}")
    print("RESUMEN")
    print("=" * 80)
    print(f"✅ Correctas: {len(correct)}")
    print(f"🚨 Con discrepancias: {len(discrepancies)}")
    print(f"⚠️  Sin datos de Amazon: {len(no_amazon_data)}")
    print(f"📊 Total: {len(listings)}")
    print()

    if discrepancies:
        print("⚠️  Se encontraron discrepancias. Revisar las publicaciones arriba.")
    else:
        print("✅ Todas las publicaciones tienen medidas correctas!")

if __name__ == "__main__":
    main()
