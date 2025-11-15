#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
autonomous_search_and_publish.py
═══════════════════════════════════════════════════════════════════════════════
SISTEMA AUTÓNOMO DE BÚSQUEDA Y PUBLICACIÓN
═══════════════════════════════════════════════════════════════════════════════

Flujo completo:
1. Selecciona keyword (por prioridad)
2. Busca ASINs en Amazon SP-API
3. Filtra por marcas/categorías prohibidas
4. Guarda ASINs en asins.txt
5. Ejecuta pipeline de publicación (mainglobal.py)
6. Espera X minutos y repite

Características:
✅ Loop infinito (hasta emergency stop)
✅ Filtrado inteligente de marcas/categorías
✅ Tracking de métricas y progreso
✅ Logs detallados
✅ Manejo de errores robusto
✅ Límites de publicación diaria

Uso:
    python scripts/autonomous/autonomous_search_and_publish.py [--dry-run] [--max-cycles N]
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple

# Añadir src y scripts al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))
sys.path.insert(0, str(project_root / 'scripts'))

from autonomous.keyword_manager import KeywordManager
from autonomous.brand_filter import ProductFilter
from autonomous.product_quality_analyzer import ProductQualityAnalyzer
from tools.search_asins_by_keyword import search_products_by_keyword
from integrations.amazon_pricing import get_prime_offers_batch_optimized

# Importar notificador de búsqueda
try:
    from tools.telegram_search_notifier import (
        notify_search_start,
        notify_search_phase,
        notify_search_complete,
        notify_search_error,
        notify_cycle_start,
        notify_cycle_complete,
        is_configured as search_notifier_configured
    )
    SEARCH_NOTIFIER_AVAILABLE = True
except ImportError:
    SEARCH_NOTIFIER_AVAILABLE = False
    def notify_search_start(*args, **kwargs): pass
    def notify_search_phase(*args, **kwargs): pass
    def notify_search_complete(*args, **kwargs): pass
    def notify_search_error(*args, **kwargs): pass
    def notify_cycle_start(*args, **kwargs): pass
    def notify_cycle_complete(*args, **kwargs): pass
    def search_notifier_configured(): return False

