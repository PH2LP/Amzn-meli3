#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para la nueva función ai_desc_es
Verifica que el post-procesamiento elimina espacios extra y normaliza saltos
"""

import json
import sys
from src.transform_mapper_new import ai_desc_es

def test_description(asin):
    """Prueba la generación de descripción con el ASIN dado"""

    print(f"\n{'='*70}")
    print(f"Probando generación de descripción para ASIN: {asin}")
    print(f"{'='*70}\n")

    # Cargar el JSON de Amazon
    with open(f"storage/asins_json/{asin}.json", "r", encoding="utf-8") as f:
        amazon_json = json.load(f)

    # Preparar datos para la función
    datos = {"full_json": amazon_json}

    # Generar descripción
    print("🧠 Generando descripción con IA...\n")
    descripcion = ai_desc_es(datos)

    if not descripcion:
        print("❌ No se pudo generar la descripción (probablemente falta OPENAI_API_KEY)")
        return

    # Mostrar resultado
    print("✅ DESCRIPCIÓN GENERADA:")
    print("-" * 70)
    print(descripcion)
    print("-" * 70)

    # Verificar calidad del post-procesamiento
    print("\n🔍 VERIFICACIÓN DE POST-PROCESAMIENTO:")
    print("-" * 70)

    # 1. Verificar líneas con solo espacios
    lines = descripcion.split('\n')
    lines_with_only_spaces = [i for i, line in enumerate(lines) if line and line.strip() == '']

    if lines_with_only_spaces:
        print(f"⚠️  Encontradas {len(lines_with_only_spaces)} líneas con solo espacios en posiciones: {lines_with_only_spaces}")
    else:
        print("✅ No hay líneas con solo espacios")

    # 2. Verificar espacios al final de líneas
    lines_with_trailing_spaces = [i for i, line in enumerate(lines) if line != line.rstrip()]

    if lines_with_trailing_spaces:
        print(f"⚠️  Encontradas {len(lines_with_trailing_spaces)} líneas con espacios al final en posiciones: {lines_with_trailing_spaces}")
    else:
        print("✅ No hay líneas con espacios al final")

    # 3. Verificar saltos múltiples (más de 2 seguidos)
    import re
    multiple_breaks = re.findall(r'\n{3,}', descripcion)

    if multiple_breaks:
        print(f"⚠️  Encontrados {len(multiple_breaks)} bloques con 3+ saltos de línea seguidos")
    else:
        print("✅ No hay saltos múltiples (máximo 2 seguidos)")

    # 4. Verificar que el footer está presente
    if "INFORMACIÓN IMPORTANTE PARA COMPRAS INTERNACIONALES" in descripcion:
        print("✅ Footer incluido correctamente")
    else:
        print("⚠️  Footer no encontrado")

    # 5. Verificar que no hay HTML ni markdown
    if any(marker in descripcion for marker in ['```', '<', '>']):
        print("⚠️  Posible HTML o markdown detectado")
    else:
        print("✅ No hay HTML ni markdown")

    # 6. Mostrar primeras 500 chars con repr() para ver caracteres invisibles
    print("\n🔬 PRIMEROS 500 CARACTERES (con caracteres invisibles visibles):")
    print("-" * 70)
    print(repr(descripcion[:500]))
    print("-" * 70)

    # 7. Estadísticas
    print(f"\n📊 ESTADÍSTICAS:")
    print(f"   - Total de caracteres: {len(descripcion)}")
    print(f"   - Total de líneas: {len(lines)}")
    print(f"   - Palabras aproximadas: {len(descripcion.split())}")

    # Guardar resultado para inspección manual
    output_path = f"storage/logs/test_description_{asin}.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(descripcion)
    print(f"\n💾 Descripción guardada en: {output_path}")

    return descripcion

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asin = sys.argv[1]
    else:
        # ASIN por defecto
        asin = "B0FQ9Z4WF8"
        print(f"ℹ️  No se especificó ASIN, usando: {asin}")
        print(f"   Uso: python test_new_description.py <ASIN>")

    test_description(asin)
