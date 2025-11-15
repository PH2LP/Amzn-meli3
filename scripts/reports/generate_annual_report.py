#!/usr/bin/env python3
"""
Generador de Reporte Anual de Negocio
======================================
Analiza todos los datos históricos del año para generar un reporte completo:
- Productos publicados por mes
- Cambios de precio históricos
- Productos pausados y reactivados
- Errores y problemas frecuentes
- Métricas de rendimiento
- Análisis de categorías más exitosas
"""

import json
import gzip
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import sys

PROJECT_DIR = Path(__file__).parent.parent.parent
LOGS_DIR = PROJECT_DIR / "logs" / "sync"
DB_PATH = PROJECT_DIR / "storage" / "listings_database.db"
OUTPUT_DIR = PROJECT_DIR / "reports"
OUTPUT_DIR.mkdir(exist_ok=True)

def load_sync_logs(year=None):
    """Carga todos los logs de sync (JSON y JSON.gz) del año especificado"""
    if year is None:
        year = datetime.now().year

    sync_logs = []

    # Buscar archivos JSON y JSON.gz
    for pattern in ["sync_*.json", "sync_*.json.gz"]:
        for file_path in LOGS_DIR.glob(pattern):
            try:
                # Extraer fecha del nombre del archivo: sync_YYYYMMDD_HHMMSS.json
                filename = file_path.stem.replace('.json', '')
                date_part = filename.split('_')[1]  # YYYYMMDD
                file_year = int(date_part[:4])

                if file_year != year:
                    continue

                # Leer archivo (comprimido o no)
                if file_path.suffix == '.gz':
                    with gzip.open(file_path, 'rt') as f:
                        data = json.load(f)
                else:
                    with open(file_path, 'r') as f:
                        data = json.load(f)

                sync_logs.append({
                    'file': file_path.name,
                    'date': datetime.strptime(date_part, '%Y%m%d'),
                    'data': data
                })

            except Exception as e:
                print(f"⚠️  Error leyendo {file_path.name}: {e}")

    return sorted(sync_logs, key=lambda x: x['date'])

def analyze_sync_logs(logs):
    """Analiza todos los logs de sync para extraer métricas"""
    metrics = {
        'total_syncs': len(logs),
        'products_by_month': defaultdict(int),
        'price_changes': [],
        'paused_products': [],
        'reactivated_products': [],
        'errors': defaultdict(int),
        'total_price_updates': 0,
        'total_paused': 0,
        'total_reactivated': 0,
    }

    for log_entry in logs:
        data = log_entry['data']
        month_key = log_entry['date'].strftime('%Y-%m')

        # Extraer información del log
        if 'actions' in data:
            for action in data['actions']:
                if action.get('action') == 'price_update':
                    metrics['total_price_updates'] += 1
                    metrics['price_changes'].append({
                        'date': log_entry['date'],
                        'asin': action.get('asin'),
                        'old_price': action.get('old_price'),
                        'new_price': action.get('new_price')
                    })

                elif action.get('action') == 'pause':
                    metrics['total_paused'] += 1
                    metrics['paused_products'].append({
                        'date': log_entry['date'],
                        'asin': action.get('asin'),
                        'reason': action.get('reason')
                    })

                elif action.get('action') == 'reactivate':
                    metrics['total_reactivated'] += 1
                    metrics['reactivated_products'].append({
                        'date': log_entry['date'],
                        'asin': action.get('asin')
                    })

        # Contar errores
        if 'errors' in data:
            for error in data['errors']:
                error_type = error.get('error', 'unknown')
                metrics['errors'][error_type] += 1

    return metrics

def get_database_stats():
    """Obtiene estadísticas de la base de datos"""
    if not DB_PATH.exists():
        return None

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    stats = {}

    # Total de productos
    cursor.execute("SELECT COUNT(*) FROM listings WHERE item_id IS NOT NULL")
    stats['total_products'] = cursor.fetchone()[0]

    # Productos por país
    cursor.execute("""
        SELECT country, COUNT(*)
        FROM listings
        WHERE item_id IS NOT NULL
        GROUP BY country
        ORDER BY COUNT(*) DESC
    """)
    stats['by_country'] = dict(cursor.fetchall())

    # Top 10 categorías
    cursor.execute("""
        SELECT category_name, COUNT(*)
        FROM listings
        WHERE item_id IS NOT NULL AND category_name IS NOT NULL
        GROUP BY category_name
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    stats['top_categories'] = dict(cursor.fetchall())

    # Rango de precios
    cursor.execute("""
        SELECT
            MIN(price_usd) as min_price,
            MAX(price_usd) as max_price,
            AVG(price_usd) as avg_price
        FROM listings
        WHERE item_id IS NOT NULL AND price_usd > 0
    """)
    row = cursor.fetchone()
    stats['price_range'] = {
        'min': row[0],
        'max': row[1],
        'avg': row[2]
    }

    conn.close()
    return stats

def generate_report(year=None):
    """Genera el reporte anual completo"""
    if year is None:
        year = datetime.now().year

    print("=" * 80)
    print(f"📊 GENERANDO REPORTE ANUAL {year}")
    print("=" * 80)
    print()

    # 1. Cargar logs de sync
    print("📂 Cargando logs históricos...")
    logs = load_sync_logs(year)
    print(f"   ✅ Cargados {len(logs)} logs de sync del {year}")
    print()

    # 2. Analizar logs
    print("🔍 Analizando datos...")
    metrics = analyze_sync_logs(logs)
    print("   ✅ Análisis completado")
    print()

    # 3. Obtener estadísticas de BD
    print("💾 Consultando base de datos...")
    db_stats = get_database_stats()
    print("   ✅ Estadísticas obtenidas")
    print()

    # 4. Generar reporte
    report = {
        'year': year,
        'generated_at': datetime.now().isoformat(),
        'sync_metrics': {
            'total_syncs': metrics['total_syncs'],
            'total_price_updates': metrics['total_price_updates'],
            'total_paused': metrics['total_paused'],
            'total_reactivated': metrics['total_reactivated'],
            'errors_by_type': dict(metrics['errors'])
        },
        'database_stats': db_stats,
        'price_changes_sample': metrics['price_changes'][:100],  # Primeros 100
        'paused_products_sample': metrics['paused_products'][:50],
        'logs_analyzed': len(logs)
    }

    # 5. Guardar reporte
    output_file = OUTPUT_DIR / f"annual_report_{year}.json"
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)

    print("=" * 80)
    print(f"📄 REPORTE GENERADO: {output_file}")
    print("=" * 80)
    print()
    print(f"📊 Resumen:")
    print(f"   Total productos activos: {db_stats['total_products'] if db_stats else 'N/A'}")
    print(f"   Syncs realizados: {metrics['total_syncs']}")
    print(f"   Actualizaciones de precio: {metrics['total_price_updates']}")
    print(f"   Productos pausados: {metrics['total_paused']}")
    print(f"   Productos reactivados: {metrics['total_reactivated']}")
    print()

    return output_file

if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else None
    generate_report(year)
