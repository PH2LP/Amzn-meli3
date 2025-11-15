#!/usr/bin/env python3
"""
EJEMPLO: Cómo usar el módulo de ranking de ASINs
================================================

Este script demuestra cómo usar el módulo rank_asins_for_publication
para obtener una lista de los mejores ASINs.

NO MODIFICA NINGÚN CÓDIGO EXISTENTE - Es completamente independiente.
"""

from scripts.tools.rank_asins_for_publication import rank_and_select_top_asins


def ejemplo_basico():
    """Ejemplo básico: Obtener top 1000 ASINs"""

    print("\n" + "="*60)
    print("EJEMPLO 1: Uso básico del módulo")
    print("="*60)

    # Obtener top 1000 ASINs rankeados
    top_asins = rank_and_select_top_asins('asins.txt', limit=1000)

    print(f"\n📦 Total ASINs recibidos: {len(top_asins)}")
    print(f"\n🏆 Top 5 ASINs:")
    for i, asin in enumerate(top_asins[:5], 1):
        print(f"   {i}. {asin}")

    return top_asins


def ejemplo_guardar_archivo(top_asins):
    """Ejemplo: Guardar lista de ASINs en archivo personalizado"""

    print("\n" + "="*60)
    print("EJEMPLO 2: Guardar en archivo personalizado")
    print("="*60)

    output_file = "mis_mejores_asins.txt"

    with open(output_file, 'w') as f:
        f.write("# ASINs rankeados para publicar\n")
        f.write(f"# Total: {len(top_asins)}\n\n")
        for asin in top_asins:
            f.write(f"{asin}\n")

    print(f"\n✅ Guardado en: {output_file}")
    print(f"📄 Total líneas: {len(top_asins)}")


def ejemplo_filtrar_por_score():
    """Ejemplo: Filtrar ASINs por score mínimo"""

    print("\n" + "="*60)
    print("EJEMPLO 3: Solo ASINs con score alto")
    print("="*60)

    # Este ejemplo requiere acceso a los scores completos
    # Para simplificar, solo mostramos cómo obtener más o menos ASINs

    # Top 500 (los mejores de los mejores)
    top_500 = rank_and_select_top_asins('asins.txt', limit=500, verbose=False)

    print(f"\n🌟 Top 500 ASINs (elite): {len(top_500)}")
    print(f"   Primero: {top_500[0]}")
    print(f"   Último: {top_500[-1]}")


def ejemplo_uso_en_pipeline():
    """Ejemplo: Cómo integrar en tu pipeline existente"""

    print("\n" + "="*60)
    print("EJEMPLO 4: Integración en pipeline")
    print("="*60)

    print("\nPuedes usar esto en tu código existente:")
    print("""
    # En cualquier parte de tu código:
    from scripts.tools.rank_asins_for_publication import rank_and_select_top_asins

    # Después de que autonomous_search genere asins.txt:
    top_1000 = rank_and_select_top_asins('asins.txt', limit=1000)

    # Ahora pasa esos ASINs a main2.py:
    with open('asins_filtered.txt', 'w') as f:
        for asin in top_1000:
            f.write(f"{asin}\\n")

    # Y ejecuta main2.py con ese archivo
    """)


def main():
    """Ejecutar todos los ejemplos"""

    print("\n" + "="*60)
    print("🎯 EJEMPLOS DE USO DEL MÓDULO DE RANKING")
    print("="*60)
    print("\nEste módulo es INDEPENDIENTE - no modifica tu código existente")
    print("Solo retorna una lista de ASINs rankeados.\n")

    # Verificar que existe asins.txt
    from pathlib import Path
    if not Path('asins.txt').exists():
        print("❌ Error: No existe asins.txt")
        print("\nPara probar, crea un archivo asins.txt con algunos ASINs:")
        print("  B08L5VN96K")
        print("  B09WXYZ123")
        print("  B0ABC12345")
        print("  ...")
        return

    # Ejemplo 1: Uso básico
    top_asins = ejemplo_basico()

    # Ejemplo 2: Guardar en archivo
    ejemplo_guardar_archivo(top_asins)

    # Ejemplo 3: Filtrar por score
    # ejemplo_filtrar_por_score()  # Descomenta si quieres probarlo

    # Ejemplo 4: Integración
    ejemplo_uso_en_pipeline()

    print("\n" + "="*60)
    print("✅ Ejemplos completados")
    print("="*60)
    print("\nResumen:")
    print(f"  • Función principal: rank_and_select_top_asins()")
    print(f"  • Input: archivo con ASINs")
    print(f"  • Output: lista de ASINs rankeados")
    print(f"  • Sin modificar código existente")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
