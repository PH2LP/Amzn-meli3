#!/usr/bin/env python3
"""
Validación POST-publicación con IA.
Después de que ML asigna la categoría, verifica con IA si es correcta.
Si no coincide, busca la categoría correcta y re-publica.
"""

import os
import json
import requests
from typing import Optional, Dict, Tuple
from openai import OpenAI

def get_category_name(category_id: str, ml_token: str) -> str:
    """Obtiene el nombre de una categoría de ML."""
    try:
        response = requests.get(
            f"https://api.mercadolibre.com/categories/{category_id}",
            headers={"Authorization": f"Bearer {ml_token}"},
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get('name', category_id)
    except:
        pass
    return category_id


def validate_category_with_ai(
    title: str,
    description: str,
    images: list,
    current_category_id: str,
    current_category_name: str,
    ml_token: str
) -> Tuple[bool, float, str]:
    """
    Valida con IA si el título, descripción e imágenes coinciden con la categoría asignada.

    Args:
        title: Título del producto
        description: Descripción del producto
        images: Lista de URLs de imágenes
        current_category_id: ID de categoría asignada por ML
        current_category_name: Nombre de categoría asignada
        ml_token: Token de ML

    Returns:
        tuple: (is_valid, confidence, suggested_category_name)
    """

    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        return True, 100.0, ""  # Si no hay OpenAI, asumir válido

    try:
        client = OpenAI(api_key=openai_key)

        # Obtener nombre completo de la categoría
        category_full_name = get_category_name(current_category_id, ml_token)

        prompt = f"""Eres un experto en categorización de productos para ecommerce.

Analiza si el siguiente producto pertenece REALMENTE a la categoría asignada por MercadoLibre.

**Categoría asignada:** {category_full_name} (ID: {current_category_id})

**Título del producto:**
{title}

**Descripción:**
{description[:500]}...

**Imágenes disponibles:** {len(images)} fotos del producto

**CRITERIOS DE VALIDACIÓN:**

1. **Title Match (40%)**: ¿El título describe un producto típico de esta categoría?
2. **Product Type (40%)**: ¿El tipo de producto corresponde a esta categoría?
3. **Category Logic (20%)**: ¿Hay coherencia entre categoría y producto?

**IMPORTANTE:**
- "Building Blocks & Figures" = LEGO, bloques de construcción, juguetes de armar
- "Toys & Games" = Juguetes generales, juegos de mesa, peluches
- "Relojes Deportivos" = Smartwatches, relojes GPS, fitness trackers
- "Sports & Fitness" = Equipamiento deportivo, balones, accesorios gym
- "Beauty & Personal Care" = Cosméticos, cuidado de piel, maquillaje

**RESPONDE EN JSON:**
{{
  "is_valid": true/false,
  "confidence": 0-100,
  "reasoning": "Explicación breve de por qué sí o no coincide",
  "suggested_category": "Nombre de categoría correcta si is_valid=false, o vacío si is_valid=true"
}}

**EJEMPLOS:**

Título: "LEGO Set Construcción 3 en 1 Animales"
Categoría: "Toys & Games"
→ is_valid: false (debería ser "Building Blocks & Figures")

Título: "Garmin Reloj GPS Smartwatch"
Categoría: "Relojes Deportivos"
→ is_valid: true

Título: "Balón Baloncesto Azul Tamaño 7"
Categoría: "Toys & Games"
→ is_valid: false (debería ser "Sports & Fitness")

Responde SOLO con el JSON, sin explicaciones adicionales.
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.choices[0].message.content.strip()

        # Extraer JSON de la respuesta
        import re
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))

            is_valid = result.get('is_valid', True)
            confidence = float(result.get('confidence', 100))
            suggested = result.get('suggested_category', '')
            reasoning = result.get('reasoning', '')

            return is_valid, confidence, suggested, reasoning

    except Exception as e:
        print(f"⚠️ Error en validación IA: {e}")

    return True, 100.0, "", ""


def find_correct_category(
    title: str,
    description: str,
    suggested_category_name: str,
    ml_token: str
) -> Optional[str]:
    """
    Busca la categoría correcta basándose en la sugerencia de IA.

    Mapea nombres de categorías sugeridos a IDs de categoría CBT.
    """

    # Mapeo de nombres comunes a IDs CBT
    category_mapping = {
        # LEGO y construcción
        'building blocks': 'CBT1157',
        'building blocks & figures': 'CBT1157',
        'construction toys': 'CBT1157',
        'lego': 'CBT1157',

        # Juguetes generales
        'toys': 'CBT116629',
        'toys & games': 'CBT29890',
        'games': 'CBT116629',
        'juguetes': 'CBT116629',

        # Relojes y wearables
        'relojes': 'CBT116629',  # Categoría más flexible
        'watches': 'CBT116629',
        'smartwatches': 'CBT116629',
        'fitness trackers': 'CBT116629',

        # Deportes
        'sports': 'CBT116629',
        'sports & fitness': 'CBT116629',
        'sporting goods': 'CBT116629',
        'fitness': 'CBT116629',

        # Belleza
        'beauty': 'CBT29890',
        'beauty & personal care': 'CBT29890',
        'cosmetics': 'CBT29890',
        'skincare': 'CBT29890',

        # Joyería
        'jewelry': 'CBT29890',
        'accessories': 'CBT29890',
    }

    suggested_lower = suggested_category_name.lower().strip()

    # Buscar match exacto
    if suggested_lower in category_mapping:
        return category_mapping[suggested_lower]

    # Buscar match parcial
    for key, cat_id in category_mapping.items():
        if key in suggested_lower or suggested_lower in key:
            return cat_id

    # Default: categoría más universal
    return 'CBT116629'


def post_publish_validation_and_fix(
    mini_ml: dict,
    ml_token: str
) -> Tuple[bool, str, Optional[dict]]:
    """
    Valida la categoría POST-publicación y sugiere corrección si es necesario.

    Args:
        mini_ml: Datos del producto publicado
        ml_token: Token de ML

    Returns:
        tuple: (needs_republish, reason, fixed_mini_ml)
    """

    asin = mini_ml.get('asin', 'UNKNOWN')
    title = mini_ml.get('title_ai', '')
    description = mini_ml.get('description_ai', '')
    images = mini_ml.get('images', [])
    current_category_id = mini_ml.get('category_id', '')
    current_category_name = mini_ml.get('category_name', '')

    print(f"\n🔍 Validando POST-publicación: {asin}")
    print(f"   Categoría actual: {current_category_id} - {current_category_name}")

    # Validar con IA
    is_valid, confidence, suggested_cat, reasoning = validate_category_with_ai(
        title=title,
        description=description,
        images=images,
        current_category_id=current_category_id,
        current_category_name=current_category_name,
        ml_token=ml_token
    )

    print(f"   Validación IA: {'✅ VÁLIDA' if is_valid else '❌ INCORRECTA'} (confianza: {confidence}%)")

    if reasoning:
        print(f"   Razón: {reasoning}")

    if not is_valid and suggested_cat:
        print(f"   Sugerencia IA: {suggested_cat}")

        # Buscar categoría correcta
        correct_category_id = find_correct_category(
            title=title,
            description=description,
            suggested_category_name=suggested_cat,
            ml_token=ml_token
        )

        if correct_category_id and correct_category_id != current_category_id:
            print(f"   📝 Categoría correcta encontrada: {correct_category_id}")

            # Crear mini_ml corregido
            fixed_mini = mini_ml.copy()
            fixed_mini['category_id'] = correct_category_id
            fixed_mini['category_name'] = suggested_cat

            return True, f"Categoría incorrecta: {reasoning}", fixed_mini

    return False, "", None


def batch_post_validation(asins: list, ml_token: str) -> Dict:
    """
    Valida POST-publicación un lote de ASINs.

    Returns:
        Dict con ASINs que necesitan re-publicación
    """
    from pathlib import Path

    results = {
        'valid': [],
        'need_republish': [],
        'fixes': {}
    }

    for asin in asins:
        mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")

        if not mini_path.exists():
            continue

        with open(mini_path) as f:
            mini_ml = json.load(f)

        needs_fix, reason, fixed_mini = post_publish_validation_and_fix(
            mini_ml, ml_token
        )

        if needs_fix and fixed_mini:
            results['need_republish'].append(asin)
            results['fixes'][asin] = {
                'reason': reason,
                'old_category': mini_ml['category_id'],
                'new_category': fixed_mini['category_id'],
                'fixed_mini_ml': fixed_mini
            }

            # Guardar mini_ml corregido
            with open(mini_path, 'w') as f:
                json.dump(fixed_mini, f, indent=2, ensure_ascii=False)

            print(f"   💾 Mini ML actualizado para re-publicación")
        else:
            results['valid'].append(asin)

    return results


def main():
    """Test de validación POST-publicación"""
    import os
    from dotenv import load_dotenv
    from pathlib import Path

    load_dotenv()

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
    print("🔍 VALIDACIÓN POST-PUBLICACIÓN CON IA")
    print("=" * 70)

    results = batch_post_validation(asins, ml_token)

    print("\n" + "=" * 70)
    print("📊 RESULTADOS DE VALIDACIÓN POST-PUBLICACIÓN")
    print("=" * 70)
    print(f"✅ Categorías válidas: {len(results['valid'])}")
    print(f"🔄 Necesitan re-publicación: {len(results['need_republish'])}")

    if results['need_republish']:
        print(f"\n🔄 ASINs que necesitan re-publicación:")
        for asin in results['need_republish']:
            fix = results['fixes'][asin]
            print(f"\n  {asin}:")
            print(f"    Razón: {fix['reason']}")
            print(f"    Categoría anterior: {fix['old_category']}")
            print(f"    Categoría correcta: {fix['new_category']}")

        # Guardar reporte
        report_path = Path("storage/post_validation_report.json")
        with open(report_path, 'w') as f:
            json.dump({
                'valid': results['valid'],
                'need_republish': results['need_republish'],
                'fixes': {k: {
                    'reason': v['reason'],
                    'old_category': v['old_category'],
                    'new_category': v['new_category']
                } for k, v in results['fixes'].items()}
            }, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Reporte guardado: {report_path}")
        print(f"\nPara re-publicar con categorías corregidas:")
        print(f"  python3 republish_failed.py")


if __name__ == "__main__":
    main()
