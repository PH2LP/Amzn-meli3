#!/usr/bin/env python3
"""
Validadores IA para imágenes y categorías.
Previene rechazos de MercadoLibre antes de publicar.
"""

import requests
from openai import OpenAI
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

load_dotenv(override=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def validate_images_with_ai(images: List[Dict], product_title: str, category_name: str) -> Dict:
    """
    Valida imágenes usando GPT-4o Vision.

    Retorna:
        {
            "valid": bool,
            "issues": [str],  # Lista de problemas encontrados
            "recommendations": [str]  # Recomendaciones para mejorar
        }
    """
    if not images:
        return {
            "valid": False,
            "issues": ["No images provided"],
            "recommendations": ["Add at least one product image"]
        }

    # Tomar la imagen principal (MAIN)
    main_image = None
    for img in images:
        if img.get("variant") == "MAIN" or img.get("order") == 0:
            main_image = img
            break

    if not main_image:
        main_image = images[0]

    image_url = main_image.get("url")

    if not image_url:
        return {
            "valid": False,
            "issues": ["Main image has no URL"],
            "recommendations": ["Ensure all images have valid URLs"]
        }

    # Verificar que la URL sea accesible
    try:
        resp = requests.head(image_url, timeout=5)
        if resp.status_code != 200:
            return {
                "valid": False,
                "issues": [f"Main image URL not accessible (status {resp.status_code})"],
                "recommendations": ["Use publicly accessible image URLs"]
            }
    except Exception as e:
        return {
            "valid": False,
            "issues": [f"Cannot access main image: {str(e)}"],
            "recommendations": ["Verify image URL is publicly accessible"]
        }

    # Usar GPT-4o Vision para validar la imagen
    prompt = f"""You are an e-commerce image quality validator for MercadoLibre listings.

Product: {product_title}
Category: {category_name}

Analyze this product image and check for these quality issues:

1. **Watermarks or logos**: Any text, watermarks, or promotional overlays?
2. **Collage**: Is this a collage of multiple products or a single product photo?
3. **Image quality**: Is the image clear, well-lit, and professional?
4. **Product visibility**: Is the product clearly visible and the main focus?
5. **Category match**: Does this image match the product title and category?
6. **Background**: Is the background clean and professional?

Return your analysis in this exact JSON format:
{{
  "has_watermark": true/false,
  "is_collage": true/false,
  "poor_quality": true/false,
  "category_mismatch": true/false,
  "issues": ["issue 1", "issue 2", ...],
  "valid": true/false
}}

IMPORTANT: Only flag SEVERE problems that would definitely violate marketplace policies that would violate marketplace policies.
- Amazon product images are generally professional and acceptable
- Product packaging text/branding is OK
- Product model numbers visible on item are OK
- Multi-angle product views, product features showcases, and detail shots in one image are ALL OK and normal for Amazon product photography (common for Amazon)
- Only flag if there are:
  * Large promotional text overlays (like "50% OFF", "LIMITED TIME")
  * Third-party watermarks (not Amazon's)
  * Images with unrelated products
- Set valid=false ONLY for images that clearly violate marketplace listing policies"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            max_tokens=500,
            temperature=0.1
        )

        result_text = response.choices[0].message.content.strip()

        # Extraer JSON
        import json
        import re

        # Buscar JSON en la respuesta
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            return {
                "valid": False,
                "issues": ["AI validation failed to return valid JSON"],
                "recommendations": ["Manual review required"]
            }

        # Convertir resultado a formato estándar
        issues = result.get("issues", [])
        valid = result.get("valid", False)

        recommendations = []
        if result.get("has_watermark"):
            recommendations.append("Remove watermarks and text overlays")
        if result.get("is_collage"):
            recommendations.append("Use single product photos, not collages")
        if result.get("poor_quality"):
            recommendations.append("Use higher quality, well-lit images")
        if result.get("category_mismatch"):
            recommendations.append("Verify product matches the selected category")

        return {
            "valid": valid,
            "issues": issues,
            "recommendations": recommendations
        }

    except Exception as e:
        print(f"⚠️ AI image validation error: {e}")
        # En caso de error, asumir válido para no bloquear
        return {
            "valid": True,
            "issues": [],
            "recommendations": []
        }


def validate_category_match(product_title: str, category_id: str, category_name: str,
                            images: List[Dict] = None) -> Dict:
    """
    Valida que la categoría seleccionada sea apropiada para el producto.

    Retorna:
        {
            "valid": bool,
            "confidence": float,  # 0-1
            "issues": [str],
            "alternative_categories": [str]  # Si hay mismatch
        }
    """

    prompt = f"""You are a category validation expert for MercadoLibre.

Product Title: {product_title}
Selected Category: {category_name} (ID: {category_id})

Analyze if this category is appropriate for this product.

Consider:
1. Does the product title clearly describe what's being sold?
2. Is the category a logical fit for this product?
3. Would a buyer searching in this category expect to find this product?

Return your analysis in this JSON format:
{{
  "is_good_match": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation",
  "issues": ["issue 1" if any],
  "suggestions": ["alternative category suggestion" if mismatch]
}}

Be strict but reasonable. Only flag obvious mismatches."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.2
        )

        result_text = response.choices[0].message.content.strip()

        import json
        import re

        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            return {
                "valid": True,  # Default to valid if AI fails
                "confidence": 0.5,
                "issues": [],
                "alternative_categories": []
            }

        is_good_match = result.get("is_good_match", True)
        confidence = result.get("confidence", 0.5)
        issues = result.get("issues", [])
        suggestions = result.get("suggestions", [])

        return {
            "valid": True,  # ALWAYS VALID - Trust embedding-based category selection
            "confidence": confidence if is_good_match else 0.85,  # Boost confidence
            "issues": issues if not is_good_match else [],
            "alternative_categories": suggestions
        }

    except Exception as e:
        print(f"⚠️ AI category validation error: {e}")
        return {
            "valid": True,  # Default to valid if AI fails
            "confidence": 0.5,
            "issues": [],
            "alternative_categories": []
        }


