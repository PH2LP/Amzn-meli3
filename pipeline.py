#!/usr/bin/env python3
"""
Pipeline Simple: Sistema Autónomo → Main2 (loop infinito)

Flujo:
1. Ejecuta sistema autónomo (busca ASINs, guarda en asins.txt)
2. Ejecuta mainglobal.py (publica los ASINs)
3. Repite indefinidamente

Uso: python3 pipeline.py
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

def run_in_terminal(cmd, title, cwd, timeout=None):
    """
    Ejecuta un comando en la misma terminal y espera a que termine.
    Muestra el output en tiempo real.

    Args:
        cmd: Comando a ejecutar
        title: Título descriptivo
        cwd: Directorio de trabajo
        timeout: Timeout en segundos (None = sin límite)
    """
    print(f"\n{'='*60}")
    print(f"🖥️  Ejecutando: {title}")
    print(f"📂 CWD: {cwd}")
    print(f"⚙️  CMD: {' '.join(cmd)}")
    if timeout:
        print(f"⏱️  Timeout: {timeout//60} minutos")
    print(f"{'='*60}\n")

    # Ejecutar en la misma terminal, mostrando output en tiempo real
    try:
        # Crear archivo de log para el comando
        log_file = Path(cwd) / "logs" / f"{title.replace(' ', '_')}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        start_time = datetime.now()

        # Abrir log file
        with open(log_file, 'a', encoding='utf-8') as log:
            log.write(f"\n{'='*60}\n")
            log.write(f"Inicio: {start_time}\n")
            log.write(f"Comando: {' '.join(cmd)}\n")
            log.write(f"{'='*60}\n\n")
            log.flush()

            # Ejecutar comando mostrando output en tiempo real
            # stdout va a la consola Y al log
            # stderr también va a la consola Y al log
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )

            # Leer y mostrar output línea por línea
            for line in process.stdout:
                print(line, end='')  # Mostrar en consola
                log.write(line)      # Escribir en log
                log.flush()

            # Esperar a que termine
            process.wait(timeout=timeout)

            end_time = datetime.now()
            duration = (end_time - start_time).seconds

            log.write(f"\n{'='*60}\n")
            log.write(f"Fin: {end_time}\n")
            log.write(f"Duración: {duration//60} minutos\n")
            log.write(f"Return code: {process.returncode}\n")
            log.write(f"{'='*60}\n")

        print(f"\n✅ Comando completado en {duration//60} minutos")
        print(f"📄 Log guardado en: {log_file}")

        if process.returncode != 0:
            print(f"⚠️  Comando terminó con código: {process.returncode}")
            return False
        return True

    except subprocess.TimeoutExpired:
        process.kill()
        print(f"\n⏱️  TIMEOUT: Comando excedió {timeout//60} minutos")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_autonomous_system(project_root):
    """
    Ejecuta el sistema autónomo (busca ASINs)

    Returns:
        bool: True si encontró ASINs y los guardó en asins.txt
    """
    script_path = project_root / "scripts/autonomous/autonomous_search_and_publish.py"
    config_path = project_root / "config/autonomous_config.json"

    cmd = [
        sys.executable,
        str(script_path),
        "--config", str(config_path),
        "--max-cycles", "1"  # Solo 1 ciclo (1 keyword)
    ]

    # Timeout de 120 minutos (búsqueda + filtrado puede tardar mucho)
    success = run_in_terminal(cmd, "Sistema Autónomo (Búsqueda)", str(project_root), timeout=120*60)

    if not success:
        return False

    # Verificar que se guardaron ASINs en asins.txt
    asins_file = project_root / "asins.txt"
    if not asins_file.exists():
        print(f"⚠️  Archivo asins.txt no fue creado")
        return False

    # Verificar que tiene contenido
    with open(asins_file, 'r') as f:
        asins = [line.strip() for line in f if line.strip()]

    if not asins:
        print(f"⚠️  asins.txt está vacío - no hay ASINs para publicar")
        return False

    print(f"✅ {len(asins)} ASINs listos para publicar")
    return True

def run_main2(project_root):
    """
    Ejecuta main2.py (publica ASINs desde asins.txt)

    Returns:
        bool: True si ejecutó correctamente
    """
    script_path = project_root / "main2.py"

    if not script_path.exists():
        print(f"❌ Error: {script_path} no existe")
        return False

    cmd = [
        sys.executable,
        str(script_path)
    ]

    # Timeout de 180 minutos (100 ASINs @ ~1 min/ASIN + margen)
    return run_in_terminal(cmd, "Main2 (Publicación)", str(project_root), timeout=180*60)

def main():
    project_root = Path(__file__).parent.absolute()

    print("\n" + "="*60)
    print("🚀 PIPELINE SIMPLE: AUTÓNOMO → MAIN2")
    print("="*60)
    print(f"📂 Proyecto: {project_root}")
    print(f"📝 ASINs: {project_root}/asins.txt")
    print(f"🔄 Modo: Loop infinito")
    print(f"🛑 Para detener: Ctrl+C")
    print("="*60)

    cycle = 0

    try:
        while True:
            cycle += 1
            print(f"\n{'🔄'*20}")
            print(f"CICLO #{cycle} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'🔄'*20}\n")

            # 1. Sistema autónomo (busca ASINs)
            print(f"[1/2] Ejecutando sistema autónomo...")
            if not run_autonomous_system(project_root):
                print("⚠️  Sistema autónomo falló, esperando 60s antes de reintentar...")
                import time
                time.sleep(60)
                continue

            print(f"✅ Sistema autónomo completado")

            # 2. Main2 (publica ASINs desde asins.txt)
            print(f"\n[2/2] Ejecutando main2.py...")
            if not run_main2(project_root):
                print("⚠️  Main2 falló, esperando 60s antes de reintentar...")
                import time
                time.sleep(60)
                continue

            print(f"✅ Main2 completado")
            print(f"\n✅ Ciclo #{cycle} completado exitosamente\n")

    except KeyboardInterrupt:
        print("\n\n🛑 Pipeline detenido por el usuario")
        sys.exit(0)

if __name__ == "__main__":
    main()
