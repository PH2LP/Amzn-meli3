#!/usr/bin/env python3
"""
Test con producto REAL del pipeline: Teclado iPad (B0D9WB36MF)
Validar sistema ULTRA ESTRICTO con imágenes reales
"""

import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Cargar producto real
with open('storage/logs/publish_ready/B0D9WB36MF_mini_ml.json') as f:
    product_data = json.load(f)

images = product_data['images']
title = product_data['title_ai']

def analyze_image_ultra_strict(image_url):
    """Análisis ULTRA ESTRICTO (mismo prompt validado)"""

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
                            "image_url": {"url": image_url, "detail": "high"}
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
        return {"error": "No JSON"}

    except Exception as e:
        return {"error": str(e)}


print("=" * 80)
print("🧪 TEST: Producto Real del Pipeline (Teclado iPad)")
print("=" * 80)
print(f"\n📦 Producto: {title}")
print(f"🆔 ASIN: B0D9WB36MF")
print(f"🖼️  Total imágenes: {len(images)}")
print()

results = []
keep_count = 0
remove_count = 0

for i, img in enumerate(images[:6], 1):  # Primeras 6
    print(f"\n{'━' * 80}")
    print(f"IMAGEN {i}/6")
    print(f"{'━' * 80}")
    print(f"🔗 {img['url'][:60]}...")
    print()

    analysis = analyze_image_ultra_strict(img['url'])

    if "error" in analysis:
        print(f"❌ ERROR: {analysis['error']}")
        continue

    reasoning = analysis.get('reasoning', 'N/A')
    has_logos = analysis.get('has_logos', False)
    recommendation = analysis.get('recommendation', 'unknown')
    confidence = analysis.get('overall_confidence', 0)

    print(f"📊 Razonamiento:")
    print(f"   {reasoning}")
    print(f"\n   ¿Tiene logos?: {has_logos}")

    logos = analysis.get('logos_detected', [])
    flagged = [l for l in logos if l.get('should_flag', False)]

    if logos:
        print(f"   Logos encontrados: {len(logos)}")
        for logo in logos:
            flag = "🚩" if logo.get('should_flag') else "✓"
            print(f"      {flag} {logo.get('brand')} ({logo.get('location')}) - Conf: {logo.get('confidence', 0):.2f}")

    print(f"\n   Confianza: {confidence:.2f}")

    if recommendation == 'keep':
        print(f"   ✅ MANTENER")
        keep_count += 1
    else:
        print(f"   ❌ ELIMINAR")
        remove_count += 1

    results.append({
        "image": i,
        "url": img['url'][:50],
        "recommendation": recommendation,
        "flagged_logos": len(flagged),
        "reasoning": reasoning
    })

# Resumen
print("\n" + "=" * 80)
print("📊 RESUMEN")
print("=" * 80)

print(f"\nImágenes analizadas: {len(results)}")
print(f"✅ MANTENER: {keep_count}")
print(f"❌ ELIMINAR: {remove_count}")

if remove_count > 0:
    print(f"\n❌ Imágenes que serían eliminadas:")
    for r in results:
        if r['recommendation'] == 'remove':
            print(f"   • Imagen {r['image']} ({r['flagged_logos']} logos)")

print(f"\n🎯 Resultado final:")
if keep_count >= 1:
    print(f"   ✅ Quedarían {keep_count} imágenes (suficiente para publicar)")
    print(f"   📊 Se eliminarían {remove_count} imágenes con logos")
else:
    print(f"   ⚠️  No quedarían imágenes - se mantendría la primera por seguridad")

print()
