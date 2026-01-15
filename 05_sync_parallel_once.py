#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SYNC PARALELO (UNA VEZ) - Amazon ↔ MercadoLibre
================================================
Versión PARALELA del sync con 3 workers simultáneos (configurable).

MEJORAS vs sync normal:
- 🚀 3x más rápido (3 threads procesando ASINs simultáneamente)
- 🎲 Timing irregular (mejor anti-detección de Amazon)
- 🔒 Mantiene todas las protecciones (rate limiting, session rotation, etc)

CONFIGURACIÓN (.env):
- SYNC_WORKERS: Número de threads (default: 3, max recomendado: 5)

USO:
    python3 05_sync_parallel_once.py
"""

import os
import sys
from pathlib import Path

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

# Importar y ejecutar sync principal
from scripts.tools.sync_amazon_ml_GLOW import (
    main as sync_main,
    get_glow_data_batch,
    get_all_published_listings,
    sync_one_listing,
    check_amazon_product_status_from_cache
)
import json
import sqlite3
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

# Configuración de workers paralelos
MAX_WORKERS = int(os.getenv("SYNC_WORKERS", "3"))

# ============================================================
# VERSIÓN PARALELA DE get_glow_data_batch
# ============================================================

def get_glow_data_batch_parallel(asins: list, show_progress: bool = True) -> dict:
    """
    Versión PARALELA de get_glow_data_batch que procesa ASINs en múltiples threads.

    Divide los ASINs en grupos y los procesa simultáneamente con diferentes sesiones.
    Cada thread tiene su propia sesión de curl_cffi con cookies y user-agent únicos.
    """
    if not asins:
        return {}

    from src.integrations.amazon_glow_api_v2_advanced import check_availability_v2_advanced

    # Deduplicar ASINs
    unique_asins = list(set(asins))
    total_listings = len(asins)
    total_unique = len(unique_asins)

    # Configuración
    max_delivery_days = int(os.getenv("MAX_DELIVERY_DAYS", "3"))
    buyer_zipcode = os.getenv("BUYER_ZIPCODE", "33172")

    if show_progress:
        print(f"🚀 SYNC PARALELO - {MAX_WORKERS} WORKERS", flush=True)
        print(f"🌐 Consultando Glow API para {total_unique} ASINs únicos (de {total_listings} listings)...", flush=True)
        if total_unique < total_listings:
            print(f"   ⚡ Optimización: {total_listings - total_unique} consultas ahorradas", flush=True)
        print(f"   Zipcode: {buyer_zipcode}", flush=True)
        print(f"   Max delivery: {max_delivery_days} días", flush=True)
        print(f"   Workers paralelos: {MAX_WORKERS}", flush=True)
        print(flush=True)

    results = {}
    results_lock = __import__('threading').Lock()
    print_lock = __import__('threading').Lock()  # Lock para prints secuenciales

    def process_asin(asin, index, total):
        """Procesa un ASIN individual"""

        try:
            # Print inicial SIN esperar resultado (para ver progreso)
            if show_progress:
                with print_lock:
                    print(f"   [{index}/{total}] {asin}...", end=" ", flush=True)

            # API call SIN lock (aquí se ejecuta en paralelo)
            glow_result = check_availability_v2_advanced(asin, buyer_zipcode)

            # Procesar resultado con lock solo para prints
            if glow_result.get("error"):
                error_msg = str(glow_result.get("error"))[:50]
                if show_progress:
                    with print_lock:
                        print(f"❌ {error_msg}", flush=True)
                return (asin, None)

            if not glow_result.get("available"):
                if show_progress:
                    with print_lock:
                        print("❌ No disponible", flush=True)
                return (asin, None)

            if not glow_result.get("price"):
                if show_progress:
                    with print_lock:
                        print("❌ Sin precio", flush=True)
                return (asin, None)

            days_until = glow_result.get("days_until_delivery")
            delivery_date_text = glow_result.get("delivery_date", "")
            delivery_date_clean = glow_result.get("delivery_date_clean")

            if days_until is None:
                if show_progress:
                    with print_lock:
                        if delivery_date_text:
                            print(f"❌ Llega entre {delivery_date_text[:50]} (sin fecha específica)", flush=True)
                        else:
                            print("❌ Sin información de delivery", flush=True)
                return (asin, None)

            if days_until > max_delivery_days:
                if show_progress:
                    with print_lock:
                        fecha_display = delivery_date_clean if delivery_date_clean else delivery_date_text[:30]
                        print(f"❌ Llega: {fecha_display}, Días: {days_until} (max: {max_delivery_days})", flush=True)
                return (asin, None)

            # ✅ Producto aprobado
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
                    fecha_display = delivery_date_clean if delivery_date_clean else delivery_date_text[:30]
                    print(f"✅ Precio: ${glow_result['price']:.2f}, Llega: {fecha_display}, Días: {days_until}", flush=True)

            return (asin, result_data)

        except Exception as e:
            if show_progress:
                with print_lock:
                    print(f"❌ Error: {str(e)[:50]}", flush=True)
            return (asin, None)

    # Procesar ASINs en paralelo
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_asin, asin, i+1, total_unique): asin
                  for i, asin in enumerate(unique_asins)}

        for future in as_completed(futures):
            asin, result = future.result()
            with results_lock:
                results[asin] = result

    if show_progress:
        passed = sum(1 for v in results.values() if v is not None)
        print()
        print(f"✅ Resultados: {passed}/{total_unique} productos aprobados")
        print()

    return results


# ============================================================
# MAIN MODIFICADO PARA USAR VERSIÓN PARALELA
# ============================================================

def main():
    """Main con procesamiento paralelo de Glow API"""

    # Importar todas las funciones necesarias
    from scripts.tools.sync_amazon_ml_GLOW import (
        get_fresh_ml_token,
        refresh_ml_token,
        DB_PATH,
        LOG_DIR,
        ML_API
    )
    from dotenv import load_dotenv

    load_dotenv(override=False)

    start_time = datetime.now()

    # Refrescar token de ML
    print("🔑 Verificando token de MercadoLibre...", flush=True)
    if refresh_ml_token():
        print("✅ Token de ML refrescado correctamente", flush=True)
    else:
        print("⚠️ Token de ML ya está vigente", flush=True)
    print(flush=True)

    load_dotenv(override=False)

    # Configuración
    current_markup = float(os.getenv("PRICE_MARKUP", "30"))
    use_tax = os.getenv("USE_TAX", "true").lower() == "true"
    fulfillment_fee = float(os.getenv("FULFILLMENT_FEE", "4.0"))
    max_delivery_days = int(os.getenv("MAX_DELIVERY_DAYS", "3"))

    print("=" * 80, flush=True)
    print("🔄 SINCRONIZACIÓN PARALELA AMAZON → MERCADOLIBRE", flush=True)
    print("=" * 80, flush=True)
    print(f"📅 Fecha: {start_time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"⚡ Workers paralelos: {MAX_WORKERS}", flush=True)
    print(f"💰 Markup configurado: {current_markup}%", flush=True)
    print(f"💵 Tax (7% Florida): {'ACTIVADO' if use_tax else 'DESACTIVADO'}", flush=True)
    print(f"📦 Fulfillment Fee: ${fulfillment_fee} USD", flush=True)
    print(f"🚚 Max Delivery Days: {max_delivery_days} días", flush=True)
    print(flush=True)

    # Verificar BD
    if not os.path.exists(DB_PATH):
        print(f"❌ No se encontró la base de datos: {DB_PATH}", flush=True)
        sys.exit(1)

    # Cargar listings
    print("📋 Cargando listings desde la base de datos...", flush=True)
    listings = get_all_published_listings()

    if not listings:
        print("⚠️ No se encontraron listings publicados", flush=True)
        sys.exit(0)

    print(f"✅ Encontrados {len(listings)} listings para sincronizar\n", flush=True)

    # Extraer ASINs
    asins = [listing["asin"] for listing in listings]

    # ===== PROCESAMIENTO PARALELO DE GLOW API =====
    print(f"{'='*80}", flush=True)
    print(f"🌐 CONSULTANDO GLOW API (MODO PARALELO)", flush=True)
    print(f"{'='*80}", flush=True)
    print()

    glow_start_time = datetime.now()
    glow_cache = get_glow_data_batch_parallel(asins, show_progress=True)
    glow_end_time = datetime.now()
    glow_duration = (glow_end_time - glow_start_time).total_seconds()

    passed = sum(1 for v in glow_cache.values() if v is not None)
    print(f"{'='*80}", flush=True)
    print(f"✅ Cache de Glow API listo: {passed}/{len(glow_cache)} productos aprobados")
    print(f"⏱️  Tiempo de consulta Amazon: {glow_duration:.1f}s ({glow_duration/60:.1f} min)")
    print(f"⚡ Velocidad: {len(asins)/glow_duration:.2f} ASINs/segundo")
    print(f"{'='*80}", flush=True)
    print()

    # Continuar con sync normal (ML updates son secuenciales)
    changes_log = []
    stats = {
        "total": len(listings),
        "paused": 0,
        "reactivated": 0,
        "price_updated": 0,
        "no_change": 0,
        "errors": 0,
        "errors_wrong_account": 0
    }

    ml_update_start_time = datetime.now()
    for i, listing in enumerate(listings, 1):
        print(f"\n[{i}/{len(listings)}]", end=" ")
        result = sync_one_listing(listing, glow_cache, changes_log)

        # Actualizar stats
        if result["success"]:
            if result["action"] == "paused":
                stats["paused"] += 1
            elif result["action"] == "reactivated":
                stats["reactivated"] += 1
            elif result["action"] == "price_updated":
                stats["price_updated"] += 1
            elif result["action"] == "no_change":
                stats["no_change"] += 1
        else:
            stats["errors"] += 1

    # Guardar log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"sync_{timestamp}.json"

    log_data = {
        "timestamp": datetime.now().isoformat(),
        "parallel_mode": True,
        "workers": MAX_WORKERS,
        "statistics": stats,
        "changes": changes_log
    }

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    ml_update_duration = (datetime.now() - ml_update_start_time).total_seconds()
    total_duration = (datetime.now() - start_time).total_seconds()

    # Resumen
    print("\n" + "=" * 80)
    print("📊 RESUMEN DE SINCRONIZACIÓN")
    print("=" * 80)
    print(f"Total procesados:              {stats['total']}")
    print(f"Productos reactivados:         {stats['reactivated']}")
    print(f"Publicaciones pausadas:        {stats['paused']}")
    print(f"Precios actualizados:          {stats['price_updated']}")
    print(f"Sin cambios:                   {stats['no_change']}")
    print(f"Errores:                       {stats['errors']}")
    print()
    print("⏱️  TIEMPOS DE EJECUCIÓN")
    print("=" * 80)
    print(f"Consulta Amazon (paralelo):    {glow_duration:.1f}s ({glow_duration/60:.1f} min)")
    print(f"Actualización MercadoLibre:    {ml_update_duration:.1f}s")
    print(f"TOTAL:                         {total_duration:.1f}s ({total_duration/60:.1f} min)")
    print(f"\n📄 Log guardado en: {log_file}")
    print("\n✅ Sincronización paralela completada")


if __name__ == "__main__":
    main()
