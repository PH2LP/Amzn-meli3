#!/usr/bin/env python3
"""
Script autónomo para recopilar y fix todos los errores del pipeline
"""
import re
import json
from pathlib import Path

def extract_invalid_attributes(log_file):
    """Extrae todos los atributos inválidos del log"""
    invalid_attrs = set()

    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Buscar pattern: "Attribute: XXX was dropped because does not exists"
    pattern = r"Attribute: (\w+) was dropped because does not exists"
    matches = re.findall(pattern, content)

    for attr in matches:
        invalid_attrs.add(attr)

    return sorted(invalid_attrs)

def extract_gender_errors(log_file):
    """Detecta errores de formato en GENDER attribute"""
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r"Attribute \[GENDER\] is not valid, item values \[\(null:(\w+)\)\]"
    matches = re.findall(pattern, content)

    return matches

def add_to_blacklist(attrs):
    """Agrega atributos al blacklist en mainglobal.py"""
    file_path = "mainglobal.py"

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Encontrar el final del set BLACKLISTED_ATTRS
    # Buscar la última línea antes del cierre del set
    pattern = r'(BROWSE_CLASSIFICATION", "ADULT_PRODUCT", "AUTOGRAPHED",  # No existen\s+"ITEM_TYPE", "BULLET_POINTS"  # No existen)\s+\}'

    if re.search(pattern, content):
        # Construir la nueva línea con todos los atributos
        new_attrs_str = ', '.join(f'"{attr}"' for attr in attrs)
        new_line = f',  # No existen\n                "{new_attrs_str}"  # No existen (auto-added)'

        replacement = r'\1' + new_line + r'\n            }'
        content = re.sub(pattern, replacement, content)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ Agregados {len(attrs)} atributos al blacklist")
        return True
    else:
        print("⚠️ No se pudo encontrar el pattern del blacklist")
        return False

def main():
    log_file = "/tmp/pipeline_FINAL_100PCT.log"

    if not Path(log_file).exists():
        print(f"⚠️ Log file not found: {log_file}")
        return

    print("🔍 Analizando errores del pipeline...")

    # 1. Extraer atributos inválidos
    invalid_attrs = extract_invalid_attributes(log_file)
    print(f"\n📋 Atributos inválidos encontrados: {len(invalid_attrs)}")
    for attr in invalid_attrs:
        print(f"   • {attr}")

    # 2. Extraer errores de GENDER
    gender_errors = extract_gender_errors(log_file)
    if gender_errors:
        print(f"\n⚠️ Errores de GENDER encontrados: {gender_errors}")

    # 3. Agregar al blacklist
    if invalid_attrs:
        print("\n🔧 Agregando atributos al blacklist...")
        add_to_blacklist(invalid_attrs)

    print("\n✅ Análisis completado")

if __name__ == "__main__":
    main()
