#!/usr/bin/env python3
"""
Test de detección de logos con imágenes REALES de internet
"""

import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def build_logo_detection_prompt_v2(product_title, product_description):
    """Prompt mejorado V2"""

    prompt = f"""You are an expert trademark and logo detector for MercadoLibre compliance.

CRITICAL MISSION: Detect ONLY actual, visible brand logos and trademarks that would violate MercadoLibre policies.

PRODUCT CONTEXT:
Title: {product_title}
Description: {product_description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT TO DETECT (STRICT CRITERIA - ALL must be met):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. BRAND LOGOS (Graphical):
   ✅ DETECT: Apple logo (🍎), Samsung logo, PlayStation symbols, Nintendo logo, Windows logo, Android robot
   ❌ IGNORE: Generic shapes, connectors, ports, buttons without branding

2. BRAND TEXT/WORDMARKS:
   ✅ DETECT: "Apple", "Samsung", "PlayStation", "Xbox", "Nintendo" when part of product/packaging branding
   ❌ IGNORE: Text in compatibility descriptions (e.g., "Compatible with iPad" is OK)

3. BRANDED DEVICES VISIBLE:
   ✅ DETECT: Actual branded devices showing logos (iPhone with Apple logo, PS5 with branding)
   ❌ IGNORE: Generic device shapes without visible branding

4. GAME/APP LOGOS:
   ✅ DETECT: Official game cover art, app icons (Instagram, WhatsApp)
   ❌ IGNORE: Generic icons without specific branding

5. PACKAGING WITH BRANDING:
   ✅ DETECT: Original retail boxes with brand logos
   ❌ IGNORE: Generic packaging

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL: WHAT NOT TO DETECT (Avoid False Positives):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ DO NOT flag:
- Compatibility text mentioning brands
- Generic USB/Lightning/USB-C connectors
- Generic buttons, ports
- Certification marks (CE, FCC)
- Model numbers
- Generic shapes
- System UI without branding
- Blurry shapes

CONFIDENCE RULES:
- 0.90-1.00: Crystal clear logo
- 0.70-0.89: Clearly visible
- 0.60-0.69: Somewhat visible
- Below 0.60: DO NOT REPORT

If unsure, default to "keep".

OUTPUT FORMAT (JSON only):
{{
  "has_logos": true/false,
  "logos_detected": [
    {{
      "brand": "exact brand name",
      "type": "hardware_logo|device_visible|game_cover|app_icon|packaging",
      "location": "specific location",
      "confidence": 0.60-1.00,
      "description": "specific detail"
    }}
  ],
  "recommendation": "keep|remove",
  "reason": "brief explanation",
  "false_positive_check": "confirmation this is real logo"
}}

DECISION: If any logo confidence >= 0.60 → "remove", else → "keep"

Now analyze the image."""

    return prompt


def analyze_image(image_url, product_title, product_description):
    """Analiza imagen con GPT-4 Vision"""

    prompt = build_logo_detection_prompt_v2(product_title, product_description)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=800,
            temperature=0.1
        )

        result_text = response.choices[0].message.content.strip()

        # Extraer JSON
        import re
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        else:
            return {"error": "No JSON found", "raw": result_text[:200]}

    except Exception as e:
        return {"error": str(e)}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST CASES CON IMÁGENES REALES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

