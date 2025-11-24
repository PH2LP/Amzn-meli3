#!/usr/bin/env python3
"""
Test directo de actualización de precio en ML
Sin usar site_listings, solo net_proceeds global
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
ML_API = "https://api.mercadolibre.com"

item_id = "CBT3079074206"

# Obtener precio actual desde alguno de los item_ids locales que aún existan
# Intentemos con MLC (Chile) que según el usuario aún existe
local_item_id = "MLC3354195536"

print("=" * 80)
print("🧪 TEST DIRECTO DE ACTUALIZACIÓN DE PRECIO")
print("=" * 80)

# PASO 1: Ver precio actual
print(f"\n📊 PASO 1: Obtener precio actual del item local {local_item_id}")
headers = {"Authorization": f"Bearer {ML_TOKEN}"}

try:
    r = requests.get(f"{ML_API}/items/{local_item_id}", headers=headers, timeout=30)
    r.raise_for_status()
    current_data = r.json()

    current_price = current_data.get("price")
    print(f"✅ Precio actual: ${current_price} USD")
    print(f"   Stock: {current_data.get('available_quantity')}")
    print(f"   Status: {current_data.get('status')}")

except Exception as e:
    print(f"❌ Error: {e}")
    print("El item local puede haber sido eliminado. Verificando item global...")

    # Intentar obtener desde Argentina
    local_item_id = "MLA2593142442"
    try:
        r = requests.get(f"{ML_API}/items/{local_item_id}", headers=headers, timeout=30)
        r.raise_for_status()
        current_data = r.json()
        current_price = current_data.get("price")
        print(f"✅ Precio actual (desde MLA): ${current_price} USD")
    except:
        print("❌ Tampoco funciona Argentina. Todos los items pueden haber sido eliminados.")
        exit(1)

# PASO 2: Calcular nuevo precio (simulando cambio de Amazon)
print(f"\n🔄 PASO 2: Simular cambio de precio")

# Precio de Amazon actual
amazon_price = 35.99
# Simular aumento del 20%
new_amazon_price = round(amazon_price * 1.20, 2)

print(f"   Precio Amazon actual: ${amazon_price}")
print(f"   Precio Amazon simulado: ${new_amazon_price}")

# Calcular precio ML con la fórmula correcta
THREE_PL_FEE = 4.0
TAX_EXEMPT = os.getenv("TAX_EXEMPT", "false").lower() == "true"
FLORIDA_TAX_PERCENT = 7.0
MARKUP_PCT = 0.30

tax = 0.0 if TAX_EXEMPT else round(new_amazon_price * (FLORIDA_TAX_PERCENT / 100.0), 2)
cost = round(new_amazon_price + tax + THREE_PL_FEE, 2)
new_ml_price = round(cost * (1.0 + MARKUP_PCT), 2)

print(f"   Nuevo precio ML calculado: ${new_ml_price}")

# PASO 3: Actualizar precio en ML
print(f"\n📝 PASO 3: Actualizar precio en ML")

# Para CBT global, actualizar con net_proceeds
url = f"{ML_API}/global/items/{item_id}"
body = {"net_proceeds": new_ml_price}

print(f"   URL: {url}")
print(f"   Body: {body}")

try:
    r = requests.put(url, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    result = r.json()

    print(f"✅ Precio actualizado exitosamente")
    print(f"   Response: {result}")

except Exception as e:
    print(f"❌ Error actualizando precio: {e}")
    if hasattr(e, 'response') and e.response:
        print(f"   Response: {e.response.text[:500]}")

# PASO 4: Verificar que se actualizó
print(f"\n✅ PASO 4: Verificar actualización")

try:
    r = requests.get(f"{ML_API}/items/{local_item_id}", headers=headers, timeout=30)
    r.raise_for_status()
    updated_data = r.json()

    updated_price = updated_data.get("price")
    print(f"Precio después de actualización: ${updated_price} USD")

    if abs(updated_price - new_ml_price) < 0.01:
        print(f"✅ VERIFICACIÓN EXITOSA - Precio actualizado correctamente")
    else:
        print(f"⚠️ Precio no coincide:")
        print(f"   Esperado: ${new_ml_price}")
        print(f"   Obtenido: ${updated_price}")

except Exception as e:
    print(f"⚠️ No se pudo verificar: {e}")

print(f"\n{'='*80}")
print("🏁 TEST COMPLETADO")
print("=" * 80)
