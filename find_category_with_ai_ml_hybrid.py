#!/usr/bin/env python3
"""
Sistema híbrido IA + ML Predictor para encontrar categorías correctas.

Flujo:
1. ML Predictor da categoría inicial (garantizado que existe)
2. IA valida si es correcta
3. Si NO: IA sugiere mejor keyword
4. Re-intentar ML Predictor con nueva keyword
5. IA valida nuevamente
6. Repetir hasta que IA confirme que es correcta (max 3 intentos)
"""

import os
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Tuple
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


def ml_predict_category(query: str, ml_token: str) -> Optional[Dict]:
    """
    Usa el predictor oficial de ML para obtener categoría.

    Returns:
        Dict con 'category_id', 'category_name', 'domain_id'
    """
    try:
        response = requests.get(
            "https://api.mercadolibre.com/sites/CBT/domain_discovery/search",
            params={'limit': 1, 'q': query},
            headers={"Authorization": f"Bearer {ml_token}"},
            timeout=10
        )

        if response.status_code == 200:
            results = response.json()
            if results and len(results) > 0:
                prediction = results[0]
                return {
                    'category_id': prediction.get('category_id'),
                    'category_name': prediction.get('category_name'),
                    'domain_id': prediction.get('domain_id'),
                    'domain_name': prediction.get('domain_name')
                }
    except Exception as e:
        print(f"      ⚠️ Error en ML predictor: {e}")

    return None


