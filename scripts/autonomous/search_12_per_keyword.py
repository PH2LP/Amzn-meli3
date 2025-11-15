#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search_12_per_keyword.py
═══════════════════════════════════════════════════════════════════════════════
BÚSQUEDA: 12 ASINs POR KEYWORD (ORDENADOS POR BSR)
═══════════════════════════════════════════════════════════════════════════════

Idéntico a autonomous_search_and_publish.py EXCEPTO:
- ❌ NO analiza calidad de keywords
- ✅ SIEMPRE toma top 12 ASINs por BSR
- ✅ Keywords desde ~/Desktop/asins-1000.txt
- ✅ Busca 100 páginas fijo

Flujo por keyword:
1. Buscar 100 páginas en Amazon (~1000 ASINs)
2. Filtrar por marcas + categorías prohibidas (batch API)
3. Filtrar por Prime + Fast Fulfillment
4. Ordenar por BSR (menor = más vendido)
5. Tomar top 12 ASINs
6. Guardar en asins.txt

Uso:
    python scripts/autonomous/search_12_per_keyword.py
    python scripts/autonomous/search_12_per_keyword.py --keywords-file ~/Desktop/mis-keywords.txt
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

# Añadir project root al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))
sys.path.insert(0, str(project_root / 'scripts'))

from autonomous.brand_filter import ProductFilter
from tools.search_asins_by_keyword import search_products_by_keyword
from integrations.amazon_pricing import get_prime_offers_batch_optimized
from integrations.amazon_api import get_products_batch, get_product_bsr_only


