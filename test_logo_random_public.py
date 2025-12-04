#!/usr/bin/env python3
"""
Test con imágenes RANDOM públicas para verificar falsos positivos
"""

import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_image_simple(image_url, product_title="Accesorio genérico"):
    """Análisis simple"""

    prompt = """Analyze this product image.

Does it contain ANY of these brand logos or trademarks:
- Apple logo (apple symbol) or iPad/iPhone/Mac branding
- Samsung logo or Galaxy branding
- PlayStation, Xbox, Nintendo logos
- Game logos (FIFA, Spider-Man, GTA, etc.)
- App icons (Instagram, WhatsApp, Facebook, etc.)
- Any other major brand logos

BE STRICT:
- DO NOT flag generic text or compatibility descriptions
- DO NOT flag generic USB connectors or ports
- DO NOT flag generic shapes that aren't actual logos
- ONLY flag if you clearly see an actual trademarked logo

Respond in JSON:
{
  "has_logos": true/false,
  "logos_found": ["list of brands"],
  "confidence": 0.0-1.0,
  "recommendation": "keep" or "remove",
  "what_i_see": "description"
}

Only recommend "remove" if confidence > 0.6"""

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
            return {"error": "No JSON", "raw": result_text[:200]}

    except Exception as e:
        return {"error": str(e)}


# Test cases con URLs públicas de Unsplash/Wikipedia/etc
test_cases = [
    {
        "name": "✅ Cable USB genérico (SIN logos)",
        "url": "https://images.unsplash.com/photo-1556656793-08538906a9f8?w=800",
        "product": "Cable USB",
        "expected": "keep",
        "reason": "Cable genérico sin marcas"
    },
    {
        "name": "✅ Teclado mecánico genérico (SIN logos)",
        "url": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=800",
        "product": "Teclado mecánico",
        "expected": "keep",
        "reason": "Teclado sin branding visible"
    },
    {
        "name": "❌ MacBook con logo Apple (CON logo)",
        "url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=800",
        "product": "Funda para laptop",
        "expected": "remove",
        "reason": "MacBook con logo Apple visible"
    },
    {
        "name": "✅ Audífonos genéricos (SIN logos)",
        "url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800",
        "product": "Audífonos",
        "expected": "keep",
        "reason": "Audífonos sin marca visible"
    },
    {
        "name": "❌ iPhone con logo Apple (CON logo)",
        "url": "https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5?w=800",
        "product": "Funda para iPhone",
        "expected": "remove",
        "reason": "iPhone con logo Apple"
    },
    {
        "name": "✅ Mouse gaming genérico (SIN logos)",
        "url": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=800",
        "product": "Mouse",
        "expected": "keep",
        "reason": "Mouse sin marcas evidentes"
    },
    {
        "name": "✅ Fondo blanco vacío (SIN logos)",
        "url": "https://images.unsplash.com/photo-1557682250-33bd709cbe85?w=800",
        "product": "Producto genérico",
        "expected": "keep",
        "reason": "Fondo blanco sin nada"
    },
    {
        "name": "✅ Producto con texto genérico (SIN logos)",
        "url": "https://images.unsplash.com/photo-1531297484001-80022131f5a1?w=800",
        "product": "Tech gadget",
        "expected": "keep",
        "reason": "Tech genérico sin branding"
    }
]

print("=" * 80)
print("🧪 TEST: Imágenes RANDOM Públicas - Verificación de Falsos Positivos")
print("=" * 80)
print(f"\nAnalizando {len(test_cases)} imágenes públicas...")
print()

results = []

for i, test in enumerate(test_cases, 1):
    print(f"\n{'━' * 80}")
    print(f"TEST {i}/{len(test_cases)}: {test['name']}")
    print(f"{'━' * 80}")
    print(f"📦 Producto: {test['product']}")
    print(f"🔗 URL: {test['url'][:70]}...")
    print(f"✅ Esperado: {test['expected'].upper()}")
    print()
    print("🧠 Analizando...")

    analysis = analyze_image_simple(test['url'], test['product'])

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
    logos = analysis.get('logos_found', [])
    what_i_see = analysis.get('what_i_see', 'N/A')
    confidence = analysis.get('confidence', 0)

    print(f"\n📊 Resultado:")
    print(f"   Lo que veo: {what_i_see}")
    print(f"   ¿Tiene logos?: {analysis.get('has_logos', False)}")

    if logos:
        print(f"   Logos detectados: {', '.join(logos)}")
        print(f"   Confianza: {confidence:.2f}")

    print(f"   Decisión: {got.upper()}")

    # Verificar si es correcto
    is_correct = (got == test['expected'])

    if is_correct:
        print(f"\n✅ CORRECTO - Decidió {got.upper()} como esperado")
    else:
        print(f"\n❌ INCORRECTO - Esperaba {test['expected'].upper()} pero obtuvo {got.upper()}")
        if got == 'remove' and test['expected'] == 'keep':
            print(f"   ⚠️  FALSO POSITIVO - Eliminó imagen sin logos")
        elif got == 'keep' and test['expected'] == 'remove':
            print(f"   ⚠️  FALSO NEGATIVO - No detectó logos que sí había")

    results.append({
        "test": test['name'],
        "status": "PASS" if is_correct else "FAIL",
        "expected": test['expected'],
        "got": got,
        "logos": logos,
        "confidence": confidence,
        "what_i_see": what_i_see
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

# Análisis de falsos positivos/negativos
false_positives = [r for r in results if r['status'] == 'FAIL' and r['expected'] == 'keep' and r['got'] == 'remove']
false_negatives = [r for r in results if r['status'] == 'FAIL' and r['expected'] == 'remove' and r['got'] == 'keep']

if false_positives:
    print(f"\n⚠️  FALSOS POSITIVOS ({len(false_positives)}):")
    for r in false_positives:
        print(f"   • {r['test']}")
        print(f"     Eliminó sin razón - Logos: {', '.join(r['logos']) if r['logos'] else 'ninguno'}")

if false_negatives:
    print(f"\n⚠️  FALSOS NEGATIVOS ({len(false_negatives)}):")
    for r in false_negatives:
        print(f"   • {r['test']}")
        print(f"     No detectó logos que debía detectar")

if failed > 0:
    print(f"\n❌ Tests fallados:")
    for r in results:
        if r['status'] == 'FAIL':
            print(f"   • {r['test']}")
            print(f"     Esperaba: {r['expected']} | Obtuvo: {r['got']}")

print("\n" + "=" * 80)

if accuracy >= 85:
    print("✅ SISTEMA APROBADO - Precisión excelente (≥85%)")
    print(f"   Falsos positivos: {len(false_positives)}")
    print(f"   Falsos negativos: {len(false_negatives)}")
elif accuracy >= 70:
    print("⚠️  SISTEMA ACEPTABLE - Precisión buena (70-84%)")
    print("   Considerar ajustar umbral de confianza")
else:
    print("❌ SISTEMA REQUIERE AJUSTES - Precisión baja (<70%)")

print()
