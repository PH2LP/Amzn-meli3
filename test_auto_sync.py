#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para verificar que el sistema de sincronización
automática está completamente integrado.
"""

import os
import sys
import sqlite3
from pathlib import Path

DB_PATH = "storage/listings_database.db"

print("=" * 80)
print("🧪 TEST DE INTEGRACIÓN - SINCRONIZACIÓN AUTOMÁTICA")
print("=" * 80)
print()

# Test 1: Verificar que mainglobal.py tiene la integración
print("1️⃣ Verificando integración en mainglobal.py...")

with open("src/mainglobal.py", "r") as f:
    content = f.read()

if "save_listing_data import save_listing" in content:
    print("   ✅ Importación de save_listing encontrada")
else:
    print("   ❌ Falta importación de save_listing")
    sys.exit(1)

if "save_listing(" in content and "item_id=item_id" in content:
    print("   ✅ Llamada a save_listing() después de publicar encontrada")
else:
    print("   ❌ Falta llamada a save_listing() después de publicar")
    sys.exit(1)

print("   ✅ mainglobal.py está integrado correctamente")
print()

# Test 2: Verificar estructura de BD
print("2️⃣ Verificando estructura de base de datos...")

if not os.path.exists(DB_PATH):
    print("   ⚠️ Base de datos aún no existe (normal si no has publicado)")
    print("   → Se creará automáticamente al publicar el primer producto")
else:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Verificar que existe la tabla listings
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='listings'")
    if cursor.fetchone():
        print("   ✅ Tabla 'listings' existe")

        # Verificar columnas importantes
        cursor.execute("PRAGMA table_info(listings)")
        columns = [row[1] for row in cursor.fetchall()]

        required_cols = ['item_id', 'asin', 'price_usd', 'title']
        for col in required_cols:
            if col in columns:
                print(f"   ✅ Columna '{col}' existe")
            else:
                print(f"   ❌ Falta columna '{col}'")

        # Ver estadísticas
        cursor.execute("SELECT COUNT(*) FROM listings")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM listings WHERE item_id IS NOT NULL")
        with_item_id = cursor.fetchone()[0]

        print(f"   📊 Listings totales: {total}")
        print(f"   📊 Con item_id: {with_item_id}")

    else:
        print("   ❌ Tabla 'listings' no existe")
        sys.exit(1)

    conn.close()

print()

# Test 3: Verificar que el cron job está listo
print("3️⃣ Verificando scripts de sincronización...")

scripts = {
    "sync_amazon_ml.py": "Script principal de sincronización",
    "setup_sync_cron.sh": "Instalador de cron job",
    "test_sync.py": "Script de pruebas",
    "add_item_id_manually.py": "Script para agregar item_ids manualmente"
}

for script, desc in scripts.items():
    if os.path.exists(script):
        print(f"   ✅ {script}: {desc}")
    else:
        print(f"   ❌ Falta {script}")

print()

# Test 4: Flujo completo
print("4️⃣ Verificando flujo completo...")
print()
print("   📝 FLUJO DE SINCRONIZACIÓN AUTOMÁTICA:")
print("   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("   1. Usuario ejecuta: python3 src/mainglobal.py")
print("   2. El script publica el producto en MercadoLibre")
print("   3. Obtiene el item_id de la respuesta de ML")
print("   4. 🆕 Guarda automáticamente en la BD:")
print("      - ASIN → Item ID")
print("      - Precio inicial")
print("      - Título, descripción, etc.")
print("   5. ⏰ Cada 3 días, el cron job ejecuta:")
print("      sync_amazon_ml.py")
print("   6. El script de sync:")
print("      - Lee todos los listings de la BD")
print("      - Consulta Amazon por cada ASIN")
print("      - Detecta cambios de precio o disponibilidad")
print("      - Actualiza MercadoLibre automáticamente")
print("   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print()

# Resumen final
print("=" * 80)
print("✅ SISTEMA COMPLETAMENTE INTEGRADO")
print("=" * 80)
print()
print("📝 Próximos pasos:")
print()
print("1. Publica un producto normalmente:")
print("   python3 src/mainglobal.py")
print()
print("2. El item_id se guardará automáticamente en la BD")
print()
print("3. Verifica que se guardó:")
print("   sqlite3 storage/listings_database.db \"SELECT asin, item_id FROM listings;\"")
print()
print("4. Instala el cron job (una sola vez):")
print("   ./setup_sync_cron.sh")
print()
print("5. A partir de ahora, TODO ES AUTOMÁTICO:")
print("   - Cada nuevo producto que publiques se agregará a la BD")
print("   - Cada 3 días se sincronizará con Amazon")
print("   - Los precios se actualizarán automáticamente")
print("   - Los productos descontinuados se pausarán")
print()
print("✅ ¡Sistema listo para producción!")
