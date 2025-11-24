#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
item_id = "CBT3079074206"

url = f"https://api.mercadolibre.com/global/items/{item_id}"
headers = {"Authorization": f"Bearer {ML_TOKEN}"}

try:
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    print("Países activos en este item:")
    if "site_listings" in data:
        for site in data["site_listings"]:
            print(f"  - {site.get('site_id')}: {site.get('listing_item_id')} (stock: {site.get('available_quantity', 'N/A')})")
    else:
        print("No hay site_listings en el response")

    # También ver net_proceeds
    if "net_proceeds" in data:
        print(f"\nPrecio global (net_proceeds): ${data['net_proceeds']} USD")

except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, 'response') and e.response:
        print(f"Response: {e.response.text[:500]}")
