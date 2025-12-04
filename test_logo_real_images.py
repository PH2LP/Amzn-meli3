#!/usr/bin/env python3
"""
Test con imágenes REALES del producto B0D9WB36MF (Teclado iPad)
"""

import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Usar las imágenes reales del teclado iPad
with open('storage/logs/publish_ready/B0D9WB36MF_mini_ml.json') as f:
    product_data = json.load(f)

images = product_data['images']
title = product_data['title_ai']
description = product_data['description_ai'][:300]

print("=" * 80)
print("🧪 TEST: Detección de Logos en Producto Real (Teclado iPad)")
print("=" * 80)
print(f"\n📦 Producto: {title}")
print(f"📝 Descripción: {description}...")
print(f"\n🖼️  Total imágenes: {len(images)}")
print()

def analyze_image_simple(image_url):
    """Análisis simple y directo"""

    prompt = """Analyze this product image.

Does it contain ANY of these brand logos or trademarks:
- Apple logo (apple symbol)
- iPad device showing Apple branding
- iPhone device showing Apple branding
- Any other major brand logos (Samsung, Sony, Nintendo, etc.)
- Game logos or app icons

Respond in JSON:
{
  "has_logos": true/false,
  "logos_found": ["list of brands found"],
  "confidence": 0.0-1.0,
  "recommendation": "keep" or "remove",
  "what_i_see": "brief description of what's in the image"
}

If you detect ANY logo with confidence > 0.6, recommend "remove"."""

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
            max_tokens=500,
            temperature=0.1
        )

        result_text = response.choices[0].message.content.strip()

        # Extraer JSON
        import re
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        else:
            return {"error": "No JSON", "raw": result_text}

    except Exception as e:
        return {"error": str(e)}


# Analizar cada imagen
results = []

for i, img in enumerate(images[:5], 1):  # Solo primeras 5 para ahorrar
    print(f"\n{'━' * 80}")
    print(f"IMAGEN {i}/{min(5, len(images))}")
    print(f"{'━' * 80}")
    print(f"🔗 URL: {img['url'][:70]}...")
    print()
    print("🧠 Analizando...")

    analysis = analyze_image_simple(img['url'])

    if "error" in analysis:
        print(f"❌ ERROR: {analysis['error']}")
        results.append({"image": i, "status": "ERROR", "error": analysis['error']})
        continue

    print(f"\n📊 Resultado:")
    print(f"   Lo que veo: {analysis.get('what_i_see', 'N/A')}")
    print(f"   ¿Tiene logos?: {analysis.get('has_logos', 'N/A')}")

    if analysis.get('has_logos'):
        logos = analysis.get('logos_found', [])
        print(f"   Logos detectados: {', '.join(logos)}")
        print(f"   Confianza: {analysis.get('confidence', 0):.2f}")

    recommendation = analysis.get('recommendation', 'unknown')
    print(f"   Decisión: {recommendation.upper()}")

    if recommendation == 'remove':
        print(f"   ❌ Esta imagen SERÍA ELIMINADA")
    else:
        print(f"   ✅ Esta imagen se MANTENDRÍA")

    results.append({
        "image": i,
        "url": img['url'][:60],
        "recommendation": recommendation,
        "has_logos": analysis.get('has_logos', False),
        "logos": analysis.get('logos_found', []),
        "what_i_see": analysis.get('what_i_see', '')
    })

# Resumen
print("\n" + "=" * 80)
print("📊 RESUMEN")
print("=" * 80)

keep_count = sum(1 for r in results if r.get('recommendation') == 'keep')
remove_count = sum(1 for r in results if r.get('recommendation') == 'remove')
error_count = sum(1 for r in results if r.get('status') == 'ERROR')

print(f"\nImágenes analizadas: {len(results)}")
print(f"✅ MANTENER: {keep_count}")
print(f"❌ ELIMINAR: {remove_count}")
print(f"⚠️  ERRORES: {error_count}")

if remove_count > 0:
    print(f"\n❌ Imágenes que serían eliminadas:")
    for r in results:
        if r.get('recommendation') == 'remove':
            print(f"   • Imagen {r['image']}: {', '.join(r.get('logos', []))}")
            print(f"     {r.get('what_i_see', '')}")

print(f"\n🎯 Resultado:")
if keep_count >= 1:
    print(f"   ✅ Quedarían {keep_count} imágenes para publicar (suficiente)")
else:
    print(f"   ⚠️  No quedarían imágenes - se mantendría la primera por seguridad")

print()
