#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO DE RANKING PARA SELECCIONAR LOS MEJORES ASINs
====================================================

MÓDULO INDEPENDIENTE - NO MODIFICA NINGÚN CÓDIGO EXISTENTE

Calcula un score para cada ASIN basado en múltiples factores:
- BSR (Best Seller Rank): 35%
- Reviews: 25%
- Precio: 20%
- Competencia ML: 15%
- Categoría: 5%

Uso como script:
    python3 scripts/tools/rank_asins_for_publication.py --limit 1000

Uso como módulo:
    from scripts.tools.rank_asins_for_publication import rank_and_select_top_asins
    top_asins = rank_and_select_top_asins('asins.txt', limit=1000)
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional
import sqlite3

# Agregar project root al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.integrations.amazon_api import get_amazon_data_batch


def calculate_asin_score(asin_data: dict) -> dict:
    """
    Calcula score de 0-100 para un ASIN basado en múltiples factores.

    Args:
        asin_data: Dict con datos del ASIN desde Amazon

    Returns:
        dict: {
            'score': float (0-100),
            'breakdown': {
                'bsr_score': float,
                'review_score': float,
                'price_score': float,
                'competition_score': float,
                'category_score': float
            }
        }
    """

    score_breakdown = {}
    total_score = 0

    # 1. BSR Score (35 puntos) - Mientras más bajo, mejor
    bsr = asin_data.get('sales_rank', 999999)
    if bsr and bsr > 0:
        # Normalizar BSR (log scale)
        # BSR 1-100: 35 pts
        # BSR 100-1000: 30 pts
        # BSR 1000-10000: 25 pts
        # BSR 10000-50000: 20 pts
        # BSR 50000+: 10 pts
        if bsr <= 100:
            bsr_score = 35
        elif bsr <= 1000:
            bsr_score = 30
        elif bsr <= 10000:
            bsr_score = 25
        elif bsr <= 50000:
            bsr_score = 20
        elif bsr <= 100000:
            bsr_score = 15
        else:
            bsr_score = 10
    else:
        bsr_score = 5  # Sin BSR = peor score

    score_breakdown['bsr_score'] = bsr_score
    total_score += bsr_score

    # 2. Reviews Score (25 puntos)
    review_count = asin_data.get('review_count', 0)
    rating = asin_data.get('rating', 0)

    # Sub-score por cantidad de reviews (15 pts)
    if review_count >= 1000:
        review_count_score = 15
    elif review_count >= 500:
        review_count_score = 12
    elif review_count >= 100:
        review_count_score = 10
    elif review_count >= 50:
        review_count_score = 8
    elif review_count >= 10:
        review_count_score = 5
    else:
        review_count_score = 2

    # Sub-score por rating (10 pts)
    if rating >= 4.5:
        rating_score = 10
    elif rating >= 4.0:
        rating_score = 8
    elif rating >= 3.5:
        rating_score = 5
    elif rating >= 3.0:
        rating_score = 3
    else:
        rating_score = 1

    review_score = review_count_score + rating_score
    score_breakdown['review_score'] = review_score
    total_score += review_score

    # 3. Price Score (20 puntos) - Precio ideal: $20-$70
    price = asin_data.get('price', 0)

    if 20 <= price <= 70:
        price_score = 20  # Rango ideal
    elif 15 <= price < 20 or 70 < price <= 100:
        price_score = 15  # Aceptable
    elif 10 <= price < 15 or 100 < price <= 150:
        price_score = 10  # Marginal
    elif price > 0:
        price_score = 5   # Muy bajo o muy alto
    else:
        price_score = 0   # Sin precio

    score_breakdown['price_score'] = price_score
    total_score += price_score

    # 4. Competition Score (15 puntos) - Basado en saturación de categoría
    # Por ahora asignamos score base, después puedes integrarlo con ML API
    competition_score = 10  # Score neutral por defecto
    score_breakdown['competition_score'] = competition_score
    total_score += competition_score

    # 5. Category Score (5 puntos) - Categorías populares
    category = asin_data.get('category', '').lower()
    popular_categories = [
        'electronics', 'home', 'kitchen', 'sports', 'outdoor',
        'tools', 'automotive', 'pet', 'baby', 'health', 'beauty'
    ]

    category_score = 5 if any(cat in category for cat in popular_categories) else 3
    score_breakdown['category_score'] = category_score
    total_score += category_score

    return {
        'score': total_score,
        'breakdown': score_breakdown
    }


