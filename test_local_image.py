#!/usr/bin/env python3
"""
Test con imagen local de Downloads
"""

import os
import json
import base64
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Leer imagen local
image_path = os.path.expanduser("~/Downloads/71gwc82PMqL._SL1500_.jpg")

print("=" * 80)
print("🧪 TEST: Análisis de Imagen Local")
print("=" * 80)
print(f"\n📁 Archivo: {image_path}")
print(f"📊 Tamaño: {os.path.getsize(image_path) / 1024:.1f} KB")
print()

# Convertir a base64
with open(image_path, "rb") as image_file:
    base64_image = base64.b64encode(image_file.read()).decode('utf-8')

print("🧠 Analizando imagen con GPT-4 Vision...")
print()

prompt = """Analyze this product image in detail.

TASK: Detect ANY visible brand logos or trademarks.

Look for:
1. Hardware brand logos: Apple (🍎), Samsung, Sony, Nintendo, Microsoft, PlayStation, Xbox, etc.
2. Software/Game logos: FIFA, Spider-Man, GTA, Call of Duty, etc.
3. App icons: Instagram, WhatsApp, Facebook, TikTok, etc.
4. Any other recognizable brand trademarks

BE STRICT but ACCURATE:
- Only report logos you can CLEARLY see
- Don't flag generic shapes or connectors
- Don't flag compatibility text (e.g., "for iPad" is OK)
- Confidence > 0.6 required to report

Respond in JSON:
{
  "has_logos": true/false,
  "logos_detected": [
    {
      "brand": "brand name",
      "location": "where in image",
      "confidence": 0.0-1.0,
      "description": "what specifically you see"
    }
  ],
  "overall_confidence": 0.0-1.0,
  "recommendation": "keep" or "remove",
  "what_i_see_in_image": "detailed description of the entire image"
}

If ANY logo detected with confidence >= 0.60, recommend "remove"."""

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
        analysis = json.loads(json_match.group(0))

        print("━" * 80)
        print("📊 RESULTADO DEL ANÁLISIS")
        print("━" * 80)
        print()

        # Descripción de la imagen
        print(f"🖼️  Descripción de la imagen:")
        print(f"   {analysis.get('what_i_see_in_image', 'N/A')}")
        print()

        # Logos detectados
        has_logos = analysis.get('has_logos', False)
        logos = analysis.get('logos_detected', [])

        if has_logos and logos:
            print(f"⚠️  LOGOS DETECTADOS ({len(logos)}):")
            for logo in logos:
                print(f"\n   🏷️  {logo.get('brand', 'Unknown')}")
                print(f"      Ubicación: {logo.get('location', 'N/A')}")
                print(f"      Confianza: {logo.get('confidence', 0):.2f}")
                print(f"      Detalle: {logo.get('description', 'N/A')}")
        else:
            print(f"✅ NO SE DETECTARON LOGOS")

        print()
        print("━" * 80)

        # Decisión final
        recommendation = analysis.get('recommendation', 'unknown')
        confidence = analysis.get('overall_confidence', 0)

        print(f"🎯 DECISIÓN FINAL:")
        print(f"   Confianza general: {confidence:.2f}")
        print(f"   Recomendación: {recommendation.upper()}")
        print()

        if recommendation == 'remove':
            print(f"   ❌ Esta imagen SERÍA ELIMINADA de la publicación")
            print(f"   Razón: Contiene logos de marcas registradas")
        else:
            print(f"   ✅ Esta imagen SE MANTENDRÍA en la publicación")
            print(f"   Razón: No contiene logos problemáticos")

        print()
        print("━" * 80)

        # Guardar resultado completo
        with open('/tmp/logo_analysis_result.json', 'w') as f:
            json.dump(analysis, f, indent=2)

        print(f"\n📄 Resultado completo guardado en: /tmp/logo_analysis_result.json")

    else:
        print(f"❌ No se pudo parsear JSON de la respuesta")
        print(f"\n📝 Respuesta raw:")
        print(result_text[:500])

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print()
