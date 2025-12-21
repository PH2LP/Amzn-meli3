#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stress Test Exhaustivo para Smart Answer Engine v2.0

Genera preguntas difíciles con IA y prueba el sistema con productos reales.
Objetivo: Intentar que "pise el palito" y encontrar todos los casos extremos.
"""

import os
import sys
import json
import random
from pathlib import Path
from datetime import datetime
import openai
from dotenv import load_dotenv

sys.path.insert(0, 'scripts/tools')
from smart_answer_engine_v2 import answer_question_v2

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

CONFIG = {
    "max_products": 10,  # Número de productos a testear (más rápido)
    "questions_per_product": 3,  # Preguntas por producto
    "question_difficulty": "high",  # low, medium, high, extreme
    "enable_comparison": True,  # Comparar con sistema viejo
    "save_results": True,
    "output_dir": "test_results_stress"
}

# ============================================================================
# CARGA DE PRODUCTOS
# ============================================================================

def get_available_products(max_products=100):
    """
    Obtiene lista de productos disponibles con mini_ml.
    """
    print(f"\n📦 Buscando productos disponibles...")

    products_dir = Path("storage/logs/publish_ready")
    mini_ml_files = list(products_dir.glob("*_mini_ml.json"))

    # Limitar cantidad
    mini_ml_files = mini_ml_files[:max_products]

    products = []

    for file_path in mini_ml_files:
        asin = file_path.stem.replace("_mini_ml", "")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            products.append({
                "asin": asin,
                "title": data.get("title_ai", "")[:80],
                "brand": data.get("brand", ""),
                "category": data.get("category_name", ""),
                "data": data
            })
        except Exception as e:
            print(f"  ⚠️  Error cargando {asin}: {e}")

    print(f"  ✅ {len(products)} productos cargados")
    return products


# ============================================================================
# GENERACIÓN DE PREGUNTAS DIFÍCILES
# ============================================================================

QUESTION_TYPES = {
    "tricky_specifications": {
        "description": "Preguntas sobre specs técnicas que pueden confundir",
        "examples": [
            "¿Es compatible con Android 11 o necesita versión más nueva?",
            "¿La batería es removible o viene integrada?",
            "¿Tiene puerto USB-C o es micro USB?",
            "¿Soporta carga rápida de 65W o solo 45W?",
        ]
    },
    "comparison_questions": {
        "description": "Comparaciones difíciles entre versiones/modelos",
        "examples": [
            "¿Cuál es la diferencia entre este modelo y el Pro?",
            "¿Es la versión 2023 o 2024?",
            "¿Es el modelo internacional o nacional?",
        ]
    },
    "ambiguous_features": {
        "description": "Preguntas sobre features que pueden interpretarse mal",
        "examples": [
            "¿Tiene cámara? (en un videoportero vs smartphone)",
            "¿Usa baterías? (recargable vs desechables)",
            "¿Es resistente al agua? (splash-proof vs waterproof)",
        ]
    },
    "quantity_and_contents": {
        "description": "Preguntas sobre cantidad y contenido del paquete",
        "examples": [
            "¿Cuántos vienen en el paquete?",
            "¿Viene con cable de carga o hay que comprarlo aparte?",
            "¿Incluye adaptador para 220v?",
        ]
    },
    "compatibility_questions": {
        "description": "Compatibilidad con otros dispositivos",
        "examples": [
            "¿Funciona con iPhone 15?",
            "¿Es compatible con Windows 11?",
            "¿Sirve para PS5 o solo PS4?",
        ]
    },
    "critical_safety": {
        "description": "Preguntas de seguridad que DEBEN notificar",
        "examples": [
            "¿Funciona a 220v o necesita transformador?",
            "¿Tiene certificación ANATEL?",
            "¿Es seguro para niños menores de 3 años?",
        ]
    },
    "product_search": {
        "description": "Búsquedas de otros productos (debe detectar)",
        "examples": [
            "¿Tenés el modelo XYZ disponible?",
            "¿Vendés también auriculares Sony?",
            "¿Cuánto sale el iPhone 15 Pro?",
        ]
    },
    "multiple_questions": {
        "description": "Varias preguntas en una (debe manejar bien)",
        "examples": [
            "¿De qué color es y cuánto pesa?",
            "¿Viene con garantía y se puede devolver?",
            "¿Es original, tiene caja sellada y envío gratis?",
        ]
    },
    "negatively_framed": {
        "description": "Preguntas formuladas negativamente",
        "examples": [
            "¿No usa pilas desechables, verdad?",
            "¿No es compatible con iOS?",
            "¿No necesita instalación profesional?",
        ]
    },
    "edge_cases": {
        "description": "Casos extremos y confusos",
        "examples": [
            "Si lo uso 8 horas diarias, cuánto dura la batería?",
            "¿El color negro es mate o brillante?",
            "¿La garantía cubre daños por agua si es resistente al agua?",
        ]
    }
}


def generate_difficult_questions(product_info, num_questions=5):
    """
    Genera preguntas difíciles y realistas usando IA.
    """

    # Preparar info del producto
    product_summary = f"""
