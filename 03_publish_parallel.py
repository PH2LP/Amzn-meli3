#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 03_publish_parallel.py - PUBLICAR PRODUCTOS EN PARALELO (RÁPIDO)
# ═══════════════════════════════════════════════════════════════════════════════
# 
# ¿Qué hace?
#   Publica productos en MercadoLibre usando múltiples procesos en paralelo.
#   Mucho más rápido que 02_publish.py (6 workers simultáneos).
# 
# Comando:
#   python3 03_publish_parallel.py
# 
# ═══════════════════════════════════════════════════════════════════════════════
import os
import sys
import time
import tempfile
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Cargar .env
load_dotenv(override=True)


def print_header():
    """Imprime header del script"""
    print("\n" + "="*80)
    print("🚀 PARALLEL PUBLISH - Publicación en paralelo")
    print("="*80 + "\n")


def divide_asins(asins_file: Path, num_workers: int) -> list:
    """
    Divide la lista de ASINs en partes iguales para cada worker

    Returns:
        List of tuples: [(temp_file_path, start_idx, end_idx), ...]
    """
    # Leer ASINs
    if not asins_file.exists():
        print(f"❌ Error: No se encontró el archivo {asins_file}")
        sys.exit(1)

    with open(asins_file, 'r') as f:
        asins = [line.strip() for line in f if line.strip()]

    if not asins:
        print(f"❌ Error: El archivo {asins_file} está vacío")
        sys.exit(1)

    total_asins = len(asins)
    asins_per_worker = (total_asins + num_workers - 1) // num_workers  # Ceiling division

    print(f"📊 Total ASINs: {total_asins}")
    print(f"👥 Workers: {num_workers}")
    print(f"📦 ASINs por worker: ~{asins_per_worker}")
    print()

    # Crear directorio temporal con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = Path(f"temp_parallel_publish_{timestamp}")
    temp_dir.mkdir(exist_ok=True)

    # Dividir ASINs en archivos temporales
    parts = []
    for i in range(num_workers):
        start_idx = i * asins_per_worker
        end_idx = min((i + 1) * asins_per_worker, total_asins)

        if start_idx >= total_asins:
            break

        asins_chunk = asins[start_idx:end_idx]

        # Crear archivo temporal para este worker
        temp_file = temp_dir / f"asins_part_{i}.txt"
        with open(temp_file, 'w') as f:
            f.write('\n'.join(asins_chunk))

        parts.append({
            'file': temp_file,
            'start': start_idx,
            'end': end_idx,
            'count': len(asins_chunk),
            'worker_id': i
        })

        print(f"   Worker {i+1}: {len(asins_chunk)} ASINs ({start_idx+1}-{end_idx})")

    print()
    return parts, temp_dir


