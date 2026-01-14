#!/usr/bin/env python3
"""
Script para filtrar items de ML que tienen IDs locales
Elimina del export los items que no tienen publicaciones locales (MLM, MLA, MLB, MLC, MCO)
"""

import re
import sys
from pathlib import Path

def filter_items_with_locales(input_file):
    """
    Filtra items manteniendo solo los que tienen ITEMS LOCALES
    """
    print(f"📖 Leyendo archivo: {input_file}")

    # Leer el archivo original
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extraer el header
    header_match = re.match(r'(EXPORTACIÓN SIMPLE DE ITEMS MERCADOLIBRE.*?\n={100}\n)', content, re.DOTALL)
    header = header_match.group(1) if header_match else ""

    # Dividir por items
    items_split = re.split(r'\n(\[\d+/\d+\] CBT\d+\n)', content)

    # Filtrar solo items CON locales
    filtered_items = []
    items_kept = 0
    items_removed = 0
    removed_cbts = []

    for i in range(1, len(items_split), 2):
        if i+1 < len(items_split):
            item_header = items_split[i]
            item_content = items_split[i+1]

            # Extraer CBT ID
            cbt_match = re.search(r'CBT\d+', item_header)
            cbt_id = cbt_match.group(0) if cbt_match else "Unknown"

            # Si tiene "ITEMS LOCALES:", lo mantenemos
            if "ITEMS LOCALES:" in item_content:
                filtered_items.append(item_header)
                filtered_items.append(item_content)
                items_kept += 1
            else:
                items_removed += 1
                removed_cbts.append(cbt_id)

    # Actualizar el header con el nuevo total
    new_header = re.sub(r'Total de items: \d+', f'Total de items: {items_kept}', header)

    # Reindexar los números [1/total], [2/total], etc.
    final_content = new_header
    for idx, i in enumerate(range(0, len(filtered_items), 2)):
        if i+1 < len(filtered_items):
            item_header = filtered_items[i]
            item_content = filtered_items[i+1]

            # Reemplazar el número [old/old] por [new/total]
            new_item_header = re.sub(r'\[\d+/\d+\]', f'[{idx+1}/{items_kept}]', item_header)
            final_content += new_item_header + item_content

    # Guardar el archivo actualizado
    with open(input_file, 'w', encoding='utf-8') as f:
        f.write(final_content)

    # Guardar lista de CBTs eliminados
    removed_file = 'cbt_sin_locales.txt'
    if removed_cbts:
        with open(removed_file, 'w', encoding='utf-8') as f:
            for cbt in removed_cbts:
                f.write(cbt + '\n')

    # Resultados
    print(f"\n✓ Archivo actualizado: {input_file}")
    print(f"  Items mantenidos (CON locales): {items_kept}")
    print(f"  Items eliminados (SIN locales): {items_removed}")
    print(f"  Total original: {items_kept + items_removed}")

    if removed_cbts:
        print(f"\n✓ CBTs sin locales guardados en: {removed_file}")

    return items_kept, items_removed

if __name__ == "__main__":
    # Buscar archivo de export más reciente si no se especifica
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        # Buscar el archivo más reciente que coincida con el patrón
        pattern = "ml_items_simple_export_*.txt"
        files = sorted(Path('.').glob(pattern), key=lambda x: x.stat().st_mtime, reverse=True)

        if files:
            input_file = str(files[0])
            print(f"📁 Usando archivo más reciente: {input_file}")
        else:
            print(f"❌ Error: No se encontró ningún archivo {pattern}")
            print(f"Uso: python3 {sys.argv[0]} [archivo_export.txt]")
            sys.exit(1)

    # Verificar que existe
    if not Path(input_file).exists():
        print(f"❌ Error: Archivo no encontrado: {input_file}")
        sys.exit(1)

    # Filtrar
    filter_items_with_locales(input_file)
