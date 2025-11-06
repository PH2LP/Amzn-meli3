#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para calcular el costo de IA por ASIN en el pipeline
Analiza todas las llamadas a OpenAI API y estima tokens/costos

Precios GPT-4o-mini (2025):
- Input: $0.150 / 1M tokens
- Output: $0.600 / 1M tokens
"""

import json
import os
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════
# PRICING (GPT-4o-mini)
# ═══════════════════════════════════════════════════════════════════════════

PRICE_INPUT_PER_1M = 0.150  # USD
PRICE_OUTPUT_PER_1M = 0.600  # USD


# ═══════════════════════════════════════════════════════════════════════════
# ANÁLISIS DE LLAMADAS IA POR FASE
# ═══════════════════════════════════════════════════════════════════════════

class AICallAnalyzer:
    """Analiza y estima costos de llamadas a IA en el pipeline"""

    def __init__(self):
        self.calls = []
        self.cache_enabled = True  # Mayoría usa cache

    def add_call(self, name: str, phase: str, input_tokens: int,
                 output_tokens: int, uses_cache: bool = True,
                 conditional: str = None):
        """
        Registra una llamada a IA

        Args:
            name: Nombre de la función
            phase: Fase del pipeline (transform, validate, publish)
            input_tokens: Tokens estimados de input
            output_tokens: Tokens estimados de output
            uses_cache: Si usa cache (ahorra costos en ejecuciones posteriores)
            conditional: Condición para que se ejecute (ej: "solo si missing attributes")
        """
        self.calls.append({
            'name': name,
            'phase': phase,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'uses_cache': uses_cache,
            'conditional': conditional,
            'cost_input': (input_tokens / 1_000_000) * PRICE_INPUT_PER_1M,
            'cost_output': (output_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M,
            'cost_total': ((input_tokens / 1_000_000) * PRICE_INPUT_PER_1M +
                          (output_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M)
        })

    def calculate_costs(self, first_run: bool = False) -> Dict:
        """
        Calcula costos totales considerando cache

        Args:
            first_run: Si es primera ejecución (no usa cache)
        """
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0
        calls_executed = []
        calls_cached = []

        for call in self.calls:
            # Si usa cache y no es first run, costo = 0
            if call['uses_cache'] and not first_run:
                calls_cached.append(call['name'])
                continue

            calls_executed.append(call['name'])
            total_input_tokens += call['input_tokens']
            total_output_tokens += call['output_tokens']
            total_cost += call['cost_total']

        return {
            'total_input_tokens': total_input_tokens,
            'total_output_tokens': total_output_tokens,
            'total_tokens': total_input_tokens + total_output_tokens,
            'total_cost_usd': round(total_cost, 4),
            'calls_executed': calls_executed,
            'calls_cached': calls_cached,
            'breakdown_by_phase': self._breakdown_by_phase(first_run)
        }

    def _breakdown_by_phase(self, first_run: bool) -> Dict:
        """Agrupa costos por fase del pipeline"""
        phases = {}

        for call in self.calls:
            if call['uses_cache'] and not first_run:
                continue

            phase = call['phase']
            if phase not in phases:
                phases[phase] = {
                    'calls': [],
                    'total_tokens': 0,
                    'total_cost': 0
                }

            phases[phase]['calls'].append(call['name'])
            phases[phase]['total_tokens'] += call['input_tokens'] + call['output_tokens']
            phases[phase]['total_cost'] += call['cost_total']

        return phases


# ═══════════════════════════════════════════════════════════════════════════
# DEFINIR LLAMADAS IA DEL PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

def build_pipeline_analysis() -> AICallAnalyzer:
    """
    Construye análisis completo de llamadas IA en el pipeline
    Basado en código de main2.py + transform_mapper_new.py
    """
    analyzer = AICallAnalyzer()

    # ═══════════════════════════════════════════════════════════════════════
    # FASE 1: DOWNLOAD - Sin IA
    # ═══════════════════════════════════════════════════════════════════════
    # (No hay llamadas IA aquí)

    # ═══════════════════════════════════════════════════════════════════════
    # FASE 2: TRANSFORM (build_mini_ml en transform_mapper_new.py)
    # ═══════════════════════════════════════════════════════════════════════

    # 2.1) detect_category → CategoryMatcherV2
    # - Usa embeddings primero (sin costo)
    # - Si use_ai=True, hace llamada de validación
    analyzer.add_call(
        name='CategoryMatcherV2.validate_with_ai',
        phase='transform',
        input_tokens=800,  # product_data + top 5 categories
        output_tokens=30,  # max_tokens=30
        uses_cache=True,  # Cache por ASIN
        conditional='Solo si use_ai=True (default en pipeline)'
    )

    # 2.2) detect_gtin_with_ai (fallback si no encuentra GTIN en JSON)
    analyzer.add_call(
        name='detect_gtin_with_ai',
        phase='transform',
        input_tokens=8000,  # Hasta 8000 chars del JSON
        output_tokens=50,   # Solo devuelve GTIN o null
        uses_cache=False,   # No usa cache explícito
        conditional='Solo si extract_gtins() no encuentra GTIN'
    )

    # 2.3) ai_title_es
    analyzer.add_call(
        name='ai_title_es',
        phase='transform',
        input_tokens=400,   # base_title + brand + model + bullets
        output_tokens=80,   # max_tokens=80
        uses_cache=True,    # TITLE_CACHE_PATH
    )

    # 2.4) ai_characteristics
    analyzer.add_call(
        name='ai_characteristics',
        phase='transform',
        input_tokens=12000,  # JSON truncado a 12000 chars
        output_tokens=800,   # 20+ características con detalles
        uses_cache=False,    # No usa cache explícito, pero rara vez cambia
    )

    # 2.5) ai_desc_es
    analyzer.add_call(
        name='ai_desc_es',
        phase='transform',
        input_tokens=15000,  # JSON completo truncado + prompt largo
        output_tokens=1500,  # max_tokens=1500
        uses_cache=True,     # DESC_CACHE_PATH
    )

    # 2.6) ask_gpt_equivalences (solo si hay atributos faltantes)
    analyzer.add_call(
        name='ask_gpt_equivalences',
        phase='transform',
        input_tokens=6000,   # 800 claves del JSON flat + prompt
        output_tokens=300,   # Lista de equivalencias
        uses_cache=True,     # CACHE_EQ_PATH + guarda en _equiv.json
        conditional='Solo si hay atributos missing Y no están en cache'
    )

    # ═══════════════════════════════════════════════════════════════════════
    # FASE 3: VALIDATION (ai_validators.py) - DESACTIVADA POR DEFAULT
    # ═══════════════════════════════════════════════════════════════════════

    # validate_listing_complete está DESACTIVADA (Config.SKIP_VALIDATION = True)
    # No la incluyo porque no se ejecuta en producción

    # ═══════════════════════════════════════════════════════════════════════
    # FASE 4: PUBLISH (mainglobal.py)
    # ═══════════════════════════════════════════════════════════════════════

    # Hay varias llamadas IA en mainglobal.py pero son para validaciones
    # avanzadas y mapeo de atributos. No todas se ejecutan siempre.

    # validate_dimensions_with_ai (línea 159)
    analyzer.add_call(
        name='validate_dimensions_with_ai',
        phase='publish',
        input_tokens=300,
        output_tokens=100,
        uses_cache=False,
        conditional='Solo si dimensiones sospechosas'
    )

    # improve_title_with_ai (línea 555) - solo si título muy largo
    analyzer.add_call(
        name='improve_title_with_ai',
        phase='publish',
        input_tokens=200,
        output_tokens=60,
        uses_cache=False,
        conditional='Solo si título > 60 chars'
    )

    # enhance_description_with_ai (línea 661) - enriquece descripción
    analyzer.add_call(
        name='enhance_description_with_ai',
        phase='publish',
        input_tokens=2000,
        output_tokens=800,
        uses_cache=False,
        conditional='Siempre se ejecuta'
    )

    # validate_category_with_ai (línea 699) - validación adicional
    analyzer.add_call(
        name='validate_category_with_ai',
        phase='publish',
        input_tokens=500,
        output_tokens=100,
        uses_cache=False,
        conditional='Siempre se ejecuta'
    )

    # fix_publishing_error_with_ai (línea 748) - solo en errores
    analyzer.add_call(
        name='fix_publishing_error_with_ai',
        phase='publish',
        input_tokens=3000,
        output_tokens=1000,
        uses_cache=False,
        conditional='Solo si hay error en publicación'
    )

    return analyzer


# ═══════════════════════════════════════════════════════════════════════════
# ANÁLISIS Y REPORTE
# ═══════════════════════════════════════════════════════════════════════════

def print_cost_analysis():
    """Imprime análisis detallado de costos"""

    analyzer = build_pipeline_analysis()

    print("="*80)
    print("💰 ANÁLISIS DE COSTOS DE IA POR ASIN")
    print("="*80)
    print()

    # Escenario 1: Primera ejecución (sin cache)
    print("📊 ESCENARIO 1: Primera ejecución (sin cache)")
    print("-" * 80)
    first_run = analyzer.calculate_costs(first_run=True)

    print(f"Total de tokens: {first_run['total_tokens']:,}")
    print(f"  - Input:  {first_run['total_input_tokens']:,} tokens")
    print(f"  - Output: {first_run['total_output_tokens']:,} tokens")
    print()
    print(f"💵 COSTO TOTAL: ${first_run['total_cost_usd']:.4f} USD por ASIN")
    print()
    print("Desglose por fase:")
    for phase, data in first_run['breakdown_by_phase'].items():
        print(f"  {phase.upper()}: ${data['total_cost']:.4f} ({data['total_tokens']:,} tokens)")
        for call in data['calls']:
            print(f"    - {call}")
    print()

    # Escenario 2: Ejecuciones posteriores (con cache)
    print("📊 ESCENARIO 2: Ejecuciones posteriores (con cache)")
    print("-" * 80)
    cached_run = analyzer.calculate_costs(first_run=False)

    print(f"Total de tokens: {cached_run['total_tokens']:,}")
    print(f"  - Input:  {cached_run['total_input_tokens']:,} tokens")
    print(f"  - Output: {cached_run['total_output_tokens']:,} tokens")
    print()
    print(f"💵 COSTO TOTAL: ${cached_run['total_cost_usd']:.4f} USD por ASIN")
    print()
    print(f"✅ Ahorro por cache: ${first_run['total_cost_usd'] - cached_run['total_cost_usd']:.4f} USD")
    print(f"   ({len(cached_run['calls_cached'])} llamadas en cache)")
    print()
    print("Llamadas que usan cache (costo = 0 después de primera vez):")
    for call in cached_run['calls_cached']:
        print(f"  ✓ {call}")
    print()

    # Llamadas que SIEMPRE se ejecutan
    print("⚠️  Llamadas que SIEMPRE se ejecutan (sin cache):")
    for call in cached_run['calls_executed']:
        print(f"  • {call}")
    print()

    # Proyección para múltiples ASINs
    print("="*80)
    print("📈 PROYECCIÓN DE COSTOS PARA MÚLTIPLES ASINS")
    print("="*80)
    print()

    asins_to_test = [1, 10, 50, 100, 500, 1000]

    print(f"{'ASINs':<10} {'Primera vez':<20} {'Posteriores':<20} {'Total':<15}")
    print("-" * 80)

    for n_asins in asins_to_test:
        # Primera ejecución de todos
        cost_first = first_run['total_cost_usd'] * n_asins
        # Ejecuciones posteriores (solo las que no tienen cache)
        cost_subsequent = cached_run['total_cost_usd'] * n_asins
        # Total asumiendo 1 primera vez + 0 posteriores (peor caso)
        total = cost_first

        print(f"{n_asins:<10} ${cost_first:>15.2f}     ${cost_subsequent:>15.2f}     ${total:>12.2f}")

    print()
    print("Nota: 'Primera vez' es el costo de procesar cada ASIN por primera vez.")
    print("      'Posteriores' es el costo de reprocesar ASINs que ya tienen datos en cache.")
    print()

    # Análisis de optimización
    print("="*80)
    print("💡 ANÁLISIS Y RECOMENDACIONES")
    print("="*80)
    print()

    # Identificar llamadas más costosas
    sorted_calls = sorted(analyzer.calls, key=lambda x: x['cost_total'], reverse=True)

    print("🔥 Top 5 llamadas más costosas:")
    for i, call in enumerate(sorted_calls[:5], 1):
        print(f"  {i}. {call['name']}")
        print(f"     Costo: ${call['cost_total']:.4f}")
        print(f"     Tokens: {call['input_tokens'] + call['output_tokens']:,} " +
              f"({call['input_tokens']:,} in, {call['output_tokens']:,} out)")
        print(f"     Cache: {'✅ Sí' if call['uses_cache'] else '❌ No'}")
        if call['conditional']:
            print(f"     Condicional: {call['conditional']}")
        print()

    print("💡 Recomendaciones de optimización:")
    print()
    print("  1. Cache es crítico: Las llamadas con cache ahorran ~${:.4f} por ASIN".format(
        first_run['total_cost_usd'] - cached_run['total_cost_usd']
    ))
    print("     → Mantener storage/logs/*_cache.json persistente")
    print()
    print("  2. ai_desc_es es la más costosa ({:.1f}% del total)".format(
        (sorted_calls[0]['cost_total'] / first_run['total_cost_usd']) * 100
    ))
    print("     → Validar que max_tokens=1500 sea necesario")
    print("     → Considerar reducir tamaño del prompt")
    print()
    print("  3. Llamadas en mainglobal.py se ejecutan SIEMPRE sin cache")
    print("     → Considerar agregar cache o condicionales más estrictos")
    print()
    print("  4. detect_gtin_with_ai solo se ejecuta en fallback")
    print("     → Asegurar que extract_gtins() encuentre GTINs correctamente")
    print()

    # Guardar reporte en JSON
    report = {
        'timestamp': str(Path('storage/logs/ia_cost_report.json').stat().st_mtime if
                        Path('storage/logs/ia_cost_report.json').exists() else 'N/A'),
        'pricing': {
            'model': 'gpt-4o-mini',
            'input_per_1m': PRICE_INPUT_PER_1M,
            'output_per_1m': PRICE_OUTPUT_PER_1M
        },
        'scenarios': {
            'first_run': first_run,
            'cached_run': cached_run
        },
        'all_calls': analyzer.calls
    }

    report_path = Path('storage/logs/ia_cost_report.json')
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"📄 Reporte completo guardado en: {report_path}")
    print()


if __name__ == '__main__':
    print_cost_analysis()
