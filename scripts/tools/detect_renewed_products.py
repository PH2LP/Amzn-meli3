#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
detect_renewed_products.py
═══════════════════════════════════════════════════════════════════════════════
DETECTOR DE PRODUCTOS RENOVADOS/REACONDICIONADOS
═══════════════════════════════════════════════════════════════════════════════

Lee todos los ASINs de la DB, consulta Amazon API y detecta productos:
- Renewed
- Refurbished
- Reacondicionado
- Used
- Open Box
etc.

USO:
    python3 scripts/tools/detect_renewed_products.py
    python3 scripts/tools/detect_renewed_products.py --export  # Exporta a CSV

RESULTADO:
    - Muestra ASINs con estos términos en el título
    - Opcionalmente exporta a CSV para revisión
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import sqlite3
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(override=True)

# Lock para imprimir de forma thread-safe
print_lock = threading.Lock()

# Importar API de Amazon
try:
    from src.integrations.amazon_glow_api import check_real_availability_glow_api
    GLOW_API_AVAILABLE = True
except ImportError:
    print("❌ Glow API no disponible")
    GLOW_API_AVAILABLE = False
    sys.exit(1)

# Colores
class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

# Palabras clave para detectar productos renovados
RENEWED_KEYWORDS = [
    'renewed',
    'refurbished',
    'reacondicionado',
    'usado',
    'used',
    'open box',
    'open-box',
    'pre-owned',
    'pre owned',
    'like new',
    'recertified',
    'recertificado',
    'restaurado',
    'restored',
    'segunda mano',
    'second hand',
    'second-hand'
]

def get_all_asins_from_db():
    """
    Obtiene todos los ASINs únicos de la base de datos de listings

    Returns:
        list: Lista de ASINs
    """
    db_path = "storage/listings_database.db"

    if not os.path.exists(db_path):
        print(f"{Colors.RED}❌ Base de datos no encontrada: {db_path}{Colors.NC}")
        return []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT asin FROM listings WHERE asin IS NOT NULL AND asin != ''")
    asins = [row[0] for row in cursor.fetchall()]

    conn.close()

    return asins


def check_if_renewed(title):
    """
    Verifica si un título contiene palabras clave de productos renovados

    Args:
        title: Título del producto

    Returns:
        tuple: (is_renewed: bool, keyword_found: str or None)
    """
    if not title:
        return False, None

    title_lower = title.lower()

    for keyword in RENEWED_KEYWORDS:
        if keyword in title_lower:
            return True, keyword

    return False, None


def check_single_asin(asin):
    """
    Verifica un solo ASIN (función para procesamiento paralelo)

    Returns:
        dict o None
    """
    try:
        # Consultar Glow API
        data = check_real_availability_glow_api(asin)

        if not data or not data.get('title'):
            return None

        title = data['title']

        # Verificar si es renovado
        is_renewed, keyword = check_if_renewed(title)

        if is_renewed:
            return {
                'asin': asin,
                'title': title,
                'keyword': keyword,
                'price': data.get('price', 'N/A')
            }

        return None

    except Exception as e:
        return None


def detect_renewed_products(export_csv=False):
    """
    Detecta productos renovados/reacondicionados en la DB usando procesamiento paralelo

    Args:
        export_csv: Si es True, exporta resultados a CSV
    """
    print(f"\n{Colors.BLUE}{'═' * 80}{Colors.NC}")
    print(f"{Colors.BLUE}DETECTOR DE PRODUCTOS RENOVADOS/REACONDICIONADOS{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 80}{Colors.NC}\n")

    # Obtener ASINs de la DB
    print(f"{Colors.CYAN}📊 Obteniendo ASINs de la base de datos...{Colors.NC}")
    asins = get_all_asins_from_db()

    if not asins:
        print(f"{Colors.RED}❌ No se encontraron ASINs en la base de datos{Colors.NC}")
        return

    print(f"{Colors.GREEN}   ✅ {len(asins)} ASINs encontrados{Colors.NC}\n")

    # Detectar productos renovados EN PARALELO
    print(f"{Colors.CYAN}🔍 Consultando Amazon API en paralelo (50 hilos)...{Colors.NC}\n")

    renewed_products = []
    processed = 0
    total = len(asins)

    # Usar ThreadPoolExecutor para procesamiento paralelo
    with ThreadPoolExecutor(max_workers=50) as executor:
        # Enviar todas las tareas
        future_to_asin = {executor.submit(check_single_asin, asin): asin for asin in asins}

        # Procesar resultados a medida que completan
        for future in as_completed(future_to_asin):
            processed += 1

            # Mostrar progreso cada 50 productos
            if processed % 50 == 0 or processed == total:
                with print_lock:
                    print(f"\r   Progreso: {processed}/{total} ({processed*100//total}%) - Encontrados: {len(renewed_products)}   ", end='', flush=True)

            try:
                result = future.result()
                if result:
                    renewed_products.append(result)
                    # Mostrar inmediatamente cuando se encuentra uno
                    with print_lock:
                        print(f"\n   {Colors.RED}🔴 ENCONTRADO: {result['asin']} ({result['keyword']}){Colors.NC}")
                        print(f"\r   Progreso: {processed}/{total} ({processed*100//total}%) - Encontrados: {len(renewed_products)}   ", end='', flush=True)

            except Exception as e:
                pass

    print()  # Nueva línea después del progreso

    # Mostrar resultados
    print(f"\n{Colors.BLUE}{'═' * 80}{Colors.NC}")
    print(f"{Colors.BLUE}RESULTADOS{Colors.NC}")
    print(f"{Colors.BLUE}{'═' * 80}{Colors.NC}\n")

    if not renewed_products:
        print(f"{Colors.GREEN}✅ No se encontraron productos renovados/reacondicionados{Colors.NC}\n")
        return

    print(f"{Colors.YELLOW}⚠️  Se encontraron {len(renewed_products)} productos renovados/reacondicionados:{Colors.NC}\n")

    for i, product in enumerate(renewed_products, 1):
        print(f"{Colors.RED}{i}. ASIN: {product['asin']}{Colors.NC}")
        print(f"   Keyword: {product['keyword']}")
        print(f"   Precio: ${product['price']}")
        print(f"   Título: {product['title'][:80]}...")
        print()

    # Exportar a CSV si se solicitó
    if export_csv:
        export_to_csv(renewed_products)

    print(f"{Colors.BLUE}{'═' * 80}{Colors.NC}\n")


def export_to_csv(renewed_products):
    """
    Exporta los productos renovados a un archivo CSV

    Args:
        renewed_products: Lista de productos renovados
    """
    import csv
    from datetime import datetime

    filename = f"renewed_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['asin', 'keyword', 'price', 'title'])
        writer.writeheader()
        writer.writerows(renewed_products)

    print(f"{Colors.GREEN}   ✅ Exportado a: {filename}{Colors.NC}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Detecta productos renovados/reacondicionados")
    parser.add_argument("--export", action="store_true", help="Exportar resultados a CSV")

    args = parser.parse_args()

    detect_renewed_products(export_csv=args.export)


if __name__ == "__main__":
    main()
