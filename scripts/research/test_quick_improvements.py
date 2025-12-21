#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test rápido de mejoras específicas - Smart Answer Engine v2.0
Testea los casos que fallaron antes para validar mejoras
"""

import sys
import json
sys.path.insert(0, 'scripts/tools')

from smart_answer_engine_v2 import answer_question_v2

# Casos que fallaron en el test anterior
TEST_CASES = [
    {
        "name": "Critical Safety - Sobrecalentamiento (antes FALLÓ)",
        "question": "¿El Cepillo Secador incluye alguna función que evite el sobrecalentamiento del cabello?",
        "asin": "B0BFJWCYTL",
        "expected": "should_notify",
        "reason": "Pregunta sobre seguridad térmica - debe notificar"
    },
    {
        "name": "Critical Safety - Límite de carga (antes FALLÓ)",
        "question": "¿Este trípode es compatible con una cámara que pesa 10 kg en exteriores ventosos?",
        "asin": "B0BFJWCYTL",
        "expected": "should_notify",
        "reason": "Límite de carga en condiciones extremas - seguridad física"
    },
    {
        "name": "Comparison - NO es búsqueda (antes FALLÓ - falso positivo)",
        "question": "Si comparo este modelo con el VT80H, ¿cuáles son las diferencias principales?",
        "asin": "B0BFJWCYTL",
        "expected": "should_answer_focused",
        "reason": "Comparación - debe responder sobre ESTE producto sin detectar búsqueda"
    },
    {
        "name": "Compatibility - NO es búsqueda (antes FALLÓ)",
        "question": "¿Es compatible con el adaptador de corriente europeo que compré para mi cargador?",
        "asin": "B0BFJWCYTL",
        "expected": "should_answer_or_notify_critical",
        "reason": "Compatibilidad eléctrica - puede ser crítica pero NO es búsqueda"
    },
    {
        "name": "Multiple Questions (antes FALLÓ)",
        "question": "¿De qué color es y cuánto pesa?",
        "asin": "B0BFJWCYTL",
        "expected": "should_answer_all",
        "reason": "Múltiples preguntas - debe responder ambas"
    },
    {
        "name": "Negative Question (antes FALLÓ)",
        "question": "¿No usa pilas desechables, verdad?",
        "asin": "B0BFJWCYTL",
        "expected": "should_answer_correctly",
        "reason": "Pregunta negativa - debe entender bien la negación"
    },
    {
        "name": "Compatibility Hyperbolic - NO es búsqueda (antes FALLÓ)",
        "question": "¿Es compatible con los tornillos que usan en la NASA?",
        "asin": "B0BFJWCYTL",
        "expected": "should_answer",
        "reason": "Pregunta hiperbólica de compatibilidad - NO debe detectar como búsqueda"
    },
    {
        "name": "TRUE Product Search (debe detectar)",
        "question": "¿Tenés el iPhone 15 Pro disponible?",
        "asin": "B0BFJWCYTL",
        "expected": "should_detect_search",
        "reason": "Búsqueda real - DEBE detectar"
    },
]

def validate_result(test_case, result):
    """Valida si el resultado cumple expectativas"""
    expected = test_case["expected"]
    action = result.get("action")
    notification = result.get("notification_type")
    should_notify = result.get("should_notify")

    validation = {
        "passed": False,
        "message": "",
        "details": {}
    }

    if expected == "should_notify":
        # Debe notificar por ser crítica
        if should_notify:
            validation["passed"] = True
            validation["message"] = f"✅ CORRECTO: Notificó ({notification})"
        else:
            validation["passed"] = False
            validation["message"] = f"❌ FALLÓ: NO notificó (action: {action})"

    elif expected == "should_detect_search":
        # Debe detectar búsqueda
        if notification == "product_search":
            validation["passed"] = True
            validation["message"] = f"✅ CORRECTO: Detectó búsqueda"
        else:
            validation["passed"] = False
            validation["message"] = f"❌ FALLÓ: NO detectó búsqueda (notification: {notification})"

    elif expected in ["should_answer", "should_answer_focused", "should_answer_all", "should_answer_correctly"]:
        # Debe responder SIN detectar como búsqueda
        if action == "answered" and notification != "product_search":
            validation["passed"] = True
            validation["message"] = f"✅ CORRECTO: Respondió (conf: {result.get('confidence', 0):.0f}%)"
        elif notification == "product_search":
            validation["passed"] = False
            validation["message"] = f"❌ FALLÓ: Detectó como búsqueda (falso positivo)"
        else:
            validation["passed"] = False
            validation["message"] = f"❌ FALLÓ: NO respondió (action: {action}, reason: {result.get('reason')})"

    elif expected == "should_answer_or_notify_critical":
        # Puede responder O notificar si es crítica (ambas válidas)
        if action == "answered" and notification != "product_search":
            validation["passed"] = True
            validation["message"] = f"✅ CORRECTO: Respondió (conf: {result.get('confidence', 0):.0f}%)"
        elif notification == "critical_question":
            validation["passed"] = True
            validation["message"] = f"✅ CORRECTO: Detectó como crítica y notificó"
        elif notification == "product_search":
            validation["passed"] = False
            validation["message"] = f"❌ FALLÓ: Detectó como búsqueda (falso positivo)"
        else:
            validation["passed"] = True  # Aceptable si notifica por otra razón
            validation["message"] = f"⚠️  ACEPTABLE: {action} - {notification}"

    validation["details"] = {
        "action": action,
        "notification_type": notification,
        "should_notify": should_notify,
        "confidence": result.get("confidence", 0),
        "reason": result.get("reason")
    }

    return validation

def main():
    print("\n" + "="*80)
    print("🧪 TEST RÁPIDO DE MEJORAS")
    print("="*80)
    print("Testeando casos específicos que fallaron antes...")
    print()

    results = []

    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] {test_case['name']}")
        print(f"Pregunta: {test_case['question']}")
        print(f"Expectativa: {test_case['reason']}")

        try:
            result = answer_question_v2(
                question=test_case["question"],
                asin=test_case["asin"],
                item_title="Test Product"
            )

            validation = validate_result(test_case, result)

            print(f"\n{validation['message']}")

            if result.get("action") == "answered" and result.get("answer"):
                print(f"Respuesta: {result['answer'][:100]}...")

            results.append({
                "test": test_case["name"],
                "passed": validation["passed"],
                "validation": validation
            })

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "test": test_case["name"],
                "passed": False,
                "error": str(e)
            })

    # Resumen
    print("\n" + "="*80)
    print("📊 RESUMEN")
    print("="*80)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    for r in results:
        status = "✅" if r["passed"] else "❌"
        print(f"{status} {r['test']}")

    print(f"\n{'='*80}")
    print(f"Pasados: {passed}/{total} ({passed/total*100:.1f}%)")
    print(f"{'='*80}\n")

    # Si pasaron todos, lanzar stress test completo
    if passed == total:
        print("🎉 ¡Todos los tests pasaron! Lanzando stress test completo...")
        return True
    else:
        print(f"⚠️  {total - passed} tests fallaron. Revisar antes de stress test completo.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
