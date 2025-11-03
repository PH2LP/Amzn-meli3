#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para el sistema de sincronización Amazon → MercadoLibre
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("🧪 TEST DEL SISTEMA DE SINCRONIZACIÓN")
print("=" * 80)
print()

# Test 1: Verificar variables de entorno
print("1️⃣ Verificando variables de entorno...")
required_vars = [
    "LWA_CLIENT_ID",
    "LWA_CLIENT_SECRET",
    "REFRESH_TOKEN",
    "ML_ACCESS_TOKEN",
    "PRICE_MARKUP_PERCENT"
]

missing_vars = []
for var in required_vars:
    value = os.getenv(var)
    if value:
        masked_value = value[:10] + "..." if len(value) > 10 else value
        print(f"   ✅ {var}: {masked_value}")
    else:
        print(f"   ❌ {var}: NO ENCONTRADA")
        missing_vars.append(var)

if missing_vars:
    print(f"\n❌ Faltan variables de entorno: {', '.join(missing_vars)}")
    sys.exit(1)

print("   ✅ Todas las variables encontradas\n")

# Test 2: Verificar base de datos
print("2️⃣ Verificando base de datos...")
import sqlite3

DB_PATH = "storage/listings_database.db"

if not os.path.exists(DB_PATH):
    print(f"   ❌ Base de datos no encontrada: {DB_PATH}")
    print(f"   → Ejecuta: python3 save_listing_data.py")
    sys.exit(1)

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM listings")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM listings WHERE item_id IS NOT NULL")
    with_item_id = cursor.fetchone()[0]

    print(f"   ✅ Base de datos encontrada")
    print(f"   📊 Total de listings: {total}")
    print(f"   📊 Con item_id: {with_item_id}")

    if with_item_id == 0:
        print(f"   ⚠️ Ningún listing tiene item_id asignado")
        print(f"   → Los item_ids se asignan cuando publicas en ML")
        print(f"   → O ejecuta: python3 update_listings_item_ids.py")

    conn.close()
except Exception as e:
    print(f"   ❌ Error accediendo a la BD: {e}")
    sys.exit(1)

print()

# Test 3: Probar conexión con Amazon
print("3️⃣ Probando conexión con Amazon SP-API...")
try:
    from sync_amazon_ml import get_amazon_access_token, check_amazon_product_status

    print("   🔐 Obteniendo access token...")
    token = get_amazon_access_token()
    print("   ✅ Token obtenido exitosamente")

    # Probar con un ASIN de la BD
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT asin FROM listings LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if row:
        test_asin = row[0]
        print(f"   📦 Probando con ASIN: {test_asin}")

        status = check_amazon_product_status(test_asin, token)

        print(f"   📊 Estado: {status['status']}")
        print(f"   📊 Disponible: {status['available']}")
        print(f"   📊 Precio: ${status['price']} USD" if status['price'] else "   📊 Precio: N/A")
        print(f"   📊 Comprable: {status['buyable']}")

        if status.get('error'):
            print(f"   ⚠️ Nota: {status['error']}")

        if status['status'] in ['active', 'unavailable']:
            print("   ✅ Conexión con Amazon exitosa")
        else:
            print(f"   ⚠️ Respuesta inesperada de Amazon")
    else:
        print("   ⚠️ No hay ASINs en la BD para probar")

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 4: Verificar permisos de MercadoLibre
print("4️⃣ Verificando conexión con MercadoLibre...")
try:
    import requests

    ML_API = "https://api.mercadolibre.com"
    ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    r = requests.get(f"{ML_API}/users/me", headers=headers, timeout=10)
    r.raise_for_status()
    user = r.json()

    print(f"   ✅ Conectado como: {user.get('nickname', 'N/A')}")
    print(f"   📊 User ID: {user.get('id', 'N/A')}")
    print(f"   📊 País: {user.get('site_id', 'N/A')}")

except Exception as e:
    print(f"   ❌ Error conectando a ML: {e}")
    print(f"   → Verifica que ML_ACCESS_TOKEN sea válido")
    sys.exit(1)

print()

# Resumen
print("=" * 80)
print("✅ TODOS LOS TESTS PASARON EXITOSAMENTE")
print("=" * 80)
print()
print("📝 Próximos pasos:")
print()

if with_item_id == 0:
    print("⚠️ IMPORTANTE: Ningún listing tiene item_id asignado")
    print()
    print("Opciones:")
    print("   1. Publica productos en ML usando tu pipeline normal")
    print("   2. Si ya publicaste, actualiza los item_ids con:")
    print("      python3 update_listings_item_ids.py")
    print()
else:
    print("1. Ejecutar sincronización manual:")
    print("   python3 sync_amazon_ml.py")
    print()
    print("2. Instalar cron job (cada 3 días):")
    print("   ./setup_sync_cron.sh")
    print()
    print("3. Ver logs:")
    print("   cat logs/sync/sync_cron.log")
    print()

print("✅ Sistema listo para usar")
