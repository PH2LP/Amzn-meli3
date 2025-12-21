#!/usr/bin/env python3
"""
Test para verificar que el auto-answer detecta preguntas técnicas críticas
y NO las responde automáticamente
"""
import sys
sys.path.insert(0, 'scripts/tools')

from auto_answer_questions import answer_question, is_critical_technical_question

# Casos de prueba
test_questions = [
    # Preguntas críticas (NO deben responderse)
    {
        "question": "does it need a transformer from 220 to 110, how many watts?",
        "should_detect": True,
        "description": "Pregunta sobre transformador y watts"
    },
    {
        "question": "Necesito transformador de 220 a 110?",
        "should_detect": True,
        "description": "Pregunta sobre transformador en español"
    },
    {
        "question": "Cuál es el voltaje de entrada?",
        "should_detect": True,
        "description": "Pregunta sobre voltaje"
    },
    {
        "question": "Se puede conectar a 220v o necesita 110v?",
        "should_detect": True,
        "description": "Compatibilidad eléctrica"
    },
    {
        "question": "Cuántos watts consume?",
        "should_detect": True,
        "description": "Consumo en watts"
    },

    # Preguntas normales (SÍ pueden responderse)
    {
        "question": "De qué color es?",
        "should_detect": False,
        "description": "Pregunta sobre color"
    },
    {
        "question": "Cuánto tiempo dura la batería?",
        "should_detect": False,
        "description": "Duración de batería (no es crítica)"
    },
    {
        "question": "Es original?",
        "should_detect": False,
        "description": "Pregunta sobre autenticidad"
    }
]

print("="*80)
print("TEST: DETECCIÓN DE PREGUNTAS TÉCNICAS CRÍTICAS")
print("="*80)
print()

passed = 0
failed = 0

for i, test in enumerate(test_questions, 1):
    question = test["question"]
    expected = test["should_detect"]
    description = test["description"]

    is_critical = is_critical_technical_question(question)

    status = "✅ PASS" if is_critical == expected else "❌ FAIL"
    if is_critical == expected:
        passed += 1
    else:
        failed += 1

    print(f"Test {i}: {description}")
    print(f"  Pregunta: '{question}'")
    print(f"  Esperado: {'CRÍTICA' if expected else 'NORMAL'}")
    print(f"  Detectado: {'CRÍTICA' if is_critical else 'NORMAL'}")
    print(f"  {status}")
    print()

print("="*80)
print(f"RESULTADO: {passed} passed, {failed} failed")
print("="*80)

# Test con ASIN real
if passed == len(test_questions):
    print("\n" + "="*80)
    print("TEST: Respuesta completa con pregunta crítica")
    print("="*80)
    print()

    result = answer_question(
        asin="B0B89C8H4Q",
        question="does it need a transformer from 220 to 110, how many watts?",
        question_translated=None,
        item_title="Robot Aspiradora Shark",
        customer_nickname="test_user",
        site_id="MLM",
        question_id="12345678"
    )

    print(f"\nResultado:")
    print(f"  Método: {result['method']}")
    print(f"  Respuesta: {result['answer']}")
    print(f"  Tokens: {result['tokens_used']}")

    if result['method'] == 'critical_technical_no_answer' and result['answer'] is None:
        print("\n✅ ÉXITO: Pregunta crítica detectada y NO respondida")
        print("   Se debe haber enviado notificación por Telegram")
    else:
        print("\n❌ FALLO: La pregunta crítica fue respondida automáticamente")
