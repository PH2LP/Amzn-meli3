#!/usr/bin/env python3
"""
Validador PREVENTIVO de categorías.
Valida ANTES de publicar que la categoría es correcta.
"""

import sys
import os
import json
from pathlib import Path
from typing import Optional, Dict, List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.category_validator import (
    validate_and_fix_category,
    use_ml_category_predictor
)


def validate_all_mini_ml(ml_token: str) -> Dict[str, List[str]]:
    """
    Valida todos los mini_ml y corrige categorías antes de publicar.

    Returns:
        Dict con 'validated', 'fixed', 'warnings'
    """
    asins_file = Path("resources/asins.txt")
    if not asins_file.exists():
        print("❌ resources/asins.txt no existe")
        return {}

    with open(asins_file) as f:
        asins = [line.strip() for line in f if line.strip()]

    results = {
        'validated': [],
        'fixed': [],
        'warnings': []
    }

    print(f"🔍 VALIDANDO {len(asins)} MINI_ML FILES")
    print("=" * 70)

    for i, asin in enumerate(asins, 1):
        print(f"\n{i}/{len(asins)}. {asin}")
        print("-" * 50)

        mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")

        if not mini_path.exists():
            print(f"⚠️  Mini ML no existe")
            results['warnings'].append(f"{asin}: Mini ML no existe")
            continue

        with open(mini_path) as f:
            mini_ml = json.load(f)

        original_cat = mini_ml.get('category_id', '')
        original_attrs = len(mini_ml.get('attributes_mapped', {}))

        print(f"📋 Categoría actual: {original_cat}")
        print(f"📋 Atributos: {original_attrs}")

        # Validar y corregir
        fixed_mini, warnings = validate_and_fix_category(mini_ml, ml_token)

        new_cat = fixed_mini.get('category_id', '')
        new_attrs = len(fixed_mini.get('attributes_mapped', {}))

        # Verificar si hubo cambios
        if new_cat != original_cat:
            print(f"✏️  Categoría cambiada: {original_cat} → {new_cat}")
            results['fixed'].append(asin)

            # Guardar mini_ml actualizado
            with open(mini_path, 'w') as f:
                json.dump(fixed_mini, f, indent=2, ensure_ascii=False)

            print(f"💾 Mini ML actualizado")
        else:
            print(f"✅ Categoría validada: {new_cat}")
            results['validated'].append(asin)

        if warnings:
            print(f"⚠️  Advertencias:")
            for w in warnings:
                print(f"   • {w}")
                results['warnings'].append(f"{asin}: {w}")

    print("\n" + "=" * 70)
    print(f"📊 RESUMEN DE VALIDACIÓN")
    print(f"   ✅ Validados sin cambios: {len(results['validated'])}")
    print(f"   ✏️  Corregidos: {len(results['fixed'])}")
    print(f"   ⚠️  Advertencias: {len(results['warnings'])}")
    print("=" * 70)

    # Guardar reporte
    report_path = Path("storage/validation_report.json")
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Reporte guardado en: {report_path}")

    return results


def double_check_with_ml_predictor(ml_token: str):
    """
    Double-check: usa el predictor de ML para verificar todas las categorías.
    Solo reporta, no modifica.
    """
    asins_file = Path("resources/asins.txt")
    if not asins_file.exists():
        return

    with open(asins_file) as f:
        asins = [line.strip() for line in f if line.strip()]

    print(f"\n🤖 DOUBLE-CHECK CON ML PREDICTOR")
    print("=" * 70)

    mismatches = []

    for i, asin in enumerate(asins, 1):
        mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")

        if not mini_path.exists():
            continue

        with open(mini_path) as f:
            mini_ml = json.load(f)

        title = mini_ml.get('title_ai', '')
        current_cat = mini_ml.get('category_id', '')

        # Consultar predictor ML
        prediction = use_ml_category_predictor(title, ml_token)

        if prediction:
            predicted_cat = prediction['category_id']

            if predicted_cat != current_cat:
                print(f"⚠️  {asin}:")
                print(f"   Actual:    {current_cat}")
                print(f"   ML sugiere: {predicted_cat}")
                print(f"   Título: {title[:60]}...")

                mismatches.append({
                    'asin': asin,
                    'current': current_cat,
                    'predicted': predicted_cat,
                    'title': title
                })

    if mismatches:
        print(f"\n📋 {len(mismatches)} productos con posible categoría incorrecta")

        # Guardar reporte
        report_path = Path("storage/ml_predictor_mismatches.json")
        with open(report_path, 'w') as f:
            json.dump(mismatches, f, indent=2, ensure_ascii=False)

        print(f"💾 Reporte guardado en: {report_path}")
    else:
        print(f"\n✅ Todas las categorías coinciden con ML predictor")


def main():
    """Ejecuta validación completa"""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    ml_token = os.getenv('ML_TOKEN')
    if not ml_token:
        print("❌ ML_TOKEN no encontrado en .env")
        return

    print("=" * 70)
    print("🔍 VALIDACIÓN PREVENTIVA DE CATEGORÍAS")
    print("=" * 70)

    # Paso 1: Validar y corregir con schema
    results = validate_all_mini_ml(ml_token)

    # Paso 2: Double-check con ML predictor
    double_check_with_ml_predictor(ml_token)

    print("\n✅ Validación completada")
    print("\nAhora puedes ejecutar:")
    print("   python3 validate_and_publish_existing.py")


if __name__ == "__main__":
    main()
