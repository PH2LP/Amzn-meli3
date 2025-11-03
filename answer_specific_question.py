#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para responder una pregunta específica si conoces el question_id.
Útil cuando el token no tiene permisos para buscar preguntas automáticamente.
"""

import sys
from auto_answer_questions import answer_question, post_answer_to_ml, get_item_asin

def answer_specific_question(question_id, question_text, item_id):
    """
    Responde una pregunta específica.

    Args:
        question_id: ID de la pregunta en MercadoLibre
        question_text: Texto de la pregunta
        item_id: ID del item (puede ser None si tienes ASIN)
    """
    print("=" * 80)
    print(f"📩 Respondiendo pregunta #{question_id}")
    print("=" * 80)
    print(f"Pregunta: {question_text}")
    print()

    # Si tenemos item_id, obtener ASIN
    if item_id:
        print(f"Item ID: {item_id}")
        asin = get_item_asin(item_id)
        if not asin:
            print("❌ No se pudo obtener ASIN del item")
            return False
        print(f"ASIN: {asin}")
    else:
        # Si no tenemos item_id, pedir ASIN directamente
        asin = input("Ingresa el ASIN del producto: ").strip()

    print()

    # Generar respuesta
    result = answer_question(asin, question_text)

    print(f"💬 Respuesta generada:")
    print(f"   Método: {result['method']}")
    print(f"   Tokens: {result['tokens_used']}")
    print(f"   Costo: ${result['cost_usd']:.6f} USD")
    print()
    print("📝 Texto de la respuesta:")
    print("-" * 80)
    print(result['answer'])
    print("-" * 80)
    print()

    # Confirmar antes de postear
    confirm = input("¿Postear esta respuesta en MercadoLibre? (s/n): ").strip().lower()

    if confirm == 's':
        if post_answer_to_ml(question_id, result['answer']):
            print("✅ Respuesta posteada exitosamente!")
            return True
        else:
            print("❌ Error al postear respuesta")
            return False
    else:
        print("❌ Respuesta NO posteada (cancelado por el usuario)")
        return False

if __name__ == "__main__":
    # Ejemplo de uso:
    # python3 answer_specific_question.py 1572433991 "¿Cuánto demora el envío?" MLA123456

    if len(sys.argv) >= 3:
        question_id = sys.argv[1]
        question_text = sys.argv[2]
        item_id = sys.argv[3] if len(sys.argv) > 3 else None

        answer_specific_question(question_id, question_text, item_id)
    else:
        print("=" * 80)
        print("🤖 RESPONDER PREGUNTA ESPECÍFICA")
        print("=" * 80)
        print()

        question_id = input("Ingresa el question_id: ").strip()
        question_text = input("Ingresa el texto de la pregunta: ").strip()
        item_id = input("Ingresa el item_id (o presiona Enter si tienes el ASIN): ").strip()

        if not item_id:
            item_id = None

        answer_specific_question(question_id, question_text, item_id)
