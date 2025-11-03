#!/usr/bin/env python3
"""
Usa IA para encontrar LA categoría correcta para cada producto.
NO usa categorías genéricas - IA decide basándose en el producto real.
"""

import os
import json
import requests
from pathlib import Path
from typing import Optional, Dict
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


def get_correct_category_with_ai(
    title: str,
    description: str,
    brand: str,
    amazon_json: dict,
    ml_token: str
) -> Optional[Dict]:
    """
    Usa IA para determinar la categoría CBT correcta basándose en el producto real.

    Returns:
        Dict con 'category_id' y 'category_name' o None
    """

    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        return None

    try:
        client = OpenAI(api_key=openai_key)

        # Extraer info clave del producto
        product_type = amazon_json.get('attributes', {}).get('product_type', [{}])[0].get('value', '')
        item_type = amazon_json.get('attributes', {}).get('item_type_name', [{}])[0].get('value', '')

        prompt = f"""Eres un experto en categorización de productos para MercadoLibre Cross Border Trade (CBT).

Tu tarea: Determinar la categoría CBT MÁS ESPECÍFICA Y CORRECTA para este producto.

**PRODUCTO:**
Título: {title}
Marca: {brand}
Tipo (Amazon): {product_type or item_type}
Descripción: {description[:300]}...

**REGLAS IMPORTANTES:**

1. **NO uses categorías genéricas** como "Toys & Games" a menos que sea realmente un juguete
2. **Usa la categoría MÁS ESPECÍFICA** que describa el producto exactamente
3. **Prioriza la función/uso del producto** sobre la apariencia

**CATEGORÍAS CBT DISPONIBLES:**

**Relojes y Wearables:**
- CBT3814: Smartwatches (relojes inteligentes con GPS, fitness tracking)
- CBT75891: Relojes Deportivos (relojes fitness, cronómetros deportivos)
- CBT3937: Relojes de Pulsera (relojes tradicionales, fashion watches)

**LEGO y Construcción:**
- CBT1157: Building Blocks & Figures (LEGO, bloques de construcción)
- CBT4545: Construction Sets (sets de construcción grandes, LEGO Icons)

**Deportes:**
- CBT170196: Basketballs (balones de baloncesto)
- CBT29878: Sports Equipment (equipamiento deportivo general)
- CBT180362: Fitness Accessories (accesorios para gimnasio/fitness)

**Electrónicos:**
- CBT8328: Headphones & Earbuds (audífonos, auriculares)
- CBT1058: Bluetooth Speakers (altavoces Bluetooth)
- CBT1663: Wearable Technology (tecnología portable)

**Belleza y Cuidado Personal:**
- CBT1276: Nail Polish (esmalte de uñas)
- CBT1280: Facial Masks (mascarillas faciales)
- CBT1254: Bath & Shower Gels (geles de baño)
- CBT1273: Leather Care (cuidado de cuero)

**Joyería:**
- CBT3676: Earrings (aretes, pendientes)
- CBT3928: Necklaces (collares)
- CBT3674: Rings (anillos)

**Juguetes y Manualidades:**
- CBT45462: Arts & Crafts Kits (kits de arte y manualidades)
- CBT116629: Toys General (juguetes generales solo si no hay otra categoría)

**EJEMPLOS DE CATEGORIZACIÓN CORRECTA:**

Producto: "Garmin Forerunner 55 GPS Running Watch"
Categoría CORRECTA: CBT3814 - Smartwatches
Razón: Es un reloj GPS con funciones smart, NO es un juguete

Producto: "LEGO Creator 3 in 1 Animals Building Set"
Categoría CORRECTA: CBT1157 - Building Blocks & Figures
Razón: Es un set LEGO de construcción

Producto: "Wilson Evolution Basketball Official Size"
Categoría CORRECTA: CBT170196 - Basketballs
Razón: Es específicamente un balón de baloncesto

Producto: "Picun Bluetooth Headphones Over-Ear"
Categoría CORRECTA: CBT8328 - Headphones & Earbuds
Razón: Son audífonos Bluetooth

Producto: "Dr.Jart+ Dermask Water Jet Facial Mask"
Categoría CORRECTA: CBT1280 - Facial Masks
Razón: Es una mascarilla facial de cuidado de piel

**RESPONDE EN JSON:**
{{
  "category_id": "CBT####",
  "category_name": "Nombre exacto de la categoría",
  "confidence": 0-100,
  "reasoning": "Por qué esta es la categoría correcta (1 línea)"
}}

Responde SOLO con el JSON, sin explicaciones adicionales.
"""

        response = client.chat.completions.create(
            model="gpt-4o",  # Usar GPT-4o para mejor precisión
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.choices[0].message.content.strip()

        # Extraer JSON
        import re
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))

            category_id = result.get('category_id', '')
            category_name = result.get('category_name', '')
            confidence = result.get('confidence', 0)
            reasoning = result.get('reasoning', '')

            print(f"   🤖 IA sugiere: {category_id} - {category_name}")
            print(f"      Confianza: {confidence}%")
            print(f"      Razón: {reasoning}")

            return {
                'category_id': category_id,
                'category_name': category_name,
                'confidence': confidence,
                'reasoning': reasoning
            }

    except Exception as e:
        print(f"   ⚠️ Error en IA: {e}")

    return None


def assign_correct_categories():
    """Asigna categorías correctas a todos los mini_ml usando IA."""

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
    print("🤖 ASIGNANDO CATEGORÍAS CORRECTAS CON IA")
    print("=" * 70)

    updated_count = 0

    for i, asin in enumerate(asins, 1):
        print(f"\n{i}/{len(asins)}. {asin}")
        print("-" * 70)

        # Cargar mini_ml
        mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")
        if not mini_path.exists():
            print(f"   ⚠️  Mini ML no existe")
            continue

        with open(mini_path) as f:
            mini_ml = json.load(f)

        # Cargar Amazon JSON para más contexto
        amazon_path = Path(f"storage/asins_json/{asin}.json")
        amazon_json = {}
        if amazon_path.exists():
            with open(amazon_path) as f:
                amazon_json = json.load(f)

        current_cat = mini_ml.get('category_id')
        print(f"   📋 Categoría actual: {current_cat} - {mini_ml.get('category_name')}")

        # Obtener categoría correcta con IA
        correct_cat = get_correct_category_with_ai(
            title=mini_ml.get('title_ai', ''),
            description=mini_ml.get('description_ai', ''),
            brand=mini_ml.get('brand', ''),
            amazon_json=amazon_json,
            ml_token=ml_token
        )

        if correct_cat and correct_cat['category_id'] != current_cat:
            # Actualizar mini_ml
            mini_ml['category_id'] = correct_cat['category_id']
            mini_ml['category_name'] = correct_cat['category_name']

            with open(mini_path, 'w') as f:
                json.dump(mini_ml, f, indent=2, ensure_ascii=False)

            print(f"   ✅ Categoría actualizada:")
            print(f"      {current_cat} → {correct_cat['category_id']}")

            updated_count += 1
        elif correct_cat:
            print(f"   ✓  Categoría ya es correcta")
        else:
            print(f"   ⚠️  IA no pudo determinar categoría")

    print("\n" + "=" * 70)
    print(f"📊 {updated_count}/{len(asins)} categorías actualizadas")
    print("\nAhora ejecuta:")
    print("  python3 validate_and_publish_existing.py")


if __name__ == "__main__":
    assign_correct_categories()