def rank_asins_from_file(asins_file: Path, limit: int = 1000) -> List[Dict]:
    """
    Rankea ASINs desde un archivo y retorna los top N.

    Args:
        asins_file: Path al archivo con ASINs (uno por línea)
        limit: Cantidad de ASINs a retornar

    Returns:
        List[Dict]: Lista de ASINs rankeados con sus scores
    """

    # Leer ASINs del archivo
    if not asins_file.exists():
        print(f"❌ Archivo no encontrado: {asins_file}")
        return []

    with open(asins_file, 'r') as f:
        asins = [
            line.strip().upper()
            for line in f
            if line.strip() and not line.startswith("#")
        ]

    print(f"\n📊 Evaluando {len(asins)} ASINs...")
    print("="*60)

    # Obtener datos de Amazon en batch (20 ASINs por request)
    batch_size = 20
    all_ranked_asins = []

    for i in range(0, len(asins), batch_size):
        batch = asins[i:i+batch_size]
        print(f"\n[{i+1}-{min(i+batch_size, len(asins))}/{len(asins)}] Obteniendo datos de Amazon...")

        # Obtener datos del batch
        batch_data = get_amazon_data_batch(batch)

        # Calcular score para cada ASIN
        for asin in batch:
            asin_data = batch_data.get(asin, {})

            if not asin_data or 'error' in asin_data:
                print(f"   ⚠️  {asin}: Sin datos")
                continue

            # Calcular score
            score_result = calculate_asin_score(asin_data)

            # Agregar a lista
            ranked_asin = {
                'asin': asin,
                'score': score_result['score'],
                'breakdown': score_result['breakdown'],
                'title': asin_data.get('title', 'N/A')[:60],
                'price': asin_data.get('price', 0),
                'bsr': asin_data.get('sales_rank', 999999),
                'reviews': asin_data.get('review_count', 0),
                'rating': asin_data.get('rating', 0)
            }

            all_ranked_asins.append(ranked_asin)

            print(f"   ✅ {asin}: Score {score_result['score']:.1f}/100")

    # Ordenar por score (mayor a menor)
    all_ranked_asins.sort(key=lambda x: x['score'], reverse=True)

    # Retornar top N
    top_asins = all_ranked_asins[:limit]

    print(f"\n{'='*60}")
    print(f"📊 RANKING COMPLETADO")
    print(f"{'='*60}")
    print(f"  Total evaluados: {len(all_ranked_asins)}")
    print(f"  Top seleccionados: {len(top_asins)}")
    print(f"  Score promedio top {limit}: {sum(a['score'] for a in top_asins)/len(top_asins):.1f}")
    print(f"  Score más alto: {top_asins[0]['score']:.1f}")
    print(f"  Score más bajo (top {limit}): {top_asins[-1]['score']:.1f}")
    print(f"{'='*60}\n")

    return top_asins


def rank_and_select_top_asins(
    input_file: str,
    limit: int = 1000,
    verbose: bool = True
) -> List[str]:
    """
    FUNCIÓN PRINCIPAL DEL MÓDULO

    Rankea ASINs desde un archivo y retorna solo la lista de los mejores.

    Args:
        input_file: Path al archivo con ASINs (uno por línea)
        limit: Cantidad de ASINs a retornar
        verbose: Si es True, imprime progreso

    Returns:
        List[str]: Lista de ASINs rankeados (solo los códigos, sin metadata)

    Ejemplo:
        >>> top_asins = rank_and_select_top_asins('asins.txt', limit=1000)
        >>> print(len(top_asins))
        1000
        >>> print(top_asins[0])
        'B08L5VN96K'
    """

    # Rankear con metadata completa
    ranked_asins = rank_asins_from_file(Path(input_file), limit=limit)

    # Extraer solo los ASINs (sin metadata)
    asin_list = [asin_data['asin'] for asin_data in ranked_asins]

    if verbose:
        print(f"\n✅ Retornando lista de {len(asin_list)} ASINs rankeados")

    return asin_list


