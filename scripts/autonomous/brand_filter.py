#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
brand_filter.py
═══════════════════════════════════════════════════════════════════════════════
Filtrado inteligente de productos por:
- Marcas prohibidas (Nike, Adidas, etc.)
- Categorías restringidas (Ropa, Alimentos, Medicamentos)
- Keywords prohibidas (supplements, vitamins, etc.)

Uso:
    from scripts.autonomous.brand_filter import ProductFilter

    filter = ProductFilter()
    if filter.is_allowed(asin, product_data):
        # Publicar producto
    else:
        # Rechazar producto
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, Tuple

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

class ProductFilter:
    """
    Filtro inteligente para productos de Amazon → MercadoLibre
    """

    def __init__(self, config_file: str = "config/brand_blacklist.json"):
        """
        Inicializa el filtro cargando la configuración de blacklist

        Args:
            config_file: Ruta al archivo JSON de configuración
        """
        self.config_file = Path(config_file)
        self.config = self._load_config()

        # Listas de filtrado
        self.blacklisted_brands = self.config.get("blacklisted_brands", [])
        self.brand_patterns = self.config.get("brand_patterns_regex", [])
        self.prohibited_categories = self.config.get("prohibited_categories", [])
        self.restricted_categories = self.config.get("restricted_categories", [])
        self.prohibited_keywords = self.config.get("prohibited_keywords", [])
        self.restricted_keywords = self.config.get("restricted_keywords", [])
        self.irrelevant_types = self.config.get("irrelevant_product_types", [])
        self.irrelevant_keywords = self.config.get("irrelevant_keywords", [])

        # Compilar regex patterns
        self.compiled_patterns = [re.compile(pattern) for pattern in self.brand_patterns]

        # Stats
        self.total_checked = 0
        self.total_rejected = 0
        self.rejection_reasons = {
            "brand": 0,
            "category": 0,
            "keyword": 0,
            "missing_data": 0
        }

    def _load_config(self) -> dict:
        """Carga la configuración de blacklist"""
        if not self.config_file.exists():
            print(f"⚠️ Advertencia: No se encontró {self.config_file}, usando lista vacía")
            return {}

        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def is_allowed(self, asin: str, product_data: dict, strict: bool = True) -> Tuple[bool, str]:
        """
        Verifica si un producto está permitido para publicación

        Args:
            asin: ASIN del producto
            product_data: Datos del producto de Amazon (JSON completo o mini)
            strict: Si es True, rechaza productos sin información suficiente

        Returns:
            Tuple[bool, str]: (permitido, razón de rechazo si aplica)
        """
        self.total_checked += 1

        # Extraer información del producto
        # Soporta tanto el formato directo como el formato de Amazon SP-API (summaries)
        if "summaries" in product_data and product_data["summaries"]:
            # Formato Amazon SP-API
            summary = product_data["summaries"][0]
            title = summary.get("itemName", "").lower()
            brand = summary.get("brand", "").lower()
            category = summary.get("productType", "").lower()
        else:
            # Formato directo (legacy)
            title = product_data.get("title", "").lower()
            brand = product_data.get("brand", "").lower()
            category = product_data.get("product_type", "").lower()

        # Intentar extraer de binding/category si no hay product_type
        if not category:
            category = product_data.get("binding", "").lower()
        if not category:
            category = product_data.get("product_group", "").lower()

        # 1. Verificar datos mínimos
        if strict and not (title and brand):
            self.total_rejected += 1
            self.rejection_reasons["missing_data"] += 1
            return False, f"Datos insuficientes (título: {bool(title)}, marca: {bool(brand)})"

        # 2. Verificar marca exacta
        if brand in [b.lower() for b in self.blacklisted_brands]:
            self.total_rejected += 1
            self.rejection_reasons["brand"] += 1
            return False, f"Marca prohibida: {brand}"

        # 3. Verificar marca con regex
        full_text = f"{title} {brand} {category}"
        for pattern in self.compiled_patterns:
            if pattern.search(full_text):
                self.total_rejected += 1
                self.rejection_reasons["brand"] += 1
                matched_brand = pattern.pattern.replace("(?i)", "").replace("\\s+", " ")
                return False, f"Marca prohibida detectada: {matched_brand}"

        # 4. Verificar categorías prohibidas (HARD BLOCK)
        for prohibited_cat in self.prohibited_categories:
            if prohibited_cat.lower() in category or prohibited_cat.lower() in title:
                self.total_rejected += 1
                self.rejection_reasons["category"] += 1
                return False, f"Categoría prohibida: {prohibited_cat}"

        # 5. EXCEPCIÓN: Ropa de cama/Home NO es ropa con talles
        # Productos de Home/Bedding tienen medidas estándar en la caja (no talles)
        home_bedding_keywords = [
            # Bedding
            "sheet", "bedding", "comforter", "duvet", "pillowcase", "pillow case",
            "blanket", "quilt", "mattress pad", "mattress topper", "bed sheet",
            "fitted sheet", "flat sheet", "bedspread", "coverlet", "bed skirt",
            "valance", "bed set", "bedding set", "throw blanket",
            # Towels
            "towel", "bath towel", "hand towel", "kitchen towel", "beach towel",
            "washcloth", "bath mat", "bath rug",
            # Window treatments
            "curtain", "drape", "window panel", "valance", "window treatment",
            "shower curtain", "curtain panel",
            # Table linens
            "tablecloth", "table cloth", "napkin", "table runner", "placemat",
            "place mat", "table linen",
            # Rugs & Mats
            "rug", "area rug", "runner rug", "doormat", "door mat", "floor mat",
            # Pillows (decorative)
            "throw pillow", "decorative pillow", "pillow cover", "cushion cover"
        ]

        is_home_bedding = any(keyword in title for keyword in home_bedding_keywords)

        # 6. Verificar categorías restringidas (ropa, calzado) - EXCEPTO Home/Bedding
        if not is_home_bedding:
            for restricted_cat in self.restricted_categories:
                if restricted_cat.lower() in category or restricted_cat.lower() in title:
                    self.total_rejected += 1
                    self.rejection_reasons["category"] += 1
                    return False, f"Categoría restringida: {restricted_cat}"

        # 7. Verificar keywords prohibidas (supplements, vitamins, food, etc.)
        for keyword in self.prohibited_keywords:
            if keyword.lower() in title or keyword.lower() in category:
                self.total_rejected += 1
                self.rejection_reasons["keyword"] += 1
                return False, f"Keyword prohibida: {keyword}"

        # 8. Verificar keywords restringidas (ropa) - EXCEPTO Home/Bedding
        if not is_home_bedding:
            for keyword in self.restricted_keywords:
                if keyword.lower() in title:
                    self.total_rejected += 1
                    self.rejection_reasons["keyword"] += 1
                    return False, f"Keyword restringida: {keyword}"

        # 9. Verificar tipos de producto irrelevantes (DVDs, libros, etc.)
        for irrelevant_type in self.irrelevant_types:
            if irrelevant_type.lower() in category or irrelevant_type.lower() in title:
                self.total_rejected += 1
                self.rejection_reasons["category"] += 1
                return False, f"Tipo de producto irrelevante: {irrelevant_type}"

        # 10. Verificar keywords irrelevantes (dvd, book, etc.)
        for keyword in self.irrelevant_keywords:
            if keyword.lower() in title:
                self.total_rejected += 1
                self.rejection_reasons["keyword"] += 1
                return False, f"Keyword irrelevante: {keyword}"

        # Producto permitido
        return True, "OK"

    def check_asin_from_amazon_api(self, asin: str) -> Tuple[bool, str]:
        """
        Verifica un ASIN consultando la API de Amazon

        Args:
            asin: ASIN a verificar

        Returns:
            Tuple[bool, str]: (permitido, razón)
        """
        try:
            from integrations.amazon_api import get_product_data_from_asin

            product_data = get_product_data_from_asin(asin)

            if not product_data:
                return False, "No se pudo obtener información del producto"

            return self.is_allowed(asin, product_data)

        except Exception as e:
            return False, f"Error al consultar API: {e}"

    def filter_asin_list(self, asins: list, verbose: bool = True) -> Tuple[list, list]:
        """
        Filtra una lista de ASINs

        Args:
            asins: Lista de ASINs a filtrar
            verbose: Si es True, muestra progreso

        Returns:
            Tuple[list, list]: (asins_permitidos, asins_rechazados_con_razon)
        """
        allowed = []
        rejected = []

        for i, asin in enumerate(asins, 1):
            if verbose:
                print(f"[{i}/{len(asins)}] Verificando {asin}...", end=" ")

            is_ok, reason = self.check_asin_from_amazon_api(asin)

            if is_ok:
                allowed.append(asin)
                if verbose:
                    print("✅ Permitido")
            else:
                rejected.append({"asin": asin, "reason": reason})
                if verbose:
                    print(f"❌ Rechazado: {reason}")

        return allowed, rejected

    def get_stats(self) -> dict:
        """
        Retorna estadísticas de filtrado

        Returns:
            dict: Estadísticas
        """
        rejection_rate = (self.total_rejected / self.total_checked * 100) if self.total_checked > 0 else 0

        return {
            "total_checked": self.total_checked,
            "total_rejected": self.total_rejected,
            "total_allowed": self.total_checked - self.total_rejected,
            "rejection_rate": round(rejection_rate, 2),
            "rejection_reasons": self.rejection_reasons
        }

    def print_stats(self):
        """Imprime estadísticas de filtrado"""
        stats = self.get_stats()

        print("\n" + "="*60)
        print("📊 ESTADÍSTICAS DE FILTRADO")
        print("="*60)
        print(f"Total verificados:  {stats['total_checked']}")
        print(f"Permitidos:         {stats['total_allowed']} ({100 - stats['rejection_rate']:.1f}%)")
        print(f"Rechazados:         {stats['total_rejected']} ({stats['rejection_rate']:.1f}%)")
        print("\nRazones de rechazo:")
        print(f"  • Marca prohibida:     {stats['rejection_reasons']['brand']}")
        print(f"  • Categoría prohibida: {stats['rejection_reasons']['category']}")
        print(f"  • Keyword prohibida:   {stats['rejection_reasons']['keyword']}")
        print(f"  • Datos insuficientes: {stats['rejection_reasons']['missing_data']}")
        print("="*60)


