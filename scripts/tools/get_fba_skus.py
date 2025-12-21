#!/usr/bin/env python3
"""
Obtener SKUs de inventario FBA para probar getFulfillmentPreview
"""
import os
import sys
import json
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.integrations.amazon_api import get_amazon_access_token

SPAPI_BASE = "https://sellingpartnerapi-na.amazon.com"
MARKETPLACE_ID = "ATVPDKIKX0DER"

print("="*80)
print("Obteniendo SKUs de inventario FBA")
print("="*80)
print()

token = get_amazon_access_token()

headers = {
    "Authorization": f"Bearer {token}",
    "x-amz-access-token": token,
}

# Endpoint: FBA Inventory API
url = f"{SPAPI_BASE}/fba/inventory/v1/summaries"

params = {
    "details": "true",
    "granularityType": "Marketplace",
    "granularityId": MARKETPLACE_ID,
    "marketplaceIds": MARKETPLACE_ID
}

try:
    response = requests.get(url, headers=headers, params=params, timeout=30)

    print(f"Status: {response.status_code}")
    print()

    if response.status_code == 200:
        data = response.json()

        summaries = data.get('payload', {}).get('inventorySummaries', [])

        print(f"✅ Encontrados {len(summaries)} items en inventario FBA")
        print()

        if summaries:
            print("Primeros 10 SKUs:")
            print("="*80)

            skus_asins = []

            for i, item in enumerate(summaries[:10], 1):
                sku = item.get('sellerSku', 'N/A')
                asin = item.get('asin', 'N/A')
                fn_sku = item.get('fnSku', 'N/A')
                condition = item.get('condition', 'N/A')

                total_quantity = item.get('totalQuantity', 0)

                print(f"{i}. SKU: {sku}")
                print(f"   ASIN: {asin}")
                print(f"   FN-SKU: {fn_sku}")
                print(f"   Condition: {condition}")
                print(f"   Total Quantity: {total_quantity}")
                print()

                skus_asins.append({
                    "sku": sku,
                    "asin": asin,
                    "fn_sku": fn_sku,
                    "quantity": total_quantity
                })

            # Guardar para uso posterior
            with open('/tmp/fba_skus.json', 'w') as f:
                json.dump(skus_asins, f, indent=2)

            print("="*80)
            print(f"✅ Guardados {len(skus_asins)} SKUs en /tmp/fba_skus.json")
            print()

            if skus_asins:
                print("PARA PROBAR getFulfillmentPreview, usa:")
                print(f"  SKU: {skus_asins[0]['sku']}")
                print(f"  ASIN: {skus_asins[0]['asin']}")
        else:
            print("⚠️  No se encontraron items en inventario FBA")
            print("   Esto puede significar:")
            print("   - No tienes productos en FBA")
            print("   - Necesitas permisos adicionales")

    elif response.status_code == 403:
        print("❌ ERROR 403 - Sin permisos para FBA Inventory API")
        print("   Necesitas agregar el rol 'Inventory and Order Tracking' en Seller Central")
    else:
        print(f"❌ ERROR {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Exception: {e}")
    import traceback
    traceback.print_exc()
