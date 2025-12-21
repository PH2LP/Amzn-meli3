#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGA STRESS TEST - Smart Answer Engine v2.0

Test con 200 productos reales y preguntas VARIADAS:
- Fáciles y difíciles
- Raras y rebuscadas (como clientes reales)
- Que requieran buscar info en JSONs
- Casos edge y normales
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
    "max_products": 300,  # Test completo con 300 productos
    "questions_per_product": 1,  # 1 pregunta variada por producto
    "save_results": True,
    "output_dir": "test_results_stress"
}

# ============================================================================
# CARGA DE PRODUCTOS DESDE DB
# ============================================================================

def load_products_from_db(max_products=200):
    """
    Carga productos con mini_ml disponibles
    """
    print(f"\n📦 Cargando hasta {max_products} productos desde DB...")

    products_dir = Path("storage/logs/publish_ready")
    mini_ml_files = list(products_dir.glob("*_mini_ml.json"))

    print(f"  Encontrados: {len(mini_ml_files)} archivos mini_ml")

    # Mezclar aleatoriamente para variedad
    random.shuffle(mini_ml_files)

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
                "price": data.get("price", 0),
                "data": data
            })
        except Exception as e:
            print(f"  ⚠️  Error cargando {asin}: {e}")

    print(f"  ✅ {len(products)} productos cargados exitosamente")
    return products


# ============================================================================
# GENERACIÓN DE PREGUNTAS VARIADAS Y REALISTAS
# ============================================================================

