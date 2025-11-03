#!/usr/bin/env python3
"""
Sistema Híbrido de Categorización: AI + Category Matcher Local

Proceso:
1. IA analiza el producto y extrae keyword/tipo principal
2. Se usa ese keyword para buscar en Category Matcher (embeddings local)
3. IA valida que la categoría devuelta sea correcta
4. Si no es correcta, IA sugiere mejor keyword y se reintenta (máx 3 intentos)
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple
import requests
from openai import OpenAI

# Configuración
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
ML_TOKEN = os.getenv("ML_TOKEN")

def ai_extract_product_keyword(title: str, description: str, brand: str, amazon_json: dict) -> str:
    """
    IA extrae el keyword/tipo principal del producto.
    Ej: "smartwatch", "LEGO building set", "nail polish", "bluetooth headphones"
    """

    # Extraer información relevante de Amazon
    product_type = amazon_json.get("product_type", "")
    category = amazon_json.get("category", "")
    features = amazon_json.get("features", [])[:3]

    prompt = f"""Analiza este producto y extrae UNA keyword o tipo de producto principal en inglés (máximo 3-4 palabras).

Título: {title}
Marca: {brand}
Tipo de producto Amazon: {product_type}
Categoría Amazon: {category}
Características: {', '.join(features) if features else 'N/A'}

Ejemplos de respuestas correctas:
- "smartwatch"
- "LEGO building blocks"
- "nail polish"
- "bluetooth headphones"
- "basketball hoop"
- "diamond painting kit"
- "leather cleaner"

Responde SOLO con el keyword, sin explicación ni puntuación adicional."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Eres un experto en clasificación de productos de ecommerce. Extrae keywords precisos."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=20
    )

    keyword = response.choices[0].message.content.strip().strip('"').strip("'")
    print(f"  🔍 IA extrajo keyword: '{keyword}'")
    return keyword


def search_category_with_matcher(keyword: str, title: str, description: str, asin: str) -> Optional[Dict]:
    """
    Usa el Category Matcher local con embeddings para buscar categoría.
    """

    # Importar el Category Matcher existente
    sys.path.insert(0, '/Users/felipemelucci/Desktop/revancha/src')
    from category_matcher import match_category

    # Buscar categoría usando el keyword
    # El matcher toma un string de categoría y busca el embedding más similar
    search_text = f"{keyword}"

    result = match_category(ai_category=search_text, asin=asin)

    if result and result.get("matched_category_id"):
        print(f"  📦 Category Matcher encontró: {result['matched_category_id']} - {result['matched_category_name']} (similitud: {result['similarity']:.3f})")
        return {
            "category_id": result['matched_category_id'],
            "category_name": result['matched_category_name'],
            "similarity": result['similarity']
        }
    else:
        print(f"  ❌ Category Matcher no encontró categoría para '{keyword}'")
        return None


