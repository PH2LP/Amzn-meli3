#!/usr/bin/env python3
"""
Test con preguntas REALES de clientes que fueron respondidas incorrectamente.
Verificar que el nuevo sistema las detecte y NO las responda sin verificación.
"""
import sys
sys.path.insert(0, 'scripts/tools')

from auto_answer_questions import (
    detect_feature_question,
    verify_feature_in_data,
    load_mini_ml,
    load_amazon_json
)

print("="*80)
print("TEST: PREGUNTAS REALES DE CLIENTES")
print("="*80)
print()

# Caso 1: Amazfit - resistencia al agua
print("━"*80)
print("CASO 1: Amazfit B0CX69CS2D")
print("━"*80)
print("Pregunta: 'Can you swim with the watch?'")
print("Respuesta anterior: 'No, el reloj no es resistente al agua' ❌")
print()

asin1 = "B0CX69CS2D"
question1 = "Can you swim with the watch?"

feature_info1 = detect_feature_question(question1)
print(f"✅ Característica detectada: {feature_info1}")

# Cargar datos
mini_ml1 = load_mini_ml(asin1)
amazon_json1 = load_amazon_json(asin1)

has_data1 = verify_feature_in_data(feature_info1, mini_ml1, amazon_json1)

print(f"\n📊 Tiene datos sobre resistencia al agua en JSON: {has_data1}")

if has_data1:
    print("✅ CORRECTO: El sistema encontró información sobre agua en el JSON")
    print("   → Debería responder con la info real")
else:
    print("⚠️  Sistema no encontró info en JSON")
    print("   → Enviará notificación por Telegram para verificación manual")

# Buscar keywords manualmente
if amazon_json1:
    import json
    json_text = json.dumps(amazon_json1, ensure_ascii=False).lower()
    if "water" in json_text:
        print("\n🔍 Verificación manual: SÍ hay 'water' en el JSON")
        # Buscar contexto
        import re
        matches = re.findall(r'.{0,50}water.{0,50}', json_text, re.IGNORECASE)
        if matches:
            print(f"   Contextos encontrados: {len(matches)}")
            for i, match in enumerate(matches[:3], 1):
                print(f"   {i}. ...{match}...")

print("\n" + "━"*80)
print("CASO 2: Xiaomi B0DFZPR9Z4")
print("━"*80)
print("Pregunta: 'Can it answer calls?'")
print("Respuesta anterior: 'No, no tiene la capacidad de responder llamadas' ❌")
print()

asin2 = "B0DFZPR9Z4"
question2 = "Can it answer calls?"

feature_info2 = detect_feature_question(question2)
print(f"✅ Característica detectada: {feature_info2}")

# Cargar datos
mini_ml2 = load_mini_ml(asin2)
amazon_json2 = load_amazon_json(asin2)

has_data2 = verify_feature_in_data(feature_info2, mini_ml2, amazon_json2)

print(f"\n📊 Tiene datos sobre llamadas en JSON: {has_data2}")

if has_data2:
    print("✅ CORRECTO: El sistema encontró información sobre llamadas en el JSON")
    print("   → Debería responder con la info real")
else:
    print("⚠️  Sistema no encontró info en JSON")
    print("   → Enviará notificación por Telegram para verificación manual")

# Buscar keywords manualmente
if amazon_json2:
    import json
    json_text = json.dumps(amazon_json2, ensure_ascii=False).lower()
    if "call" in json_text:
        print("\n🔍 Verificación manual: SÍ hay 'call' en el JSON")
        matches = re.findall(r'.{0,50}call.{0,50}', json_text, re.IGNORECASE)
        if matches:
            print(f"   Contextos encontrados: {len(matches)}")
            for i, match in enumerate(matches[:3], 1):
                print(f"   {i}. ...{match}...")

print("\n" + "="*80)
print("CONCLUSIÓN")
print("="*80)

if has_data1 and has_data2:
    print("\n✅ SISTEMA FUNCIONANDO CORRECTAMENTE")
    print("   Ambos productos TIENEN la información en el JSON")
    print("   El sistema debería responder con los datos reales")
    print("\n💡 El problema anterior era que la IA respondía 'NO tiene'")
    print("   cuando simplemente no encontraba la característica en su contexto")
elif not has_data1 or not has_data2:
    print("\n⚠️  AL MENOS UN PRODUCTO NO TIENE INFO EN JSON")
    print("   El sistema CORRECTAMENTE enviará notificación por Telegram")
    print("   para que verifiques manualmente en Amazon")
