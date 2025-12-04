#!/usr/bin/env python3
"""
Test con prompt MUY ESTRICTO - solo detectar LOGOS VISIBLES
"""

import os
import json
import base64
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_image_strict(image_path):
    """Análisis ESTRICTO - solo logos visibles"""

    # Convertir a base64
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')

    prompt = """Analyze this product image for VISIBLE brand logos or trademarks.

⚠️ CRITICAL RULES:

WHAT TO DETECT (logos you CAN see):
- Apple logo symbol (🍎)
- PlayStation logo text or "PS" symbol
- Xbox logo
- Nintendo logo text
- Samsung logo text
- Brand text on products (e.g., "Sony", "Microsoft" written on device)
- Game title logos on boxes/covers
- App icons visible on screens

WHAT TO IGNORE (do NOT report these):
- Product shapes or designs (e.g., PlayStation controller shape is NOT a logo)
- Generic connectors or ports
- Compatibility text (e.g., "for iPad" is OK)
- Product recognition without visible branding (recognizing a PS5 shape is NOT a logo detection)
- Colors or form factors

ONLY report if you can LITERALLY SEE text, symbols, or trademarked graphics.

Respond in JSON:
{
  "has_logos": true/false,
  "logos_detected": [
    {
      "brand": "brand name",
      "location": "where exactly in image",
      "what_exactly": "describe the EXACT visible logo/text you see",
      "confidence": 0.0-1.0
    }
  ],
  "overall_confidence": 0.0-1.0,
  "recommendation": "keep" or "remove",
  "what_i_see": "general description"
}

If ANY logo detected with confidence >= 0.70 → recommend "remove"."""

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
                                "url": f"data:image/jpeg;base64,{base64_image}",
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
            return {"error": "No JSON", "raw": result_text[:300]}

    except Exception as e:
        return {"error": str(e)}


# Test con ambas imágenes
test_images = [
    {
        "name": "PS5 Setup (primera imagen)",
        "path": os.path.expanduser("~/Downloads/81HDj9fPVRL._SL1500_.jpg"),
        "expected": "remove",
        "reason": "Tiene logos de juegos visibles (God of War, etc.)"
    },
    {
        "name": "PS5 Dock (segunda imagen)",
        "path": os.path.expanduser("~/Downloads/71gwc82PMqL._SL1500_.jpg"),
        "expected": "keep",
        "reason": "Solo muestra consola/control SIN logos visibles + juego Attack on Titan"
    }
]

print("=" * 80)
print("🧪 TEST: Detección ESTRICTA de Logos (solo logos VISIBLES)")
print("=" * 80)
print()

results = []

for i, test in enumerate(test_images, 1):
    print(f"\n{'━' * 80}")
    print(f"TEST {i}/{len(test_images)}: {test['name']}")
    print(f"{'━' * 80}")
    print(f"📁 Archivo: {test['path']}")
    print(f"✅ Esperado: {test['expected'].upper()}")
    print(f"📝 Razón: {test['reason']}")
    print()
    print("🧠 Analizando con prompt ESTRICTO...")

    analysis = analyze_image_strict(test['path'])

    if "error" in analysis:
        print(f"❌ ERROR: {analysis['error']}")
        results.append({"test": test['name'], "status": "ERROR"})
        continue

    print(f"\n📊 Resultado:")
    print(f"   Descripción: {analysis.get('what_i_see', 'N/A')}")
    print(f"   ¿Tiene logos visibles?: {analysis.get('has_logos', False)}")

    logos = analysis.get('logos_detected', [])
    if logos:
        print(f"\n   🏷️  Logos VISIBLES detectados ({len(logos)}):")
        for logo in logos:
            print(f"      • {logo.get('brand', 'Unknown')}")
            print(f"        Lo que VEO exactamente: {logo.get('what_exactly', 'N/A')}")
            print(f"        Ubicación: {logo.get('location', 'N/A')}")
            print(f"        Confianza: {logo.get('confidence', 0):.2f}")

    recommendation = analysis.get('recommendation', 'unknown')
    confidence = analysis.get('overall_confidence', 0)

    print(f"\n   Confianza general: {confidence:.2f}")
    print(f"   Decisión: {recommendation.upper()}")

    is_correct = (recommendation == test['expected'])

    if is_correct:
        print(f"\n✅ CORRECTO - Decidió {recommendation.upper()} como esperado")
    else:
        print(f"\n❌ INCORRECTO - Esperaba {test['expected'].upper()} pero obtuvo {recommendation.upper()}")

    results.append({
        "test": test['name'],
        "status": "PASS" if is_correct else "FAIL",
        "expected": test['expected'],
        "got": recommendation,
        "logos": [l.get('brand') for l in logos]
    })

# Resumen
print("\n" + "=" * 80)
print("📊 RESUMEN")
print("=" * 80)

passed = sum(1 for r in results if r.get('status') == 'PASS')
failed = sum(1 for r in results if r.get('status') == 'FAIL')

print(f"\n✅ Pasados: {passed}/{len(results)}")
print(f"❌ Fallados: {failed}/{len(results)}")

accuracy = (passed / len(results) * 100) if results else 0
print(f"\n🎯 Precisión: {accuracy:.1f}%")

if failed > 0:
    print(f"\n❌ Tests fallados:")
    for r in results:
        if r.get('status') == 'FAIL':
            print(f"   • {r['test']}")
            print(f"     Esperaba: {r['expected']} | Obtuvo: {r['got']}")

print()