PRODUCTO: {product_info['title']}
MARCA: {product_info['brand']}
CATEGORÍA: {product_info['category']}
"""

    # Prompt para generar preguntas difíciles
    prompt = f"""Eres un cliente experto haciendo preguntas DIFÍCILES sobre productos en MercadoLibre.

{product_summary}

Genera {num_questions} preguntas REALISTAS pero DIFÍCILES que:
1. Puedan confundir a un sistema automático
2. Requieran entender el contexto del producto
3. Tengan trampas o ambigüedades
4. Sean del tipo que realmente hacen los clientes

Tipos de preguntas a incluir:
- Especificaciones técnicas confusas
- Comparaciones con otros modelos
- Características ambiguas
- Cantidad y contenidos
- Compatibilidad
- Seguridad (alguna debe requerir notificación)
- Búsqueda de otros productos (1 para testear detección)
- Múltiples preguntas en una
- Formuladas negativamente

Responde SOLO este JSON:
{{
  "questions": [
    {{
      "text": "la pregunta en español",
      "type": "tricky_specifications|comparison|ambiguous|quantity|compatibility|critical_safety|product_search|multiple|negative|edge_case",
      "difficulty": "medium|high|extreme",
      "trap": "descripción de la trampa o dificultad",
      "expected_behavior": "should_answer|should_notify|should_detect_search|should_ask_clarification"
    }},
    ...
  ]
}}

Importante:
- Al menos 1 pregunta tipo "critical_safety" (debe notificar)
- Al menos 1 pregunta tipo "product_search" (debe detectar)
- Al menos 2 preguntas muy difíciles (extreme difficulty)
- Preguntas variadas, no repetir el mismo patrón"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.8  # Más creatividad
        )

        result_text = response.choices[0].message.content.strip()

        # Parsear JSON
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
        if json_match:
            result_text = json_match.group(1)

        result = json.loads(result_text)
        return result["questions"]

    except Exception as e:
        print(f"  ⚠️  Error generando preguntas: {e}")

        # Fallback: preguntas genéricas difíciles
        return [
            {
                "text": "¿Funciona a 220v o necesita transformador?",
                "type": "critical_safety",
                "difficulty": "high",
                "trap": "Debe notificar por ser pregunta crítica eléctrica",
                "expected_behavior": "should_notify"
            },
            {
                "text": "¿Cuántos vienen en el paquete?",
                "type": "quantity",
                "difficulty": "medium",
                "trap": "Puede confundir unidad con set",
                "expected_behavior": "should_answer"
            },
            {
                "text": "¿Tenés el modelo Pro disponible?",
                "type": "product_search",
                "difficulty": "medium",
                "trap": "Debe detectar búsqueda de otro producto",
                "expected_behavior": "should_detect_search"
            },
            {
                "text": "¿De qué color es y cuánto pesa?",
                "type": "multiple",
                "difficulty": "medium",
                "trap": "Múltiples preguntas en una",
                "expected_behavior": "should_answer"
            },
            {
                "text": "¿No usa pilas desechables, verdad?",
                "type": "negative",
                "difficulty": "high",
                "trap": "Pregunta negativa que requiere respuesta positiva",
                "expected_behavior": "should_answer"
            }
        ]


# ============================================================================
# TESTING
# ============================================================================

def test_product_with_questions(product, questions):
    """
    Testea un producto con varias preguntas.
    """
    results = []

    for i, q in enumerate(questions, 1):
        print(f"\n  Pregunta {i}/{len(questions)}: {q['text'][:60]}...")

        # Ejecutar sistema v2
        try:
            result_v2 = answer_question_v2(
                question=q["text"],
                asin=product["asin"],
                item_title=product["title"]
            )

            # Analizar resultado
            analysis = analyze_result(q, result_v2)

            results.append({
                "question": q,
                "result_v2": result_v2,
                "analysis": analysis,
                "product_asin": product["asin"],
                "product_title": product["title"]
            })

            # Mostrar resultado breve
            status = "✅" if analysis["passed"] else "❌"
            print(f"    {status} {analysis['verdict']}")

        except Exception as e:
            print(f"    ❌ ERROR: {e}")
            results.append({
                "question": q,
                "result_v2": {"error": str(e)},
                "analysis": {"passed": False, "verdict": f"Error: {e}"},
                "product_asin": product["asin"],
                "product_title": product["title"]
            })

    return results


