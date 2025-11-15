#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
product_quality_analyzer.py
═══════════════════════════════════════════════════════════════════════════════
Análisis inteligente de calidad de productos para optimizar publicaciones

Métricas evaluadas:
  1. Rating (estrellas) → Mayor rating = mayor calidad
  2. Cantidad de reviews → Más reviews = producto más vendido
  3. Ranking de ventas (BSR) → Menor BSR = más ventas
  4. Precio → Rango óptimo (no muy barato, no muy caro)

Sistema de Scoring:
  • Score 90-100: EXCELENTE → Publicar TODOS los ASINs encontrados
  • Score 70-89:  BUENO     → Publicar 70% de ASINs
  • Score 50-69:  REGULAR   → Publicar 50% de ASINs
  • Score 30-49:  BAJO      → Publicar 30% de ASINs
  • Score 0-29:   MUY BAJO  → Publicar solo top 10-20 ASINs

Uso:
    from scripts.autonomous.product_quality_analyzer import ProductQualityAnalyzer

    analyzer = ProductQualityAnalyzer()
    score = analyzer.analyze_keyword_quality("lego")
    recommended_count = analyzer.get_recommended_asin_count(score, total_found=100)
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import statistics
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

class ProductQualityAnalyzer:
    """
    Analizador de calidad de productos basado en métricas de Amazon
    """

    def __init__(self, config_file: str = "config/quality_config.json"):
        """
        Inicializa el analizador

        Args:
            config_file: Archivo de configuración de thresholds
        """
        self.config_file = Path(config_file)
        self.config = self._load_config()

        # Thresholds por defecto
        self.thresholds = self.config.get("thresholds", {
            # RATINGS: Criterios más realistas
            "excellent_rating": 4.3,      # Rating >= 4.3 = excelente (antes 4.5)
            "good_rating": 3.8,           # Rating >= 3.8 = bueno (antes 4.0)
            "min_rating": 3.0,            # Rating < 3.0 = descartable (antes 3.5)

            # REVIEWS: Ajustados a volúmenes reales de Amazon
            "high_reviews": 500,          # >= 500 reviews = muy vendido (antes 1000)
            "medium_reviews": 50,         # >= 50 reviews = vendido (antes 100)
            "min_reviews": 5,             # < 5 reviews = poco conocido (antes 10)

            # BSR: Más realista para categorías de electronics/home
            "top_bsr": 50000,             # BSR < 50k = top seller (antes 10k)
            "good_bsr": 150000,           # BSR < 150k = buen vendedor (antes 50k)
            "medium_bsr": 500000,         # BSR < 500k = vendedor regular (antes 100k)

            # PRECIO: Sin cambios
            "min_price": 10,              # Precio mínimo USD
            "max_price": 300,             # Precio máximo USD
            "optimal_min_price": 20,      # Precio óptimo mínimo
            "optimal_max_price": 150      # Precio óptimo máximo
        })

        # Pesos para el scoring
        self.weights = self.config.get("weights", {
            "rating": 0.3,      # 30% del score
            "reviews": 0.3,     # 30% del score
            "bsr": 0.25,        # 25% del score
            "price": 0.15       # 15% del score
        })

    def _load_config(self) -> dict:
        """Carga configuración de thresholds"""
        if not self.config_file.exists():
            return {}

        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def score_rating(self, rating: float) -> float:
        """
        Score basado en rating (0-100)

        Args:
            rating: Rating del producto (0-5)

        Returns:
            float: Score 0-100
        """
        if rating is None or rating <= 0:
            return 0

        if rating >= self.thresholds["excellent_rating"]:
            return 100
        elif rating >= self.thresholds["good_rating"]:
            return 80
        elif rating >= self.thresholds["min_rating"]:
            return 50
        else:
            return 20

    def score_reviews(self, review_count: int) -> float:
        """
        Score basado en cantidad de reviews (0-100)

        Args:
            review_count: Cantidad de reviews

        Returns:
            float: Score 0-100
        """
        if review_count is None or review_count <= 0:
            return 0

        if review_count >= self.thresholds["high_reviews"]:
            return 100
        elif review_count >= self.thresholds["medium_reviews"]:
            return 70
        elif review_count >= self.thresholds["min_reviews"]:
            return 40
        else:
            return 20

    def score_bsr(self, bsr: int) -> float:
        """
        Score basado en Best Seller Rank (0-100)
        Menor BSR = mejor score

        Args:
            bsr: Best Seller Rank

        Returns:
            float: Score 0-100
        """
        if bsr is None or bsr <= 0:
            return 50  # Neutral si no hay BSR

        if bsr <= self.thresholds["top_bsr"]:
            return 100
        elif bsr <= self.thresholds["good_bsr"]:
            return 80
        elif bsr <= self.thresholds["medium_bsr"]:
            return 60
        else:
            return 30

    def score_price(self, price: float) -> float:
        """
        Score basado en precio (0-100)
        Rango óptimo = mejor score

        Args:
            price: Precio en USD

        Returns:
            float: Score 0-100
        """
        if price is None or price <= 0:
            return 0

        # Fuera de rango mínimo/máximo
        if price < self.thresholds["min_price"] or price > self.thresholds["max_price"]:
            return 20

        # Rango óptimo
        if self.thresholds["optimal_min_price"] <= price <= self.thresholds["optimal_max_price"]:
            return 100

        # Dentro del rango pero no óptimo
        return 60

    def calculate_product_score(self, product_data: dict) -> Dict[str, Any]:
        """
        Calcula score global de un producto

        MODO SIMPLIFICADO: Si no hay rating/reviews, usa solo BSR + precio
        Esto es más realista para Amazon Catalog API que no devuelve ratings.

        Args:
            product_data: Datos del producto de Amazon

        Returns:
            dict: Score detallado
        """
        # Extraer métricas - Soporta tanto formato directo como Amazon SP-API
        rating = 0
        review_count = 0
        bsr = 0
        price = 0

        # Intentar extraer de formato Amazon SP-API (salesRanks, attributes)
        if "salesRanks" in product_data and product_data.get("salesRanks"):
            sales_ranks = product_data["salesRanks"]
            if isinstance(sales_ranks, list) and sales_ranks:
                sales_ranks = sales_ranks[0]

            # BSR viene de classificationRanks
            if "classificationRanks" in sales_ranks:
                classification_ranks = sales_ranks["classificationRanks"]
                if classification_ranks:
                    bsr = classification_ranks[0].get("rank", 0)

        # Precio de attributes
        if "attributes" in product_data:
            attrs = product_data["attributes"]
            if "list_price" in attrs and attrs["list_price"]:
                price_data = attrs["list_price"][0] if isinstance(attrs["list_price"], list) else attrs["list_price"]
                price = price_data.get("value", 0)

        # Formato directo (legacy)
        if not rating:
            rating = product_data.get("rating", 0)
        if not review_count:
            review_count = product_data.get("reviews_count", 0)
        if not bsr:
            bsr = product_data.get("sales_rank", 0)
            if not bsr and "sales_rankings" in product_data:
                rankings = product_data.get("sales_rankings", [])
                if rankings:
                    bsr = rankings[0].get("rank", 0)
        if not price:
            price = product_data.get("price", 0)
            if not price and "amount" in product_data:
                price = product_data.get("amount", 0)

        # Calcular scores individuales
        rating_score = self.score_rating(rating)
        reviews_score = self.score_reviews(review_count)
        bsr_score = self.score_bsr(bsr)
        price_score = self.score_price(price)

        # MODO SIMPLIFICADO: Si no hay rating/reviews, usar solo BSR + precio
        has_rating_data = rating > 0 or review_count > 0

        if not has_rating_data:
            # Solo BSR (70%) + Precio (30%)
            total_score = (bsr_score * 0.70) + (price_score * 0.30)
        else:
            # Score completo con todos los factores
            total_score = (
                rating_score * self.weights["rating"] +
                reviews_score * self.weights["reviews"] +
                bsr_score * self.weights["bsr"] +
                price_score * self.weights["price"]
            )

        return {
            "total_score": round(total_score, 2),
            "rating_score": rating_score,
            "reviews_score": reviews_score,
            "bsr_score": bsr_score,
            "price_score": price_score,
            "metrics": {
                "rating": rating,
                "review_count": review_count,
                "bsr": bsr,
                "price": price
            },
            "quality_tier": self._get_quality_tier(total_score),
            "simplified_mode": not has_rating_data
        }

    def _get_quality_tier(self, score: float) -> str:
        """
        Determina el tier de calidad basado en score

        Args:
            score: Score total (0-100)

        Returns:
            str: Tier (EXCELLENT, GOOD, REGULAR, LOW, VERY_LOW)
        """
        if score >= 90:
            return "EXCELLENT"
        elif score >= 70:
            return "GOOD"
        elif score >= 50:
            return "REGULAR"
        elif score >= 30:
            return "LOW"
        else:
            return "VERY_LOW"

    def analyze_keyword_quality(self, asins_data: List[dict], sample_size: int = 20) -> Dict[str, Any]:
        """
        Analiza la calidad promedio de una keyword basándose en una muestra de productos

        Args:
            asins_data: Lista de productos (con datos de Amazon)
            sample_size: Cantidad de productos a analizar (default: 20)

        Returns:
            dict: Análisis de calidad de la keyword
        """
        if not asins_data:
            return {
                "avg_score": 0,
                "quality_tier": "VERY_LOW",
                "products_analyzed": 0,
                "recommendation": "skip"
            }

        # Limitar a sample_size
        sample = asins_data[:min(sample_size, len(asins_data))]

        # Calcular scores
        scores = []
        quality_tiers = []

        for product in sample:
            result = self.calculate_product_score(product)
            scores.append(result["total_score"])
            quality_tiers.append(result["quality_tier"])

        # Estadísticas
        avg_score = statistics.mean(scores) if scores else 0
        median_score = statistics.median(scores) if scores else 0

        # Contar por tier
        tier_counts = {
            "EXCELLENT": quality_tiers.count("EXCELLENT"),
            "GOOD": quality_tiers.count("GOOD"),
            "REGULAR": quality_tiers.count("REGULAR"),
            "LOW": quality_tiers.count("LOW"),
            "VERY_LOW": quality_tiers.count("VERY_LOW")
        }

        # Tier dominante
        dominant_tier = max(tier_counts, key=tier_counts.get)

        # Recomendación
        recommendation = self._get_recommendation(avg_score, tier_counts, len(sample))

        return {
            "avg_score": round(avg_score, 2),
            "median_score": round(median_score, 2),
            "quality_tier": self._get_quality_tier(avg_score),
            "dominant_tier": dominant_tier,
            "products_analyzed": len(sample),
            "tier_distribution": tier_counts,
            "recommendation": recommendation
        }

    def _get_recommendation(self, avg_score: float, tier_counts: dict, sample_size: int) -> str:
        """
        Genera recomendación de acción basada en el análisis

        Args:
            avg_score: Score promedio
            tier_counts: Conteo por tier
            sample_size: Tamaño de muestra

        Returns:
            str: Recomendación (publish_all, publish_most, publish_some, publish_few, skip)
        """
        excellent_ratio = tier_counts.get("EXCELLENT", 0) / sample_size
        good_ratio = tier_counts.get("GOOD", 0) / sample_size

        # Thresholds más estrictos para evitar que TODO sea EXCELLENT
        if avg_score >= 92 and excellent_ratio >= 0.7:
            return "publish_all"  # Publicar todos (score 92+ Y 70%+ excellent)
        elif avg_score >= 80 or excellent_ratio >= 0.5:
            return "publish_most"  # Publicar 70-80% (score 80+ O 50%+ excellent)
        elif avg_score >= 65:
            return "publish_some"  # Publicar 50% (score 65+)
        elif avg_score >= 45:
            return "publish_few"  # Publicar 20-30% (score 45+)
        else:
            return "skip"  # Saltar esta keyword (score < 45)

    def get_recommended_asin_count(self, analysis: dict, total_found: int, apply_main2_multiplier: bool = True, target_publications: int = 60) -> int:
        """
        Calcula cuántos ASINs pasar a main2 basándose en el análisis de calidad.

        LÓGICA CORREGIDA:
        - Keyword EXCELENTE → Pasar MÁS ASINs (aprovechar la mina de oro)
        - Keyword BUENA → Pasar cantidad normal
        - Keyword REGULAR → Pasar MENOS ASINs (no vale la pena procesar basura)

        El multiplicador de main2 compensa que algunos fallarán en:
        - Categorización (~10% falla)
        - Validación (~5% falla)
        - Publicación ML (~10% rechaza)
        Tasa éxito main2: ~75%

        Args:
            analysis: Resultado de analyze_keyword_quality()
            total_found: Total de ASINs encontrados después de filtro de marcas
            apply_main2_multiplier: Si aplicar multiplicador para compensar fallos de main2
            target_publications: Objetivo de publicaciones finales por keyword

        Returns:
            int: Cantidad recomendada a pasar a main2
        """
        recommendation = analysis.get("recommendation", "skip")
        avg_score = analysis.get("avg_score", 0)

        # Determinar target y tasa de éxito según calidad
        if recommendation == "publish_all":
            # EXCELENTE: Aprovechar al máximo, publicar muchos
            target = target_publications * 1.5  # 90 publicados
            main2_success_rate = 0.85  # 85% éxito (productos de calidad)
            percentage = 1.0  # 100% de los encontrados

        elif recommendation == "publish_most":
            # BUENO: Publicar cantidad normal-alta
            target = target_publications  # 60 publicados
            main2_success_rate = 0.75  # 75% éxito
            percentage = 0.85  # 85% de los encontrados

        elif recommendation == "publish_some":
            # REGULAR: Publicar menos, ser selectivo
            target = target_publications * 0.6  # 36 publicados
            main2_success_rate = 0.65  # 65% éxito (productos mediocres)
            percentage = 0.60  # 60% de los encontrados

        elif recommendation == "publish_few":
            # BAJO: Solo los mejores, muy pocos
            target = target_publications * 0.3  # 18 publicados
            main2_success_rate = 0.50  # 50% éxito (productos malos)
            percentage = 0.40  # 40% de los encontrados

        else:  # skip
            return 0

        # Aplicar porcentaje al total encontrado
        base_count = int(total_found * percentage)

        if not apply_main2_multiplier:
            return base_count

        # Aplicar multiplicador para compensar fallos de main2
        recommended_count = int(target / main2_success_rate)

        # No exceder lo que tenemos disponible
        final_count = min(recommended_count, total_found)

        # Límites de seguridad
        if final_count < 10:
            final_count = min(10, total_found)  # Mínimo 10
        elif final_count > 200:
            final_count = 200  # Máximo 200

        return final_count

    def sort_asins_by_quality(self, asins_data: List[dict]) -> List[dict]:
        """
        Ordena ASINs por calidad (mejores primero)

        Args:
            asins_data: Lista de productos con datos

        Returns:
            list: Lista ordenada por score descendente
        """
        scored_products = []

        for product in asins_data:
            score_result = self.calculate_product_score(product)
            product["_quality_score"] = score_result["total_score"]
            product["_quality_tier"] = score_result["quality_tier"]
            scored_products.append(product)

        # Ordenar por score descendente
        return sorted(scored_products, key=lambda x: x.get("_quality_score", 0), reverse=True)

    def print_analysis(self, analysis: dict, keyword: str = None):
        """
        Imprime análisis de calidad de manera formateada

        Args:
            analysis: Resultado de analyze_keyword_quality()
            keyword: Nombre de la keyword (opcional)
        """
        print("\n" + "="*70)
        if keyword:
            print(f"📊 ANÁLISIS DE CALIDAD: '{keyword}'")
        else:
            print("📊 ANÁLISIS DE CALIDAD")
        print("="*70)

        print(f"\n🎯 Score Promedio:    {analysis['avg_score']:.1f}/100")
        print(f"   Tier de Calidad:   {analysis['quality_tier']}")
        print(f"   Productos Analizados: {analysis['products_analyzed']}")

        print(f"\n📈 Distribución de Calidad:")
        tier_dist = analysis['tier_distribution']
        for tier, count in tier_dist.items():
            if count > 0:
                pct = (count / analysis['products_analyzed'] * 100)
                bar = "█" * int(pct / 5)
                print(f"   {tier:12} {count:3} ({pct:5.1f}%) {bar}")

        print(f"\n💡 Recomendación:     {analysis['recommendation'].upper()}")

        if analysis['recommendation'] == 'publish_all':
            print("   → Excelente categoría, publicar TODOS los ASINs encontrados")
        elif analysis['recommendation'] == 'publish_most':
            print("   → Buena categoría, publicar 75% de los ASINs")
        elif analysis['recommendation'] == 'publish_some':
            print("   → Categoría regular, publicar 50% de los ASINs")
        elif analysis['recommendation'] == 'publish_few':
            print("   → Categoría baja, publicar solo top 20-30 ASINs")
        else:
            print("   → Categoría muy baja, SALTAR esta keyword")

        print("="*70)


