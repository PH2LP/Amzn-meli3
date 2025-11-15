#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
keyword_manager.py
═══════════════════════════════════════════════════════════════════════════════
Gestor inteligente de keywords para búsqueda automática

Estrategias:
1. Round-robin por prioridad (empieza con prioridad 10, luego 9, etc.)
2. Tracking de última búsqueda
3. Actualización de métricas (ASINs encontrados, tasa de éxito)
4. Enable/disable de keywords dinámicamente

Uso:
    from scripts.autonomous.keyword_manager import KeywordManager

    km = KeywordManager()
    keyword_data = km.get_next_keyword()
    km.mark_as_searched(keyword_data, asins_found=50, successful_publications=45)
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

class KeywordManager:
    """
    Gestor de keywords para búsqueda automática en Amazon
    """

    def __init__(self, config_file: str = "config/master_keywords.json"):
        """
        Inicializa el gestor de keywords

        Args:
            config_file: Ruta al archivo JSON de keywords
        """
        self.config_file = Path(config_file)

        # Si master_keywords.json no existe, usar keywords.json como fallback
        if not self.config_file.exists():
            fallback_file = Path("config/keywords.json")
            if fallback_file.exists():
                print(f"⚠️  {self.config_file} no existe, usando {fallback_file}")
                self.config_file = fallback_file

        self.config = self._load_config()

        self.keywords = self.config.get("keywords", [])
        self.strategy = self.config.get("strategy", "by_search_volume")

        # Detectar si es master_keywords.json (tiene search_volume)
        self.is_master_keywords = any("search_volume" in k for k in self.keywords[:5] if isinstance(k, dict))

        # Estado del gestor
        self.current_index = 0
        self.current_priority = self._get_max_priority()

    def _load_config(self) -> dict:
        """Carga la configuración de keywords"""
        if not self.config_file.exists():
            raise FileNotFoundError(f"No se encontró {self.config_file}")

        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_config(self):
        """Guarda la configuración actualizada"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def _get_max_priority(self) -> int:
        """Obtiene la prioridad máxima de keywords habilitadas"""
        enabled_keywords = [k for k in self.keywords if k.get("enabled", True)]
        if not enabled_keywords:
            return 0
        return max(k.get("priority", 0) for k in enabled_keywords)

    def get_next_keyword(self, strategy: str = None) -> Optional[Dict[str, Any]]:
        """
        Obtiene la siguiente keyword según la estrategia configurada

        Args:
            strategy: Estrategia a usar (None = usar la configurada)

        Returns:
            dict: Datos de la keyword o None si no hay más
        """
        strategy = strategy or self.strategy

        # Si es master_keywords.json, usar estrategia by_search_volume
        if self.is_master_keywords or strategy == "by_search_volume":
            return self._get_next_by_search_volume()
        elif strategy == "round_robin_by_priority":
            return self._get_next_by_priority()
        elif strategy == "least_recently_searched":
            return self._get_least_recently_searched()
        elif strategy == "best_success_rate":
            return self._get_best_success_rate()
        else:
            # Default: round-robin simple
            return self._get_next_round_robin()

    def _get_next_by_search_volume(self) -> Optional[Dict[str, Any]]:
        """
        Estrategia: Por search volume (de mayor a menor)
        Retorna la primera keyword NO procesada de la lista ordenada
        """
        # Las keywords ya vienen ordenadas por search_volume en master_keywords.json
        # Solo retornamos la primera que NO esté procesada

        for keyword_data in self.keywords:
            # Verificar si está habilitada (si tiene ese campo)
            if not keyword_data.get("enabled", True):
                continue

            # Verificar si ya fue procesada
            if not keyword_data.get("processed", False):
                return keyword_data

        # No hay más keywords sin procesar
        return None

    def _get_next_by_priority(self) -> Optional[Dict[str, Any]]:
        """
        Estrategia: Round-robin por prioridad
        Primero todas las de prioridad 10, luego 9, etc.
        """
        # Filtrar keywords habilitadas
        enabled = [k for k in self.keywords if k.get("enabled", True)]

        if not enabled:
            return None

        # Agrupar por prioridad
        by_priority = {}
        for k in enabled:
            priority = k.get("priority", 0)
            if priority not in by_priority:
                by_priority[priority] = []
            by_priority[priority].append(k)

        # Ordenar prioridades descendente
        priorities = sorted(by_priority.keys(), reverse=True)

        # Buscar la siguiente keyword de la prioridad actual
        if self.current_priority not in priorities:
            self.current_priority = priorities[0]

        keywords_at_priority = by_priority[self.current_priority]

        # Ciclar entre keywords de esta prioridad
        if self.current_index >= len(keywords_at_priority):
            self.current_index = 0
            # Bajar a siguiente prioridad
            current_idx = priorities.index(self.current_priority)
            if current_idx + 1 < len(priorities):
                self.current_priority = priorities[current_idx + 1]
            else:
                # Volver a empezar desde la prioridad más alta
                self.current_priority = priorities[0]
            keywords_at_priority = by_priority[self.current_priority]

        keyword_data = keywords_at_priority[self.current_index]
        self.current_index += 1

        return keyword_data

    def _get_least_recently_searched(self) -> Optional[Dict[str, Any]]:
        """Estrategia: Menos recientemente buscada"""
        enabled = [k for k in self.keywords if k.get("enabled", True)]

        if not enabled:
            return None

        # Ordenar por last_searched (None primero)
        def sort_key(k):
            last = k.get("last_searched")
            if last is None:
                return datetime.min
            return datetime.fromisoformat(last)

        sorted_keywords = sorted(enabled, key=sort_key)
        return sorted_keywords[0]

    def _get_best_success_rate(self) -> Optional[Dict[str, Any]]:
        """Estrategia: Mejor tasa de éxito"""
        enabled = [k for k in self.keywords if k.get("enabled", True)]

        if not enabled:
            return None

        # Ordenar por success_rate descendente
        sorted_keywords = sorted(enabled, key=lambda k: k.get("success_rate", 0), reverse=True)
        return sorted_keywords[0]

    def _get_next_round_robin(self) -> Optional[Dict[str, Any]]:
        """Estrategia: Round-robin simple"""
        enabled = [k for k in self.keywords if k.get("enabled", True)]

        if not enabled:
            return None

        if self.current_index >= len(enabled):
            self.current_index = 0

        keyword_data = enabled[self.current_index]
        self.current_index += 1

        return keyword_data

    def mark_as_searched(self, keyword_data: dict, asins_found: int = 0, successful_publications: int = 0):
        """
        Marca una keyword como buscada y actualiza métricas

        Args:
            keyword_data: Datos de la keyword
            asins_found: Cantidad de ASINs encontrados
            successful_publications: Cantidad de publicaciones exitosas
        """
        keyword_str = keyword_data.get("keyword")

        # Buscar la keyword en la lista
        for k in self.keywords:
            if k.get("keyword") == keyword_str:
                k["last_searched"] = datetime.now().isoformat()
                k["total_asins_found"] = k.get("total_asins_found", 0) + asins_found

                # Si es master_keywords.json, marcar como procesada y actualizar publicaciones
                if self.is_master_keywords:
                    k["processed"] = True
                    k["asins_published"] = k.get("asins_published", 0) + successful_publications
                    k["last_processed"] = datetime.now().isoformat()

                    # Actualizar totales en el config principal
                    self.config["total_publications_current"] = sum(
                        kw.get("asins_published", 0) for kw in self.keywords
                    )
                    self.config["last_updated"] = datetime.now().isoformat()

                # Calcular success_rate (para keywords.json o master_keywords.json)
                total_asins = k.get("total_asins_found", 0)
                if total_asins > 0:
                    # Estimar success_rate basado en esta búsqueda
                    current_success_rate = (successful_publications / asins_found) if asins_found > 0 else 0
                    # Promedio móvil simple
                    old_rate = k.get("success_rate", 0)
                    k["success_rate"] = round((old_rate + current_success_rate) / 2, 2)
                else:
                    k["success_rate"] = 0

                break

        # Guardar cambios
        self._save_config()

    def disable_keyword(self, keyword: str):
        """
        Deshabilita una keyword

        Args:
            keyword: Keyword a deshabilitar
        """
        for k in self.keywords:
            if k.get("keyword") == keyword:
                k["enabled"] = False
                break

        self._save_config()

    def enable_keyword(self, keyword: str):
        """
        Habilita una keyword

        Args:
            keyword: Keyword a habilitar
        """
        for k in self.keywords:
            if k.get("keyword") == keyword:
                k["enabled"] = True
                break

        self._save_config()

    def add_keyword(self, keyword: str, category: str, priority: int = 5, max_asins: int = 50):
        """
        Agrega una nueva keyword

        Args:
            keyword: Keyword a agregar
            category: Categoría
            priority: Prioridad (1-10)
            max_asins: Máximo de ASINs por búsqueda
        """
        new_keyword = {
            "keyword": keyword,
            "category": category,
            "priority": priority,
            "max_asins_per_search": max_asins,
            "enabled": True,
            "last_searched": None,
            "total_asins_found": 0,
            "success_rate": 0
        }

        self.keywords.append(new_keyword)
        self._save_config()

    def get_stats(self) -> dict:
        """
        Obtiene estadísticas generales de keywords

        Returns:
            dict: Estadísticas
        """
        enabled = [k for k in self.keywords if k.get("enabled", True)]
        disabled = [k for k in self.keywords if not k.get("enabled", True)]

        total_asins = sum(k.get("total_asins_found", 0) for k in self.keywords)
        avg_success_rate = sum(k.get("success_rate", 0) for k in enabled) / len(enabled) if enabled else 0

        return {
            "total_keywords": len(self.keywords),
            "enabled_keywords": len(enabled),
            "disabled_keywords": len(disabled),
            "total_asins_found": total_asins,
            "avg_success_rate": round(avg_success_rate, 2),
            "strategy": self.strategy
        }

    def print_stats(self):
        """Imprime estadísticas de keywords"""
        stats = self.get_stats()

        print("\n" + "="*60)
        print("📊 ESTADÍSTICAS DE KEYWORDS")
        print("="*60)
        print(f"Total keywords:      {stats['total_keywords']}")
        print(f"Habilitadas:         {stats['enabled_keywords']}")
        print(f"Deshabilitadas:      {stats['disabled_keywords']}")
        print(f"ASINs encontrados:   {stats['total_asins_found']}")
        print(f"Tasa éxito promedio: {stats['avg_success_rate']:.1f}%")
        print(f"Estrategia:          {stats['strategy']}")
        print("="*60)

        # Top 5 keywords por éxito
        enabled = [k for k in self.keywords if k.get("enabled", True)]
        top_keywords = sorted(enabled, key=lambda k: k.get("success_rate", 0), reverse=True)[:5]

        if top_keywords:
            print("\n🏆 Top 5 Keywords (por tasa de éxito):")
            for i, k in enumerate(top_keywords, 1):
                print(f"  {i}. {k['keyword']} ({k.get('success_rate', 0):.1f}% éxito)")

        print("="*60)


# ═══════════════════════════════════════════════════════════════════════════
# CLI Mode
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gestor de keywords")
    parser.add_argument("--next", action="store_true", help="Obtener siguiente keyword")
    parser.add_argument("--stats", action="store_true", help="Mostrar estadísticas")
    parser.add_argument("--list", action="store_true", help="Listar todas las keywords")
    parser.add_argument("--add", nargs=4, metavar=("KEYWORD", "CATEGORY", "PRIORITY", "MAX_ASINS"), help="Agregar keyword")
    parser.add_argument("--enable", metavar="KEYWORD", help="Habilitar keyword")
    parser.add_argument("--disable", metavar="KEYWORD", help="Deshabilitar keyword")

    args = parser.parse_args()

    km = KeywordManager()

    if args.next:
        next_kw = km.get_next_keyword()
        if next_kw:
            print(f"\n🔍 Siguiente keyword: {next_kw['keyword']}")
            print(f"   Categoría: {next_kw.get('category')}")
            print(f"   Prioridad: {next_kw.get('priority')}")
            print(f"   Max ASINs: {next_kw.get('max_asins_per_search')}")
        else:
            print("\n❌ No hay keywords disponibles")

    elif args.stats:
        km.print_stats()

    elif args.list:
        print("\n📋 Keywords configuradas:")
        for k in km.keywords:
            status = "✅" if k.get("enabled", True) else "❌"
            print(f"{status} {k['keyword']} (prioridad: {k.get('priority')}, categoría: {k.get('category')})")

    elif args.add:
        keyword, category, priority, max_asins = args.add
        km.add_keyword(keyword, category, int(priority), int(max_asins))
        print(f"✅ Keyword '{keyword}' agregada")

    elif args.enable:
        km.enable_keyword(args.enable)
        print(f"✅ Keyword '{args.enable}' habilitada")

    elif args.disable:
        km.disable_keyword(args.disable)
        print(f"❌ Keyword '{args.disable}' deshabilitada")

    else:
        parser.print_help()