def analyze_result(question, result_v2):
    """
    Analiza si el resultado es correcto según lo esperado.
    """
    expected = question.get("expected_behavior", "should_answer")
    actual_action = result_v2.get("action", "unknown")
    notification_type = result_v2.get("notification_type")
    confidence = result_v2.get("confidence", 0)
    answer = result_v2.get("answer", "")

    analysis = {
        "passed": False,
        "verdict": "",
        "issues": [],
        "score": 0.0
    }

    # Verificar comportamiento esperado
    if expected == "should_notify":
        # Debe notificar (crítica o search)
        if result_v2.get("should_notify"):
            analysis["passed"] = True
            analysis["verdict"] = f"✓ Correctamente notificó ({notification_type})"
            analysis["score"] = 1.0
        else:
            analysis["passed"] = False
            analysis["verdict"] = "✗ NO notificó cuando debía"
            analysis["issues"].append("Debía notificar pero respondió")
            analysis["score"] = 0.0

    elif expected == "should_detect_search":
        # Debe detectar búsqueda de producto
        if notification_type == "product_search":
            analysis["passed"] = True
            analysis["verdict"] = "✓ Detectó búsqueda de producto"
            analysis["score"] = 1.0
        else:
            analysis["passed"] = False
            analysis["verdict"] = "✗ NO detectó búsqueda de producto"
            analysis["issues"].append("Debía detectar product_search")
            analysis["score"] = 0.0

    elif expected == "should_answer":
        # Debe responder
        if actual_action == "answered":
            # Verificar calidad de respuesta
            issues_found = check_answer_quality(answer, question)

            if not issues_found:
                analysis["passed"] = True
                analysis["verdict"] = f"✓ Respondió bien (conf: {confidence:.1f}%)"
                analysis["score"] = 1.0
            else:
                analysis["passed"] = False
                analysis["verdict"] = f"✗ Respondió pero con problemas"
                analysis["issues"] = issues_found
                analysis["score"] = 0.5
        else:
            analysis["passed"] = False
            analysis["verdict"] = "✗ NO respondió cuando debía"
            analysis["issues"].append(f"Acción: {actual_action}, Razón: {result_v2.get('reason')}")
            analysis["score"] = 0.0

    return analysis


def check_answer_quality(answer, question):
    """
    Verifica calidad de la respuesta.
    Detecta contradicciones, vaguedad, etc.
    """
    issues = []

    if not answer or len(answer) < 10:
        issues.append("Respuesta muy corta o vacía")

    # Detectar contradicciones obvias
    answer_lower = answer.lower()

    contradiction_patterns = [
        (r"sí.*pero\s+no", "Contradicción: Sí... pero no"),
        (r"no.*pero\s+sí", "Contradicción: No... pero sí"),
        (r"es.*no\s+es", "Contradicción: Es... no es"),
        (r"tiene.*no\s+tiene", "Contradicción: Tiene... no tiene"),
    ]

    import re
    for pattern, issue_desc in contradiction_patterns:
        if re.search(pattern, answer_lower):
            issues.append(issue_desc)

    # Detectar vaguedad
    vague_phrases = [
        "no tengo información",
        "consulta al vendedor",
        "verifica en la descripción",
        "no puedo confirmar",
        "[",  # Placeholders
        "..."
    ]

    for phrase in vague_phrases:
        if phrase in answer_lower:
            issues.append(f"Respuesta vaga: contiene '{phrase}'")

    return issues


# ============================================================================
# REPORTE
# ============================================================================