# ═══════════════════════════════════════════════════════════════════════════
# CLI Mode
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analizar calidad de productos")
    parser.add_argument("--asins", "-a", nargs="+", help="ASINs a analizar")
    parser.add_argument("--keyword", "-k", help="Keyword (para mostrar en output)")
    parser.add_argument("--sample-size", "-s", type=int, default=20, help="Tamaño de muestra")

    args = parser.parse_args()

    if not args.asins:
        parser.print_help()
        print("\n❌ Debes proporcionar ASINs con --asins")
        sys.exit(1)

    # Obtener datos de productos
    from integrations.amazon_api import get_product_data_from_asin

    print(f"\n🔍 Obteniendo información de {len(args.asins)} productos...")

    products_data = []
    for asin in args.asins[:args.sample_size]:
        try:
            data = get_product_data_from_asin(asin)
            if data:
                products_data.append(data)
        except Exception as e:
            print(f"⚠️ Error con {asin}: {e}")

    if not products_data:
        print("\n❌ No se pudo obtener datos de ningún producto")
        sys.exit(1)

    # Analizar
    analyzer = ProductQualityAnalyzer()
    analysis = analyzer.analyze_keyword_quality(products_data, sample_size=args.sample_size)

    # Mostrar resultados
    analyzer.print_analysis(analysis, keyword=args.keyword)

    # Recomendación de cantidad
    recommended = analyzer.get_recommended_asin_count(analysis, len(args.asins))
    print(f"\n📦 De {len(args.asins)} ASINs encontrados, se recomienda publicar: {recommended}")
