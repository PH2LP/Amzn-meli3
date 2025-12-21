#!/usr/bin/env python3
"""
Test completo del sistema de pricing con Glow API integrado
Verifica que productos que tardan >3 días sean rechazados
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.integrations.amazon_pricing import get_prime_offer

# ASINs de prueba que sabemos que tardan >3 días en Miami 33172
test_asins = [
    "B0FDWT3MXK",  # Tarda 4 días según Glow API
    "B0D9H19PBL",  # Tarda 6 días según Glow API
    "B0DJH46BBL",  # Tarda 4 días según Glow API
]

print("="*80)
print("TEST: Sistema de pricing con validación Glow API")
print("="*80)
print()
print(f"Configuración:")
print(f"  BUYER_ZIPCODE: {os.getenv('BUYER_ZIPCODE', 'NOT SET')}")
print(f"  USE_SCRAPER_VALIDATION: {os.getenv('USE_SCRAPER_VALIDATION', 'NOT SET')}")
print(f"  MAX_DELIVERY_DAYS: {os.getenv('MAX_DELIVERY_DAYS', 'NOT SET')}")
print()
print("="*80)
print()

for i, asin in enumerate(test_asins, 1):
    print(f"[{i}/{len(test_asins)}] Probando {asin}...")

    offer = get_prime_offer(asin)

    if offer:
        print(f"  ✅ ACEPTADO")
        print(f"     Precio: ${offer['price']}")
        print(f"     Validación: {offer.get('fulfillment_validation', 'N/A')}")
    else:
        print(f"  ❌ RECHAZADO - Sin oferta Prime válida")
        print(f"     (Probablemente rechazado por Glow API: tarda >3 días)")

    print()

print("="*80)
print("CONCLUSIÓN:")
print("Si USE_SCRAPER_VALIDATION=true, los productos que tardan >3 días")
print("deben ser RECHAZADOS por el Glow API.")
print("="*80)