def ai_validate_category(
    product_title: str,
    product_description: str,
    product_type: str,
    brand: str,
    ml_category_id: str,
    ml_category_name: str
) -> Tuple[bool, str]:
    """
    IA valida si la categoría sugerida por ML es correcta.

    Returns:
        tuple: (is_correct, suggestion_or_reason)
    """

    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        return True, ""  # Sin OpenAI, asumir válido

    try:
        client = OpenAI(api_key=openai_key)

        prompt = f"""Eres un experto en categorización de productos para ecommerce.

MercadoLibre sugirió una categoría para este producto. Tu tarea es validar si es CORRECTA o no.

**PRODUCTO:**
Título: {product_title}
Marca: {brand}
Tipo: {product_type}
Descripción: {product_description[:200]}...

**CATEGORÍA SUGERIDA POR MERCADOLIBRE:**
ID: {ml_category_id}
Nombre: {ml_category_name}

**CRITERIOS DE VALIDACIÓN:**

✅ CORRECTA si:
- La categoría describe EXACTAMENTE el tipo de producto
- La función principal del producto coincide con la categoría
- Es la categoría MÁS ESPECÍFICA posible

❌ INCORRECTA si:
- La categoría es demasiado genérica (ej: "Otros" cuando hay una más específica)
- El producto NO es del tipo que describe la categoría
- Hay una categoría más apropiada

**EJEMPLOS:**

Producto: "Garmin Forerunner 55 GPS Running Watch"
Categoría ML: "Smartwatches & Accessories"
→ CORRECTA (es un smartwatch)

Producto: "LEGO Creator 3in1 Building Set"
Categoría ML: "Action Figures"
→ INCORRECTA (no son figuras de acción, son bloques de construcción)
Mejor keyword: "LEGO building blocks construction set"

Producto: "Wilson Basketball Official Size"
Categoría ML: "Sports & Outdoors"
→ INCORRECTA (demasiado genérica, debería ser específica de basketball)
Mejor keyword: "basketball ball official"

**RESPONDE EN JSON:**
{{
  "is_correct": true/false,
  "confidence": 0-100,
  "reasoning": "Explicación de por qué sí o no (1 línea)",
  "better_keyword": "Si is_correct=false, sugiere una frase/keyword mejor para que ML encuentre la categoría correcta. Si is_correct=true, dejar vacío."
}}

**IMPORTANTE:** Si is_correct=false, el "better_keyword" debe ser una frase corta y específica que describa EXACTAMENTE qué es el producto, enfocándose en su función o tipo específico.

Responde SOLO con el JSON.
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.choices[0].message.content.strip()

        # Extraer JSON
        import re
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))

            is_correct = result.get('is_correct', True)
            better_keyword = result.get('better_keyword', '')
            reasoning = result.get('reasoning', '')
            confidence = result.get('confidence', 100)

            return is_correct, better_keyword, reasoning, confidence

    except Exception as e:
        print(f"      ⚠️ Error en IA validación: {e}")

    return True, "", "", 100


def find_correct_category_hybrid(
    product_title: str,
    product_description: str,
    product_type: str,
    brand: str,
    ml_token: str,
    max_iterations: int = 3
) -> Optional[Dict]:
    """
    Sistema híbrido: ML Predictor + IA Validation.

    Itera hasta encontrar una categoría que IA confirme como correcta.

    Returns:
        Dict con 'category_id', 'category_name', 'confidence', 'iterations'
    """

    # Intento inicial con título del producto
    query = product_title

    for iteration in range(1, max_iterations + 1):
        print(f"      Intento {iteration}: Query = \"{query[:60]}...\"")

        # Paso 1: ML Predictor
        ml_prediction = ml_predict_category(query, ml_token)

        if not ml_prediction:
            print(f"      ❌ ML Predictor no devolvió resultado")
            continue

        ml_cat_id = ml_prediction['category_id']
        ml_cat_name = ml_prediction['category_name']

        print(f"      📦 ML sugiere: {ml_cat_id} - {ml_cat_name}")

        # Paso 2: IA valida
        is_correct, better_keyword, reasoning, confidence = ai_validate_category(
            product_title=product_title,
            product_description=product_description,
            product_type=product_type,
            brand=brand,
            ml_category_id=ml_cat_id,
            ml_category_name=ml_cat_name
        )

        print(f"      🤖 IA dice: {'✅ CORRECTA' if is_correct else '❌ INCORRECTA'} ({confidence}%)")
        if reasoning:
            print(f"         Razón: {reasoning}")

        if is_correct:
            # ✅ IA confirmó que es correcta!
            return {
                'category_id': ml_cat_id,
                'category_name': ml_cat_name,
                'confidence': confidence,
                'iterations': iteration,
                'final_query': query
            }

        # ❌ IA dice que no es correcta
        if better_keyword and iteration < max_iterations:
            print(f"      💡 IA sugiere keyword mejor: \"{better_keyword}\"")
            query = better_keyword  # Usar keyword mejorada en próximo intento
        else:
            # Último intento o sin sugerencia, mantener query
            pass

    # Después de max_iterations, usar la última predicción
    print(f"      ⚠️ Alcanzado máximo de intentos ({max_iterations})")
    print(f"      → Usando última categoría de ML: {ml_cat_id}")

    return {
        'category_id': ml_cat_id,
        'category_name': ml_cat_name,
        'confidence': 50,  # Baja confianza porque IA no confirmó
        'iterations': max_iterations,
        'final_query': query
    }


def assign_categories_hybrid():
    """Asigna categorías usando sistema híbrido IA + ML."""

    ml_token = os.getenv('ML_TOKEN')
    if not ml_token:
        print("❌ ML_TOKEN no encontrado")
        return

    # Cargar ASINs
    asins_file = Path("resources/asins.txt")
    if not asins_file.exists():
        print("❌ resources/asins.txt no existe")
        return

    with open(asins_file) as f:
        asins = [line.strip() for line in f if line.strip()]

    print("=" * 70)
    print("🔄 SISTEMA HÍBRIDO: ML PREDICTOR + IA VALIDATION")
    print("=" * 70)

    updated_count = 0
    results = {
        'success': [],
        'warnings': []
    }

    for i, asin in enumerate(asins, 1):
        print(f"\n{i}/{len(asins)}. {asin}")
        print("-" * 70)

        # Cargar mini_ml
        mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")
        if not mini_path.exists():
            print(f"   ⚠️ Mini ML no existe")
            continue

        with open(mini_path) as f:
            mini_ml = json.load(f)

        # Cargar Amazon JSON
        amazon_path = Path(f"storage/asins_json/{asin}.json")
        amazon_json = {}
        product_type = ""

        if amazon_path.exists():
            with open(amazon_path) as f:
                amazon_json = json.load(f)
                product_type = amazon_json.get('attributes', {}).get('product_type', [{}])[0].get('value', '')
                if not product_type:
                    product_type = amazon_json.get('attributes', {}).get('item_type_name', [{}])[0].get('value', '')

        current_cat = mini_ml.get('category_id')
        print(f"   📋 Categoría actual: {current_cat} - {mini_ml.get('category_name')}")

        # Buscar categoría con sistema híbrido
        print(f"   🔍 Buscando categoría correcta...")

        correct_cat = find_correct_category_hybrid(
            product_title=mini_ml.get('title_ai', ''),
            product_description=mini_ml.get('description_ai', ''),
            product_type=product_type,
            brand=mini_ml.get('brand', ''),
            ml_token=ml_token,
            max_iterations=3
        )

        if correct_cat:
            new_cat_id = correct_cat['category_id']
            new_cat_name = correct_cat['category_name']
            confidence = correct_cat['confidence']
            iterations = correct_cat['iterations']

            if new_cat_id != current_cat:
                # Actualizar mini_ml
                mini_ml['category_id'] = new_cat_id
                mini_ml['category_name'] = new_cat_name

                with open(mini_path, 'w') as f:
                    json.dump(mini_ml, f, indent=2, ensure_ascii=False)

                print(f"   ✅ Categoría actualizada:")
                print(f"      {current_cat} → {new_cat_id}")
                print(f"      Confianza: {confidence}% (iteraciones: {iterations})")

                updated_count += 1
                results['success'].append({
                    'asin': asin,
                    'old_category': current_cat,
                    'new_category': new_cat_id,
                    'confidence': confidence
                })
            else:
                print(f"   ✓ Categoría ya es correcta ({confidence}%)")
        else:
            print(f"   ❌ No se pudo encontrar categoría")
            results['warnings'].append(f"{asin}: No category found")

    print("\n" + "=" * 70)
    print(f"📊 {updated_count}/{len(asins)} categorías actualizadas")

    if results['warnings']:
        print(f"\n⚠️ Advertencias:")
        for w in results['warnings']:
            print(f"   • {w}")

    # Guardar reporte
    report_path = Path("storage/hybrid_category_report.json")
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Reporte guardado: {report_path}")
    print("\nAhora ejecuta:")
    print("  python3 validate_and_publish_existing.py")


if __name__ == "__main__":
    assign_categories_hybrid()
