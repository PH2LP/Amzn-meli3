#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SYNC AMAZON → MERCADOLIBRE - LOOP AUTOMÁTICO
═══════════════════════════════════════════════════════════════════════════════

Este script ejecuta el sync cada 6 horas automáticamente en un loop infinito.

USO:
    python3 sync_amazon_ml_LOOP.py

El proceso corre en background y se ejecuta:
- Inmediatamente al iniciar
- Cada 6 horas después

Para detener: usa 06_stop_sync_amzn_meli.py
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Agregar directorio raíz al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src' / 'integrations'))

# Importar el sync principal
from scripts.tools.sync_amazon_ml_GLOW import main as run_sync

# Configuración
SYNC_INTERVAL_HOURS = 6  # Ejecutar cada 6 horas

def log(message):
    """Imprime mensaje con timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)

def main():
    log("=" * 80)
    log("🔄 SYNC LOOP INICIADO")
    log("=" * 80)
    log(f"⏱️  Intervalo: Cada {SYNC_INTERVAL_HOURS} horas")
    log(f"📂 Directorio: {Path(__file__).parent.parent.parent}")
    log("=" * 80)
    log("")

    iteration = 0

    while True:
        iteration += 1

        try:
            log("=" * 80)
            log(f"🚀 INICIANDO SYNC #{iteration}")
            log("=" * 80)
            log("")

            # Esperar 10 minutos (servidor refresca token a las :00, sync empieza a las :10)
            log("⏸️  Esperando 10 minutos (servidor refresca token)...")
            time.sleep(600)  # 10 minutos
            log("")

            # Descargar token actualizado desde servidor
            log("🔄 Descargando token actualizado desde servidor...")
            try:
                import subprocess
                result = subprocess.run(
                    ["sshpass", "-p", "koqven-1regka-nyfXiw", "scp", "-o", "StrictHostKeyChecking=no",
                     "root@138.197.32.67:/opt/amz-ml-system/.env", str(project_root / ".env")],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    log("   ✅ Token sincronizado desde servidor")
                    # Recargar variables de entorno
                    from dotenv import load_dotenv
                    load_dotenv(override=True)
                else:
                    log(f"   ⚠️  No se pudo descargar .env: {result.stderr}")
                    log("   Continuando con token local...")
            except Exception as e:
                log(f"   ⚠️  Error descargando .env: {e}")
                log("   Continuando con token local...")
            log("")

            # Ejecutar sync
            start_time = time.time()

            try:
                run_sync()
                elapsed = time.time() - start_time
                log("")
                log(f"✅ Sync completado exitosamente en {elapsed/60:.1f} minutos")
            except Exception as e:
                elapsed = time.time() - start_time
                log("")
                log(f"❌ Error en sync después de {elapsed/60:.1f} minutos: {e}")
                import traceback
                traceback.print_exc()

            # Calcular próxima ejecución
            next_run = datetime.now() + timedelta(hours=SYNC_INTERVAL_HOURS)

            log("")
            log("=" * 80)
            log(f"⏸️  ESPERANDO {SYNC_INTERVAL_HOURS} HORAS")
            log(f"⏰ Próxima ejecución: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            log("=" * 80)
            log("")

            # Esperar 6 horas
            time.sleep(SYNC_INTERVAL_HOURS * 3600)

        except KeyboardInterrupt:
            log("")
            log("=" * 80)
            log("⚠️  SYNC LOOP DETENIDO MANUALMENTE")
            log("=" * 80)
            log("")
            break

        except Exception as e:
            log("")
            log(f"❌ Error crítico en loop: {e}")
            import traceback
            traceback.print_exc()
            log("")
            log("⏸️  Esperando 10 minutos antes de reintentar...")
            time.sleep(600)  # Esperar 10 minutos y reintentar

if __name__ == "__main__":
    main()
