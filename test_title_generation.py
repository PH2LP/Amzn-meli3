#!/usr/bin/env python3
"""Test directo de generación de título con nuevo prompt"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline.transform_mapper_new import ai_title_es

# Datos del teclado iPad
base_title = "NOOX Bluetooth Keyboard for iPad 10th Generation"
brand = "NOOX"
model = "apple_ipad_10th_generation"
bullets = [
    "Compatible with iPad 10th Generation",
    "Bluetooth 3.0 wireless connection",
    "Rechargeable battery",
    "Portable and lightweight design"
]

print("="*70)
print("🧪 TEST: Generación de Título con Detección de Accesorios")
print("="*70)
print()
print(f"📦 Input:")
print(f"   Base Title: {base_title}")
print(f"   Brand: {brand}")
print(f"   Model: {model}")
print(f"   Bullets: {bullets[:2]}")
print()

print("🧠 Generando título con IA...")
print()

new_title = ai_title_es(base_title, brand, model, bullets, max_chars=60)

print("="*70)
print("📝 RESULTADO:")
print("="*70)
print(f"Título generado: {new_title}")
print()

# Verificar
if "PARA" in new_title or "Compatible" in new_title or "para" in new_title:
    print("✅ CORRECTO - Contiene indicador de accesorio ('PARA' o 'Compatible')")
    print("   El título cumple con las reglas de MercadoLibre")
else:
    print("❌ ERROR - NO contiene indicador de accesorio")
    print("   MercadoLibre podría suspender esta publicación")
    print()
    print("   Debería ser algo como:")
    print("   'Teclado Bluetooth PARA iPad 10ma Gen Portátil'")

print()
