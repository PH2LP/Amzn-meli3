#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema Unificado de Transformación Amazon → ML
Una sola llamada a IA para generar TODO el JSON de ML
"""

import os
import json
from typing import Dict, Optional

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def transform_amazon_to_ml_unified(amazon_json: dict, target_category: Optional[str] = None) -> Optional[Dict]:
    """
    Transforma el JSON completo de Amazon a formato ML en UNA sola llamada a IA.

    Retorna un diccionario con:
    - category_id
    - category_name
    - title
    - description
    - attributes (lista completa ya mapeada)
    - images
    - price info
    - dimensions
    """

    if not OPENAI_API_KEY:
        print("⚠️ Sin OPENAI_API_KEY, no se puede usar transformación unificada")
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        # Limitar el JSON de Amazon para no exceder tokens
        amazon_data_str = json.dumps(amazon_json, indent=2)[:20000]

        prompt = f"""You are an expert e-commerce data transformer. Your task is to transform Amazon product data into MercadoLibre CBT format.

Input: Amazon SP-API JSON
Output: Complete MercadoLibre listing JSON

Amazon Product Data (truncated):
```json
{amazon_data_str}
```

TASK: Generate a COMPLETE MercadoLibre listing JSON with ALL required fields.

REQUIREMENTS:
1. **Category**: Analyze the product and suggest the best CBT category ID and name
   - Use generic categories like: CBT1157 (LEGO/Building), CBT455414 (Headphones), CBT29890 (Nail Polish), etc.
   - Base the decision on product type, not brand

2. **Title**: Create Spanish title (max 60 chars) following format:
   - Brand + Product Type + Key Feature
   - Example: "LEGO Icons 10314 Set de Construcción para Adultos"

3. **Description**: Generate Spanish description (3-4 paragraphs) with:
   - Product benefits and features
   - Technical specifications
   - Use case / target audience
   - No HTML, just plain text

4. **Attributes**: Extract and map ALL relevant attributes from Amazon data
   - Use MercadoLibre attribute names (BRAND, MODEL, COLOR, MATERIAL, etc.)
   - Include both value_id (if known) and value_name
   - Format: [{{"id": "BRAND", "value_name": "LEGO"}}, ...]

5. **Images**: Extract image URLs from Amazon data
   - Format: [{{"url": "https://...", "order": 0}}, ...]

6. **Dimensions**: Extract package dimensions (length, width, height in cm, weight in kg)
   - Use item_package_dimensions if available
   - Convert inches to cm, pounds to kg

7. **Price**: Extract price information
   - base_usd: listing price without tax
   - tax_usd: tax amount (if any)

IMPORTANT:
- Return ONLY valid JSON, no markdown, no explanations
- Use real data from the Amazon JSON, don't invent
- All text in Spanish (Latin America)
- Be comprehensive but accurate

Output Format:
```json
{{
  "category_id": "CBT1157",
  "category_name": "Building Blocks & Figures",
  "title": "...",
  "description": "...",
  "attributes": [...],
  "images": [...],
  "dimensions": {{
    "length_cm": 0,
    "width_cm": 0,
    "height_cm": 0,
    "weight_kg": 0
  }},
  "price": {{
    "base_usd": 0,
    "tax_usd": 0
  }}
}}
```
"""

        print("🧠 Llamando a IA para transformación completa...")

        response = client.chat.completions.create(
            model="gpt-4o",  # Usar GPT-4o para máxima precisión en esta tarea crítica
            temperature=0.3,
            messages=[
                {"role": "system", "content": "You are a product data transformer. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000
        )

        result_text = response.choices[0].message.content.strip()

        # Extraer JSON de la respuesta
        import re
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if not json_match:
            print("❌ IA no devolvió JSON válido")
            return None

        result = json.loads(json_match.group(0))

        print(f"✅ Transformación completa generada por IA")
        print(f"   Categoría: {result.get('category_id')} - {result.get('category_name')}")
        print(f"   Atributos: {len(result.get('attributes', []))}")
        print(f"   Imágenes: {len(result.get('images', []))}")

        return result

    except Exception as e:
        print(f"❌ Error en transformación unificada: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        asin = sys.argv[1]
        with open(f"storage/asins_json/{asin}.json", "r") as f:
            amazon_json = json.load(f)

        print(f"\n{'='*70}")
        print(f"Transformando {asin} con sistema unificado...")
        print(f"{'='*70}\n")

        result = transform_amazon_to_ml_unified(amazon_json)

        if result:
            print(f"\n✅ RESULTADO:")
            print(json.dumps(result, indent=2, ensure_ascii=False))

            # Guardar resultado
            os.makedirs("storage/logs/unified_transform", exist_ok=True)
            with open(f"storage/logs/unified_transform/{asin}_unified.json", "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Guardado en: storage/logs/unified_transform/{asin}_unified.json")
        else:
            print(f"\n❌ No se pudo transformar")
    else:
        print("Uso: python src/unified_transformer.py <ASIN>")