# ═══════════════════════════════════════════════════════════════════════════
# CLI Mode
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Filtrar ASINs por marca/categoría")
    parser.add_argument("asins", nargs="*", help="ASINs a verificar")
    parser.add_argument("--file", "-f", help="Archivo con ASINs (uno por línea)")
    parser.add_argument("--config", "-c", default="config/brand_blacklist.json", help="Archivo de configuración")
    parser.add_argument("--output", "-o", help="Guardar ASINs permitidos en archivo")
    parser.add_argument("--rejected", "-r", help="Guardar ASINs rechazados en JSON")
    parser.add_argument("--quiet", "-q", action="store_true", help="Modo silencioso")

    args = parser.parse_args()

    # Cargar ASINs
    asins = args.asins

    if args.file:
        with open(args.file, 'r') as f:
            asins.extend([line.strip() for line in f if line.strip()])

    if not asins:
        parser.print_help()
        print("\n❌ Error: Debes proporcionar ASINs o un archivo con --file")
        sys.exit(1)

    # Crear filtro
    filter = ProductFilter(args.config)

    # Filtrar
    allowed, rejected = filter.filter_asin_list(asins, verbose=not args.quiet)

    # Guardar resultados
    if args.output and allowed:
        with open(args.output, 'w') as f:
            f.write("\n".join(allowed))
        print(f"\n✅ {len(allowed)} ASINs permitidos guardados en {args.output}")

    if args.rejected and rejected:
        with open(args.rejected, 'w') as f:
            json.dump(rejected, f, indent=2)
        print(f"✅ {len(rejected)} ASINs rechazados guardados en {args.rejected}")

    # Stats
    if not args.quiet:
        filter.print_stats()
