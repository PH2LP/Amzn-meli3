#!/usr/bin/env python3
"""
Test con URLs de diferentes marcas y productos genéricos REALES
"""

import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_image_simple(image_url):
    prompt = """Analyze this image.

List ALL brand logos/trademarks you can see:
- Hardware brands: Apple, Samsung, Sony, Nintendo, Microsoft, etc.
- Software/Games: FIFA, Spider-Man, Instagram, etc.
- ANY other recognizable brand

Respond in JSON:
{
  "logos_found": ["brand1", "brand2", ...],
  "confidence": 0.0-1.0,
  "recommendation": "keep" or "remove",
  "description": "what you see"
}

If ANY logo detected with confidence > 0.6 → "remove"
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}}
                ]
            }],
            max_tokens=400,
            temperature=0.1
        )

        import re
        result_text = response.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return {"error": "No JSON"}
    except Exception as e:
        return {"error": str(e)}


# URLs de productos VERDADERAMENTE genéricos o de diferentes marcas
test_cases = [
    {
        "name": "Cables simples sin marca",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/USB_Type-C_Receptacle_Pinout.svg/800px-USB_Type-C_Receptacle_Pinout.svg.png",
        "should_keep": True
    },
    {
        "name": "Teclado mecánico sin branding",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/45/QWERTY_keyboard.jpg/800px-QWERTY_keyboard.jpg",
        "should_keep": True
    },
    {
        "name": "Mouse genérico",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/22/3-Tastenmaus_Microsoft.jpg/800px-3-Tastenmaus_Microsoft.jpg",
        "should_keep": False  # Tiene Microsoft
    },
    {
        "name": "PlayStation 5 console (logo visible)",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/PlayStation_5_and_DualSense_with_transparent_background.png/800px-PlayStation_5_and_DualSense_with_transparent_background.png",
        "should_keep": False  # PlayStation
    },
    {
        "name": "Nintendo Switch (logo visible)",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f2/Nintendo_Switch_Logo.svg/800px-Nintendo_Switch_Logo.svg.png",
        "should_keep": False  # Nintendo logo
    },
    {
        "name": "Funda genérica sin marca",
        "url": "https://images.unsplash.com/photo-1601784551446-20c9e07cdbdb?w=800",
        "should_keep": True
    }
]

print("=" * 80)
print("🧪 TEST: Detección de Logos - Diferentes Marcas")
print("=" * 80)
print()

results = []

for i, test in enumerate(test_cases, 1):
    print(f"\n{'━' * 80}")
    print(f"TEST {i}/{len(test_cases)}: {test['name']}")
    print(f"{'━' * 80}")
    print(f"🔗 {test['url'][:70]}...")
    print(f"✅ Debería: {'MANTENER' if test['should_keep'] else 'ELIMINAR'}")
    print()

    analysis = analyze_image_simple(test['url'])

    if "error" in analysis:
        print(f"❌ ERROR: {analysis['error'][:100]}")
        continue

    logos = analysis.get('logos_found', [])
    desc = analysis.get('description', '')
    rec = analysis.get('recommendation', 'unknown')
    conf = analysis.get('confidence', 0)

    print(f"📊 Resultado:")
    print(f"   {desc}")
    print(f"   Logos: {', '.join(logos) if logos else 'Ninguno'}")
    print(f"   Confianza: {conf:.2f}")
    print(f"   Decisión: {rec.upper()}")

    is_correct = (rec == 'keep' and test['should_keep']) or (rec == 'remove' and not test['should_keep'])

    if is_correct:
        print(f"\n✅ CORRECTO")
    else:
        print(f"\n❌ INCORRECTO")

    results.append({
        "name": test['name'],
        "correct": is_correct,
        "logos": logos,
        "recommendation": rec
    })

# Resumen
print("\n" + "=" * 80)
print("📊 RESUMEN")
print("=" * 80)

correct = sum(1 for r in results if r['correct'])
print(f"\n✅ Correctos: {correct}/{len(results)}")
print(f"🎯 Precisión: {correct/len(results)*100:.1f}%")

print("\n📋 Detalle:")
for r in results:
    status = "✅" if r['correct'] else "❌"
    print(f"{status} {r['name']}")
    if r['logos']:
        print(f"   Logos: {', '.join(r['logos'])}")

print()
