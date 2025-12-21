#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests para Smart Answer Engine v2.0
"""

import sys
import json
sys.path.insert(0, 'scripts/tools')

from smart_answer_engine_v2 import answer_question_v2

# ============================================================================
# CASOS DE PRUEBA
# ============================================================================

TEST_CASES = [
    {
        "name": "Pregunta sobre voltaje (crítica)",
        "question": "Funciona a 220v o necesita transformador?",
        "asin": "B0BFJWCYTL",
        "expected_action": "no_answer",  # Debe notificar por ser crítica
        "expected_notification": "critical_question"
    },
    {
        "name": "Pregunta sobre color (simple)",
        "question": "De qué color es?",
        "asin": "B0BFJWCYTL",
        "expected_action": "answered",  # Debe responder si tiene la info
    },
    {
        "name": "Pregunta sobre funciones",
        "question": "Qué funciones trae?",
        "asin": "B0BFJWCYTL",
        "expected_action": "answered",  # Debe listar funciones
    },
    {
        "name": "Búsqueda de otro producto",
        "question": "Tenés el iPhone 15 Pro?",
        "asin": "B0BFJWCYTL",
        "expected_action": "no_answer",  # Debe detectar búsqueda
        "expected_notification": "product_search"
    },
    {
        "name": "Pregunta sobre baterías",
        "question": "Usa pilas AA o AAA?",
        "asin": "B0BFJWCYTL",
        "expected_action": "answered",  # Debe responder positivamente si tiene recargable
    },
]


def run_test(test_case):
    """Ejecuta un caso de prueba"""
    print("\n" + "="*80)
    print(f"TEST: {test_case['name']}")
    print("="*80)
    print(f"Pregunta: {test_case['question']}")
    print()

    result = answer_question_v2(
        question=test_case["question"],
        asin=test_case["asin"],
        item_title="Test Product"
    )

    print("\n📊 RESULTADO:")
    print(f"  Action: {result['action']}")
    print(f"  Confidence: {result['confidence']:.1f}%")
    print(f"  Should notify: {result['should_notify']}")
    if result['should_notify']:
        print(f"  Notification type: {result['notification_type']}")

    if result['action'] == 'answered':
        print(f"\n💬 RESPUESTA:")
        print(f"  {result['answer']}")

    # Verificar expectativas
    print("\n✅ VALIDACIÓN:")
    passed = True

    if "expected_action" in test_case:
        if result["action"] == test_case["expected_action"]:
            print(f"  ✓ Action correcto: {result['action']}")
        else:
            print(f"  ✗ Action incorrecto: esperado {test_case['expected_action']}, obtenido {result['action']}")
            passed = False

    if "expected_notification" in test_case:
        if result["notification_type"] == test_case["expected_notification"]:
            print(f"  ✓ Notification type correcto: {result['notification_type']}")
        else:
            print(f"  ✗ Notification type incorrecto: esperado {test_case['expected_notification']}, obtenido {result['notification_type']}")
            passed = False

    return passed


def main():
    """Ejecuta todos los tests"""
    print("\n" + "#"*80)
    print("# SMART ANSWER ENGINE v2.0 - SUITE DE TESTS")
    print("#"*80)

    results = []

    for test_case in TEST_CASES:
        try:
            passed = run_test(test_case)
            results.append((test_case["name"], passed))
        except Exception as e:
            print(f"\n❌ ERROR EN TEST: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_case["name"], False))

    # Resumen
    print("\n" + "#"*80)
    print("# RESUMEN DE TESTS")
    print("#"*80 + "\n")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    failed = total - passed

    for name, p in results:
        status = "✅ PASSED" if p else "❌ FAILED"
        print(f"{status}: {name}")

    print(f"\n{'='*80}")
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
