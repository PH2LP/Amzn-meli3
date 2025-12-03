#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parallel_search.py
═══════════════════════════════════════════════════════════════════════════════
BÚSQUEDA PARALELA SIMPLIFICADA - Configurable desde .env
═══════════════════════════════════════════════════════════════════════════════

USO:
    python3 parallel_search.py

CONFIGURACIÓN (.env):
    PARALLEL_PROCESSES=4          # Número de procesos paralelos
    ASINS_PER_KEYWORD=8          # ASINs objetivo por keyword
    KEYWORDS_FILE=keywords.txt    # Archivo de keywords (raíz del proyecto)
"""

import os
import sys
import json
import math
import time
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Cargar .env (override=True para sobreescribir variables del sistema)
load_dotenv(override=True)

# Colores para consola
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def log(message, color=Colors.NC):
    """Print con color"""
    print(f"{color}{message}{Colors.NC}")

def main():
    # Leer configuración desde .env
    PARTS = int(os.getenv("PARALLEL_PROCESSES", "4"))
    ASINS_PER_KEYWORD = int(os.getenv("ASINS_PER_KEYWORD", "8"))
    KEYWORDS_FILE = os.getenv("KEYWORDS_FILE", "keywords.txt")
    PROJECT_ROOT = Path(__file__).parent.absolute()

    log("╔════════════════════════════════════════════════════════════════╗", Colors.BLUE)
    log("║        BÚSQUEDA PARALELA DE ASINs POR KEYWORDS                 ║", Colors.BLUE)
    log("╚════════════════════════════════════════════════════════════════╝", Colors.BLUE)
    print()
    log("📋 Configuración:", Colors.GREEN)
    log(f"   Procesos paralelos:    {Colors.YELLOW}{PARTS}{Colors.NC}")
    log(f"   ASINs por keyword:     {Colors.YELLOW}{ASINS_PER_KEYWORD}{Colors.NC}")
    log(f"   Archivo de keywords:   {Colors.YELLOW}{KEYWORDS_FILE}{Colors.NC}")
    print()

    # Verificar que existe el archivo de keywords
    keywords_path = PROJECT_ROOT / KEYWORDS_FILE
    if not keywords_path.exists():
        log(f"❌ Error: No se encontró el archivo de keywords: {KEYWORDS_FILE}", Colors.RED)
        sys.exit(1)

    # Verificar variables de entorno necesarias
    if not os.getenv("OPENAI_API_KEY"):
        log("❌ Error: OPENAI_API_KEY no está configurada en .env", Colors.RED)
        sys.exit(1)

    # Crear directorio temporal
    temp_dir = PROJECT_ROOT / f"temp_parallel_search_{os.getpid()}"
    temp_dir.mkdir(exist_ok=True)

    log(f"🔍 Dividiendo keywords en {PARTS} partes...", Colors.BLUE)

    # Leer keywords (soporta .txt y .json)
    if keywords_path.suffix.lower() == '.json':
        # Formato JSON
        with open(keywords_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        keywords_raw = data.get("keywords", [])
        # Si es lista de dicts, extraer campo "keyword"
        if keywords_raw and isinstance(keywords_raw[0], dict):
            keywords = [kw.get("keyword", "") for kw in keywords_raw if kw.get("keyword")]
        else:
            keywords = keywords_raw
    else:
        # Formato TXT simple (una keyword por línea)
        with open(keywords_path, "r", encoding="utf-8") as f:
            keywords = [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith("#")
            ]

    total_keywords = len(keywords)
    print(f"   Total keywords: {total_keywords}")

    # Dividir en partes iguales
    keywords_per_part = math.ceil(total_keywords / PARTS)

    for i in range(PARTS):
        start_idx = i * keywords_per_part
        end_idx = min((i + 1) * keywords_per_part, total_keywords)
        part_keywords = keywords[start_idx:end_idx]

        # Guardar en archivo temporal (siempre JSON para procesos internos)
        output_file = temp_dir / f"keywords_part_{i}.json"
        part_data = {
            "comment": f"Parte {i+1}/{PARTS} de keywords para búsqueda paralela",
            "keywords": [{"keyword": kw} if isinstance(kw, str) else kw for kw in part_keywords]
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(part_data, f, indent=2, ensure_ascii=False)

        print(f"   Parte {i+1}: {len(part_keywords)} keywords → {output_file.name}")

    print(f"\n✅ Keywords divididas en {PARTS} archivos")
    print()

    log(f"🚀 Iniciando {PARTS} procesos de búsqueda en paralelo...", Colors.BLUE)
    print()

    # Array para guardar procesos
    processes = []

    # Iniciar procesos con delays escalonados
    for i in range(PARTS):
        keywords_part = temp_dir / f"keywords_part_{i}.json"
        output_part = temp_dir / f"asins_part_{i}.txt"
        log_part = temp_dir / f"log_part_{i}.log"

        # Delay escalonado para evitar rate limits (180 segundos entre cada proceso)
        delay = i * 180

        if i == 0:
            log(f"▶ Proceso {i + 1}/{PARTS} iniciando ahora...", Colors.GREEN)
        else:
            log(f"⏳ Proceso {i + 1}/{PARTS} iniciará en {delay}s...", Colors.YELLOW)

        # Crear comando con PYTHONPATH
        env = os.environ.copy()
        env['PYTHONPATH'] = str(PROJECT_ROOT)

        cmd = [
            "python3", "-u",
            str(PROJECT_ROOT / "scripts" / "autonomous" / "search_12_per_keyword.py"),
            "--keywords-file", str(keywords_part),
            "--output-file", str(output_part),
            "--asins-per-keyword", str(ASINS_PER_KEYWORD),
            "--process-id", str(i)
        ]

        # Iniciar proceso en background con delay
        if delay > 0:
            # Crear un script que espera y luego ejecuta
            subprocess.Popen(
                ["bash", "-c", f"sleep {delay} && PYTHONPATH={PROJECT_ROOT} {' '.join(cmd)} >> {log_part} 2>&1"],
                env=env
            )
        else:
            # Iniciar inmediatamente
            with open(log_part, "w") as log_f:
                process = subprocess.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    env=env
                )
                processes.append(process)

    print()
    log("⏳ Esperando que terminen todos los procesos...", Colors.BLUE)
    log(f"   Podés monitorear el progreso con:", Colors.YELLOW)
    log(f"   tail -f {temp_dir}/log_part_*.log", Colors.YELLOW)
    print()

    # Monitorear progreso
    completed = 0
    while completed < PARTS:
        completed = 0
        for i in range(PARTS):
            output_part = temp_dir / f"asins_part_{i}.txt"
            if output_part.exists():
                completed += 1
        print(f"\r   Procesos completados: {completed}/{PARTS}", end="", flush=True)
        time.sleep(5)

    print("\n")

    # Esperar a que terminen todos
    for process in processes:
        try:
            process.wait()
        except:
            pass

    print()
    log("🔗 Uniendo resultados...", Colors.BLUE)

    # Combinar todos los ASINs y eliminar duplicados
    all_asins = set()
    for i in range(PARTS):
        output_part = temp_dir / f"asins_part_{i}.txt"
        if output_part.exists():
            with open(output_part, "r") as f:
                for line in f:
                    asin = line.strip()
                    if asin:
                        all_asins.add(asin)

    # Guardar en data/asins.txt
    output_file = PROJECT_ROOT / "data" / "asins.txt"
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, "w") as f:
        for asin in sorted(all_asins):
            f.write(f"{asin}\n")

    total_asins = len(all_asins)

    print()
    log("╔════════════════════════════════════════════════════════════════╗", Colors.GREEN)
    log("║                    ✅ BÚSQUEDA COMPLETADA                      ║", Colors.GREEN)
    log("╚════════════════════════════════════════════════════════════════╝", Colors.GREEN)
    print()
    log("📊 RESUMEN:", Colors.GREEN)
    log(f"   Total ASINs únicos:    {Colors.YELLOW}{total_asins}{Colors.NC}")
    log(f"   Archivo de salida:     {Colors.YELLOW}{output_file}{Colors.NC}")
    print()
    log(f"💡 Los archivos temporales se guardaron en: {Colors.YELLOW}{temp_dir}{Colors.NC}", Colors.BLUE)
    log(f"   Para eliminarlos: {Colors.YELLOW}rm -rf {temp_dir}{Colors.NC}", Colors.BLUE)
    print()

    # Mostrar algunos ASINs de ejemplo
    log("📦 Primeros 10 ASINs encontrados:", Colors.BLUE)
    for i, asin in enumerate(sorted(all_asins)[:10]):
        log(f"   {asin}", Colors.GREEN)
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Búsqueda detenida por usuario (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
