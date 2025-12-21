#!/usr/bin/env python3
# Test de integración Smart Answer Engine v2.0

import sys
sys.path.insert(0, 'scripts/tools')

from auto_answer_questions import answer_question

print("="*80)
print("TEST - Smart Answer Engine v2.0 con Notificaciones")
print("="*80)

# Test 1: Pregunta normal que debería responder
print("\n1️⃣  TEST: Pregunta normal (debería responder)")
print("-"*80)
result1 = answer_question(
    asin="B087J9ZB98",
    question="¿De qué material está hecho el rodillo abdominal?",
    item_title="Rodillo Abdominal Luyata",
    customer_nickname="Test User",
    site_id="MLA",
    question_id=12345
)
print(f"\nResultado:")
print(f"  Método: {result1['method']}")
print(f"  Respuesta: {result1['answer'][:100] if result1['answer'] else 'NO RESPUESTA'}...")

# Test 2: Pregunta crítica (NO debería responder, notificar)
print("\n\n2️⃣  TEST: Pregunta crítica de seguridad (NO debe responder)")
print("-"*80)
result2 = answer_question(
    asin="B0CQXRBG69",
    question="¿Es seguro usar el limpiador eléctrico en la ducha?",
    item_title="Limpiador Eléctrico MR.SIGA",
    customer_nickname="Test User",
    site_id="MLA",
    question_id=12346
)
print(f"\nResultado:")
print(f"  Método: {result2['method']}")
print(f"  Respuesta: {result2['answer'][:100] if result2['answer'] else 'NO RESPUESTA (correcto - es crítica)'}...")

# Test 3: Pregunta difícil sobre uso (debería razonar y responder)
print("\n\n3️⃣  TEST: Pregunta difícil sobre uso (debe razonar)")
print("-"*80)
result3 = answer_question(
    asin="B0FCMN3927",
    question="¿Mi abuela de 80 años puede usar esta pantalla CarPlay fácilmente?",
    item_title="Pantalla CarPlay Leadtree 11.5\"",
    customer_nickname="Test User",
    site_id="MLA",
    question_id=12347
)
print(f"\nResultado:")
print(f"  Método: {result3['method']}")
print(f"  Respuesta: {result3['answer'][:200] if result3['answer'] else 'NO RESPUESTA'}...")

print("\n" + "="*80)
print("✅ Tests completados")
print("="*80)
