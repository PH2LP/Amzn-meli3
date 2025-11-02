# ============================================================
# amazon_api.py
# ✅ Conexión directa a Amazon SP-API para obtener datos de un ASIN
# ============================================================

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SPAPI_BASE = "https://sellingpartnerapi-na.amazon.com"
MARKETPLACE_ID = "ATVPDKIKX0DER"  # US marketplace

# -------------------------------------------------------------
# 🔑 Función para obtener access_token temporal de Amazon
# -------------------------------------------------------------

def get_amazon_access_token():
    """
    Obtiene un access token de Amazon usando LWA (Login with Amazon).
    Usa las credenciales configuradas en .env
    """
    client_id = os.getenv("LWA_CLIENT_ID") or os.getenv("AMZ_CLIENT_ID")
    client_secret = os.getenv("LWA_CLIENT_SECRET") or os.getenv("AMZ_CLIENT_SECRET")
    refresh_token = os.getenv("REFRESH_TOKEN") or os.getenv("AMZ_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise RuntimeError(
            "❌ Faltan credenciales de Amazon SP-API en .env:\n"
            "   - LWA_CLIENT_ID (o AMZ_CLIENT_ID)\n"
            "   - LWA_CLIENT_SECRET (o AMZ_CLIENT_SECRET)\n"
            "   - REFRESH_TOKEN (o AMZ_REFRESH_TOKEN)"
        )

    url = "https://api.amazon.com/auth/o2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    try:
        r = requests.post(url, data=data, timeout=15)
        r.raise_for_status()
        token_data = r.json()
        return token_data["access_token"]
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"❌ Error obteniendo access token de Amazon: {e}")

# -------------------------------------------------------------
# 🧠 Obtener información de un ASIN
# -------------------------------------------------------------

def get_product_data_from_asin(asin: str, save_path: str = None):
    """
    Descarga la información completa de un ASIN desde Amazon SP-API.

    Args:
        asin: El ASIN del producto a descargar
        save_path: Ruta donde guardar el JSON (opcional)

    Returns:
        dict: JSON con los datos del producto
    """
    asin = asin.strip().upper()

    if not asin or len(asin) != 10:
        raise ValueError(f"❌ ASIN inválido: '{asin}' (debe tener 10 caracteres)")

    print(f"🔐 Obteniendo access token de Amazon...")
    token = get_amazon_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "x-amz-access-token": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Endpoint de Catalog Items API 2022-04-01
    url = f"{SPAPI_BASE}/catalog/2022-04-01/items/{asin}"
    params = {
        "marketplaceIds": MARKETPLACE_ID,
        "includedData": "attributes,images,productTypes,salesRanks,summaries,relationships"
    }

    print(f"📥 Descargando datos del ASIN {asin}...")

    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.HTTPError as e:
        if r.status_code == 404:
            raise RuntimeError(f"❌ ASIN {asin} no encontrado en Amazon")
        elif r.status_code == 403:
            raise RuntimeError(f"❌ Sin permisos para acceder al ASIN {asin}")
        else:
            raise RuntimeError(f"❌ Error HTTP {r.status_code}: {r.text}")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"❌ Error de conexión con Amazon SP-API: {e}")

    # Agregar ASIN al JSON si no viene
    if "asin" not in data:
        data["asin"] = asin

    # Guardar en archivo
    if save_path is None:
        save_path = Path("asins_json") / f"{asin}.json"
    else:
        save_path = Path(save_path)

    save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Datos guardados en {save_path}")
    print(f"   → Título: {data.get('summaries', [{}])[0].get('itemName', 'N/A')[:60]}...")
    print(f"   → Marca: {data.get('summaries', [{}])[0].get('brand', 'N/A')}")

    return data


# -------------------------------------------------------------
# 🧪 Test directo desde línea de comandos
# -------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asin = sys.argv[1].strip().upper()
    else:
        asin = input("🔍 Ingresá el ASIN que querés descargar: ").strip().upper()

    try:
        get_product_data_from_asin(asin)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)