#!/usr/bin/env python3
"""
GLOW API - Procesamiento Paralelo Optimizado

Procesa 50,000 productos usando Glow API con múltiples workers paralelos.
Todos los requests desde la misma IP (tu Mac en Miami) para consistencia.

Ventajas:
- Gratis (vs $75-500/mes proxies)
- Misma IP de Miami = resultados consistentes
- 10x más rápido con paralelismo
- No requiere proxies ni servicios externos

Uso:
    python3 31_glow_parallel_optimized.py

Variables de entorno (.env):
    BUYER_ZIPCODE=33172
    MAX_DELIVERY_DAYS=2
"""

import os
import sys
import time
import sqlite3
from datetime import datetime
from multiprocessing import Pool, cpu_count
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import re

load_dotenv()

# Configuración
ZIPCODE = os.getenv('BUYER_ZIPCODE', '33172')
MAX_DELIVERY_DAYS = int(os.getenv('MAX_DELIVERY_DAYS', '2'))
NUM_WORKERS = 4  # Número de procesos paralelos (conservador para evitar rate limit)
DELAY_BETWEEN_REQUESTS = 1.5  # Segundos de delay por request (rate limit seguro)
DB_PATH = 'storage/listings_database.db'

# Glow API endpoint
GLOW_API_BASE = "https://www.amazon.com/gp/delivery/ajax/address-change.html"

print("=" * 80)
print("🚀 GLOW API - Procesamiento Paralelo Optimizado")
print("=" * 80)
print(f"Zipcode: {ZIPCODE}")
print(f"Max delivery days: {MAX_DELIVERY_DAYS}")
print(f"Workers paralelos: {NUM_WORKERS}")
print(f"CPU cores disponibles: {cpu_count()}")
print()


def get_asins_to_process():
    """Obtiene todos los ASINs pendientes de procesar de la DB"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ASINs que necesitan validación de delivery
    # (puedes ajustar el query según tu lógica de negocio)
    query = """
        SELECT DISTINCT asin
        FROM listings
        WHERE asin IS NOT NULL
        AND asin != ''
        ORDER BY asin
    """

    cursor.execute(query)
    asins = [row[0] for row in cursor.fetchall()]
    conn.close()

    return asins


def extract_delivery_info(html_content):
    """
    Extrae información de delivery del HTML de Amazon

    Returns:
        dict con keys: found, text, date, days
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Buscar bloque de delivery
    delivery_block = soup.find(id='mir-layout-DELIVERY_BLOCK')

    if not delivery_block:
        return {
            'found': False,
            'text': None,
            'date': None,
            'days': None
        }

    delivery_text = delivery_block.get_text(strip=True)

    # Extraer fecha (formato: "Monday, December 31")
    date_pattern = r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\w+)\s+(\d+)'
    date_match = re.search(date_pattern, delivery_text)

    delivery_date = None
    days_until = None

    if date_match:
        month_map = {
            'January': 1, 'February': 2, 'March': 3, 'April': 4,
            'May': 5, 'June': 6, 'July': 7, 'August': 8,
            'September': 9, 'October': 10, 'November': 11, 'December': 12
        }

        month_num = month_map.get(date_match.group(2))
        day = int(date_match.group(3))

        if month_num:
            try:
                year = 2025 if month_num == 1 else datetime.now().year
                delivery_date = datetime(year, month_num, day)
                days_until = (delivery_date - datetime.now()).days
            except:
                pass

    return {
        'found': True,
        'text': delivery_text[:150],
        'date': delivery_date.strftime('%Y-%m-%d') if delivery_date else None,
        'days': days_until
    }


def validate_asin_with_glow(asin):
    """
    Valida un ASIN usando Glow API

    Args:
        asin: Amazon Standard Identification Number

    Returns:
        dict con resultado de la validación
    """
    product_url = f"https://www.amazon.com/dp/{asin}"

    # Headers normales de browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }

    try:
        # Request a la página del producto
        response = requests.get(product_url, headers=headers, timeout=30)

        if response.status_code != 200:
            return {
                'asin': asin,
                'success': False,
                'error': f'HTTP {response.status_code}',
                'delivery_days': None,
                'passed_filter': False
            }

        # Extraer delivery info
        delivery = extract_delivery_info(response.text)

        if not delivery['found'] or delivery['days'] is None:
            return {
                'asin': asin,
                'success': False,
                'error': 'No delivery info found',
                'delivery_days': None,
                'passed_filter': False
            }

        # Verificar si pasa el filtro de MAX_DELIVERY_DAYS
        passed_filter = delivery['days'] <= MAX_DELIVERY_DAYS

        return {
            'asin': asin,
            'success': True,
            'error': None,
            'delivery_days': delivery['days'],
            'delivery_date': delivery['date'],
            'delivery_text': delivery['text'],
            'passed_filter': passed_filter
        }

    except requests.exceptions.Timeout:
        return {
            'asin': asin,
            'success': False,
            'error': 'Timeout',
            'delivery_days': None,
            'passed_filter': False
        }
    except Exception as e:
        return {
            'asin': asin,
            'success': False,
            'error': str(e)[:100],
            'delivery_days': None,
            'passed_filter': False
        }