class SimpleKeywordSearch:
    """
    Búsqueda simple: Top 12 ASINs por BSR para cada keyword
    """

    def __init__(self, keywords_file: str = None):
        """
        Inicializa el buscador

        Args:
            keywords_file: Path al archivo de keywords (default: ~/Desktop/asins-1000.txt)
        """
        # Archivo de keywords
        if keywords_file:
            self.keywords_file = Path(keywords_file).expanduser()
        else:
            self.keywords_file = Path("~/Desktop/asins-1000.txt").expanduser()

        # Archivos de salida
        self.output_file = project_root / "asins.txt"
        self.log_file = project_root / "storage" / "autonomous_logs" / "search_12_per_keyword.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Componentes
        self.product_filter = ProductFilter()

        # Configuración fija
        self.asins_per_keyword = 12
        self.search_pages = 100  # 100 páginas = ~1000 ASINs

        # Métricas
        self.total_keywords_processed = 0
        self.total_asins_found = 0
        self.start_time = datetime.now()

        self.log("═══════════════════════════════════════════════════════════")
        self.log("🔍 BÚSQUEDA: TOP 12 ASINs POR BSR (POR KEYWORD)")
        self.log("═══════════════════════════════════════════════════════════")
        self.log(f"📄 Keywords file: {self.keywords_file}")
        self.log(f"💾 Output file: {self.output_file}")
        self.log(f"📊 Target: Top {self.asins_per_keyword} ASINs por keyword (ordenados por BSR)")
        self.log(f"📄 Páginas búsqueda: {self.search_pages} páginas (~{self.search_pages * 10} ASINs)")
        self.log("═══════════════════════════════════════════════════════════")

    def log(self, message: str, level: str = "INFO", keyword: str = None):
        """Escribe log en archivo y consola"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if keyword:
            log_line = f"[{timestamp}] [{level}] [{keyword}] {message}"
        else:
            log_line = f"[{timestamp}] [{level}] {message}"

        print(log_line)

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_line + "\n")

    def load_keywords(self) -> List[str]:
        """
        Carga keywords desde el archivo

        Returns:
            list: Lista de keywords (una por línea)
        """
        if not self.keywords_file.exists():
            self.log(f"❌ Archivo no encontrado: {self.keywords_file}", "ERROR")
            return []

        with open(self.keywords_file, 'r', encoding='utf-8') as f:
            keywords = [
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            ]

        self.log(f"📋 Cargadas {len(keywords)} keywords desde {self.keywords_file}")
        return keywords

    def filter_asins_by_brand_batch(self, asins: List[str], keyword: str) -> Tuple[List[str], List[dict]]:
        """
        Filtra ASINs por marcas + categorías prohibidas usando BATCH API

        Args:
            asins: Lista de ASINs a filtrar
            keyword: Keyword actual (para logs)

        Returns:
            Tuple[list, list]: (asins_permitidos, asins_rechazados)
        """
        allowed = []
        rejected = []

        # Procesar en batches de 20 ASINs
        batch_size = 20
        total_batches = (len(asins) + batch_size - 1) // batch_size

        for batch_num, i in enumerate(range(0, len(asins), batch_size), 1):
            batch = asins[i:i+batch_size]

            self.log(f"   Batch {batch_num}/{total_batches}: Verificando {len(batch)} ASINs...", keyword=keyword)

            try:
                # Obtener datos de 20 ASINs en 1 sola llamada
                products_data = get_products_batch(batch, include_data="summaries")

                # Filtrar cada producto
                for asin in batch:
                    product_data = products_data.get(asin)

                    if not product_data:
                        rejected.append({"asin": asin, "reason": "No se pudo obtener info"})
                        continue

                    # Verificar con ProductFilter (marcas + categorías + keywords)
                    is_ok, reason = self.product_filter.is_allowed(asin, product_data)

                    if is_ok:
                        allowed.append(asin)
                    else:
                        rejected.append({"asin": asin, "reason": reason})

            except Exception as e:
                self.log(f"⚠️ Error en batch {batch_num}: {e}", "WARNING", keyword=keyword)
                # Rechazar todo el batch en caso de error
                for asin in batch:
                    rejected.append({"asin": asin, "reason": f"Error batch: {str(e)[:50]}"})

            # Delay entre batches
            if i + batch_size < len(asins):
                time.sleep(2)

        return allowed, rejected

    def filter_prime_asins(self, asins: List[str], keyword: str) -> List[str]:
        """
        Filtra ASINs por Prime + Fast Fulfillment

        Args:
            asins: Lista de ASINs a filtrar
            keyword: Keyword actual (para logs)

        Returns:
            list: ASINs con Prime válido
        """
        if not asins:
            return []

        self.log(f"⭐ Filtrando {len(asins)} ASINs por Prime + Fast Fulfillment...", keyword=keyword)

        # Obtener ofertas Prime en batch
        prime_offers = get_prime_offers_batch_optimized(asins, batch_size=20, show_progress=True)

        # Filtrar solo ASINs con oferta Prime válida
        prime_asins = [
            asin for asin, offer in prime_offers.items()
            if offer is not None and offer.get("is_prime") and offer.get("price", 0) > 0
        ]

        rejected = len(asins) - len(prime_asins)

        self.log(f"✅ Prime: {len(prime_asins)}/{len(asins)} ASINs", keyword=keyword)
        self.log(f"   ❌ Rechazados: {rejected} ASINs", keyword=keyword)

        return prime_asins

    def rank_asins_by_bsr(self, asins: List[str], keyword: str) -> List[str]:
        """
        Ordena ASINs por BSR y retorna los top 12 más vendidos

        Args:
            asins: Lista de ASINs a ordenar
            keyword: Keyword actual (para logs)

        Returns:
            list: Top 12 ASINs ordenados por BSR (menor = más vendido)
        """
        self.log(f"📊 Obteniendo BSR de {len(asins)} ASINs para ordenar por ventas...", keyword=keyword)
        self.log(f"   Esto tomará ~{len(asins) * 2 // 60} minutos (2s por ASIN)", keyword=keyword)

        asins_with_bsr = []

        # Procesar cada ASIN
        for i, asin in enumerate(asins, 1):
            try:
                self.log(f"   [{i}/{len(asins)}] Obteniendo BSR de {asin}...", keyword=keyword)

                bsr = get_product_bsr_only(asin)

                if bsr:
                    asins_with_bsr.append({"asin": asin, "bsr": bsr})
                    self.log(f"      ✅ BSR: {bsr:,}", keyword=keyword)
                else:
                    self.log(f"      ⚠️ Sin BSR", keyword=keyword)

                # Delay entre requests
                time.sleep(2)

            except Exception as e:
                self.log(f"   ⚠️ Error obteniendo BSR de {asin}: {e}", "WARNING", keyword=keyword)

        if not asins_with_bsr:
            self.log(f"❌ No se pudo obtener BSR de ningún ASIN", "ERROR", keyword=keyword)
            return []

        # Ordenar por BSR (menor = más vendido = primero)
        asins_with_bsr.sort(key=lambda x: x["bsr"])

        # Tomar los top 12
        top_asins = [item["asin"] for item in asins_with_bsr[:self.asins_per_keyword]]

        self.log(f"✅ Ranking completado: {len(asins_with_bsr)} ASINs con BSR → Top {len(top_asins)} seleccionados", keyword=keyword)

        if top_asins:
            self.log(f"   🏆 Mejor BSR: {asins_with_bsr[0]['bsr']:,} (ASIN: {asins_with_bsr[0]['asin']})", keyword=keyword)
            if len(asins_with_bsr) > 1:
                last_idx = min(len(top_asins) - 1, len(asins_with_bsr) - 1)
                self.log(f"   📉 BSR #12: {asins_with_bsr[last_idx]['bsr']:,}", keyword=keyword)

        return top_asins

    def search_asins_for_keyword(self, keyword: str) -> List[str]:
        """
        Busca ASINs para una keyword y retorna top 12 por BSR

        Args:
            keyword: Keyword a buscar

        Returns:
            list: Lista de hasta 12 ASINs (top por BSR)
        """
        self.log(f"\n{'='*60}")
        self.log(f"🔍 Keyword: '{keyword}'")
        self.log(f"{'='*60}")

        try:
            # 1. Buscar en Amazon (100 páginas = ~1000 ASINs)
            self.log(f"[1/4] Buscando en Amazon ({self.search_pages} páginas)...", keyword=keyword)
            all_asins = search_products_by_keyword(
                keyword,
                max_pages=self.search_pages,
                log_callback=lambda msg: self.log(msg, keyword=keyword)
            )
            self.log(f"✅ Encontrados {len(all_asins)} ASINs", keyword=keyword)

            if not all_asins:
                self.log(f"⚠️ No se encontraron ASINs", keyword=keyword)
                return []

            # 2. Filtrar por marcas + categorías prohibidas
            self.log(f"[2/4] Filtrando por marcas + categorías prohibidas (BATCH API)...", keyword=keyword)
            allowed_asins, rejected = self.filter_asins_by_brand_batch(all_asins, keyword)
            self.log(f"✅ Filtro: {len(allowed_asins)}/{len(all_asins)} ASINs permitidos", keyword=keyword)

            if not allowed_asins:
                self.log(f"⚠️ Todos rechazados por filtros de marca/categoría", keyword=keyword)
                return []

            # 3. Filtrar por Prime
            self.log(f"[3/4] Filtrando por Prime + Fast Fulfillment...", keyword=keyword)
            prime_asins = self.filter_prime_asins(allowed_asins, keyword)

            if not prime_asins:
                self.log(f"⚠️ Ningún ASIN con Prime", keyword=keyword)
                return []

            self.log(f"✅ {len(prime_asins)} ASINs con Prime (de {len(allowed_asins)} marcas OK)", keyword=keyword)

            # 4. Ordenar por BSR y tomar top 12
            self.log(f"[4/4] Ordenando por BSR y tomando top {self.asins_per_keyword}...", keyword=keyword)
            top_asins = self.rank_asins_by_bsr(prime_asins, keyword)

            if not top_asins:
                self.log(f"⚠️ No se pudieron ordenar por BSR", keyword=keyword)
                return []

            self.log(f"✅ FINAL: {len(top_asins)} ASINs seleccionados (top {self.asins_per_keyword} por BSR)", keyword=keyword)
            self.log(f"   Resumen: {len(all_asins)} encontrados → {len(allowed_asins)} marcas OK → {len(prime_asins)} Prime → {len(top_asins)} top BSR", keyword=keyword)

            return top_asins

        except Exception as e:
            self.log(f"❌ Error buscando '{keyword}': {e}", "ERROR", keyword=keyword)
            import traceback
            traceback.print_exc()
            return []

    def save_asins(self, asins: List[str], mode: str = 'a'):
        """
        Guarda ASINs en asins.txt

        Args:
            asins: Lista de ASINs
            mode: 'w' = sobrescribir, 'a' = append
        """
        with open(self.output_file, mode, encoding='utf-8') as f:
            for asin in asins:
                f.write(f"{asin}\n")

        self.log(f"💾 {len(asins)} ASINs guardados en {self.output_file}")

    def run(self):
        """Ejecuta la búsqueda para todas las keywords"""

        # Limpiar archivo de salida
        if self.output_file.exists():
            self.output_file.unlink()
            self.log(f"🗑️  Limpiado {self.output_file}")

        # Cargar keywords
        keywords = self.load_keywords()

        if not keywords:
            self.log("❌ No hay keywords para procesar", "ERROR")
            return

        self.log(f"\n🚀 Iniciando búsqueda de {len(keywords)} keywords...")
        self.log(f"   Target total: {len(keywords)} × {self.asins_per_keyword} = {len(keywords) * self.asins_per_keyword} ASINs")

        # Procesar cada keyword
        all_asins = []

        for i, keyword in enumerate(keywords, 1):
            self.log(f"\n{'#'*60}")
            self.log(f"Keyword {i}/{len(keywords)}")
            self.log(f"{'#'*60}")

            asins = self.search_asins_for_keyword(keyword)

            if asins:
                all_asins.extend(asins)
                self.total_keywords_processed += 1
                self.total_asins_found += len(asins)

                # Guardar inmediatamente (append)
                self.save_asins(asins, mode='a')
            else:
                self.log(f"⚠️ No se encontraron ASINs para '{keyword}'")

            # Pequeño delay entre keywords
            if i < len(keywords):
                self.log(f"⏱️  Esperando 10 segundos antes de siguiente keyword...")
                time.sleep(10)

        # Resumen final
        elapsed = (datetime.now() - self.start_time).total_seconds() / 60

        self.log(f"\n{'='*60}")
        self.log("✅ BÚSQUEDA COMPLETADA")
        self.log(f"{'='*60}")
        self.log(f"📊 RESUMEN:")
        self.log(f"   Keywords procesadas:  {self.total_keywords_processed}/{len(keywords)}")
        self.log(f"   ASINs encontrados:    {self.total_asins_found}")
        self.log(f"   Promedio por keyword: {self.total_asins_found / max(self.total_keywords_processed, 1):.1f} ASINs")
        self.log(f"   Tiempo total:         {elapsed:.1f} minutos ({elapsed/60:.1f} horas)")
        self.log(f"   Output:               {self.output_file}")
        self.log(f"{'='*60}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Búsqueda: Top 12 ASINs por BSR para cada keyword"
    )
    parser.add_argument(
        '--keywords-file',
        type=str,
        help='Path al archivo de keywords (default: ~/Desktop/asins-1000.txt)'
    )

    args = parser.parse_args()

    try:
        searcher = SimpleKeywordSearch(keywords_file=args.keywords_file)
        searcher.run()

    except KeyboardInterrupt:
        print("\n\n🛑 Búsqueda detenida por usuario (Ctrl+C)")
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
