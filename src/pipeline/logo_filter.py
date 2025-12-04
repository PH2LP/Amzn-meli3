#!/usr/bin/env python3
"""
logo_filter.py - Filtrado de imágenes con logos de marca
═══════════════════════════════════════════════════════════════════════════════
Sistema de detección ultra estricto de logos de marca en imágenes usando GPT-4 Vision.

Solo elimina imágenes que contengan logos GRANDES y CLAROS en el producto principal.
Ignora: texto de compatibilidad, logos en el fondo, formas de productos sin branding.

Author: Pipeline v2.0
Date: 2025-01-03
"""

import os
import json
import re
from typing import List, Dict, Optional
from openai import OpenAI

class LogoFilter:
    """Filtro de logos en imágenes usando GPT-4 Vision"""

    def __init__(self):
        """Inicializa el cliente OpenAI"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY no configurada")

        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o"  # GPT-4 Vision
        self.confidence_threshold = 0.75

    def analyze_image(self, image_url: str) -> Dict:
        """
        Analiza una imagen para detectar logos de marca.

        Args:
            image_url: URL de la imagen a analizar

        Returns:
            Dict con análisis: {
                "has_logos": bool,
                "should_remove": bool,
                "logos_detected": list,
                "reasoning": str,
                "confidence": float
            }
        """

        prompt = """Analyze this product image for trademarked brand logos.

⚠️ ULTRA STRICT RULES:

✅ DETECT THESE (report as logos):
- Apple logo symbol (🍎) on the actual product
- PlayStation logo/symbol on the console/controller itself
- Xbox logo on hardware
- Samsung logo text on device
- Brand text directly printed/embossed on the main product
- Game title logos IF they are the main focus of the image

❌ IGNORE THESE (do NOT report):
- Compatibility text: "for PS5", "for iPad", "compatible with"
- Product shapes without visible branding
- Small background items (game boxes, devices in background)
- Generic connectors, ports, cables
- Text descriptions or specifications
- Packaging text in background

FOCUS: Only report logos that are LARGE, CLEAR, and on the MAIN product being sold.

Background items (like game boxes on a shelf) should be IGNORED unless they dominate the image.

Respond in JSON:
{
  "has_logos": true/false,
  "logos_detected": [
    {
      "brand": "brand name",
      "type": "symbol" or "text",
      "location": "on main product" or "background",
      "size": "large" or "small",
      "what_exactly": "what you see",
      "should_flag": true/false,
      "confidence": 0.0-1.0
    }
  ],
  "overall_confidence": 0.0-1.0,
  "recommendation": "keep" or "remove",
  "reasoning": "why you decided this"
}

Only recommend "remove" if should_flag=true for ANY logo with confidence >= 0.75"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url, "detail": "high"}
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.1
            )

            result_text = response.choices[0].message.content.strip()

            # Extraer JSON de la respuesta
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(0))

                # Procesar resultado
                logos = analysis.get('logos_detected', [])
                flagged_logos = [l for l in logos if l.get('should_flag', False)]

                return {
                    "has_logos": analysis.get('has_logos', False),
                    "should_remove": analysis.get('recommendation') == 'remove',
                    "logos_detected": flagged_logos,
                    "reasoning": analysis.get('reasoning', ''),
                    "confidence": analysis.get('overall_confidence', 0),
                    "raw_response": analysis
                }
            else:
                return {
                    "has_logos": False,
                    "should_remove": False,
                    "logos_detected": [],
                    "reasoning": "No se pudo parsear respuesta",
                    "confidence": 0,
                    "error": "No JSON in response"
                }

        except Exception as e:
            return {
                "has_logos": False,
                "should_remove": False,
                "logos_detected": [],
                "reasoning": f"Error: {str(e)[:100]}",
                "confidence": 0,
                "error": str(e)
            }

    def filter_images(self, images: List[Dict], product_title: str = "") -> Dict:
        """
        Filtra lista de imágenes eliminando las que contienen logos.

        Args:
            images: Lista de dicts con {"url": "...", ...}
            product_title: Título del producto (para contexto)

        Returns:
            Dict con:
                - filtered_images: Lista de imágenes limpias
                - removed_count: Número de imágenes eliminadas
                - analysis_details: Detalles del análisis por imagen
        """

        if not images:
            return {
                "filtered_images": [],
                "removed_count": 0,
                "analysis_details": []
            }

        filtered = []
        removed = []
        analysis_details = []

        for i, img in enumerate(images):
            url = img.get('url', '')

            if not url:
                filtered.append(img)
                continue

            # Analizar imagen
            analysis = self.analyze_image(url)

            analysis_details.append({
                "index": i,
                "url": url[:60],
                "should_remove": analysis['should_remove'],
                "logos": [l.get('brand') for l in analysis['logos_detected']],
                "reasoning": analysis['reasoning'],
                "confidence": analysis['confidence']
            })

            if analysis['should_remove']:
                removed.append(img)
            else:
                filtered.append(img)

        # Seguridad: mantener al menos la primera imagen
        if not filtered and images:
            filtered = [images[0]]
            analysis_details[0]['forced_keep'] = True

        return {
            "filtered_images": filtered,
            "removed_count": len(removed),
            "kept_count": len(filtered),
            "analysis_details": analysis_details
        }


# Función helper para uso directo
def filter_product_images(images: List[Dict], product_title: str = "") -> List[Dict]:
    """
    Filtra imágenes de producto eliminando las que contienen logos.

    Args:
        images: Lista de imágenes con estructura [{"url": "...", ...}, ...]
        product_title: Título del producto (opcional, para contexto)

    Returns:
        Lista filtrada de imágenes sin logos
    """

    # Si no hay OPENAI_API_KEY, retornar todas las imágenes sin filtrar
    if not os.getenv("OPENAI_API_KEY"):
        return images

    try:
        filter_obj = LogoFilter()
        result = filter_obj.filter_images(images, product_title)
        return result['filtered_images']
    except Exception as e:
        # En caso de error, retornar imágenes originales
        print(f"[logo_filter] Error: {e}")
        return images


if __name__ == "__main__":
    # Test básico
    test_images = [
        {"url": "https://m.media-amazon.com/images/I/71LlZKF47sL.jpg"}
    ]

    result = filter_product_images(test_images, "Teclado para iPad")
    print(f"Imágenes filtradas: {len(result)}")