def generate_realistic_questions(product_info):
    """
    Genera 1 pregunta VARIADA para un producto.
    La pregunta puede ser fácil, media o difícil aleatoriamente.
    """

    product_summary = f"""
PRODUCTO: {product_info['title']}
MARCA: {product_info['brand']}
CATEGORÍA: {product_info['category']}
PRECIO: ${product_info['price']}
"""

    prompt = f"""Eres un CLIENTE REAL de MercadoLibre haciendo UNA pregunta sobre un producto.

{product_summary}

Genera EXACTAMENTE 1 pregunta REALISTA y VARIADA:

La pregunta puede ser de CUALQUIER nivel (varía aleatoriamente):

🟢 FÁCIL/SIMPLE (~40% de las veces):
- Info básica que debería estar en la descripción
- Color, tamaño, peso, marca, qué incluye
- Ejemplos: "¿De qué material es?", "¿Viene con pilas?", "¿Qué tamaño tiene?"

🟡 MEDIA (~40% de las veces):
- Compatibilidad, funcionamiento, características técnicas
- Requiere buscar en JSON o razonar
- Ejemplos: "¿Funciona con mi iPhone 12?", "¿Se puede lavar?", "¿Cuánto dura la batería con uso normal?"

🔴 DIFÍCIL/RARA/REBUSCADA (~20% de las veces):
- Comparaciones raras, casos de uso específicos
- Preguntas rebuscadas o con múltiples condiciones
- Ejemplos reales:
  * "Si lo uso en un día lluvioso, ¿se puede mojar sin que se arruine?"
  * "Mi abuela tiene 80 años y no sabe de tecnología, ¿es fácil de usar para ella?"
  * "¿El rojo es rojo Ferrari o más tirando a bordó?"
  * "Tengo manos grandes, ¿me va a quedar chico?"
  * "Lo quiero regalar, ¿viene en caja bonita o en bolsa nomás?"

IMPORTANTE:
- Preguntas en español argentino/latinoamericano
- Que suenen NATURALES, como un cliente real preguntaría
- La pregunta difícil debe ser REBUSCADA pero realista
- NO preguntes por otros productos (búsqueda)
- NO preguntes cosas de seguridad crítica (voltaje, garantías) en TODAS

Responde SOLO este JSON:
{{
  "pregunta": "la pregunta aquí",
  "dificultad": "facil|media|dificil",
  "tipo": "simple|compatibility|funcionamiento|specs|edge_case|comparison|use_case_specific|rebuscada",
  "info_necesaria": "qué info del JSON necesita o qué debe razonar"
}}"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.9  # Más creatividad para preguntas variadas
        )

        result_text = response.choices[0].message.content.strip()

        # Parsear JSON
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
        if json_match:
            result_text = json_match.group(1)

        result = json.loads(result_text)

        # Mapear dificultad
        diff_map = {"facil": "easy", "media": "medium", "dificil": "hard"}
        difficulty = diff_map.get(result.get("dificultad", "media"), "medium")

        # Determinar expected behavior
        if difficulty == "easy":
            expected = "should_answer"
        elif difficulty == "medium":
            expected = "should_answer_or_low_confidence"
        else:
            expected = "should_handle_gracefully"

        # Convertir a formato de test
        question = {
            "text": result["pregunta"],
            "difficulty": difficulty,
            "type": result.get("tipo", "unknown"),
            "expected_behavior": expected,
            "info_needed": result.get("info_necesaria", "")
        }

        return [question]  # Retorna lista con 1 pregunta

    except Exception as e:
        print(f"    ⚠️  Error generando preguntas IA: {e}")

        # Fallback: preguntas genéricas
        return [
            {
                "text": "¿De qué color es?",
                "difficulty": "easy",
                "type": "simple",
                "expected_behavior": "should_answer"
            },
            {
                "text": "¿Cuánto dura la batería aproximadamente?",
                "difficulty": "medium",
                "type": "specs",
                "expected_behavior": "should_answer_or_low_confidence"
            },
            {
                "text": "¿Es fácil de usar para alguien que no sabe mucho de tecnología?",
                "difficulty": "hard",
                "type": "use_case_specific",
                "expected_behavior": "should_handle_gracefully"
            }
        ]


# ============================================================================
# TESTING
# ============================================================================

def test_product(product, questions):
    """Testea un producto con sus preguntas"""
    results = []

    for i, q in enumerate(questions, 1):
        difficulty_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}
        emoji = difficulty_emoji.get(q["difficulty"], "⚪")

        print(f"    {emoji} [{i}/3] {q['difficulty'].upper()}: {q['text'][:60]}...")

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
                "result": result_v2,
                "analysis": analysis,
                "product_asin": product["asin"],
                "product_title": product["title"]
            })

            # Mostrar resultado breve
            status = "✅" if analysis["acceptable"] else "❌"
            conf = result_v2.get('confidence', 0)
            action = result_v2.get('action', 'unknown')
            print(f"        {status} {action} (conf: {conf:.0f}%) - {analysis['verdict'][:50]}")

        except Exception as e:
            print(f"        ❌ ERROR: {str(e)[:60]}")
            results.append({
                "question": q,
                "result": {"error": str(e)},
                "analysis": {"acceptable": False, "verdict": f"Error: {e}"},
                "product_asin": product["asin"],
                "product_title": product["title"]
            })

    return results


def analyze_result(question, result):
    """Analiza si el resultado es aceptable"""
    expected = question.get("expected_behavior", "should_answer")
    action = result.get("action", "unknown")
    confidence = result.get("confidence", 0)
    notification_type = result.get("notification_type")

    analysis = {
        "acceptable": False,
        "verdict": "",
        "confidence": confidence,
        "action": action
    }

    # Criterios según dificultad
    difficulty = question.get("difficulty", "medium")

    if difficulty == "easy":
        # Fácil: DEBE responder con buena confidence
        if action == "answered" and confidence >= 70:
            analysis["acceptable"] = True
            analysis["verdict"] = f"✓ Respondió bien (conf: {confidence:.0f}%)"
        elif action == "answered":
            analysis["acceptable"] = True
            analysis["verdict"] = f"⚠️ Respondió pero baja conf ({confidence:.0f}%)"
        else:
            analysis["acceptable"] = False
            analysis["verdict"] = f"✗ No respondió pregunta fácil"

    elif difficulty == "medium":
        # Media: Puede responder o dar low_confidence
        if action == "answered":
            analysis["acceptable"] = True
            analysis["verdict"] = f"✓ Respondió (conf: {confidence:.0f}%)"
        elif action == "no_answer" and result.get("reason") in ["low_confidence", "critical_question"]:
            analysis["acceptable"] = True
            analysis["verdict"] = f"✓ Correctamente conservador ({result.get('reason')})"
        else:
            analysis["acceptable"] = False
            analysis["verdict"] = f"✗ Acción inesperada: {action}"

    elif difficulty == "hard":
        # Difícil: Cualquier respuesta razonable está OK
        if action == "answered" and confidence >= 60:
            analysis["acceptable"] = True
            analysis["verdict"] = f"✓ Respondió pregunta difícil (conf: {confidence:.0f}%)"
        elif action == "no_answer":
            analysis["acceptable"] = True
            analysis["verdict"] = f"✓ Conservador en pregunta difícil"
        elif action == "answered":
            analysis["acceptable"] = True
            analysis["verdict"] = f"⚠️ Respondió con baja conf ({confidence:.0f}%)"
        else:
            analysis["acceptable"] = False
            analysis["verdict"] = f"? Comportamiento inesperado"

    return analysis


# ============================================================================
# REPORTE
# ============================================================================

def generate_report(all_results):
    """Genera reporte del mega test"""
    print("\n" + "="*80)
    print("📊 GENERANDO REPORTE DEL MEGA STRESS TEST")
    print("="*80)

    total = len(all_results)
    acceptable = sum(1 for r in all_results if r["analysis"]["acceptable"])

    # Por dificultad
    by_difficulty = {}
    for r in all_results:
        diff = r["question"].get("difficulty", "unknown")
        if diff not in by_difficulty:
            by_difficulty[diff] = {"total": 0, "acceptable": 0}
        by_difficulty[diff]["total"] += 1
        if r["analysis"]["acceptable"]:
            by_difficulty[diff]["acceptable"] += 1

    # Por tipo de pregunta
    by_type = {}
    for r in all_results:
        qtype = r["question"].get("type", "unknown")
        if qtype not in by_type:
            by_type[qtype] = {"total": 0, "acceptable": 0}
        by_type[qtype]["total"] += 1
        if r["analysis"]["acceptable"]:
            by_type[qtype]["acceptable"] += 1

    # Casos problemáticos
    problematic = [r for r in all_results if not r["analysis"]["acceptable"]]

    # Guardar reporte
    report = {
        "timestamp": datetime.now().isoformat(),
        "config": CONFIG,
        "summary": {
            "total_questions": total,
            "acceptable": acceptable,
            "problematic": total - acceptable,
            "acceptance_rate": (acceptable / total * 100) if total > 0 else 0
        },
        "by_difficulty": by_difficulty,
        "by_type": by_type,
        "problematic_cases": problematic[:20],  # Top 20
        "all_results": all_results
    }

    if CONFIG["save_results"]:
        output_dir = Path(CONFIG["output_dir"])
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = output_dir / f"mega_stress_test_{timestamp}.json"

        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Reporte guardado: {report_file}")

    # Mostrar resumen en consola
    print("\n" + "="*80)
    print("📊 RESUMEN DEL MEGA STRESS TEST")
    print("="*80)
    print(f"\nTotal de preguntas: {total}")
    print(f"✅ Aceptables: {acceptable} ({acceptable/total*100:.1f}%)")
    print(f"❌ Problemáticas: {total - acceptable} ({(total-acceptable)/total*100:.1f}%)")

    print("\n" + "-"*80)
    print("📈 POR DIFICULTAD")
    print("-"*80)
    for diff in ["easy", "medium", "hard"]:
        if diff in by_difficulty:
            stats = by_difficulty[diff]
            rate = (stats["acceptable"] / stats["total"] * 100) if stats["total"] > 0 else 0
            emoji = "🟢" if diff == "easy" else "🟡" if diff == "medium" else "🔴"
            print(f"{emoji} {diff.upper():8} {stats['acceptable']:3}/{stats['total']:3} ({rate:5.1f}%)")

    print("\n" + "-"*80)
    print("📊 TOP TIPOS DE PREGUNTA")
    print("-"*80)
    sorted_types = sorted(by_type.items(), key=lambda x: x[1]["total"], reverse=True)
    for qtype, stats in sorted_types[:10]:
        rate = (stats["acceptable"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"{qtype:25} {stats['acceptable']:3}/{stats['total']:3} ({rate:5.1f}%)")

    if problematic:
        print("\n" + "-"*80)
        print("⚠️  TOP 10 CASOS PROBLEMÁTICOS")
        print("-"*80)
        for i, case in enumerate(problematic[:10], 1):
            print(f"\n{i}. [{case['question']['difficulty'].upper()}] {case['product_title'][:50]}")
            print(f"   Pregunta: {case['question']['text'][:70]}")
            print(f"   Problema: {case['analysis']['verdict']}")

    print("\n" + "="*80)

    return report


# ============================================================================
# MAIN
# ============================================================================

def main():
    import sys
    # Force unbuffered output
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

    print("\n" + "#"*80, flush=True)
    print("# 🚀 MEGA STRESS TEST - Smart Answer Engine v2.0", flush=True)
    print("#"*80, flush=True)
    print(f"\n📊 Configuración:", flush=True)
    print(f"  - Productos: {CONFIG['max_products']}", flush=True)
    print(f"  - Preguntas por producto: {CONFIG['questions_per_product']}", flush=True)
    print(f"  - Total esperado: ~{CONFIG['max_products'] * CONFIG['questions_per_product']} preguntas", flush=True)

    # 1. Cargar productos
    products = load_products_from_db(CONFIG["max_products"])

    if not products:
        print("\n❌ No se encontraron productos")
        return

    # 2. Generar y ejecutar tests
    all_results = []

    print(f"\n🧪 Iniciando tests con {len(products)} productos...")
    print("="*80)

    for i, product in enumerate(products, 1):
        print(f"\n[{i}/{len(products)}] 📦 {product['title'][:60]}")
        print(f"  ASIN: {product['asin']} | Categoría: {product['category'][:30]}")

        # Generar preguntas variadas
        questions = generate_realistic_questions(product)

        # Testear
        results = test_product(product, questions)
        all_results.extend(results)

        # Mostrar progreso cada 20
        if i % 20 == 0:
            current_acceptable = sum(1 for r in all_results if r["analysis"]["acceptable"])
            current_rate = (current_acceptable / len(all_results) * 100) if all_results else 0
            print(f"\n  📊 Progreso: {len(all_results)} preguntas, {current_acceptable} OK ({current_rate:.1f}%)")

    # 3. Generar reporte
    report = generate_report(all_results)

    print("\n✅ Mega stress test completado")
    print(f"📁 Ver detalles en: {CONFIG['output_dir']}/")
    print()


if __name__ == "__main__":
    main()