def save_ranked_asins(ranked_asins: List[Dict], output_file: Path):
    """Guarda ASINs rankeados en archivo JSON"""

    with open(output_file, 'w') as f:
        json.dump(ranked_asins, f, indent=2, ensure_ascii=False)

    print(f"💾 Guardado: {output_file}")


def save_top_asins_to_file(ranked_asins: List[Dict], output_file: Path):
    """Guarda solo los ASINs (sin metadata) en archivo de texto"""

    with open(output_file, 'w') as f:
        f.write("# Top ASINs seleccionados por scoring\n")
        f.write(f"# Total: {len(ranked_asins)}\n")
        f.write(f"# Generado: {Path(__file__).name}\n\n")

        for asin_data in ranked_asins:
            f.write(f"{asin_data['asin']}\n")

    print(f"📄 Guardado: {output_file}")


def show_top_10(ranked_asins: List[Dict]):
    """Muestra los top 10 ASINs con detalles"""

    print("\n🏆 TOP 10 ASINs:")
    print("="*60)

    for i, asin_data in enumerate(ranked_asins[:10], 1):
        print(f"\n#{i}. {asin_data['asin']} - Score: {asin_data['score']:.1f}/100")
        print(f"   📦 {asin_data['title']}")
        print(f"   💰 ${asin_data['price']:.2f}")
        print(f"   📊 BSR: #{asin_data['bsr']:,}")
        print(f"   ⭐ {asin_data['rating']:.1f} ({asin_data['reviews']} reviews)")

        # Breakdown
        breakdown = asin_data['breakdown']
        print(f"   📈 Breakdown:")
        print(f"      BSR: {breakdown['bsr_score']:.0f}/35")
        print(f"      Reviews: {breakdown['review_score']:.0f}/25")
        print(f"      Price: {breakdown['price_score']:.0f}/20")
        print(f"      Competition: {breakdown['competition_score']:.0f}/15")
        print(f"      Category: {breakdown['category_score']:.0f}/5")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Rankea ASINs y selecciona los mejores para publicar"
    )
    parser.add_argument(
        '--input',
        type=str,
        default='asins.txt',
        help='Archivo con ASINs a evaluar (default: asins.txt)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=1000,
        help='Cantidad de ASINs a seleccionar (default: 1000)'
    )
    parser.add_argument(
        '--output-json',
        type=str,
        default='storage/ranked_asins.json',
        help='Archivo de salida JSON con detalles (default: storage/ranked_asins.json)'
    )
    parser.add_argument(
        '--output-txt',
        type=str,
        default='asins_top1000.txt',
        help='Archivo de salida TXT con solo ASINs (default: asins_top1000.txt)'
    )

    args = parser.parse_args()

    # Paths
    input_file = Path(args.input)
    output_json = Path(args.output_json)
    output_txt = Path(args.output_txt)

    # Crear directorio de salida si no existe
    output_json.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "="*60)
    print("🎯 SISTEMA DE RANKING DE ASINs")
    print("="*60)
    print(f"  Input: {input_file}")
    print(f"  Limit: {args.limit}")
    print(f"  Output JSON: {output_json}")
    print(f"  Output TXT: {output_txt}")
    print("="*60)

    # Rankear ASINs
    ranked_asins = rank_asins_from_file(input_file, limit=args.limit)

    if not ranked_asins:
        print("❌ No se pudieron rankear ASINs")
        return

    # Guardar resultados
    save_ranked_asins(ranked_asins, output_json)
    save_top_asins_to_file(ranked_asins, output_txt)

    # Mostrar top 10
    show_top_10(ranked_asins)

    print(f"\n✅ Proceso completado!")
    print(f"📄 Usa el archivo '{output_txt}' para publicar los mejores ASINs")


if __name__ == "__main__":
    main()
