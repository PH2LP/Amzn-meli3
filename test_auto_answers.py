#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para el sistema de respuestas automáticas.
Muestra ejemplos de respuestas genéricas y con IA.
"""

from auto_answer_questions import answer_question

# ASIN de prueba (uno de los que están en storage)
TEST_ASIN = "B0BRNY9HZB"

# Preguntas de prueba
test_questions = [
    # Preguntas GENÉRICAS (deberían responderse con 0 tokens)
    "¿Cuánto demora el envío?",
    "¿Tiene stock disponible?",
    "¿Es original o es copia?",
    "¿Dan factura?",
    "¿Tiene impuestos de aduana?",

    # Preguntas ESPECÍFICAS (deberían usar IA)
    "¿Qué colores tiene disponibles?",
    "¿Es compatible con iPhone 13?",
    "¿Cuál es el material del producto?",
]

print("=" * 100)
print("🧪 PRUEBA DEL SISTEMA DE RESPUESTAS AUTOMÁTICAS")
print("=" * 100)
print(f"ASIN de prueba: {TEST_ASIN}")
print()

total_generic = 0
total_ai = 0
total_tokens = 0
total_cost = 0.0

for i, question in enumerate(test_questions, 1):
    print(f"\n{'=' * 100}")
    print(f"PRUEBA #{i}")
    print(f"{'=' * 100}")
    print(f"❓ PREGUNTA: \"{question}\"")
    print()

    # Generar respuesta
    result = answer_question(TEST_ASIN, question)

    # Contar estadísticas
    if result['method'] == 'generic_question':
        total_generic += 1
    elif result['method'].startswith('ai_'):
        total_ai += 1

    total_tokens += result['tokens_used']
    total_cost += result['cost_usd']

    # Mostrar resultado
    print(f"📊 MÉTODO: {result['method']}")
    print(f"🪙 TOKENS: {result['tokens_used']}")
    print(f"💰 COSTO: ${result['cost_usd']:.6f} USD")
    print()
    print("📝 RESPUESTA COMPLETA:")
    print("-" * 100)
    print(result['answer'])
    print("-" * 100)

# Resumen final
print(f"\n\n{'=' * 100}")
print("📊 RESUMEN FINAL")
print(f"{'=' * 100}")
print(f"Total de preguntas: {len(test_questions)}")
print(f"Respuestas genéricas (0 tokens): {total_generic}")
print(f"Respuestas con IA: {total_ai}")
print(f"Tokens totales usados: {total_tokens}")
print(f"Costo total: ${total_cost:.6f} USD")
print()

# Calcular ahorro
if total_generic > 0:
    tokens_saved = total_generic * 120  # Asumiendo 120 tokens por respuesta con IA
    cost_saved = tokens_saved * 0.00000075
    print(f"💰 AHORRO:")
    print(f"   Tokens ahorrados: {tokens_saved} (gracias a respuestas genéricas)")
    print(f"   Dinero ahorrado: ${cost_saved:.6f} USD")
    print()

print("✅ Prueba completada")
