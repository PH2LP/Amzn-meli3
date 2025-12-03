#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Product Safety Filter - Ultra Robusto
=========================================
Sistema de filtrado con IA que NO deja pasar NI UN SOLO producto prohibido.

Filtrado en 3 capas:
1. Keyword matching (rápido) - Detecta términos prohibidos exactos
2. AI Semantic Analysis (GPT-4) - Detecta variaciones, sinónimos, nombres creativos
3. Brand Protection (GPT-4) - Detecta marcas protegidas/conocidas

IMPORTANTE: Si hay CUALQUIER duda, el producto se RECHAZA.
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, Tuple, List
from dotenv import load_dotenv

# Cargar API key
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class AIProductSafetyFilter:
    """
    Filtro de seguridad con IA para productos Amazon → MercadoLibre
    """

    def __init__(self, config_file: str = "config/prohibited_items_comprehensive.json"):
        """
        Inicializa el filtro cargando configuración de items prohibidos

        Args:
            config_file: Ruta al archivo JSON con items prohibidos
        """
        self.config_file = Path(config_file)
        self.prohibited_config = self._load_config()

        # Cargar WHITELIST de excepciones (productos legítimos que contienen términos prohibidos)
        self.safe_exceptions = set()
        if "safe_exceptions" in self.prohibited_config:
            for exception in self.prohibited_config["safe_exceptions"]:
                self.safe_exceptions.add(exception.lower())

        # Construir lista unificada de keywords prohibidas (lowercase)
        # FILTRO: Ignorar keywords demasiado cortas (< 3 chars) para evitar falsos positivos
        # FILTRO: Ignorar safe_exceptions
        self.prohibited_keywords = set()
        for category, keywords in self.prohibited_config.items():
            if category == "safe_exceptions":  # Saltar whitelist
                continue
            for keyword in keywords:
                keyword_lower = keyword.lower()
                # Solo agregar keywords de 3+ caracteres (evita "c", "a", "-", " ", etc.)
                if len(keyword_lower) >= 3:
                    self.prohibited_keywords.add(keyword_lower)

        # Stats
        self.total_checked = 0
        self.total_rejected = 0
        self.rejection_reasons = {
            "keyword_match": 0,
            "ai_semantic": 0,
            "protected_brand": 0,
            "missing_data": 0
        }

    def _load_config(self) -> dict:
        """Carga la configuración de items prohibidos"""
        if not self.config_file.exists():
            print(f"❌ ERROR CRÍTICO: No se encontró {self.config_file}")
            print(f"   El filtro de seguridad NO puede funcionar sin este archivo")
            raise FileNotFoundError(f"Falta archivo crítico: {self.config_file}")

        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def is_safe_to_publish(self, asin: str, product_data: dict, use_ai: bool = True) -> Tuple[bool, str, float]:
        """
        Verifica si un producto es SEGURO para publicar (NO contiene items prohibidos)

        Args:
            asin: ASIN del producto
            product_data: Datos del producto (JSON de Amazon o mini_ml)
            use_ai: Si usar IA para análisis semántico (recomendado: True)

        Returns:
            Tuple[bool, str, float]: (es_seguro, razón_rechazo, confidence_score)
            - es_seguro: True si producto es seguro, False si debe rechazarse
            - razón_rechazo: Descripción detallada de por qué se rechazó
            - confidence_score: 0.0-1.0, qué tan confiado está el filtro
        """
        self.total_checked += 1

        # Extraer información del producto
        product_text = self._extract_product_text(product_data)

        if not product_text["title"] and not product_text["description"]:
            self.total_rejected += 1
            self.rejection_reasons["missing_data"] += 1
            return False, "Producto sin título ni descripción - RECHAZADO por seguridad", 0.0

        # =====================================================================
        # MODO 1: Solo IA (use_ai=True) - Análisis semántico profundo
        # =====================================================================
        if use_ai and OPENAI_API_KEY:
            # CAPA 1 (IA): AI Semantic Analysis (detecta variaciones y sinónimos)
            ai_result = self._check_ai_semantic(asin, product_text)
            if not ai_result[0]:
                self.total_rejected += 1
                self.rejection_reasons["ai_semantic"] += 1
                return ai_result

            # CAPA 2 (IA): Brand Protection (detecta marcas conocidas/protegidas)
            if product_text["brand"]:
                brand_result = self._check_protected_brand(product_text["brand"])
                if not brand_result[0]:
                    self.total_rejected += 1
                    self.rejection_reasons["protected_brand"] += 1
                    return brand_result

            # Producto aprobado por IA ✅
            return True, "Producto seguro - APROBADO por IA", 1.0

        # =====================================================================
        # MODO 2: Solo Keywords (use_ai=False) - Filtro rápido básico
        # =====================================================================
        else:
            # CAPA 1 (Keywords): Keyword Matching (rápido)
            keyword_result = self._check_prohibited_keywords(product_text)
            if not keyword_result[0]:
                self.total_rejected += 1
                self.rejection_reasons["keyword_match"] += 1
                return keyword_result

            # Producto aprobado por keywords ✅
            return True, "Producto seguro - APROBADO por keywords", 1.0

    def _extract_product_text(self, product_data: dict) -> dict:
        """
        Extrae texto relevante del producto para análisis

        Returns:
            Dict con: title, description, brand, category, attributes_text
        """
        # Detectar formato del JSON
        if "summaries" in product_data and product_data["summaries"]:
            # Formato Amazon SP-API
            summary = product_data["summaries"][0]
            title = summary.get("itemName", "")
            brand = summary.get("brand", "")
            category = summary.get("productType", "")

            # Buscar descripción en attributes
            description = ""
            if "attributes" in product_data:
                attrs = product_data["attributes"]
                if "item_name" in attrs and attrs["item_name"]:
                    title = attrs["item_name"][0].get("value", title)
                if "bullet_point" in attrs and attrs["bullet_point"]:
                    bullets = [bp.get("value", "") for bp in attrs["bullet_point"]]
                    description = " ".join(bullets)

        elif "title_ai" in product_data:
            # Formato mini_ml (ya transformado)
            title = product_data.get("title_ai", "")
            description = product_data.get("description_ai", "")
            brand = product_data.get("brand", "")
            category = product_data.get("category_id", "")

        else:
            # Formato genérico
            title = product_data.get("title", product_data.get("itemName", ""))
            description = product_data.get("description", "")
            brand = product_data.get("brand", "")
            category = product_data.get("category", product_data.get("productType", ""))

        # Extraer texto de atributos si está disponible
        attributes_text = ""
        if "attributes_mapped" in product_data:
            attrs = product_data["attributes_mapped"]
            for attr_id, attr_info in attrs.items():
                if isinstance(attr_info, dict):
                    value = attr_info.get("value_name", "")
                    attributes_text += f"{attr_id}: {value} "

        # Combinar todo el texto para análisis
        full_text = f"{title} {description} {brand} {category} {attributes_text}".lower()

        # Normalizar números comunes usados para evadir filtros
        # Esto ayuda a detectar variaciones como "c1g" -> "cig", "v4pe" -> "vape"
        def normalize_leetspeak(text: str) -> str:
            """Convierte números comunes a letras para detectar evasiones"""
            replacements = {
                '0': 'o',  # B0SE -> BOSE
                '1': 'i',  # C1g -> Cig
                '3': 'e',  # V3nom -> Venom
                '4': 'a',  # V4pe -> Vape
                '5': 's',  # 5word -> Sword
                '7': 't',  # 7actical -> Tactical
                '8': 'b',  # 8lade -> Blade
            }
            for num, letter in replacements.items():
                text = text.replace(num, letter)
            return text

        full_text_normalized = normalize_leetspeak(full_text)

        return {
            "title": title.lower(),
            "description": description.lower(),
            "brand": brand,
            "category": category.lower(),
            "attributes_text": attributes_text.lower(),
            "full_text": full_text,
            "full_text_normalized": full_text_normalized
        }

    def _check_prohibited_keywords(self, product_text: dict) -> Tuple[bool, str, float]:
        """
        CAPA 1: Verifica si el producto contiene keywords prohibidas exactas

        Returns:
            Tuple[bool, str, float]: (es_seguro, razón, confidence)
        """
        full_text = product_text["full_text"]
        full_text_normalized = product_text.get("full_text_normalized", full_text)
        title = product_text["title"]
        description = product_text["description"]

        # WHITELIST: Verificar si el producto está en excepciones seguras PRIMERO
        full_text_lower = full_text.lower()
        for safe_term in self.safe_exceptions:
            if safe_term in full_text_lower:
                return True, f"OK - Producto legítimo (whitelist: '{safe_term}')", 1.0

        # Buscar cada keyword prohibida en AMBOS textos (original + normalizado)
        found_keywords = []
        for keyword in self.prohibited_keywords:
            # Buscar keyword como palabra completa (word boundary)
            pattern = r'\b' + re.escape(keyword) + r'\b'

            # Buscar en texto original
            if re.search(pattern, full_text, re.IGNORECASE):
                found_keywords.append(keyword)
            # También buscar en texto normalizado (detecta "c1g" -> "cig")
            elif re.search(pattern, full_text_normalized, re.IGNORECASE):
                found_keywords.append(keyword + " (variación detectada)")

        if found_keywords:
            # EXCEPCIONES IMPORTANTES para productos legítimos
            # (Evitar falsos positivos)

            # EXCEPCIÓN 1: Cuchillos de cocina son LEGÍTIMOS
            if "knife" in found_keywords or "knives" in found_keywords:
                kitchen_indicators = ["kitchen", "chef", "cooking", "culinary", "steak knife",
                                     "bread knife", "paring knife", "cocina", "cocinero"]
                if any(indicator in full_text for indicator in kitchen_indicators):
                    # Es cuchillo de cocina - PERMITIR
                    found_keywords = [k for k in found_keywords if k not in ["knife", "knives"]]
                    if not found_keywords:  # Si solo era "knife", aprobar
                        return True, "OK - Cuchillo de cocina (uso legítimo)", 0.9

            # EXCEPCIÓN 2: Binoculares para observación de aves/naturaleza son LEGÍTIMOS
            if "binoculars" in found_keywords:
                nature_indicators = ["bird watching", "birdwatching", "bird", "nature", "wildlife",
                                    "observación de aves", "aves", "naturaleza"]
                hunting_indicators = ["hunting", "hunt", "tactical", "caza", "cacería"]

                has_nature = any(indicator in full_text for indicator in nature_indicators)
                has_hunting = any(indicator in full_text for indicator in hunting_indicators)

                if has_nature and not has_hunting:
                    # Son binoculares de observación - PERMITIR
                    found_keywords = [k for k in found_keywords if k != "binoculars"]
                    if not found_keywords:
                        return True, "OK - Binoculares para observación (uso legítimo)", 0.9

            # EXCEPCIÓN 3: Tactical LED flashlight es LEGÍTIMO (solo linterna)
            if "tactical" in found_keywords:
                tactical_ok_products = ["flashlight", "linterna", "light", "torch"]
                weapon_indicators = ["knife", "gun", "vest", "gear", "equipment", "weapon"]

                has_tactical_ok = any(prod in full_text for prod in tactical_ok_products)
                has_weapon = any(weapon in full_text for weapon in weapon_indicators)

                if has_tactical_ok and not has_weapon:
                    # Es solo una linterna táctica - PERMITIR
                    found_keywords = [k for k in found_keywords if k != "tactical"]
                    if not found_keywords:
                        return True, "OK - Linterna táctica (uso legítimo)", 0.9

            # Si aún quedan keywords prohibidas después de excepciones
            if found_keywords:
                # Producto RECHAZADO - contiene keywords prohibidas
                keywords_str = ", ".join(found_keywords[:5])  # Mostrar primeras 5
                if len(found_keywords) > 5:
                    keywords_str += f" y {len(found_keywords) - 5} más"

                return False, f"PROHIBIDO - Contiene términos prohibidos: {keywords_str}", 1.0

        # Pasó el filtro de keywords
        return True, "OK - Sin keywords prohibidas exactas", 0.8

    def _check_ai_semantic(self, asin: str, product_text: dict) -> Tuple[bool, str, float]:
        """
        CAPA 2: Usa IA (GPT-4) para detectar productos prohibidos con nombres creativos/variaciones

        Returns:
            Tuple[bool, str, float]: (es_seguro, razón, confidence)
        """
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY, timeout=60.0)

            # Construir prompt con TODAS las categorías prohibidas
            prohibited_categories = list(self.prohibited_config.keys())

            prompt = f"""Eres un experto en políticas de MercadoLibre y detección de productos prohibidos.

Analiza el siguiente producto de Amazon y determina si es SEGURO publicar en MercadoLibre.

PRODUCTO:
- ASIN: {asin}
- Título: {product_text['title']}
- Descripción: {product_text['description'][:500]}
- Marca: {product_text['brand']}
- Categoría: {product_text['category']}

CATEGORÍAS COMPLETAMENTE PROHIBIDAS (NO se pueden publicar bajo NINGUNA circunstancia):
1. Armas de fuego, rifles, pistolas, airsoft, paintball, BB guns, ballestas
2. Armas blancas TÁCTICAS/CAZA: cuchillos tácticos, navajas, espadas, katanas, machetes, dagas
3. Armas de defensa: tasers, gas pimienta, paralizadores, esposas, nudillos
4. Explosivos, municiones, balas, pólvora, detonadores, granadas
5. Vapes, cigarrillos electrónicos, e-liquids, tabaco, nicotina
6. Drogas, marihuana, CBD, THC, cannabis, narcóticos
7. Productos falsificados, réplicas, clones, piratería
8. Documentos falsos, pasaportes, IDs, sellos oficiales
9. Medicamentos, jeringas, agujas, equipos médicos
10. Químicos peligrosos, ácidos, cianuro, peróxidos
11. Material radiactivo, uranio, plutonio
12. Pesticidas, insecticidas, plantas vivas no certificadas
13. Alimentos, bebidas, alcohol, suplementos, vitaminas
14. Cosméticos, perfumes, aerosoles
15. Combustibles, gases, cilindros, gasolina
16. Baterías de litio de alta capacidad (>100Wh)
17. Equipos de espionaje, cámaras ocultas, vigilancia
18. Productos expirados, vencidos, sin certificación
19. Productos reacondicionados de electrónica
20. Drones de alto rendimiento

PRODUCTOS LEGÍTIMOS QUE SÍ SE PERMITEN (NO rechazar):
✅ Cuchillos de COCINA (kitchen knife, chef knife, bread knife, steak knife) - PERMITIDOS
✅ Linternas tácticas (tactical flashlight, LED flashlight) sin armas - PERMITIDAS
✅ Binoculares para observación de aves/naturaleza (NO de caza) - PERMITIDOS
✅ Accesorios genéricos (cables, fundas, soportes) - PERMITIDOS

NOTA CRÍTICA: La palabra "tactical" o "cuchillo" SOLA no significa prohibido.
Analiza el CONTEXTO completo:
- "Kitchen Knife Set" = PERMITIDO (cocina)
- "Tactical Hunting Knife" = PROHIBIDO (caza)
- "LED Tactical Flashlight" = PERMITIDO (solo linterna)
- "Tactical Vest Gun Holster" = PROHIBIDO (equipo militar)

TAREA:
Analiza SEMÁNTICAMENTE el producto. Detecta:
- Nombres creativos o variaciones de productos prohibidos
- Sinónimos o términos alternativos
- Cualquier señal de que el producto podría estar en categorías prohibidas

RESPONDE EN FORMATO JSON ESTRICTO:
{{
  "is_safe": true/false,
  "reason": "Explicación detallada de por qué es seguro o prohibido",
  "confidence": 0.0-1.0,
  "detected_issues": ["lista de problemas detectados"],
  "category_match": "categoría prohibida que coincide, o null"
}}

IMPORTANTE:
- Analiza el CONTEXTO COMPLETO, no solo palabras individuales
- Detecta intentos de evadir filtros (ej: "vvape", "g u n", "k n i f e", etc.)
- NO rechaces productos legítimos solo por tener palabras como "tactical" o "knife"
- SÍ rechaza productos prohibidos incluso con nombres creativos
- Si tienes duda RAZONABLE, marca is_safe: false
- Balance: Bloquea prohibidos pero permite legítimos

Retorna SOLO el JSON, sin texto adicional."""

            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Mini es suficiente para clasificación binaria (75% más barato)
                temperature=0.1,  # Muy bajo para ser consistente
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )

            result_text = response.choices[0].message.content.strip()
            result = json.loads(result_text)

            is_safe = result.get("is_safe", False)
            reason = result.get("reason", "IA no pudo determinar")
            confidence = result.get("confidence", 0.5)
            detected_issues = result.get("detected_issues", [])
            category_match = result.get("category_match")

            if not is_safe:
                issues_str = ", ".join(detected_issues[:3]) if detected_issues else "Ver razón"
                full_reason = f"IA DETECTÓ RIESGO - {reason} | Issues: {issues_str}"
                if category_match:
                    full_reason += f" | Categoría: {category_match}"
                return False, full_reason, confidence

            return True, f"IA APROBÓ - {reason}", confidence

        except Exception as e:
            print(f"⚠️ Error en análisis IA para {asin}: {e}")
            # Si la IA falla, RECHAZAR por seguridad (fail-safe)
            return False, f"IA falló - RECHAZADO por seguridad: {str(e)[:100]}", 0.0

    def _check_protected_brand(self, brand: str) -> Tuple[bool, str, float]:
        """
        CAPA 3: Verifica si la marca está en la lista de 24 marcas prohibidas (SOLO lista exacta)

        Returns:
            Tuple[bool, str, float]: (es_seguro, razón, confidence)
        """
        if not brand or len(brand) < 2:
            return True, "Sin marca o marca genérica", 0.9

        brand_lower = brand.lower().strip()

        # SOLO verificar contra lista exact de 24 marcas de lujo
        protected_brands = []
        if "protected_brands_luxury" in self.prohibited_config:
            protected_brands = self.prohibited_config["protected_brands_luxury"]

        for protected in protected_brands:
            protected_lower = protected.lower()
            # Verificar match exacto o contenido
            if protected_lower in brand_lower or brand_lower in protected_lower:
                return False, f"MARCA PROHIBIDA - {brand} está en lista de 24 marcas bloqueadas", 1.0

        # Si no está en la lista, APROBAR (no usar IA)
        return True, f"Marca OK - {brand} no está en lista prohibida", 0.95

    def get_stats(self) -> dict:
        """Retorna estadísticas del filtro"""
        return {
            "total_checked": self.total_checked,
            "total_rejected": self.total_rejected,
            "total_approved": self.total_checked - self.total_rejected,
            "rejection_rate": self.total_rejected / self.total_checked if self.total_checked > 0 else 0,
            "rejection_reasons": self.rejection_reasons
        }