def run_worker(part_info: dict, in_new_terminal: bool = False) -> subprocess.Popen:
    """
    Ejecuta un proceso de 02_publish.py para una parte de ASINs

    Args:
        part_info: Información del worker
        in_new_terminal: Si True, abre en nueva terminal con log visible

    Returns:
        subprocess.Popen object
    """
    worker_id = part_info['worker_id']
    asins_file = part_info['file']

    # Crear archivo de log para este worker
    log_file = Path(f"storage/logs/parallel_publish_worker_{worker_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)

    if in_new_terminal:
        # Abrir en nueva terminal de macOS con tail -f del log
        cwd = Path.cwd()

        # Comando bash que se ejecutará en la nueva terminal
        bash_script = f"""cd '{cwd}' && echo 'Worker {worker_id+1} - Publicando {part_info['count']} ASINs...' && {sys.executable} 02_publish.py --asins-file '{asins_file}' > '{log_file}' 2>&1 & WORKER_PID=$! && echo 'PID: '$WORKER_PID && sleep 1 && tail -f '{log_file}' & TAIL_PID=$! && wait $WORKER_PID ; sleep 2 ; kill $TAIL_PID 2>/dev/null ; echo '' && echo '✅ Worker {worker_id+1} completado' && echo 'Presiona Enter para cerrar esta terminal...' && read"""

        # AppleScript para abrir nueva terminal
        applescript = f"""tell application "Terminal"
    do script "{bash_script}"
    activate
end tell"""

        # Ejecutar en background sin output
        subprocess.Popen(['osascript', '-e', applescript],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        print(f"✅ Worker {worker_id+1} abierto en nueva terminal → {log_file}")

        # Retornar None porque el proceso corre en otra terminal
        return None
    else:
        # Comando para ejecutar 02_publish.py
        cmd = [
            sys.executable,  # python3
            '02_publish.py',
            '--asins-file', str(asins_file)
        ]

        # Ejecutar proceso en background
        with open(log_file, 'w') as log:
            process = subprocess.Popen(
                cmd,
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=Path.cwd()
            )

        print(f"✅ Worker {worker_id+1} iniciado (PID: {process.pid}) → {log_file}")
        return process


def wait_for_workers(processes: list):
    """
    Espera a que todos los workers terminen

    Args:
        processes: Lista de subprocess.Popen objects
    """
    print(f"\n⏳ Esperando a que terminen los {len(processes)} workers...\n")

    start_time = time.time()

    # Esperar a que todos terminen
    for i, process in enumerate(processes):
        worker_id = i + 1
        process.wait()
        elapsed = time.time() - start_time

        if process.returncode == 0:
            print(f"✅ Worker {worker_id} completado (Tiempo: {elapsed/60:.1f} min)")
        else:
            print(f"⚠️  Worker {worker_id} terminó con código {process.returncode} (Tiempo: {elapsed/60:.1f} min)")

    total_time = time.time() - start_time
    print(f"\n✅ Todos los workers completados en {total_time/60:.1f} minutos")


def cleanup_temp_files(temp_dir: Path):
    """Limpia archivos temporales"""
    import shutil

    if temp_dir.exists():
        try:
            shutil.rmtree(temp_dir)
            print(f"\n🧹 Archivos temporales eliminados: {temp_dir}")
        except Exception as e:
            print(f"\n⚠️  Error eliminando archivos temporales: {e}")


def main():
    parser = argparse.ArgumentParser(description='Publicación paralela de ASINs')
    parser.add_argument('--file', type=str, default='asins.txt',
                       help='Archivo de ASINs a publicar (default: asins.txt)')
    parser.add_argument('--workers', type=int, default=None,
                       help='Número de procesos paralelos (default: desde .env o 4)')
    parser.add_argument('--no-cleanup', action='store_true',
                       help='No eliminar archivos temporales al finalizar')

    args = parser.parse_args()

    # Número de workers
    if args.workers:
        num_workers = args.workers
    else:
        num_workers = int(os.getenv('PARALLEL_PUBLISH_WORKERS', '4'))

    # Archivo de ASINs
    asins_file = Path(args.file)

    # Header
    print_header()

    # Dividir ASINs
    parts, temp_dir = divide_asins(asins_file, num_workers)

    if not parts:
        print("❌ No hay ASINs para procesar")
        cleanup_temp_files(temp_dir)
        sys.exit(1)

    # Ejecutar workers
    print("🚀 Abriendo 3 terminales nuevas...\n")

    # TODOS los workers se abren en nuevas terminales
    for i, part in enumerate(parts):
        run_worker(part, in_new_terminal=True)
        time.sleep(5)  # Delay para que las terminales se abran ordenadamente

    print("\n✅ Todos los workers están corriendo en terminales separadas")
    print("💡 Podés cerrar esta terminal, los workers seguirán ejecutándose")
    print(f"📁 Archivos temporales en: {temp_dir}")
    print(f"⚠️  IMPORTANTE: No borres la carpeta {temp_dir} hasta que terminen todos los workers")

    print("\n" + "="*80)
    print("✅ Publicación paralela completada")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
