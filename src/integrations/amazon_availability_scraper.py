#!/usr/bin/env python3
"""
Amazon Availability Scraper - Wrapper para usar Glow API
Verifica disponibilidad REAL de productos en Amazon.com usando la API interna Glow
porque la SP-API no respeta el parámetro de zipcode

VENTAJAS sobre scraping básico:
- 4x más rápido (~3-5s vs 15-20s con Selenium)
- Respeta zipcode correctamente
- Detecta fechas de Prime sin login
- No requiere Chrome/ChromeDriver
"""
import os
from typing import Dict
from .amazon_glow_api import check_real_availability_glow_api


def check_real_availability(asin: str, zipcode: str = None) -> Dict:
    """
    Verifica disponibilidad REAL de un producto en Amazon.com
    usando la API interna Glow de Amazon.

    Args:
        asin: ASIN del producto
        zipcode: Zipcode del comprador (default: desde .env BUYER_ZIPCODE)

    Returns:
        Dict con:
        {
            "available": bool,  # Si está disponible para compra
            "delivery_date": str,  # Fecha estimada de entrega (ej: "Wednesday, December 24")
            "days_until_delivery": int,  # Días hasta la entrega
            "is_fast_delivery": bool,  # True si llega en ≤3 días
            "prime_available": bool,  # True si tiene badge Prime
            "in_stock": bool,  # True si dice "In Stock"
            "price": float,  # Precio del producto
            "error": str or None  # Error si hubo problema
        }
    """
    # Usar Glow API para verificación rápida y precisa
    return check_real_availability_glow_api(asin, zipcode)


def validate_fast_fulfillment_scraper(asin: str, max_delivery_days: int = 3, sp_api_price: float = None) -> tuple[bool, str]:
    """
    Valida que un ASIN tenga fast fulfillment REAL usando Glow API.

    Esta función es llamada desde amazon_pricing.py cuando USE_SCRAPER_VALIDATION=true

    Args:
        asin: ASIN del producto
        max_delivery_days: Máximo días de entrega permitidos (default: 3)
        sp_api_price: Precio del SP-API para validación cruzada (opcional)

    Returns:
        Tuple (is_valid: bool, reason: str)
        - (True, "Llega en X días") si cumple
        - (False, "Tarda X días") si no cumple
    """
    # Obtener zipcode desde .env
    zipcode = os.getenv("BUYER_ZIPCODE", "33172")

    # Llamar a Glow API
    result = check_real_availability(asin, zipcode)

    # VALIDACIÓN CRUZADA DE PRECIO (si se provee)
    # Para asegurar que estamos viendo la misma oferta
    if sp_api_price and result.get("price"):
        glow_price = result.get("price")

        # Permitir hasta 6% de diferencia (precios pueden variar ligeramente)
        price_diff = abs(sp_api_price - glow_price) / sp_api_price

        if price_diff > 0.06:  # >6% diferencia
            # Probablemente están viendo ofertas diferentes
            return (False, f"Precios no coinciden: SP-API=${sp_api_price:.2f} vs Glow=${glow_price:.2f} (diferencia {price_diff*100:.1f}%)")

    # Verificar errores
    if result.get("error"):
        error = result["error"]
        # Si el error es "Out of stock", rechazar
        if "out of stock" in error.lower():
            return (False, "Sin stock")
        # Otros errores - aceptar con advertencia para no bloquear flujo
        return (True, f"Warning: {error[:50]}")

    # Verificar disponibilidad
    if not result.get("available") or not result.get("in_stock"):
        return (False, "No disponible o sin stock")

    # Verificar días de entrega
    days = result.get("days_until_delivery")

    if days is None:
        # No pudimos obtener fecha de entrega - rechazar por seguridad
        return (False, "No se pudo determinar tiempo de entrega")

    if days <= max_delivery_days:
        # ✅ Cumple fast fulfillment
        delivery_date = result.get("delivery_date", "")
        is_prime = result.get("prime_available", False)
        prime_label = " (Prime)" if is_prime else ""
        return (True, f"Llega en {days}d ({delivery_date}){prime_label}")
    else:
        # ❌ Tarda demasiado
        delivery_date = result.get("delivery_date", "")
        return (False, f"Tarda {days}d ({delivery_date}) >{max_delivery_days}d")


if __name__ == "__main__":
    # Test
    import sys

    test_asin = sys.argv[1] if len(sys.argv) > 1 else "B0FDWT3MXK"

    print("=" * 80)
    print(f"TEST: Verificando disponibilidad REAL de {test_asin}")
    print("=" * 80)
    print()

    result = check_real_availability(test_asin)

    print("Resultados:")
    print(f"  Disponible: {result['available']}")
    print(f"  In Stock: {result['in_stock']}")
    print(f"  Prime: {result['prime_available']}")
    print(f"  Fecha entrega: {result['delivery_date']}")
    print(f"  Días hasta entrega: {result['days_until_delivery']}")
    print(f"  Fast delivery (≤3d): {result['is_fast_delivery']}")
    if result['error']:
        print(f"  Error: {result['error']}")

    print()
    is_valid, reason = validate_fast_fulfillment_scraper(test_asin, max_delivery_days=3)
    print(f"Validación Fast Fulfillment: {is_valid}")
    print(f"Razón: {reason}")