class AutonomousSystem:
    """
    Sistema autónomo de búsqueda y publicación
    """

    def __init__(self, config_file: str = "config/autonomous_config.json"):
        """
        Inicializa el sistema autónomo

        Args:
            config_file: Ruta al archivo de configuración
        """
        self.config_file = Path(config_file)
        self.config = self._load_config()

        # Componentes
        self.keyword_manager = KeywordManager()
        self.product_filter = ProductFilter()
        self.quality_analyzer = ProductQualityAnalyzer()

        # Configuraciones
        self.autonomous_config = self.config.get("autonomous_mode", {})
        self.search_config = self.config.get("search_settings", {})
        self.publish_config = self.config.get("publication_settings", {})
        self.filter_config = self.config.get("filtering", {})
        self.log_config = self.config.get("logging", {})
        self.safety_config = self.config.get("safety", {})

        # Estado
        self.cycle_count = 0
        self.total_asins_searched = 0
        self.total_asins_published = 0
        self.total_asins_rejected = 0
        self.consecutive_errors = 0
        self.start_time = datetime.now()

        # Archivos
        self.log_file = Path(self.log_config.get("log_file", "storage/autonomous_logs/autonomous_system.log"))
        self.metrics_file = Path(self.log_config.get("metrics_file", "storage/autonomous_logs/metrics.json"))
        self.rejected_file = Path(self.log_config.get("rejected_asins_file", "storage/autonomous_logs/rejected_asins.json"))
        self.emergency_stop_file = Path(self.safety_config.get("emergency_stop_file", "storage/STOP_AUTONOMOUS"))

        # Crear directorios
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        self.log("═══════════════════════════════════════════════════════════")
        self.log("🤖 SISTEMA AUTÓNOMO DE BÚSQUEDA Y PUBLICACIÓN INICIADO")
        self.log("═══════════════════════════════════════════════════════════")

    def _load_config(self) -> dict:
        """Carga la configuración del sistema"""
        if not self.config_file.exists():
            raise FileNotFoundError(f"No se encontró {self.config_file}")

        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def log(self, message: str, level: str = "INFO", keyword: str = None):
        """
        Escribe un mensaje en el log

        Args:
            message: Mensaje a loggear
            level: Nivel de log (INFO, WARNING, ERROR)
            keyword: Keyword actual (opcional, se muestra al inicio)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Agregar keyword al inicio si existe
        if keyword:
            log_line = f"[{timestamp}] [{level}] [{keyword}] {message}"
        else:
            log_line = f"[{timestamp}] [{level}] {message}"

        print(log_line)

        # Escribir al archivo
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_line + "\n")

    def should_stop(self) -> bool:
        """
        Verifica si se debe detener el sistema

        Returns:
            bool: True si se debe detener
        """
        # Emergency stop file
        if self.emergency_stop_file.exists():
            self.log("🛑 EMERGENCY STOP detectado - Deteniendo sistema", "WARNING")
            return True

        # Límite de errores consecutivos
        max_errors = self.safety_config.get("max_consecutive_errors", 10)
        if self.consecutive_errors >= max_errors:
            self.log(f"🛑 Máximo de errores consecutivos alcanzado ({max_errors}) - Deteniendo", "ERROR")
            return True

        # Límite de publicaciones diarias
        max_daily = self.autonomous_config.get("max_publications_per_day", 500)
        if self.total_asins_published >= max_daily:
            self.log(f"✅ Límite diario de publicaciones alcanzado ({max_daily})", "INFO")
            return True

        return False

    def filter_asins_by_brand_quick(self, asins: List[str]) -> Tuple[List[str], List[dict]]:
        """
        Filtra ASINs por blacklist de ASINs previamente rechazados.

        Este filtro es RÁPIDO porque:
        1. Solo verifica contra la blacklist local (sin API calls)
        2. Verifica solo si el ASIN ya fue rechazado antes
        3. NO obtiene datos completos del producto (eso se hace después si necesario)

        NOTA: El filtro completo de marcas se hace DESPUÉS de ordenar por BSR,
        solo sobre los ASINs top seleccionados (para optimizar API calls).

        Args:
            asins: Lista de ASINs a filtrar

        Returns:
            Tuple[list, list]: (asins_permitidos, asins_rechazados)
        """
        if not self.filter_config.get("enable_brand_blacklist", True):
            self.log("⚠️ Filtrado de marcas deshabilitado - Todos los ASINs pasan")
            return asins, []

        allowed = []
        rejected = []

        # Cargar ASINs previamente rechazados (blacklist local)
        blacklisted_asins = set()
        if self.rejected_file.exists():
            try:
                with open(self.rejected_file, 'r', encoding='utf-8') as f:
                    rejected_data = json.load(f)
                    blacklisted_asins = {item.get("asin") for item in rejected_data if item.get("asin")}
            except Exception as e:
                self.log(f"⚠️ No se pudo cargar rejected_asins.json: {e}", "WARNING")

        # Verificar contra blacklist
        for asin in asins:
            if asin in blacklisted_asins:
                rejected.append({
                    "asin": asin,
                    "reason": "ASIN en blacklist (previamente rechazado)"
                })
            else:
                allowed.append(asin)

        return allowed, rejected

    def filter_asins_by_brand_batch(self, asins: List[str]) -> Tuple[List[str], List[dict]]:
        """
        Filtra ASINs por marcas prohibidas usando BATCH API de Amazon.
        Procesa 20 ASINs por llamada (50x más rápido que individual).

        Args:
            asins: Lista de ASINs a filtrar

        Returns:
            Tuple[list, list]: (asins_permitidos, asins_rechazados)
        """
        from integrations.amazon_api import get_products_batch

        if not self.filter_config.get("enable_brand_blacklist", True):
            self.log("⚠️ Filtrado de marcas deshabilitado - Todos los ASINs pasan")
            return asins, []

        allowed = []
        rejected = []

        # Procesar en batches de 20 ASINs
        batch_size = 20
        total_batches = (len(asins) + batch_size - 1) // batch_size

        for batch_num, i in enumerate(range(0, len(asins), batch_size), 1):
            batch = asins[i:i+batch_size]

            self.log(f"   Batch {batch_num}/{total_batches}: Verificando {len(batch)} ASINs...")

            try:
                # Obtener datos de 20 ASINs en 1 sola llamada
                products_data = get_products_batch(batch, include_data="summaries")

                # Filtrar cada producto
                for asin in batch:
                    product_data = products_data.get(asin)

                    if not product_data:
                        rejected.append({"asin": asin, "reason": "No se pudo obtener info"})
                        continue

                    # Verificar con ProductFilter
                    is_ok, reason = self.product_filter.is_allowed(asin, product_data)

                    if is_ok:
                        allowed.append(asin)
                    else:
                        rejected.append({"asin": asin, "reason": reason})

            except Exception as e:
                self.log(f"⚠️ Error en batch {batch_num}: {e}", "WARNING")
                # Rechazar todo el batch en caso de error
                for asin in batch:
                    rejected.append({"asin": asin, "reason": f"Error batch: {str(e)[:50]}"})

            # Delay entre batches
            if i + batch_size < len(asins):
                import time
                time.sleep(2)

        return allowed, rejected

    def apply_quality_multiplier(self, asins: List[str], quality_analysis: dict) -> List[str]:
        """
        Aplica multiplicador de calidad para seleccionar cantidad óptima de ASINs.

        Args:
            asins: Lista de ASINs (ya filtrados por marcas y ordenados por BSR)
            quality_analysis: Análisis de calidad de la keyword

        Returns:
            list: ASINs seleccionados según calidad
        """
        target_pubs = self.autonomous_config.get("target_publications_per_keyword", 60)
        recommended_count = self.quality_analyzer.get_recommended_asin_count(
            quality_analysis,
            total_found=len(asins),
            apply_main2_multiplier=True,
            target_publications=target_pubs
        )

        # Mostrar explicación
        recommendation = quality_analysis.get("recommendation", "skip")
        if recommendation == "publish_all":
            self.log(f"   ⭐ EXCELENTE keyword - Pasar MUCHOS ASINs para aprovechar al máximo")
        elif recommendation == "publish_most":
            self.log(f"   ✅ BUENA keyword - Pasar cantidad normal")
        elif recommendation == "publish_some":
            self.log(f"   ⚠️ REGULAR keyword - Pasar MENOS ASINs (ser selectivo)")
        else:
            self.log(f"   ❌ BAJA keyword - Pasar MUY POCOS (solo los mejores)")

        # Seleccionar top N
        selected = asins[:min(recommended_count, len(asins))]

        return selected

    def filter_prime_asins(self, asins: List[str]) -> List[str]:
        """
        Filtra ASINs para quedarse SOLO con los que tienen Amazon Prime + Fast Fulfillment.

        Este filtro se aplica TEMPRANO en el proceso, antes de ordenar por BSR,
        para evitar procesar productos que de todos modos no vamos a publicar.

        Filtros aplicados (desde amazon_pricing.py):
        - Prime + FBA + precio válido
        - availabilityType = "NOW" con maximumHours ≤ 24
        - O availabilityType = "FUTURE_WITH_DATE" con ≤7 días
        - Rechaza backorders largos y productos sin fecha

        Args:
            asins: Lista de ASINs a filtrar

        Returns:
            list: Lista de ASINs que tienen oferta Prime válida con fast fulfillment
        """
        if not asins:
            return []

        self.log(f"⭐ Filtrando {len(asins)} ASINs por Amazon Prime + Fast Fulfillment...")
        self.log(f"   Filtros: Prime + FBA + availabilityType=NOW + maximumHours≤24h")
        self.log(f"   Usando endpoint BATCH optimizado (4x más rápido)")

        # Obtener ofertas Prime en batch optimizado (20 ASINs por request)
        prime_offers = get_prime_offers_batch_optimized(asins, batch_size=20, show_progress=True)

        # Filtrar solo ASINs con oferta Prime válida
        prime_asins = [
            asin for asin, offer in prime_offers.items()
            if offer is not None and offer.get("is_prime") and offer.get("price", 0) > 0
        ]

        # Contar rechazos y razones
        rejected = len(asins) - len(prime_asins)

        self.log(f"✅ Filtro Prime + Fast Fulfillment completado:")
        self.log(f"   ✅ Aceptados: {len(prime_asins)}/{len(asins)} ASINs")
        self.log(f"   ❌ Rechazados: {rejected} ASINs")

        if rejected > 0:
            # Mostrar algunos ejemplos de rechazos (máximo 5)
            rejected_asins = [
                asin for asin, offer in prime_offers.items()
                if offer is None or not offer.get("is_prime") or offer.get("price", 0) <= 0
            ]

            if rejected_asins:
                self.log(f"   📋 Razones de rechazo (primeros 5 ejemplos):")
                for asin in rejected_asins[:5]:
                    offer = prime_offers.get(asin)
                    if offer is None:
                        self.log(f"      • {asin}: Rechazado por filtro fast fulfillment")
                        self.log(f"        (backorder >7d, maxHours >24h, o sin fecha)")
                    elif not offer.get("is_prime"):
                        self.log(f"      • {asin}: No es Prime")
                    elif offer.get("price", 0) <= 0:
                        self.log(f"      • {asin}: Sin precio válido")

        return prime_asins

    def search_asins_for_keyword(self, keyword_data: dict) -> List[str]:
        """
        Busca ASINs para una keyword.

        FLUJO OPTIMIZADO PARA CAPTAR LOS MEJORES PRODUCTOS:
        1. Buscar MUCHOS ASINs (500-1000) para tener un pool grande
        2. ✅ Filtrar por MARCAS PROHIBIDAS primero (rápido, sin API)
        3. ✅ Filtrar por Prime (ya solo procesamos marcas permitidas)
        4. Luego en run_cycle() se ordenan por BSR y se seleccionan los mejores

        Args:
            keyword_data: Datos de la keyword

        Returns:
            list: Lista de ASINs filtrados (marcas OK + Prime) sin ordenar por BSR
        """
        keyword = keyword_data.get("keyword")

        # CAMBIO CRÍTICO: Buscar MUCHOS más ASINs para tener pool grande
        # Antes: max_asins_per_search = 100 (10 páginas)
        # Ahora: Buscamos 50-100 páginas = 500-1000 ASINs
        initial_search_pages = keyword_data.get("initial_search_pages", 50)

        self.log(f"🔍 Buscando ASINs para keyword: '{keyword}'")
        self.log(f"   Estrategia: Buscar {initial_search_pages} páginas (~{initial_search_pages * 10} ASINs)")
        self.log(f"   → Filtrar marcas → Filtrar Prime+Fast Fulfillment → Ordenar por BSR")

        # Notificar inicio de búsqueda
        if SEARCH_NOTIFIER_AVAILABLE and search_notifier_configured():
            notify_search_start(keyword, initial_search_pages * 10)

        try:
            # 1. Buscar MUCHOS ASINs (pool grande para tener opciones)
            self.log(f"   [1/4] Buscando ASINs en Amazon...")
            asins = search_products_by_keyword(keyword, max_pages=initial_search_pages, log_callback=self.log)
            self.log(f"   ✅ Encontrados {len(asins)} ASINs totales")

            # Notificar fase de búsqueda completada
            if SEARCH_NOTIFIER_AVAILABLE and search_notifier_configured():
                notify_search_phase("Búsqueda", len(asins), f"{initial_search_pages} páginas")

            if not asins:
                self.log(f"   ⚠️ No se encontraron ASINs para '{keyword}'")
                return []

            # 2. 🔥 FILTRAR POR MARCAS PROHIBIDAS CON BATCH API
            # Usa endpoint batch de Amazon (20 ASINs por request) - 50x más rápido que individual
            self.log(f"   [2/4] Filtrando por marcas prohibidas (usando BATCH API)...")
            self.log(f"   (Procesa 20 ASINs por llamada - mucho más rápido que individual)")

            allowed_asins, rejected_asins = self.filter_asins_by_brand_batch(asins)

            self.log(f"   ✅ Filtro de marcas: {len(allowed_asins)}/{len(asins)} ASINs permitidos")
            if len(rejected_asins) > 0:
                self.log(f"   ⏭️  {len(rejected_asins)} ASINs rechazados (marcas prohibidas/categorías/keywords)")

            # Notificar fase de filtrado de marcas
            if SEARCH_NOTIFIER_AVAILABLE and search_notifier_configured():
                brand_ratio = len(allowed_asins) / len(asins) * 100 if asins else 0
                notify_search_phase("Filtrado", len(allowed_asins), f"{brand_ratio:.0f}% aprobadas")

            if not allowed_asins:
                self.log(f"   ⚠️ Todos los ASINs fueron rechazados por marcas prohibidas")
                if SEARCH_NOTIFIER_AVAILABLE and search_notifier_configured():
                    notify_search_error(keyword, "Todas las marcas rechazadas")
                return []

            # 3. FILTRAR PRIME + FAST FULFILLMENT (ahora solo sobre ASINs de marcas permitidas)
            # Esto asegura que SOLO procesamos productos Prime con fast fulfillment de marcas OK
            self.log(f"   [3/4] Filtrando por Amazon Prime + Fast Fulfillment...")
            prime_asins = self.filter_prime_asins(allowed_asins)

            # Notificar fase de Prime
            if SEARCH_NOTIFIER_AVAILABLE and search_notifier_configured():
                prime_ratio = len(prime_asins) / len(allowed_asins) * 100 if allowed_asins else 0
                notify_search_phase("Prime", len(prime_asins), f"{prime_ratio:.0f}% con Prime")

            if not prime_asins:
                self.log(f"   ⚠️ Ningún ASIN con Prime encontrado para '{keyword}'")
                return []

            self.log(f"   ✅ {len(prime_asins)} ASINs con Prime (de {len(allowed_asins)} marcas OK)")
            self.log(f"   📊 Ratio Prime: {len(prime_asins)/len(allowed_asins)*100:.1f}%")
            self.log(f"   📊 Aprovechamiento total: {len(prime_asins)}/{len(asins)} = {len(prime_asins)/len(asins)*100:.1f}%")

            # 4. Retornar ASINs filtrados (serán ordenados por BSR en run_cycle)
            return prime_asins

        except Exception as e:
            self.log(f"❌ Error buscando ASINs para '{keyword}': {e}", "ERROR")
            self.consecutive_errors += 1
            return []

    def rank_asins_by_bsr(self, asins: List[str], top_n: int = 100, keyword: str = None) -> List[str]:
        """
        Ordena ASINs por BSR (Best Seller Rank) y retorna los top N más vendidos

        Args:
            asins: Lista de ASINs a ordenar
            top_n: Cantidad de ASINs top a retornar
            keyword: Keyword actual (opcional, para logs)

        Returns:
            list: Top N ASINs ordenados por BSR (menor = más vendido)
        """
        from integrations.amazon_api import get_product_bsr_only

        self.log(f"   Obteniendo BSR para ordenar por ventas...", keyword=keyword)
        self.log(f"   Esto tomará ~{len(asins) * 2 // 60} minutos (2s por ASIN)", keyword=keyword)

        asins_with_bsr = []

        # Procesar en batches
        batch_size = 10
        total_batches = (len(asins) + batch_size - 1) // batch_size

        for batch_num, i in enumerate(range(0, len(asins), batch_size), 1):
            batch = asins[i:i+batch_size]

            self.log(f"   Batch {batch_num}/{total_batches}: Obteniendo BSR de {len(batch)} ASINs...", keyword=keyword)

            for asin in batch:
                try:
                    bsr = get_product_bsr_only(asin)

                    if bsr:
                        asins_with_bsr.append({"asin": asin, "bsr": bsr})

                    # Delay entre requests
                    time.sleep(2)

                except Exception as e:
                    self.log(f"⚠️ Error obteniendo BSR de {asin}: {e}", "WARNING", keyword=keyword)

            # Delay entre batches
            if i + batch_size < len(asins):
                time.sleep(10)

        # Ordenar por BSR (menor = más vendido = primero)
        asins_with_bsr.sort(key=lambda x: x["bsr"])

        # Tomar los top N
        top_asins = [item["asin"] for item in asins_with_bsr[:top_n]]

        self.log(f"✅ Ranking completado: {len(asins_with_bsr)} ASINs con BSR → Seleccionados top {len(top_asins)}", keyword=keyword)

        if top_asins:
            self.log(f"   🏆 Mejor BSR: {asins_with_bsr[0]['bsr']} (ASIN: {asins_with_bsr[0]['asin']})", keyword=keyword)
            if len(asins_with_bsr) > 1:
                self.log(f"   📉 Peor BSR del top: {asins_with_bsr[min(len(top_asins)-1, len(asins_with_bsr)-1)]['bsr']}", keyword=keyword)

        return top_asins

    def analyze_keyword_quality_from_asins(self, asins: List[str], keyword: str, sample_size: int = 20) -> dict:
        """
        Analiza la calidad de una keyword obteniendo datos de una muestra de ASINs.

        IMPORTANTE: Se ejecuta ANTES de ordenar por BSR para evitar sesgo.

        Args:
            asins: Lista de ASINs (ya filtrados por Prime)
            keyword: Keyword que se está analizando
            sample_size: Cantidad de ASINs a analizar (default: 20)

        Returns:
            dict: Análisis de calidad con score, tier, recomendación
        """
        import random
        from integrations.amazon_api import get_product_data_from_asin

        # Tomar muestra random (evitar sesgo)
        sample = random.sample(asins, min(sample_size, len(asins)))

        self.log(f"   Obteniendo datos de {len(sample)} ASINs random para análisis...")

        products_data = []
        for i, asin in enumerate(sample, 1):
            try:
                data = get_product_data_from_asin(asin)
                if data:
                    products_data.append(data)

                # Delay entre requests
                if i < len(sample):
                    import time
                    time.sleep(2)

            except Exception as e:
                self.log(f"   ⚠️ Error obteniendo datos de {asin}: {str(e)[:50]}", "WARNING")
                continue

        if not products_data:
            self.log(f"   ❌ No se pudo obtener datos de ningún ASIN", "ERROR")
            return {"avg_score": 0, "recommendation": "skip", "quality_tier": "VERY_LOW"}

        # Analizar calidad
        analysis = self.quality_analyzer.analyze_keyword_quality(products_data, sample_size=len(products_data))

        return analysis

    def filter_by_brands_and_apply_multiplier(self, asins: List[str], keyword: str, quality_analysis: dict) -> Tuple[List[str], List[dict]]:
        """
        Filtra por marcas prohibidas y aplica multiplicador según calidad.

        Args:
            asins: Lista de ASINs (ya ordenados por BSR)
            keyword: Keyword
            quality_analysis: Resultado del análisis de calidad

        Returns:
            Tuple[list, list]: (asins_permitidos, asins_rechazados)
        """
        from integrations.amazon_api import get_product_data_from_asin

        self.log(f"🔍 Filtrando {len(asins)} ASINs por marca...")

        allowed_products = []
        rejected = []

        # Procesar en batches
        batch_size = 10
        for batch_num, i in enumerate(range(0, len(asins), batch_size), 1):
            batch = asins[i:i+batch_size]

            for asin in batch:
                try:
                    product_data = get_product_data_from_asin(asin)

                    if not product_data:
                        rejected.append({"asin": asin, "reason": "No se pudo obtener info"})
                        continue

                    # Filtro de marca
                    is_ok, reason = self.product_filter.is_allowed(asin, product_data)

                    if is_ok:
                        product_data["asin"] = asin
                        allowed_products.append(product_data)
                    else:
                        rejected.append({"asin": asin, "reason": reason, "product": product_data.get("title", "")})

                    import time
                    time.sleep(2)

                except Exception as e:
                    self.log(f"⚠️ Error filtrando {asin}: {str(e)[:50]}", "WARNING")
                    rejected.append({"asin": asin, "reason": f"Error: {str(e)[:50]}"})

            # Delay entre batches
            if i + batch_size < len(asins):
                import time
                time.sleep(10)

        self.log(f"✅ Filtro de marcas: {len(allowed_products)} permitidos, {len(rejected)} rechazados")

        if not allowed_products:
            return [], rejected

        # Ordenar por calidad (mejores primero)
        sorted_products = self.quality_analyzer.sort_asins_by_quality(allowed_products)

        # Aplicar multiplicador según calidad de keyword
        target_pubs = self.autonomous_config.get("target_publications_per_keyword", 60)
        recommended_count = self.quality_analyzer.get_recommended_asin_count(
            quality_analysis,
            total_found=len(sorted_products),
            apply_main2_multiplier=True,
            target_publications=target_pubs
        )

        # Mostrar explicación
        recommendation = quality_analysis.get("recommendation", "skip")
        if recommendation == "publish_all":
            self.log(f"   ⭐ EXCELENTE keyword - Pasar MUCHOS ASINs para aprovechar al máximo")
            expected = int(recommended_count * 0.85)
        elif recommendation == "publish_most":
            self.log(f"   ✅ BUENA keyword - Pasar cantidad normal")
            expected = int(recommended_count * 0.75)
        elif recommendation == "publish_some":
            self.log(f"   ⚠️ REGULAR keyword - Pasar MENOS ASINs (ser selectivo)")
            expected = int(recommended_count * 0.65)
        else:
            self.log(f"   ❌ BAJA keyword - Pasar MUY POCOS (solo los mejores)")
            expected = int(recommended_count * 0.50)

        self.log(f"💡 Pasar {recommended_count} ASINs a main2 → ~{expected} publicados esperados")

        # Seleccionar top N
        selected_products = sorted_products[:recommended_count]

        # Agregar rechazados los que no se seleccionaron
        if recommended_count < len(sorted_products):
            skipped = sorted_products[recommended_count:]
            for p in skipped:
                rejected.append({
                    "asin": p.get("asin"),
                    "reason": f"No seleccionado (solo top {recommended_count} por calidad)",
                    "product": p.get("title", "")
                })

        # Extraer solo ASINs
        final_asins = [p.get("asin") for p in selected_products]

        return final_asins, rejected

    def filter_and_analyze_asins(self, asins: List[str], keyword: str) -> Tuple[List[str], List[dict], dict]:
        """
        Filtra ASINs por marca/categoría Y analiza calidad para determinar cuántos publicar

        Args:
            asins: Lista de ASINs a filtrar
            keyword: Keyword que se está procesando

        Returns:
            Tuple[list, list, dict]: (asins_permitidos_ordenados, asins_rechazados, quality_analysis)
        """
        if not self.filter_config.get("enable_brand_blacklist", True):
            self.log("⚠️ Filtrado de marcas deshabilitado - Todos los ASINs pasan")
            return asins, [], {"avg_score": 0, "recommendation": "publish_all"}

        self.log(f"🔍 Filtrando {len(asins)} ASINs por marca/categoría...")
        self.log(f"   Procesando en batches de 10 para evitar rate limit...")

        allowed_products = []
        rejected = []

        # Procesar en batches de 10 para evitar rate limit
        batch_size = 10
        for batch_num, i in enumerate(range(0, len(asins), batch_size), 1):
            batch = asins[i:i+batch_size]
            self.log(f"   Batch {batch_num}/{(len(asins) + batch_size - 1) // batch_size}: Procesando {len(batch)} ASINs...")

            for asin in batch:
                try:
                    # Obtener info del producto desde Amazon
                    from integrations.amazon_api import get_product_data_from_asin

                    product_data = get_product_data_from_asin(asin)

                    if not product_data:
                        rejected.append({"asin": asin, "reason": "No se pudo obtener info del producto"})
                        continue

                    # Filtro de marca/categoría
                    is_ok, reason = self.product_filter.is_allowed(asin, product_data)

                    if is_ok:
                        # Agregar ASIN con datos completos para análisis de calidad
                        product_data["asin"] = asin
                        allowed_products.append(product_data)
                    else:
                        rejected.append({"asin": asin, "reason": reason, "product": product_data.get("title", "")})

                    # Delay entre requests dentro del batch
                    time.sleep(2)  # 2 segundos entre cada request

                except Exception as e:
                    error_msg = str(e)
                    # Si es rate limit (429), esperar más tiempo
                    if "429" in error_msg or "QuotaExceeded" in error_msg:
                        self.log(f"⏱️ Rate limit detectado, esperando 30 segundos...", "WARNING")
                        time.sleep(30)
                        # Reintentar este ASIN
                        try:
                            product_data = get_product_data_from_asin(asin)
                            if product_data:
                                is_ok, reason = self.product_filter.is_allowed(asin, product_data)
                                if is_ok:
                                    product_data["asin"] = asin
                                    allowed_products.append(product_data)
                                else:
                                    rejected.append({"asin": asin, "reason": reason, "product": product_data.get("title", "")})
                        except:
                            rejected.append({"asin": asin, "reason": f"Rate limit - No se pudo procesar"})
                    else:
                        self.log(f"⚠️ Error al filtrar ASIN {asin}: {e}", "WARNING")
                        rejected.append({"asin": asin, "reason": f"Error: {e}"})

            # Delay entre batches (10 segundos)
            if i + batch_size < len(asins):
                self.log(f"   Esperando 10 segundos antes del siguiente batch...")
                time.sleep(10)

        self.log(f"✅ Filtrado completado: {len(allowed_products)} permitidos, {len(rejected)} rechazados")

        # Si no hay productos permitidos, retornar vacío
        if not allowed_products:
            return [], rejected, {"avg_score": 0, "recommendation": "skip"}

        # Analizar calidad de la keyword
        self.log(f"🧠 Analizando calidad de productos para '{keyword}'...")
        quality_analysis = self.quality_analyzer.analyze_keyword_quality(allowed_products, sample_size=20)

        self.log(f"   Score promedio: {quality_analysis['avg_score']:.1f}/100")
        self.log(f"   Tier de calidad: {quality_analysis['quality_tier']}")
        self.log(f"   Recomendación: {quality_analysis['recommendation'].upper()}")

        # Ordenar productos por calidad (mejores primero)
        sorted_products = self.quality_analyzer.sort_asins_by_quality(allowed_products)

        # Determinar cuántos ASINs pasar a main2 basado en calidad
        # LÓGICA: Keywords excelentes → PASAR MÁS (aprovechar mina de oro)
        #         Keywords regulares → PASAR MENOS (no vale la pena)
        target_pubs = self.autonomous_config.get("target_publications_per_keyword", 60)
        recommended_count = self.quality_analyzer.get_recommended_asin_count(
            quality_analysis,
            total_found=len(sorted_products),
            apply_main2_multiplier=True,
            target_publications=target_pubs
        )

        # Mostrar explicación de la lógica
        recommendation = quality_analysis.get("recommendation", "skip")
        if recommendation == "publish_all":
            self.log(f"   ⭐ EXCELENTE keyword - Pasar MUCHOS ASINs para aprovechar al máximo")
            expected_pubs = int(recommended_count * 0.85)
        elif recommendation == "publish_most":
            self.log(f"   ✅ BUENA keyword - Pasar cantidad normal")
            expected_pubs = int(recommended_count * 0.75)
        elif recommendation == "publish_some":
            self.log(f"   ⚠️ REGULAR keyword - Pasar MENOS ASINs (ser selectivo)")
            expected_pubs = int(recommended_count * 0.65)
        elif recommendation == "publish_few":
            self.log(f"   ❌ BAJA keyword - Pasar MUY POCOS (solo los mejores)")
            expected_pubs = int(recommended_count * 0.50)
        else:
            expected_pubs = 0

        self.log(f"💡 Pasar {recommended_count} ASINs a main2 → ~{expected_pubs} publicados esperados")

        # Seleccionar solo los mejores N productos
        selected_products = sorted_products[:recommended_count]

        # Extraer solo ASINs (ya ordenados por calidad)
        final_asins = [p.get("asin") for p in selected_products]

        # Agregar a rechazados los productos que no se pasarán a main2
        if recommended_count < len(sorted_products):
            skipped_products = sorted_products[recommended_count:]
            for p in skipped_products:
                rejected.append({
                    "asin": p.get("asin"),
                    "reason": f"No seleccionado (solo top {recommended_count} por calidad)",
                    "product": p.get("title", "")
                })

        return final_asins, rejected, quality_analysis

    def save_asins_to_file(self, asins: List[str], file_path: str = "asins.txt"):
        """
        Guarda ASINs en archivo

        Args:
            asins: Lista de ASINs
            file_path: Ruta del archivo
        """
        output_file = Path(file_path)

        # Limpiar archivo si está configurado
        if self.publish_config.get("clear_asins_file_before_cycle", True):
            mode = 'w'
        else:
            mode = 'a'

        with open(output_file, mode, encoding='utf-8') as f:
            for asin in asins:
                f.write(f"{asin}\n")

        self.log(f"💾 {len(asins)} ASINs guardados en {file_path}")

    def count_publications_from_log(self) -> int:
        """
        Lee el log de main2.py y cuenta publicaciones exitosas

        Returns:
            int: Cantidad de publicaciones exitosas encontradas en el log
        """
        log_file = project_root / "logs" / "Main2_(Publicación).log"

        if not log_file.exists():
            self.log("⚠️ Log de main2.py no encontrado", "WARNING")
            return 0

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Contar líneas con "✅ Publicado en:"
            publications = content.count("✅ Publicado en:")

            self.log(f"📊 Conteo del log: {publications} publicaciones encontradas")
            return publications

        except Exception as e:
            self.log(f"❌ Error leyendo log de main2.py: {e}", "ERROR")
            return 0

    def run_publication_pipeline(self) -> int:
        """
        Ejecuta el pipeline de publicación (mainglobal.py)

        Returns:
            int: Cantidad de publicaciones exitosas (estimado)
        """
        pipeline_script = self.publish_config.get("pipeline_script", "src/integrations/mainglobal.py")
        timeout_minutes = self.publish_config.get("pipeline_timeout_minutes", 60)
        timeout_seconds = timeout_minutes * 60

        self.log(f"🚀 Ejecutando pipeline de publicación: {pipeline_script}")
        self.log(f"   Timeout: {timeout_minutes} minutos")

        try:
            # Ejecutar pipeline
            result = subprocess.run(
                [sys.executable, pipeline_script],
                timeout=timeout_seconds,
                capture_output=True,
                text=True,
                cwd=str(project_root)
            )

            # Parsear output para contar publicaciones exitosas
            output = result.stdout + result.stderr
            successful = output.count("✅ Publicado exitosamente") + output.count("Published successfully")

            if result.returncode == 0:
                self.log(f"✅ Pipeline completado exitosamente (~{successful} publicaciones)")
                self.consecutive_errors = 0
            else:
                self.log(f"⚠️ Pipeline terminó con código {result.returncode}", "WARNING")
                self.consecutive_errors += 1

            return successful

        except subprocess.TimeoutExpired:
            self.log(f"⏱️ Pipeline excedió timeout de {timeout_minutes} minutos", "WARNING")
            self.consecutive_errors += 1
            return 0

        except Exception as e:
            self.log(f"❌ Error ejecutando pipeline: {e}", "ERROR")
            self.consecutive_errors += 1
            return 0

    def save_metrics(self):
        """Guarda métricas del sistema"""
        metrics = {
            "last_updated": datetime.now().isoformat(),
            "uptime_minutes": (datetime.now() - self.start_time).seconds // 60,
            "cycle_count": self.cycle_count,
            "total_asins_searched": self.total_asins_searched,
            "total_asins_published": self.total_asins_published,
            "total_asins_rejected": self.total_asins_rejected,
            "consecutive_errors": self.consecutive_errors,
            "keyword_stats": self.keyword_manager.get_stats(),
            "filter_stats": self.product_filter.get_stats()
        }

        with open(self.metrics_file, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

    def run_cycle(self, dry_run: bool = False) -> bool:
        """
        Ejecuta un ciclo completo de búsqueda y publicación

        Args:
            dry_run: Si es True, no ejecuta el pipeline (solo búsqueda y filtrado)

        Returns:
            bool: True si el ciclo fue exitoso
        """
        self.cycle_count += 1

        self.log("\n" + "═"*60)
        self.log(f"🔄 CICLO #{self.cycle_count}")
        self.log("═"*60)

        # 1. Obtener siguiente keyword
        keyword_data = self.keyword_manager.get_next_keyword()

        if not keyword_data:
            self.log("❌ No hay keywords disponibles", "ERROR")
            return False

        keyword = keyword_data.get("keyword")

        # 1.5. NUEVO: Agregar configuración de búsqueda al keyword_data
        # Esto permite que search_asins_for_keyword use initial_search_pages del config
        keyword_data["initial_search_pages"] = self.search_config.get("initial_search_pages", 50)

        # 2. Buscar ASINs (muchos) y filtrar Prime
        asins = self.search_asins_for_keyword(keyword_data)

        if not asins:
            self.log("⚠️ No se encontraron ASINs para esta keyword", "WARNING", keyword=keyword)
            self.keyword_manager.mark_as_searched(keyword_data, asins_found=0, successful_publications=0)
            return False

        self.total_asins_searched += len(asins)

        # 3. NUEVO: ANALIZAR CALIDAD ANTES DE ORDENAR POR BSR
        # Tomamos muestra RANDOM de TODOS los ASINs para tener análisis representativo
        # Esto evita sesgo de solo analizar primeros resultados (que suelen ser mejores)
        self.log(f"🧠 Analizando calidad...", keyword=keyword)
        self.log(f"   Estrategia: Muestra random de TODOS los ASINs Prime ({len(asins)} totales)", keyword=keyword)
        self.log(f"   Esto da análisis más realista incluyendo productos de todas las posiciones", keyword=keyword)

        # Tomar muestra random para análisis (máx 100 ASINs para evaluar)
        import random
        sample_size_for_analysis = min(100, len(asins))
        asins_for_analysis = random.sample(asins, sample_size_for_analysis)

        quality_analysis = self.analyze_keyword_quality_from_asins(asins_for_analysis, keyword)

        if not quality_analysis or quality_analysis.get("recommendation") == "skip":
            self.log(f"❌ Calidad muy baja, saltando...", "WARNING", keyword=keyword)
            self.keyword_manager.mark_as_searched(keyword_data, asins_found=len(asins), successful_publications=0)
            return False

        # 4. Según calidad, decidir cuántos ASINs tomar por BSR
        recommendation = quality_analysis.get("recommendation", "publish_some")
        if recommendation == "publish_all":
            top_n_bsr = 150  # Keyword excelente → tomar más
        elif recommendation == "publish_most":
            top_n_bsr = 100  # Keyword buena → cantidad normal
        elif recommendation == "publish_some":
            top_n_bsr = 75   # Keyword regular → menos
        else:  # publish_few
            top_n_bsr = 50   # Keyword baja → muy pocos

        self.log(f"   Tier: {quality_analysis.get('quality_tier')}", keyword=keyword)
        self.log(f"   Score: {quality_analysis.get('avg_score', 0):.1f}/100", keyword=keyword)
        self.log(f"   Decisión: Tomar top {top_n_bsr} por BSR", keyword=keyword)

        # 5. Ordenar por BSR y tomar top N según calidad
        enable_bsr_ranking = self.search_config.get("enable_bsr_ranking", True)

        if enable_bsr_ranking and len(asins) > top_n_bsr:
            self.log(f"📊 Ordenando {len(asins)} ASINs por BSR y tomando top {top_n_bsr}...", keyword=keyword)
            final_asins = self.rank_asins_by_bsr(asins, top_n=top_n_bsr, keyword=keyword)
        else:
            self.log(f"⏭️ Saltando ranking por BSR (pocos ASINs o ranking deshabilitado)", keyword=keyword)
            final_asins = asins[:top_n_bsr]  # Tomar primeros N

        # Calcular publicaciones esperadas (main2 rechaza ~27%)
        expected_publications = int(len(final_asins) * 0.73)

        self.log(f"✅ {len(final_asins)} ASINs finales listos para publicar", keyword=keyword)
        self.log(f"💡 Publicaciones esperadas: ~{expected_publications} (main2 rechaza ~27%)", keyword=keyword)

        # Notificar resumen completo de búsqueda
        if SEARCH_NOTIFIER_AVAILABLE and search_notifier_configured():
            stats = {
                "total_found": len(asins) if 'asins' in locals() else 0,
                "filtered_brands": len(final_asins),
                "prime_count": len(asins) if 'asins' in locals() else 0,
                "quality": quality_analysis.get("quality_tier", "N/A")
            }
            notify_search_complete(keyword, len(final_asins), stats)

        if not final_asins:
            self.log("❌ No hay ASINs disponibles después del ranking", "WARNING", keyword=keyword)
            self.keyword_manager.mark_as_searched(keyword_data, asins_found=len(asins), successful_publications=0)
            if SEARCH_NOTIFIER_AVAILABLE and search_notifier_configured():
                notify_search_error(keyword, "Sin ASINs después del ranking")
            return False

        # 6. Guardar ASINs permitidos
        asins_file = self.publish_config.get("asins_file", "asins.txt")
        self.save_asins_to_file(final_asins, asins_file)

        # 5. Ejecutar pipeline (si no es dry-run Y si está habilitado)
        successful_publications = 0
        use_pipeline = self.publish_config.get("use_existing_pipeline", True)

        if dry_run:
            self.log("🧪 DRY-RUN: Saltando ejecución del pipeline")
            successful_publications = len(final_asins)  # Simulación
        elif not use_pipeline:
            self.log("⏭️  Pipeline deshabilitado - ASINs guardados en asins.txt")
            self.log(f"   pipeline.py se encargará de publicarlos")
            # Leer conteo real del log de main2.py (si existe)
            successful_publications = self.count_publications_from_log()
        else:
            successful_publications = self.run_publication_pipeline()

        self.total_asins_published += successful_publications

        # 6. Actualizar keyword con resultados
        self.keyword_manager.mark_as_searched(
            keyword_data,
            asins_found=len(asins),
            successful_publications=successful_publications
        )

        # 7. Guardar métricas
        self.save_metrics()

        # 8. Resumen del ciclo
        self.log("\n📊 RESUMEN DEL CICLO:")
        self.log(f"   Keyword:              {keyword}")
        self.log(f"   ASINs encontrados:    {len(asins)} (Prime + marcas OK)")
        self.log(f"   ASINs seleccionados:  {len(final_asins)} (top por BSR)")
        self.log(f"   Quality Score:        {quality_analysis.get('avg_score', 0):.1f}/100 ({quality_analysis.get('quality_tier', 'N/A')})")
        self.log(f"   Publicaciones esp.:   ~{expected_publications} (main2 rechaza ~27%)")
        self.log(f"   Publicaciones reales: {successful_publications}")
        self.log("═"*60)

        return True

    def run(self, max_cycles: int = None, dry_run: bool = False):
        """
        Ejecuta el sistema autónomo en loop infinito

        Args:
            max_cycles: Máximo de ciclos (None = infinito)
            dry_run: Si es True, no ejecuta el pipeline
        """
        cycle_delay_minutes = self.autonomous_config.get("cycle_delay_minutes", 30)

        self.log(f"⚙️ Configuración:")
        self.log(f"   Delay entre ciclos: {cycle_delay_minutes} minutos")
        self.log(f"   Máx ciclos:         {max_cycles or 'Infinito'}")
        self.log(f"   Dry-run:            {dry_run}")
        self.log(f"   Emergency stop:     {self.emergency_stop_file}")

        while True:
            # Verificar si se debe detener
            if self.should_stop():
                break

            # Verificar límite de ciclos
            if max_cycles and self.cycle_count >= max_cycles:
                self.log(f"✅ Límite de ciclos alcanzado ({max_cycles})")
                break

            # Ejecutar ciclo
            try:
                success = self.run_cycle(dry_run=dry_run)

                if not success:
                    self.log("⚠️ Ciclo no exitoso, esperando antes del siguiente...", "WARNING")

            except Exception as e:
                self.log(f"❌ Error inesperado en el ciclo: {e}", "ERROR")
                self.consecutive_errors += 1

            # Esperar antes del siguiente ciclo
            if max_cycles is None or self.cycle_count < max_cycles:
                self.log(f"\n⏱️ Esperando {cycle_delay_minutes} minutos antes del siguiente ciclo...")
                time.sleep(cycle_delay_minutes * 60)

        # Sistema detenido
        self.log("\n═══════════════════════════════════════════════════════════")
        self.log("🛑 SISTEMA AUTÓNOMO DETENIDO")
        self.log("═══════════════════════════════════════════════════════════")
        self.log(f"📊 ESTADÍSTICAS FINALES:")
        self.log(f"   Ciclos completados:       {self.cycle_count}")
        self.log(f"   ASINs buscados:           {self.total_asins_searched}")
        self.log(f"   ASINs publicados:         {self.total_asins_published}")
        self.log(f"   ASINs rechazados:         {self.total_asins_rejected}")
        self.log(f"   Tiempo total:             {(datetime.now() - self.start_time).seconds // 60} minutos")
        self.log("═══════════════════════════════════════════════════════════")

        # Imprimir stats de componentes
        self.keyword_manager.print_stats()
        self.product_filter.print_stats()


# ═══════════════════════════════════════════════════════════════════════════
# CLI Mode
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sistema autónomo de búsqueda y publicación")
    parser.add_argument("--dry-run", action="store_true", help="Modo prueba (no ejecuta pipeline)")
    parser.add_argument("--max-cycles", "-n", type=int, help="Máximo de ciclos (default: infinito)")
    parser.add_argument("--config", "-c", default="config/autonomous_config.json", help="Archivo de configuración")

    args = parser.parse_args()

    try:
        system = AutonomousSystem(args.config)
        system.run(max_cycles=args.max_cycles, dry_run=args.dry_run)

    except KeyboardInterrupt:
        print("\n\n🛑 Sistema detenido por usuario (Ctrl+C)")
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
