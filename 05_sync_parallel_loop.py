#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SYNC PARALELO (LOOP) - Amazon ↔ MercadoLibre
==============================================
Versión LOOP del sync paralelo - corre continuamente en horarios programados.

Lee horarios desde SYNC_SCHEDULED_TIMES en .env (igual que sync_loop normal).

CONFIGURACIÓN (.env):
- SYNC_WORKERS: Número de threads paralelos (default: 3)
- SYNC_SCHEDULED_TIMES: Horarios de ejecución (ej: "00:05,06:05,12:05,18:05")

USO:
    python3 05_sync_parallel_loop.py
    (dejar corriendo en background)
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Agregar directorio raíz
sys.path.insert(0, str(Path(__file__).parent))

# Importar sync paralelo
from scripts.tools.sync_amazon_ml_GLOW import main as sync_function

# Reemplazar la función get_glow_data_batch con la versión paralela
import scripts.tools.sync_amazon_ml_GLOW as sync_module
from importlib import import_module

# Cargar .env
load_dotenv()

# Configuración
SYNC_SCHEDULED_TIMES = os.getenv("SYNC_SCHEDULED_TIMES", "00:05")
MAX_WORKERS = int(os.getenv("SYNC_WORKERS", "3"))

def log(msg):
    """Log con timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def parse_scheduled_times(times_str):
    """
    Parsea string de horarios "HH:MM,HH:MM,..." a lista de (hour, minute)
    """
    times = []
    for time_str in times_str.split(","):
        time_str = time_str.strip()
        if ":" in time_str:
            hour, minute = map(int, time_str.split(":"))
            times.append((hour, minute))
    return times

def get_next_run_time(scheduled_times):
    """
    Calcula cuándo debe ejecutarse el próximo sync basado en horarios programados.
    """
    now = datetime.now()
    today = now.date()

    # Crear datetimes para cada horario programado hoy
    scheduled_datetimes = []
    for hour, minute in scheduled_times:
        scheduled_dt = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
        scheduled_datetimes.append(scheduled_dt)

    # Encontrar el próximo horario (hoy o mañana)
    future_times = [dt for dt in scheduled_datetimes if dt > now]

    if future_times:
        return min(future_times)
    else:
        # Si ya pasaron todos los horarios de hoy, usar el primero de mañana
        tomorrow = today + timedelta(days=1)
        first_time = min(scheduled_times)
        return datetime.combine(tomorrow, datetime.min.time().replace(hour=first_time[0], minute=first_time[1]))

def run_parallel_sync():
    """Ejecuta sync con versión paralela de Glow API"""

    # Parchear get_glow_data_batch con versión paralela
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from src.integrations.amazon_glow_api_v2_advanced import check_availability_v2_advanced

    def get_glow_data_batch_parallel(asins: list, show_progress: bool = True) -> dict:
        """Versión paralela de get_glow_data_batch"""
        if not asins:
            return {}

        unique_asins = list(set(asins))
        total_listings = len(asins)
        total_unique = len(unique_asins)

        max_delivery_days = int(os.getenv("MAX_DELIVERY_DAYS", "3"))
        buyer_zipcode = os.getenv("BUYER_ZIPCODE", "33172")

        if show_progress:
            print(f"🚀 SYNC PARALELO - {MAX_WORKERS} WORKERS", flush=True)
            print(f"🌐 Consultando {total_unique} ASINs en paralelo...", flush=True)
            print(f"   Workers: {MAX_WORKERS}, Zipcode: {buyer_zipcode}, Max delivery: {max_delivery_days}d", flush=True)
            print(flush=True)

        results = {}
        results_lock = __import__('threading').Lock()
        print_lock = __import__('threading').Lock()

        def process_asin(asin, index, total):
            try:
                if show_progress:
                    with print_lock:
                        print(f"   [{index}/{total}] {asin}...", end=" ", flush=True)

                # API call en paralelo (SIN lock)
                glow_result = check_availability_v2_advanced(asin, buyer_zipcode)

                if glow_result.get("error"):
                    if show_progress:
                        with print_lock:
                            print(f"❌ {str(glow_result.get('error'))[:50]}", flush=True)
                    return (asin, None)

                if not glow_result.get("available") or not glow_result.get("price"):
                    if show_progress:
                        with print_lock:
                            print("❌ No disponible/sin precio", flush=True)
                    return (asin, None)

                days_until = glow_result.get("days_until_delivery")
                if days_until is None or days_until > max_delivery_days:
                    if show_progress:
                        with print_lock:
                            print(f"❌ Delivery: {days_until}d", flush=True)
                    return (asin, None)

                result_data = {
                    "price": glow_result["price"],
                    "delivery_date": glow_result.get("delivery_date"),
                    "days_until_delivery": days_until,
                    "is_fast_delivery": glow_result.get("is_fast_delivery", False),
                    "prime_available": glow_result.get("prime_available", False),
                    "in_stock": glow_result.get("in_stock", False)
                }

                if show_progress:
                    with print_lock:
                        print(f"✅ ${glow_result['price']:.2f}, {days_until}d", flush=True)

                return (asin, result_data)

            except Exception as e:
                if show_progress:
                    with print_lock:
                        print(f"❌ {str(e)[:30]}", flush=True)
                return (asin, None)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_asin, asin, i+1, total_unique): asin
                      for i, asin in enumerate(unique_asins)}

            for future in as_completed(futures):
                asin, result = future.result()
                with results_lock:
                    results[asin] = result

        if show_progress:
            passed = sum(1 for v in results.values() if v is not None)
            print(f"\n✅ {passed}/{total_unique} productos aprobados\n", flush=True)

        return results

    # Reemplazar la función original con la paralela
    sync_module.get_glow_data_batch = get_glow_data_batch_parallel

    # Ejecutar sync
    sync_function()

def main():
    """Loop principal con horarios programados"""

    scheduled_times = parse_scheduled_times(SYNC_SCHEDULED_TIMES)

    if not scheduled_times:
        log("❌ ERROR: SYNC_SCHEDULED_TIMES no configurado correctamente en .env")
        log(f"   Valor actual: '{SYNC_SCHEDULED_TIMES}'")
        log(f"   Formato esperado: 'HH:MM,HH:MM,...' (ej: '00:05,06:05,12:05,18:05')")
        sys.exit(1)

    log("=" * 80)
    log("🔄 SYNC PARALELO LOOP - Iniciado")
    log("=" * 80)
    log(f"⚡ Workers paralelos: {MAX_WORKERS}")
    log(f"⏰ Horarios programados: {SYNC_SCHEDULED_TIMES}")
    log(f"📅 Horarios: {', '.join([f'{h:02d}:{m:02d}' for h, m in scheduled_times])}")
    log("=" * 80)

    while True:
        try:
            next_run = get_next_run_time(scheduled_times)
            now = datetime.now()
            wait_seconds = (next_run - now).total_seconds()

            log(f"⏰ Próxima ejecución: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            log(f"⏸️  Esperando {wait_seconds/60:.1f} minutos...")

            time.sleep(wait_seconds)

            log("=" * 80)
            log("🚀 INICIANDO SYNC PARALELO")
            log("=" * 80)

            run_parallel_sync()

            log("=" * 80)
            log("✅ SYNC COMPLETADO")
            log("=" * 80)

        except KeyboardInterrupt:
            log("\n⚠️  Loop interrumpido por usuario")
            break
        except Exception as e:
            log(f"❌ ERROR en loop: {e}")
            import traceback
            traceback.print_exc()
            log("⏸️  Esperando 5 minutos antes de reintentar...")
            time.sleep(300)

if __name__ == "__main__":
    main()
