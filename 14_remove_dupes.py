#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 14_remove_dupes.py - REMOVER ASINs DUPLICADOS
# ═══════════════════════════════════════════════════════════════════════════════
#
# ¿Qué hace?
#   Elimina ASINs duplicados del archivo asins.txt y de la base de datos.
#   Útil para limpiar la lista antes de publicar.
#
# Comando:
#   python3 14_remove_dupes.py
# 
# ═══════════════════════════════════════════════════════════════════════════════
def remove_duplicate_asins():
    input_file = 'data/asins subidos con cat mal.txt'

    # Leer todos los ASINs
    with open(input_file, 'r') as f:
        asins = [line.strip() for line in f]

    # Contar total de líneas y duplicados
    total_original = len(asins)

    # Encontrar duplicados y contar ocurrencias
    from collections import Counter
    asin_counts = Counter(asin for asin in asins if asin)

    # Identificar cuáles están duplicados
    duplicated_asins = {asin: count for asin, count in asin_counts.items() if count > 1}

    # Eliminar duplicados manteniendo el orden (usando dict.fromkeys())
    # También filtramos las líneas vacías
    unique_asins = list(dict.fromkeys(asin for asin in asins if asin))

    total_unique = len(unique_asins)
    empty_lines = asins.count('')
    duplicates_removed = total_original - total_unique

    # Escribir de vuelta al archivo
    with open(input_file, 'w') as f:
        for asin in unique_asins:
            f.write(f"{asin}\n")

    print(f"✓ Procesamiento completado")
    print(f"  Total original: {total_original} líneas")
    print(f"  ASINs únicos: {total_unique}")
    print(f"  Duplicados eliminados: {duplicates_removed}")
    print(f"  Líneas vacías eliminadas: {empty_lines}")

    if duplicated_asins:
        print(f"\n📊 Detalle de duplicados encontrados ({len(duplicated_asins)} ASINs diferentes):")
        # Ordenar por cantidad de repeticiones (de mayor a menor)
        sorted_duplicates = sorted(duplicated_asins.items(), key=lambda x: x[1], reverse=True)
        for asin, count in sorted_duplicates[:20]:  # Mostrar solo los primeros 20
            print(f"   {asin}: {count} veces (eliminadas {count-1} copias)")

        if len(duplicated_asins) > 20:
            print(f"   ... y {len(duplicated_asins) - 20} ASINs duplicados más")

    print(f"\n✓ Archivo actualizado: {input_file}")

if __name__ == "__main__":
    remove_duplicate_asins()
