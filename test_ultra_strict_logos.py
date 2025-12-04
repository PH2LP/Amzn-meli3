#!/usr/bin/env python3
"""
Test ULTRA ESTRICTO:
- Ignorar texto de compatibilidad ("for", "compatible with")
- Ignorar logos en el FONDO que no son parte del producto principal
- Solo detectar logos GRANDES y CLAROS en el producto mismo
"""

import os
import json
import base64
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_image_ultra_strict(image_path):
    """Análisis ULTRA ESTRICTO"""

    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')

    prompt = """Analyze this product image for trademarked brand logos.

⚠️ ULTRA STRICT RULES:

✅ DETECT THESE (report as logos):
- Apple logo symbol (🍎) on the actual product
- PlayStation logo/symbol on the console/controller itself
- Xbox logo on hardware
- Samsung logo text on device
- Brand text directly printed/embossed on the main product
- Game title logos IF they are the main focus of the image

❌ IGNORE THESE (do NOT report):
- Compatibility text: "for PS5", "for iPad", "compatible with"
- Product shapes without visible branding
- Small background items (game boxes, devices in background)
- Generic connectors, ports, cables
- Text descriptions or specifications
- Packaging text in background

FOCUS: Only report logos that are LARGE, CLEAR, and on the MAIN product being sold.

Background items (like game boxes on a shelf) should be IGNORED unless they dominate the image.

Respond in JSON:
{
  "has_logos": true/false,
  "logos_detected": [
    {
      "brand": "brand name",
      "type": "symbol" or "text",
      "location": "on main product" or "background",
      "size": "large" or "small",
      "what_exactly": "what you see",
      "should_flag": true/false,
      "confidence": 0.0-1.0
    }
  ],
  "overall_confidence": 0.0-1.0,
  "recommendation": "keep" or "remove",
  "reasoning": "why you decided this"
}

Only recommend "remove" if should_flag=true for ANY logo with confidence >= 0.75"""

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
            max_tokens=1000,
            temperature=0.1
        )

        result_text = response.choices[0].message.content.strip()

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
        "name": "PS5 Setup con juegos",
        "path": os.path.expanduser("~/Downloads/81HDj9fPVRL._SL1500_.jpg"),
        "expected": "remove",
        "reason": "Cajas de juegos con logos son foco principal"
    },
    {
        "name": "PS5 Dock blanco",
        "path": os.path.expanduser("~/Downloads/71gwc82PMqL._SL1500_.jpg"),
        "expected": "keep",
        "reason": "'For PS5' es texto compatibilidad, juegos son background pequeño"
    }
]

print("=" * 80)
print("🧪 TEST: Detección ULTRA ESTRICTA de Logos")
print("=" * 80)
print()

results = []

for i, test in enumerate(test_images, 1):
    print(f"\n{'━' * 80}")
    print(f"TEST {i}/{len(test_images)}: {test['name']}")
    print(f"{'━' * 80}")
    print(f"📁 {os.path.basename(test['path'])}")
    print(f"✅ Esperado: {test['expected'].upper()}")
    print(f"📝 {test['reason']}")
    print()

    analysis = analyze_image_ultra_strict(test['path'])

    if "error" in analysis:
        print(f"❌ ERROR: {analysis['error']}")
        results.append({"test": test['name'], "status": "ERROR"})
        continue

    print(f"📊 Análisis:")
    print(f"   Razonamiento: {analysis.get('reasoning', 'N/A')}")
    print(f"   ¿Tiene logos?: {analysis.get('has_logos', False)}")

    logos = analysis.get('logos_detected', [])
    flagged_logos = [l for l in logos if l.get('should_flag', False)]

    if logos:
        print(f"\n   Logos encontrados ({len(logos)}):")
        for logo in logos:
            flag_emoji = "🚩" if logo.get('should_flag') else "✓"
            print(f"      {flag_emoji} {logo.get('brand', 'Unknown')}")
            print(f"         Tipo: {logo.get('type', 'N/A')}")
            print(f"         Ubicación: {logo.get('location', 'N/A')}")
            print(f"         Tamaño: {logo.get('size', 'N/A')}")
            print(f"         ¿Flagear?: {logo.get('should_flag', False)}")
            print(f"         Confianza: {logo.get('confidence', 0):.2f}")

    recommendation = analysis.get('recommendation', 'unknown')
    confidence = analysis.get('overall_confidence', 0)

    print(f"\n   Confianza: {confidence:.2f}")
    print(f"   Decisión: {recommendation.upper()}")

    is_correct = (recommendation == test['expected'])

    if is_correct:
        print(f"\n✅ CORRECTO")
    else:
        print(f"\n❌ INCORRECTO")
        print(f"   Esperaba: {test['expected'].upper()}")
        print(f"   Obtuvo: {recommendation.upper()}")

    results.append({
        "test": test['name'],
        "status": "PASS" if is_correct else "FAIL",
        "expected": test['expected'],
        "got": recommendation,
        "flagged_logos": len(flagged_logos)
    })

# Resumen
print("\n" + "=" * 80)
print("📊 RESUMEN")
print("=" * 80)

passed = sum(1 for r in results if r.get('status') == 'PASS')
failed = sum(1 for r in results if r.get('status') == 'FAIL')

print(f"\n✅ Correctos: {passed}/{len(results)}")
print(f"❌ Incorrectos: {failed}/{len(results)}")

accuracy = (passed / len(results) * 100) if results else 0
print(f"\n🎯 Precisión: {accuracy:.1f}%")

if accuracy >= 90:
    print("\n✅ Sistema APROBADO para producción")
elif accuracy >= 70:
    print("\n⚠️  Sistema necesita ajustes menores")
else:
    print("\n❌ Sistema necesita rediseño")

print()