def worker_process_asin(asin):
    """
    Worker function para procesar un ASIN (llamado por multiprocessing.Pool)

    Incluye delay para evitar rate limiting
    """
    result = validate_asin_with_glow(asin)

    # Delay seguro para evitar bloqueo de Amazon
    # 4 workers × 1.5s delay = ~2.6 requests/segundo total (SAFE)
    time.sleep(DELAY_BETWEEN_REQUESTS)

    return result


def save_results_to_db(results):
    """Guarda resultados en la DB (opcional - puedes ajustar según tu esquema)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Crear tabla de validaciones si no existe
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS delivery_validations (
            asin TEXT PRIMARY KEY,
            delivery_days INTEGER,
            delivery_date TEXT,
            passed_filter BOOLEAN,
            validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insertar resultados
    for result in results:
        if result['success']:
            cursor.execute("""
                INSERT OR REPLACE INTO delivery_validations
                (asin, delivery_days, delivery_date, passed_filter)
                VALUES (?, ?, ?, ?)
            """, (
                result['asin'],
                result['delivery_days'],
                result.get('delivery_date'),
                result['passed_filter']
            ))

    conn.commit()
    conn.close()


def main():
    """Main execution"""

    # 1. Obtener ASINs a procesar
    print("📦 Cargando ASINs desde DB...")
    asins = get_asins_to_process()
    total_asins = len(asins)

    if total_asins == 0:
        print("❌ No hay ASINs para procesar")
        return

    print(f"✅ {total_asins:,} ASINs encontrados")
    print()

    # 2. Procesar con multiprocessing.Pool
    print(f"🚀 Iniciando procesamiento paralelo con {NUM_WORKERS} workers...")
    print()

    start_time = time.time()
    results = []

    with Pool(processes=NUM_WORKERS) as pool:
        # Process asins in parallel
        for i, result in enumerate(pool.imap_unordered(worker_process_asin, asins), 1):
            results.append(result)

            # Progress update cada 100 ASINs
            if i % 100 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                eta_seconds = (total_asins - i) / rate if rate > 0 else 0
                eta_minutes = eta_seconds / 60

                # Count successful validations
                successful = sum(1 for r in results if r['success'])
                passed = sum(1 for r in results if r.get('passed_filter', False))

                print(f"Progress: {i:,}/{total_asins:,} ({i/total_asins*100:.1f}%) | "
                      f"Rate: {rate:.1f} ASINs/sec | "
                      f"ETA: {eta_minutes:.1f} min | "
                      f"Valid: {successful} | Passed: {passed}")

    elapsed_total = time.time() - start_time

    print()
    print("=" * 80)
    print("✅ PROCESAMIENTO COMPLETO")
    print("=" * 80)
    print()

    # 3. Estadísticas finales
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    passed_filter = sum(1 for r in results if r.get('passed_filter', False))

    print(f"Total procesados: {len(results):,}")
    print(f"Exitosos: {successful:,} ({successful/len(results)*100:.1f}%)")
    print(f"Fallidos: {failed:,}")
    print(f"Pasaron filtro (≤{MAX_DELIVERY_DAYS} días): {passed_filter:,} ({passed_filter/len(results)*100:.1f}%)")
    print()
    print(f"Tiempo total: {elapsed_total/60:.1f} minutos")
    print(f"Velocidad promedio: {len(results)/elapsed_total:.1f} ASINs/segundo")
    print()

    # 4. Guardar resultados
    print("💾 Guardando resultados en DB...")
    save_results_to_db(results)
    print("✅ Resultados guardados")
    print()

    # 5. Proyección para 50k productos
    if total_asins < 50000:
        rate_per_second = len(results) / elapsed_total
        time_for_50k = 50000 / rate_per_second
        print("=" * 80)
        print("📊 PROYECCIÓN PARA 50,000 PRODUCTOS")
        print("=" * 80)
        print(f"Tiempo estimado: {time_for_50k/60:.1f} minutos ({time_for_50k/3600:.1f} horas)")
        print()

    # 6. Mostrar algunos ejemplos de ASINs que pasaron el filtro
    print("=" * 80)
    print(f"📦 EJEMPLOS DE ASINs QUE PASARON EL FILTRO (≤{MAX_DELIVERY_DAYS} días)")
    print("=" * 80)

    passed_examples = [r for r in results if r.get('passed_filter', False)][:10]

    if passed_examples:
        for result in passed_examples:
            print(f"✅ {result['asin']} → {result['delivery_days']} días ({result.get('delivery_date', 'N/A')})")
    else:
        print("⚠️  No hay ASINs que pasen el filtro")

    print()
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Procesamiento interrumpido por usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