test_cases = [
    {
        "name": "❌ DEBE REMOVER: iPad con logo Apple visible",
        "url": "https://m.media-amazon.com/images/I/61NGnpjoRDL._AC_SL1500_.jpg",
        "product": "Teclado PARA iPad",
        "description": "Teclado bluetooth compatible",
        "expected": "remove",
        "reason": "Logo de Apple visible en iPad"
    },
    {
        "name": "✅ DEBE MANTENER: Cable USB-C genérico",
        "url": "https://m.media-amazon.com/images/I/61T7T+JG4sL._AC_SL1500_.jpg",
        "product": "Cable USB-C",
        "description": "Cable de carga",
        "expected": "keep",
        "reason": "Solo cable genérico sin logos"
    },
    {
        "name": "❌ DEBE REMOVER: Funda con iPhone mostrando logo",
        "url": "https://m.media-amazon.com/images/I/71k4JMT2CFL._AC_SL1500_.jpg",
        "product": "Funda PARA iPhone",
        "description": "Funda protectora de silicona",
        "expected": "remove",
        "reason": "iPhone visible con posible logo Apple"
    },
    {
        "name": "✅ DEBE MANTENER: Funda sola sin dispositivo",
        "url": "https://m.media-amazon.com/images/I/61vY4xOQ3KL._AC_SL1500_.jpg",
        "product": "Funda PARA iPhone",
        "description": "Funda de silicona",
        "expected": "keep",
        "reason": "Solo la funda, sin logos visibles"
    },
    {
        "name": "❌ DEBE REMOVER: Base PS5 con logos PlayStation",
        "url": "https://m.media-amazon.com/images/I/61rYzp7GTAL._AC_SL1500_.jpg",
        "product": "Base Cargadora PARA PlayStation 5",
        "description": "Estación de carga",
        "expected": "remove",
        "reason": "Logos PlayStation/PS5 visibles"
    },
    {
        "name": "✅ DEBE MANTENER: Soporte genérico",
        "url": "https://m.media-amazon.com/images/I/61QG+hCLj2L._AC_SL1500_.jpg",
        "product": "Soporte para tablet",
        "description": "Soporte ajustable",
        "expected": "keep",
        "reason": "Soporte genérico sin branding"
    }
]


def main():
    print("=" * 80)
    print("🧪 TEST: DETECCIÓN DE LOGOS CON IMÁGENES REALES")
    print("=" * 80)
    print()
    print("Analizando 6 casos de prueba con GPT-4 Vision...")
    print()

    results = []

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'━' * 80}")
        print(f"TEST {i}/6: {test['name']}")
        print(f"{'━' * 80}")
        print(f"📦 Producto: {test['product']}")
        print(f"🔗 URL: {test['url'][:70]}...")
        print(f"✅ Esperado: {test['expected'].upper()}")
        print()
        print("🧠 Analizando con IA...")

        analysis = analyze_image(
            test['url'],
            test['product'],
            test['description']
        )

        if "error" in analysis:
            print(f"❌ ERROR: {analysis['error']}")
            results.append({
                "test": test['name'],
                "status": "ERROR",
                "expected": test['expected'],
                "got": "error"
            })
            continue

        got = analysis.get('recommendation', 'unknown')
        logos = analysis.get('logos_detected', [])
        reason = analysis.get('reason', 'N/A')

        print(f"📊 Resultado:")
        print(f"   Decisión: {got.upper()}")
        print(f"   Logos detectados: {len(logos)}")

        if logos:
            for logo in logos:
                print(f"      - {logo['brand']} (conf: {logo['confidence']:.2f}) - {logo['description']}")

        print(f"   Razón: {reason}")
        print()

        # Verificar si es correcto
        is_correct = (got == test['expected'])

        if is_correct:
            print(f"✅ CORRECTO - La IA decidió {got.upper()} como esperado")
        else:
            print(f"❌ INCORRECTO - Esperaba {test['expected'].upper()} pero obtuvo {got.upper()}")
            print(f"   Explicación esperada: {test['reason']}")

        results.append({
            "test": test['name'],
            "status": "PASS" if is_correct else "FAIL",
            "expected": test['expected'],
            "got": got,
            "logos": len(logos),
            "reason": reason
        })

    # Resumen
    print("\n" + "=" * 80)
    print("📊 RESUMEN DE RESULTADOS")
    print("=" * 80)

    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')
    errors = sum(1 for r in results if r['status'] == 'ERROR')

    print(f"\n✅ Pasados: {passed}/{len(results)}")
    print(f"❌ Fallados: {failed}/{len(results)}")
    print(f"⚠️  Errores: {errors}/{len(results)}")

    accuracy = (passed / len(results) * 100) if results else 0
    print(f"\n🎯 Precisión: {accuracy:.1f}%")

    if failed > 0:
        print(f"\n❌ Tests fallados:")
        for r in results:
            if r['status'] == 'FAIL':
                print(f"   • {r['test']}")
                print(f"     Esperaba: {r['expected']} | Obtuvo: {r['got']}")

    print("\n" + "=" * 80)

    if accuracy >= 80:
        print("✅ SISTEMA FUNCIONAL - Precisión aceptable (>80%)")
    else:
        print("⚠️  REVISAR PROMPT - Precisión baja (<80%)")

    print()


if __name__ == "__main__":
    main()