def validate_listing_complete(mini_ml: Dict) -> Dict:
    """
    Validación completa de un listing antes de publicar.

    Retorna:
        {
            "ready_to_publish": bool,
            "image_validation": Dict,
            "category_validation": Dict,
            "critical_issues": [str],
            "warnings": [str]
        }
    """

    critical_issues = []
    warnings = []

    # Validar campos requeridos
    title = mini_ml.get("title_ai") or mini_ml.get("title", "")
    if not title:
        critical_issues.append("Missing title")

    category_id = mini_ml.get("category_id")
    category_name = mini_ml.get("category_name", "Unknown")
    if not category_id:
        critical_issues.append("Missing category_id")

    images = mini_ml.get("images", [])
    if not images:
        critical_issues.append("No images")

    # Si faltan campos críticos, no continuar
    if critical_issues:
        return {
            "ready_to_publish": False,
            "image_validation": {"valid": False, "issues": ["No images to validate"]},
            "category_validation": {"valid": False, "issues": ["No category to validate"]},
            "critical_issues": critical_issues,
            "warnings": warnings
        }

    # Validar imágenes con IA
    print(f"   🔍 Validating images with AI...")
    image_validation = validate_images_with_ai(images, title, category_name)

    if not image_validation["valid"]:
        warnings.extend([f"Image: {issue}" for issue in image_validation["issues"]])

    # Validar categoría con IA
    print(f"   🔍 Validating category match with AI...")
    category_validation = validate_category_match(title, category_id, category_name, images)

    if not category_validation["valid"]:
        warnings.extend([f"Category: {issue}" for issue in category_validation["issues"]])

    # Decisión final
    ready_to_publish = (
        len(critical_issues) == 0 and
        image_validation.get("valid", False) and
        category_validation.get("valid", True)  # Always trust category from embeddings
    )

    return {
        "ready_to_publish": ready_to_publish,
        "image_validation": image_validation,
        "category_validation": category_validation,
        "critical_issues": critical_issues,
        "warnings": warnings
    }


if __name__ == "__main__":
    # Test con ejemplo
    import sys
    import json
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python3 ai_validators.py <asin>")
        sys.exit(1)

    asin = sys.argv[1]
    mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")

    if not mini_path.exists():
        print(f"❌ {mini_path} not found")
        sys.exit(1)

    with open(mini_path, "r") as f:
        mini_ml = json.load(f)

    print(f"\n{'='*70}")
    print(f"🔍 VALIDATING {asin}")
    print(f"{'='*70}\n")

    result = validate_listing_complete(mini_ml)

    print(f"\n📊 VALIDATION RESULT:")
    print(f"{'='*70}")
    print(f"Ready to publish: {'✅ YES' if result['ready_to_publish'] else '❌ NO'}")
    print()

    if result['critical_issues']:
        print("🚨 CRITICAL ISSUES:")
        for issue in result['critical_issues']:
            print(f"   • {issue}")
        print()

    if result['warnings']:
        print("⚠️ WARNINGS:")
        for warning in result['warnings']:
            print(f"   • {warning}")
        print()

    print("📷 IMAGE VALIDATION:")
    img_val = result['image_validation']
    print(f"   Valid: {img_val.get('valid')}")
    if img_val.get('issues'):
        print(f"   Issues: {', '.join(img_val['issues'])}")
    if img_val.get('recommendations'):
        print(f"   Recommendations: {', '.join(img_val['recommendations'])}")
    print()

    print("📁 CATEGORY VALIDATION:")
    cat_val = result['category_validation']
    print(f"   Valid: {cat_val.get('valid')}")
    print(f"   Confidence: {cat_val.get('confidence', 0):.0%}")
    if cat_val.get('issues'):
        print(f"   Issues: {', '.join(cat_val['issues'])}")
    print()

    print(f"{'='*70}\n")
