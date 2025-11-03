#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Categorización Inteligente con IA
Usa GPT-4o-mini para categorizar productos automáticamente
"""

import os
import json
import requests
from typing import Dict, Optional, List

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def search_ml_categories(query: str, limit: int = 5) -> List[Dict]:
    """Busca categorías en MercadoLibre"""
    try:
        url = f"https://api.mercadolibre.com/sites/CBT/domain_discovery/search?limit={limit}&q={query.replace(' ', '+')}"
        response = requests.get(url, timeout=10)
        if response.ok:
            return response.json()
        return []
    except Exception as e:
        print(f"⚠️ Error buscando categorías: {e}")
        return []


def categorize_with_ai(amazon_json: dict) -> Optional[Dict]:
    """
    Usa GPT-4o-mini para categorizar un producto basándose en TODOS sus datos.
    Retorna la mejor categoría de MercadoLibre.
    """
    if not OPENAI_API_KEY:
        print("⚠️ Sin OPENAI_API_KEY, usando fallback")
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        # Extraer información clave del producto de manera segura
        summaries = amazon_json.get("summaries", [])
        if isinstance(summaries, list) and summaries:
            summary = summaries[0]
        else:
            summary = {}

        title = summary.get("itemName", "")
        brand = summary.get("brand", "")
        product_type = summary.get("productType", "")

        # Construir descripción del producto
        product_info = {
            "title": title,
            "brand": brand,
            "product_type": product_type,
            "key_attributes": []
        }

        # Extraer atributos clave
        attributes = amazon_json.get("attributes", [])
        if isinstance(attributes, list):
            for attr in attributes[:15]:  # Solo los primeros 15
                if isinstance(attr, dict):
                    name = attr.get("attributeName", "")
                    value = attr.get("attributeValue", "")
                    if name and value:
                        product_info["key_attributes"].append(f"{name}: {value}")

        product_json = json.dumps(product_info, indent=2)

        prompt = f"""You are an expert e-commerce product categorizer for MercadoLibre (Latin America's largest marketplace).

Your task is to analyze this product and suggest the BEST search query to find the correct category in MercadoLibre's catalog.

Product information:
{product_json}

RULES:
1. Return a SHORT, specific search query (3-6 words) that describes the product type
2. Use generic terms, not brand names (e.g., "GPS device" not "Garmin")
3. Think about how customers search for this product
4. Use English terms (MercadoLibre CBT uses English categories)
5. Be specific but not too narrow

Examples:
- "Garmin GPS navigator" → "gps navigation device"
- "LEGO Bonsai building set" → "lego building set"
- "Bluetooth headphones" → "bluetooth headphones"
- "Digital sports watch" → "sports watch"
- "Nail polish" → "nail polish"
- "Basketball ball" → "basketball"
- "Face mask skincare" → "face mask skin care"

Return ONLY the search query, nothing else.
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            messages=[
                {"role": "system", "content": "You are a product categorization expert. Return only the search query."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=20
        )

        search_query = response.choices[0].message.content.strip()
        print(f"🧠 IA sugiere buscar: '{search_query}'")

        # Buscar categorías con el query sugerido por IA
        categories = search_ml_categories(search_query, limit=5)

        if not categories:
            # Fallback 1: Pedir a la IA un query más genérico
            print(f"⚠️ Sin resultados, pidiendo query más genérico...")

            generic_prompt = f"""The search query "{search_query}" returned no results.
Provide a MORE GENERIC search query (2-4 words) for this product: "{title}"

Examples:
- "kids rock painting kit" → "arts crafts kit"
- "gps running watch" → "sports watch"
- "lego harry potter" → "lego set"

Return ONLY the generic query."""

            generic_response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.3,
                messages=[
                    {"role": "system", "content": "Return only the search query."},
                    {"role": "user", "content": generic_prompt}
                ],
                max_tokens=10
            )

            generic_query = generic_response.choices[0].message.content.strip()
            print(f"🧠 IA sugiere query genérico: '{generic_query}'")

            categories = search_ml_categories(generic_query, limit=5)

            if not categories:
                # Fallback 2: buscar con el título completo (primeras 4 palabras)
                print(f"⚠️ Sin resultados, buscando con título...")
                title_words = title.split()[:4]
                search_query = " ".join(title_words)
                categories = search_ml_categories(search_query, limit=5)

            if not categories:
                # Fallback 3: buscar solo con product_type
                if product_type:
                    print(f"⚠️ Último intento con product_type: {product_type}")
                    categories = search_ml_categories(product_type, limit=5)

        if categories:
            # Usar IA para elegir la MEJOR categoría entre las opciones
            print(f"🤔 IA analizando {len(categories)} categorías posibles...")

            categories_text = "\n".join([
                f"{i+1}. {cat['category_id']} - {cat['category_name']}"
                for i, cat in enumerate(categories)
            ])

            selection_prompt = f"""You are an expert product categorizer. Choose the BEST category for this product.

Product: {title}
Brand: {brand}
Type: {product_type}

Available categories:
{categories_text}

Return ONLY the number (1-{len(categories)}) of the best category. No explanation."""

            selection_response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.1,
                messages=[
                    {"role": "system", "content": "Return only a number."},
                    {"role": "user", "content": selection_prompt}
                ],
                max_tokens=5
            )

            try:
                selected_num = int(selection_response.choices[0].message.content.strip())
                if 1 <= selected_num <= len(categories):
                    best_category = categories[selected_num - 1]
                else:
                    # Fallback a la primera
                    best_category = categories[0]
            except:
                # Fallback a la primera
                best_category = categories[0]

            print(f"✅ Categoría seleccionada: {best_category['category_id']} - {best_category['category_name']}")

            return {
                "category_id": best_category["category_id"],
                "category_name": best_category["category_name"],
                "domain_name": best_category.get("domain_name", ""),
                "search_query": search_query,
                "ai_confidence": "high" if len(categories) == 1 else "medium",
                "alternatives": [
                    {
                        "category_id": cat["category_id"],
                        "category_name": cat["category_name"]
                    }
                    for cat in categories[:5] if cat != best_category  # Guardar alternativas
                ]
            }
        else:
            print(f"❌ No se encontraron categorías para: {search_query}")
            return None

    except Exception as e:
        print(f"❌ Error en categorización IA: {e}")
        import traceback
        traceback.print_exc()
        return None


