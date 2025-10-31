# ============================================================
# amazon_api.py
# ✅ Conexión directa a Amazon SP-API para obtener datos de un ASIN
# ============================================================

import os
import requests
import boto3
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

SPAPI_BASE = "https://sellingpartnerapi-na.amazon.com"
REGION = os.getenv("AMZ_REGION", "us-east-1")

# -------------------------------------------------------------
# 🔑 Función para obtener access_token temporal de Amazon
# -------------------------------------------------------------

def get_amazon_access_token():
    client_id = os.getenv("AMZ_CLIENT_ID")
    client_secret = os.getenv("AMZ_CLIENT_SECRET")
    refresh_token = os.getenv("AMZ_REFRESH_TOKEN")

    url = "https://api.amazon.com/auth/o2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

# -------------------------------------------------------------
# 🧠 Obtener información de un ASIN
# -------------------------------------------------------------

def get_product_data_from_asin(asin: str):
    """Descarga la información completa de un ASIN desde Amazon SP-API"""
    token = get_amazon_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "x-amz-access-token": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Usamos el endpoint de Product Listings
    url = f"{SPAPI_BASE}/catalog/2022-04-01/items/{asin}?marketplaceIds=ATVPDKIKX0DER"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    data = r.json()

    # Guardar en carpeta local
    os.makedirs("asins_json", exist_ok=True)
    path = f"asins_json/{asin}.json"
    with open(path, "w") as f:
        import json
        json.dump(data, f, indent=2)

    print(f"✅ Datos guardados en {path}")
    return data


if __name__ == "__main__":
    asin = input("🔍 Ingresá el ASIN que querés descargar: ").strip().upper()
    get_product_data_from_asin(asin)