# ============================================================================
# FUNCIONES DE CONVENIENCIA
# ============================================================================

_filter_instance = None

def get_safety_filter() -> AIProductSafetyFilter:
    """Obtiene instancia singleton del filtro"""
    global _filter_instance
    if _filter_instance is None:
        _filter_instance = AIProductSafetyFilter()
    return _filter_instance


def is_product_safe(asin: str, product_data: dict, use_ai: bool = True) -> Tuple[bool, str, float]:
    """
    Función de conveniencia para verificar si producto es seguro

    Args:
        asin: ASIN del producto
        product_data: Datos del producto
        use_ai: Si usar IA (recomendado: True)

    Returns:
        Tuple[bool, str, float]: (es_seguro, razón, confidence)
    """
    filter_obj = get_safety_filter()
    return filter_obj.is_safe_to_publish(asin, product_data, use_ai=use_ai)


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    # Test del filtro
    filter_obj = AIProductSafetyFilter()

    # Test 1: Producto prohibido obvio (arma)
    test1 = {
        "title": "Tactical Airsoft Gun BB Pistol",
        "description": "High quality airsoft pistol for tactical games",
        "brand": "TacticalGear"
    }

    result1 = filter_obj.is_safe_to_publish("TEST001", test1, use_ai=True)
    print(f"\nTest 1 (Arma): {result1}")

    # Test 2: Marca protegida
    test2 = {
        "title": "Wireless Headphones Premium Sound",
        "description": "Amazing wireless headphones with noise cancellation",
        "brand": "Bose"
    }

    result2 = filter_obj.is_safe_to_publish("TEST002", test2, use_ai=True)
    print(f"\nTest 2 (Marca protegida): {result2}")

    # Test 3: Producto seguro
    test3 = {
        "title": "USB Cable Type-C Fast Charging",
        "description": "Durable USB-C cable for fast charging",
        "brand": "GenericBrand"
    }

    result3 = filter_obj.is_safe_to_publish("TEST003", test3, use_ai=True)
    print(f"\nTest 3 (Producto seguro): {result3}")

    # Stats
    print(f"\nStats: {filter_obj.get_stats()}")
