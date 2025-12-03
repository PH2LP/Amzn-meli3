#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Brand Intelligence Filter - FILTRO SIMPLE DE 19 MARCAS PROHIBIDAS
====================================================================
Sistema simplificado que SOLO filtra las 19 marcas prohibidas.

NO usa:
- Whitelist de marcas seguras
- Blacklist de 1,823 marcas
- Wikidata API
- Google Search
- GPT-4 para análisis de marcas

SOLO filtra: Las 19 marcas de config/prohibited_items_comprehensive.json

Author: Sistema Autónomo
Date: 2025-12-03
"""

import json
from pathlib import Path
from typing import Tuple, Optional


class BrandIntelligenceFilter:
    """
    Filtro simple: SOLO verifica las 19 marcas prohibidas
    """

    def __init__(
        self,
        blacklist_file: str = "config/prohibited_items_comprehensive.json"
    ):
        """
        Inicializa el filtro - SOLO 19 marcas prohibidas

        Args:
            blacklist_file: Archivo con las 19 marcas prohibidas
        """
        self.blacklist_file = Path(blacklist_file)

        # Cargar solo las 19 marcas prohibidas
        self.prohibited_brands = self._load_prohibited_brands()

        # Stats
        self.total_checked = 0
        self.total_rejected = 0
        self.total_approved = 0

    def _load_prohibited_brands(self) -> list:
        """Carga SOLO las 19 marcas prohibidas"""
        if not self.blacklist_file.exists():
            print(f"⚠️ No se encontró {self.blacklist_file}")
            return []

        with open(self.blacklist_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Extraer SOLO protected_brands_luxury
        brands = []
        if "protected_brands_luxury" in config:
            brands = [brand.lower() for brand in config["protected_brands_luxury"]]

        print(f"✅ Cargadas {len(brands)} marcas prohibidas")

        return brands

    def is_brand_safe(
        self,
        title: str,
        brand: Optional[str] = None,
        product_data: Optional[dict] = None
    ) -> Tuple[bool, str, dict]:
        """
        Verifica si un producto es seguro - SOLO verifica las 19 marcas prohibidas

        Args:
            title: Título del producto
            brand: Marca del producto (opcional)
            product_data: Datos completos del producto (ignorado)

        Returns:
            Tuple[bool, str, dict]:
                - is_safe: True si producto es seguro, False si debe rechazarse
                - reason: Razón del rechazo o aprobación
                - details: Detalles adicionales
        """
        self.total_checked += 1

        title_lower = title.lower()
        brand_lower = brand.lower() if brand else ""

        # Verificar contra las 19 marcas prohibidas
        for prohibited_brand in self.prohibited_brands:
            # Verificar en título
            if prohibited_brand in title_lower:
                self.total_rejected += 1
                return False, f"Marca prohibida: {prohibited_brand}", {
                    "category": "protected_brands_luxury",
                    "matched_brand": prohibited_brand,
                    "method": "title_match"
                }

            # Verificar en campo brand (si existe)
            if brand_lower and prohibited_brand in brand_lower:
                self.total_rejected += 1
                return False, f"Marca prohibida: {prohibited_brand}", {
                    "category": "protected_brands_luxury",
                    "matched_brand": prohibited_brand,
                    "method": "brand_field_match"
                }

        # Producto aprobado (no está en las 19 marcas prohibidas)
        self.total_approved += 1
        return True, "Marca permitida (no está en blacklist de 19)", {
            "brand": brand if brand else "sin_marca",
            "method": "simple_check"
        }

    def get_stats(self) -> dict:
        """
        Retorna estadísticas del filtro

        Returns:
            dict: Estadísticas de uso
        """
        return {
            "total_checked": self.total_checked,
            "total_rejected": self.total_rejected,
            "total_approved": self.total_approved,
            "prohibited_brands_count": len(self.prohibited_brands)
        }

    def print_stats(self):
        """Imprime estadísticas del filtro"""
        stats = self.get_stats()

        print("\n" + "="*60)
        print("📊 BRAND INTELLIGENCE FILTER - ESTADÍSTICAS")
        print("="*60)
        print(f"Marcas prohibidas cargadas: {stats['prohibited_brands_count']}")
        print(f"Total verificados:          {stats['total_checked']}")
        print(f"Aprobados:                  {stats['total_approved']}")
        print(f"Rechazados:                 {stats['total_rejected']}")
        print("="*60)


# ═══════════════════════════════════════════════════════════════════════════
# TEST MODE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test del filtro
    filter = BrandIntelligenceFilter()

    print("\n🧪 TESTING BRAND FILTER")
    print("="*60)

    test_cases = [
        ("Nike Air Max 90 Running Shoes", "Nike"),
        ("Adidas Ultraboost Sneakers", "Adidas"),
        ("Anker PowerCore 20000mAh", "Anker"),
        ("Tom Ford Noir Eau de Parfum", "Tom Ford"),
        ("AmazonBasics USB Cable", "AmazonBasics"),
        ("Focusrite Scarlett 2i2 Audio Interface", "Focusrite"),
        ("Generic Bluetooth Earbuds", None),
    ]

    for title, brand in test_cases:
        is_safe, reason, details = filter.is_brand_safe(title, brand)
        status = "✅ PERMITIDO" if is_safe else "❌ RECHAZADO"
        print(f"{status} | {title[:50]}")
        print(f"         Razón: {reason}")
        print()

    filter.print_stats()