def generate_report(all_results):
    """
    Genera reporte completo de testing.
    """
    print("\n" + "="*80)
    print("📊 GENERANDO REPORTE COMPLETO")
    print("="*80)

    total_questions = len(all_results)
    passed = sum(1 for r in all_results if r["analysis"]["passed"])
    failed = total_questions - passed

    # Agrupar por tipo de error
    errors_by_type = {}
    for r in all_results:
        if not r["analysis"]["passed"]:
            issues = r["analysis"].get("issues", [])
            for issue in issues:
                errors_by_type[issue] = errors_by_type.get(issue, 0) + 1

    # Agrupar por tipo de pregunta
    by_question_type = {}
    for r in all_results:
        q_type = r["question"].get("type", "unknown")
        if q_type not in by_question_type:
            by_question_type[q_type] = {"total": 0, "passed": 0}
        by_question_type[q_type]["total"] += 1
        if r["analysis"]["passed"]:
            by_question_type[q_type]["passed"] += 1

    # Encontrar casos más problemáticos
    worst_cases = sorted(
        [r for r in all_results if not r["analysis"]["passed"]],
        key=lambda x: x["analysis"]["score"]
    )[:10]

    # Generar reporte
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_questions": total_questions,
            "passed": passed,
            "failed": failed,
            "success_rate": (passed / total_questions * 100) if total_questions > 0 else 0
        },
        "by_question_type": by_question_type,
        "errors_by_type": errors_by_type,
        "worst_cases": worst_cases,
        "all_results": all_results
    }

    # Guardar JSON
    if CONFIG["save_results"]:
        output_dir = Path(CONFIG["output_dir"])
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = output_dir / f"stress_test_{timestamp}.json"

        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Reporte guardado: {report_file}")

    # Mostrar resumen en consola
    print("\n" + "="*80)
    print("📊 RESUMEN DEL STRESS TEST")
    print("="*80)
    print(f"\nTotal de preguntas testeadas: {total_questions}")
    print(f"✅ Pasadas: {passed} ({passed/total_questions*100:.1f}%)")
    print(f"❌ Falladas: {failed} ({failed/total_questions*100:.1f}%)")

    print("\n" + "-"*80)
    print("📈 RENDIMIENTO POR TIPO DE PREGUNTA")
    print("-"*80)

    for q_type, stats in sorted(by_question_type.items(), key=lambda x: x[1]["passed"]/x[1]["total"] if x[1]["total"] > 0 else 0):
        total = stats["total"]
        passed_type = stats["passed"]
        rate = (passed_type / total * 100) if total > 0 else 0
        print(f"{q_type:25} {passed_type:3}/{total:3} ({rate:5.1f}%)")

    if errors_by_type:
        print("\n" + "-"*80)
        print("🐛 ERRORES MÁS COMUNES")
        print("-"*80)

        for error, count in sorted(errors_by_type.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"{count:3}x  {error}")

    if worst_cases:
        print("\n" + "-"*80)
        print("⚠️  TOP 10 CASOS MÁS PROBLEMÁTICOS")
        print("-"*80)

        for i, case in enumerate(worst_cases[:10], 1):
            print(f"\n{i}. ASIN: {case['product_asin']}")
            print(f"   Producto: {case['product_title'][:60]}")
            print(f"   Pregunta: {case['question']['text']}")
            print(f"   Tipo: {case['question']['type']} (dificultad: {case['question']['difficulty']})")
            print(f"   Problema: {case['analysis']['verdict']}")
            if case['analysis'].get('issues'):
                for issue in case['analysis']['issues']:
                    print(f"     - {issue}")

    print("\n" + "="*80)

    return report


# ============================================================================
# MAIN
# ============================================================================

def main():
    """
    Ejecuta stress test completo.
    """
    print("\n" + "#"*80)
    print("# STRESS TEST EXHAUSTIVO - SMART ANSWER ENGINE v2.0")
    print("#"*80)
    print(f"\nConfiguración:")
    print(f"  - Productos a testear: {CONFIG['max_products']}")
    print(f"  - Preguntas por producto: {CONFIG['questions_per_product']}")
    print(f"  - Dificultad: {CONFIG['question_difficulty']}")

    # 1. Cargar productos
    products = get_available_products(CONFIG["max_products"])

    if not products:
        print("\n❌ No se encontraron productos para testear")
        return

    # 2. Generar y ejecutar tests
    all_results = []

    print(f"\n🧪 Iniciando tests con {len(products)} productos...")
    print("="*80)

    for i, product in enumerate(products, 1):
        print(f"\n[{i}/{len(products)}] Producto: {product['title']}")
        print(f"ASIN: {product['asin']}")

        # Generar preguntas difíciles
        questions = generate_difficult_questions(product, CONFIG["questions_per_product"])

        # Testear
        results = test_product_with_questions(product, questions)
        all_results.extend(results)

        # Mostrar progreso
        passed_count = sum(1 for r in results if r["analysis"]["passed"])
        print(f"  Resultado: {passed_count}/{len(results)} preguntas pasadas")

    # 3. Generar reporte
    report = generate_report(all_results)

    print("\n✅ Stress test completado")
    print(f"📁 Ver detalles en: {CONFIG['output_dir']}/")
    print()


if __name__ == "__main__":
    main()