def ai_validate_category(
    keyword: str,
    title: str,
    description: str,
    brand: str,
    category_id: str,
    category_name: str,
    amazon_json: dict
) -> Tuple[bool, str]:
    """
    IA valida si la categoría es correcta para el producto.
    Returns: (is_correct, better_keyword_if_wrong)
    """

    product_type = amazon_json.get("product_type", "")
    features = amazon_json.get("features", [])[:3]

    prompt = f"""Valida si esta categoría de MercadoLibre es correcta para el producto.

PRODUCTO:
- Título: {title}
- Marca: {brand}
- Tipo Amazon: {product_type}
- Keyword detectado: {keyword}
- Características: {', '.join(features) if features else 'N/A'}

CATEGORÍA ASIGNADA:
- ID: {category_id}
- Nombre: {category_name}

PREGUNTA: ¿Esta categoría es correcta para el producto?

Si ES CORRECTA, responde: "CORRECTO"

Si NO ES CORRECTA, responde en este formato exacto:
INCORRECTO
Mejor keyword: [sugiere un keyword más específico en inglés]

Ejemplos:
- Si es un LEGO pero la categoría es "Toys" genérico → Mejor keyword: "LEGO building blocks"
- Si es un smartwatch pero la categoría es "Electronics" → Mejor keyword: "smartwatch fitness tracker"
- Si es esmalte de uñas pero es "Beauty Products" → Mejor keyword: "nail polish enamel"

Sé estricto pero razonable. La categoría debe ser específica y apropiada."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Eres un experto en categorización de ecommerce. Valida si la categoría es apropiada."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=100
    )

    result = response.choices[0].message.content.strip()

    if result.startswith("CORRECTO"):
        print(f"  ✅ IA confirmó que la categoría es correcta")
        return True, ""
    else:
        # Extraer el mejor keyword de la respuesta
        lines = result.split('\n')
        better_keyword = keyword  # default
        for line in lines:
            if "mejor keyword:" in line.lower():
                better_keyword = line.split(':', 1)[1].strip()
                break

        print(f"  ⚠️  IA sugiere mejor keyword: '{better_keyword}'")
        return False, better_keyword


def find_category_hybrid(asin: str, mini_ml_path: str, amazon_json_path: str, max_attempts: int = 3) -> Optional[Dict]:
    """
    Sistema híbrido completo:
    1. IA extrae keyword
    2. Category Matcher busca categoría
    3. IA valida
    4. Si no es correcta, reintenta con mejor keyword

    Returns: Dict con category_id, category_name, similarity
    """

    print(f"\n{'='*70}")
    print(f"🔄 Procesando {asin} con sistema híbrido AI + Category Matcher")
    print(f"{'='*70}")

    # Cargar datos
    with open(mini_ml_path, 'r', encoding='utf-8') as f:
        mini_ml = json.load(f)

    with open(amazon_json_path, 'r', encoding='utf-8') as f:
        amazon_json = json.load(f)

    title = mini_ml.get("title_ai", "")
    description = mini_ml.get("description_ai", "")
    brand = mini_ml.get("brand", "")

    print(f"📦 Producto: {title[:80]}...")
    print(f"🏷️  Marca: {brand}")

    keyword = None

    for attempt in range(max_attempts):
        print(f"\n🔄 Intento {attempt + 1}/{max_attempts}")

        # Paso 1: IA extrae keyword (o usa el sugerido del intento anterior)
        if keyword is None:
            keyword = ai_extract_product_keyword(title, description, brand, amazon_json)

        # Paso 2: Category Matcher busca categoría
        category_result = search_category_with_matcher(keyword, title, description, asin)

        if not category_result:
            print(f"  ❌ No se encontró categoría, intentando con keyword más genérico...")
            # Intentar con un término más genérico
            keyword = keyword.split()[0] if ' ' in keyword else keyword
            continue

        # Paso 3: IA valida la categoría
        is_correct, better_keyword = ai_validate_category(
            keyword=keyword,
            title=title,
            description=description,
            brand=brand,
            category_id=category_result['category_id'],
            category_name=category_result['category_name'],
            amazon_json=amazon_json
        )

        if is_correct:
            print(f"\n✅ CATEGORÍA VALIDADA: {category_result['category_id']} - {category_result['category_name']}")
            return category_result

        # Si no es correcta, usar el keyword sugerido por IA
        keyword = better_keyword

    # Si después de max_attempts no se validó, devolver la última categoría encontrada
    print(f"\n⚠️  Después de {max_attempts} intentos, usando la última categoría encontrada")
    return category_result if category_result else None


def update_mini_ml_category(mini_ml_path: str, category_result: Dict):
    """
    Actualiza el archivo mini_ml con la nueva categoría validada.
    """
    with open(mini_ml_path, 'r', encoding='utf-8') as f:
        mini_ml = json.load(f)

    # Actualizar categoría
    mini_ml['category_id'] = category_result['category_id']
    mini_ml['category_name'] = category_result['category_name']
    mini_ml['category_similarity'] = category_result['similarity']

    # Guardar
    with open(mini_ml_path, 'w', encoding='utf-8') as f:
        json.dump(mini_ml, f, indent=2, ensure_ascii=False)

    print(f"💾 Actualizado: {mini_ml_path}")


def main():
    """
    Procesa todos los ASINs fallidos con el sistema híbrido.
    """

    # ASINs fallidos según el reporte
    failed_asins = [
        "B092RCLKHN",
        "B0BGQLZ921",
        "B0DRW69H11",
        "B0BXSLRQH7",
        "B0D3H3NKBN",
        "B0DCYZJBYD",
        "B0CJQG4PMF",
        "B0CLC6NBBX",
        "B0D1Z99167",
        "B081SRSNWW",
        "B0BRNY9HZB"
    ]

    storage_dir = Path("/Users/felipemelucci/Desktop/revancha/storage")
    mini_ml_dir = storage_dir / "logs" / "publish_ready"
    amazon_dir = storage_dir / "asins_json"

    results = {
        "validated": [],
        "failed": []
    }

    for asin in failed_asins:
        mini_ml_path = mini_ml_dir / f"{asin}_mini_ml.json"
        amazon_json_path = amazon_dir / f"{asin}.json"

        if not mini_ml_path.exists():
            print(f"❌ No existe mini_ml para {asin}")
            results["failed"].append(asin)
            continue

        if not amazon_json_path.exists():
            print(f"❌ No existe JSON de Amazon para {asin}")
            results["failed"].append(asin)
            continue

        try:
            category_result = find_category_hybrid(
                asin=asin,
                mini_ml_path=str(mini_ml_path),
                amazon_json_path=str(amazon_json_path),
                max_attempts=3
            )

            if category_result:
                update_mini_ml_category(str(mini_ml_path), category_result)
                results["validated"].append({
                    "asin": asin,
                    "category_id": category_result['category_id'],
                    "category_name": category_result['category_name'],
                    "similarity": category_result['similarity']
                })
            else:
                print(f"❌ No se pudo validar categoría para {asin}")
                results["failed"].append(asin)

        except Exception as e:
            print(f"❌ Error procesando {asin}: {e}")
            results["failed"].append(asin)

    # Resumen final
    print(f"\n{'='*70}")
    print(f"📊 RESUMEN DE VALIDACIÓN HÍBRIDA")
    print(f"{'='*70}")
    print(f"✅ Validados: {len(results['validated'])}/{len(failed_asins)}")
    print(f"❌ Fallidos: {len(results['failed'])}/{len(failed_asins)}")

    if results['validated']:
        print(f"\n✅ ASINs validados con nuevas categorías:")
        for item in results['validated']:
            print(f"  • {item['asin']}: {item['category_id']} - {item['category_name']} (similitud: {item['similarity']:.3f})")

    if results['failed']:
        print(f"\n❌ ASINs que fallaron:")
        for asin in results['failed']:
            print(f"  • {asin}")

    # Guardar reporte
    report_path = storage_dir / "logs" / "hybrid_validation_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Reporte guardado en: {report_path}")

    return results


if __name__ == "__main__":
    main()
