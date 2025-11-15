#!/usr/bin/env python3
# ============================================================
# run_pipeline_smart.py
# ✅ Pipeline inteligente con detección de duplicados
# ✅ Filtra ASINs antes de procesarlos para ahorrar tiempo/tokens
# ============================================================

import sys
import subprocess
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from pipeline.duplicate_checker import filter_asins_batch


def main():
    """
    Pipeline inteligente que:
    1. Lee asins.txt
    2. Filtra duplicados (ASINs ya publicados)
    3. Guarda solo los nuevos en asins_filtered.txt
    4. Ejecuta el pipeline normal solo con productos nuevos
    """

    print("\n" + "="*70)
    print("🚀 PIPELINE INTELIGENTE CON DETECCIÓN DE DUPLICADOS")
    print("="*70 + "\n")

    # 1. Leer ASINs del archivo
    asins_file = Path("asins.txt")
    if not asins_file.exists():
        print("❌ No se encontró asins.txt")
        print("   Creá el archivo con un ASIN por línea o usá search_asins.sh")
        return 1

    with open(asins_file, 'r', encoding='utf-8') as f:
        asins = [line.strip().upper() for line in f if line.strip()]

    if not asins:
        print("❌ asins.txt está vacío")
        return 1

    print(f"📂 Leídos {len(asins)} ASINs desde asins.txt\n")

    # 2. Filtrar duplicados
    result = filter_asins_batch(asins, verbose=True)

    if not result['new_asins']:
        print("\n✅ Todos los ASINs ya fueron publicados previamente")
        print("   No hay nada nuevo para procesar")
        return 0

    # 3. Guardar ASINs nuevos en archivo temporal
    filtered_file = Path("asins_filtered.txt")
    with open(filtered_file, 'w', encoding='utf-8') as f:
        for asin in result['new_asins']:
            f.write(f"{asin}\n")

    print(f"\n💾 {len(result['new_asins'])} ASINs nuevos guardados en {filtered_file}")

    # 4. Preguntar al usuario si quiere continuar
    print("\n" + "="*70)
    print("📋 PRODUCTOS A PROCESAR:")
    print("="*70)
    for i, asin in enumerate(result['new_asins'][:20], 1):
        print(f"  {i}. {asin}")

    if len(result['new_asins']) > 20:
        print(f"  ... y {len(result['new_asins']) - 20} más")

    print("\n⏱️  Tiempo estimado:")
    print(f"   → {len(result['new_asins'])} productos × ~30 seg = ~{(len(result['new_asins']) * 30) / 60:.0f} minutos")

    print("\n🔄 Pasos del pipeline:")
    print("   1. Descargar datos de Amazon (SP-API)")
    print("   2. Transformar a formato MercadoLibre")
    print("   3. Encontrar categorías CBT")
    print("   4. Validar y publicar en MercadoLibre Global")

    choice = input("\n¿Querés continuar con el pipeline? [s/n]: ").strip().lower()

    if choice != 's':
        print("\n👋 Pipeline cancelado")
        print(f"   Los ASINs nuevos quedaron guardados en {filtered_file}")
        return 0

    # 5. Ejecutar el pipeline normal pero usando asins_filtered.txt
    print("\n" + "="*70)
    print("🚀 INICIANDO PIPELINE COMPLETO")
    print("="*70 + "\n")

    # Temporalmente renombrar asins.txt y usar asins_filtered.txt
    backup_file = Path("asins_backup.txt")
    asins_file.rename(backup_file)
    filtered_file.rename(asins_file)

    try:
        # Ejecutar el pipeline principal
        # Nota: Ajustá este comando según tu pipeline real
        subprocess.run([
            "./venv/bin/python3",
            "src/integrations/mainglobal.py"
        ], check=True)

        print("\n✅ Pipeline completado exitosamente")

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error ejecutando el pipeline: {e}")
        return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline interrumpido por el usuario")
        return 1

    finally:
        # Restaurar asins.txt original
        if asins_file.exists():
            asins_file.rename(filtered_file)
        if backup_file.exists():
            backup_file.rename(asins_file)

    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n👋 Proceso cancelado")
        sys.exit(1)