def validate_category_with_product(category_id: str, amazon_json: dict) -> bool:
    """
    Valida si una categoría es apropiada para un producto usando IA.
    Retorna True si es una buena categoría, False si no.
    """
    if not OPENAI_API_KEY:
        return True  # Sin IA, asumir que está bien

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        # Obtener nombre de la categoría
        try:
            response = requests.get(f"https://api.mercadolibre.com/categories/{category_id}", timeout=10)
            if response.ok:
                category_name = response.json().get("name", category_id)
            else:
                category_name = category_id
        except:
            category_name = category_id

        summaries = amazon_json.get("summaries", [{}])[0]
        title = summaries.get("itemName", "")

        prompt = f"""Is the category "{category_name}" appropriate for this product: "{title}"?

Answer with ONLY: YES or NO"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            messages=[
                {"role": "system", "content": "You are a product categorization validator. Answer only YES or NO."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=5
        )

        answer = response.choices[0].message.content.strip().upper()
        is_valid = "YES" in answer

        if not is_valid:
            print(f"⚠️ IA detectó categoría incorrecta: {category_name} para {title[:50]}")

        return is_valid

    except Exception as e:
        print(f"⚠️ Error validando categoría: {e}")
        return True  # En caso de error, asumir que está bien


if __name__ == "__main__":
    # Test con un producto de ejemplo
    import sys
    if len(sys.argv) > 1:
        asin = sys.argv[1]
        with open(f"storage/asins_json/{asin}.json", "r") as f:
            amazon_json = json.load(f)

        print(f"\n{'='*70}")
        print(f"Categorizando {asin}...")
        print(f"{'='*70}\n")

        result = categorize_with_ai(amazon_json)

        if result:
            print(f"\n✅ RESULTADO:")
            print(json.dumps(result, indent=2))
        else:
            print(f"\n❌ No se pudo categorizar")
    else:
        print("Uso: python src/smart_categorizer.py <ASIN>")
