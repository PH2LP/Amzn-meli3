# ============================================================
# amazon_api.py
# ✅ Conexión directa a Amazon SP-API para obtener datos de un ASIN
# ✅ Sistema de caché inteligente para tokens (auto-renovación)
# ============================================================

import os
import sys
import json
import requests
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SPAPI_BASE = "https://sellingpartnerapi-na.amazon.com"
MARKETPLACE_ID = "ATVPDKIKX0DER"  # US marketplace
TOKEN_CACHE_FILE = Path("cache/amazon_token.json")
TOKEN_LIFETIME = 3300  # 55 minutos (Amazon tokens duran 1 hora)

# -------------------------------------------------------------
# 🔑 Función para obtener access_token con caché inteligente
# -------------------------------------------------------------

def get_amazon_access_token():
    """
    Obtiene un access token de Amazon usando LWA (Login with Amazon).
    Sistema de caché inteligente:
    - Si existe un token válido en caché (< 55 min), lo usa
    - Si no existe o expiró, genera uno nuevo automáticamente
    - Completamente automático, sin intervención manual
    """

    # 1. Verificar si hay token cacheado válido
    if TOKEN_CACHE_FILE.exists():
        try:
            with open(TOKEN_CACHE_FILE, 'r') as f:
                cached = json.load(f)

            token_age = time.time() - cached.get('timestamp', 0)

            if token_age < TOKEN_LIFETIME:
                # Token todavía válido
                quiet_mode = os.getenv('PIPELINE_QUIET_MODE') == '1'
                if not quiet_mode:
                    mins_left = int((TOKEN_LIFETIME - token_age) / 60)
                    print(f"♻️ Usando token cacheado de Amazon (válido por {mins_left} min más)")
                return cached['access_token']
        except (json.JSONDecodeError, KeyError):
            pass  # Cache corrupto, generar nuevo token

    # 2. Generar nuevo token
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
        quiet_mode = os.getenv('PIPELINE_QUIET_MODE') == '1'
        if not quiet_mode:
            print(f"🔐 Generando nuevo access token de Amazon...")

        r = requests.post(url, data=data, timeout=15)
        r.raise_for_status()
        token_data = r.json()
        access_token = token_data["access_token"]

        # 3. Guardar en caché
        TOKEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {
            'access_token': access_token,
            'timestamp': time.time()
        }
        with open(TOKEN_CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)

        if not quiet_mode:
            print(f"✅ Token generado y cacheado (válido por 55 min)")

        return access_token

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
    quiet_mode = os.getenv('PIPELINE_QUIET_MODE') == '1'

    if not asin or len(asin) != 10:
        raise ValueError(f"❌ ASIN inválido: '{asin}' (debe tener 10 caracteres)")

    if not quiet_mode:
        print(f"🔐 Obteniendo access token de Amazon...")

    token = get_amazon_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "x-amz-access-token": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    url = f"{SPAPI_BASE}/catalog/2022-04-01/items/{asin}"
    params = {
        "marketplaceIds": MARKETPLACE_ID,
        "includedData": "attributes,images,productTypes,salesRanks,summaries,relationships"
    }

    if not quiet_mode:
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

    if "asin" not in data:
        data["asin"] = asin

    if save_path is None:
        save_path = Path("asins_json") / f"{asin}.json"
    else:
        save_path = Path(save_path)

    save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    if not quiet_mode:
        print(f"✅ Datos guardados en {save_path}")
        print(f"   → Título: {data.get('summaries', [{}])[0].get('itemName', 'N/A')[:60]}...")
        print(f"   → Marca: {data.get('summaries', [{}])[0].get('brand', 'N/A')}")

    return data


def get_product_bsr_only(asin: str):
    """
    Obtiene únicamente el BSR (Best Seller Rank) de un ASIN.

    Args:
        asin: El ASIN del producto

    Returns:
        int: El BSR del producto, o None si no tiene
    """
    try:
        # Usar PIPELINE_QUIET_MODE para no mostrar output
        os.environ['PIPELINE_QUIET_MODE'] = '1'

        data = get_product_data_from_asin(asin, save_path=None)

        # Restaurar modo normal
        os.environ.pop('PIPELINE_QUIET_MODE', None)

        # Extraer BSR de salesRanks
        sales_ranks = data.get('salesRanks', [])

        if not sales_ranks:
            return None

        # Buscar el ranking principal (classificationRanks[0])
        for rank_data in sales_ranks:
            classification_ranks = rank_data.get('classificationRanks', [])
            if classification_ranks:
                # Tomar el primer ranking (usualmente es el más importante)
                bsr = classification_ranks[0].get('rank')
                if bsr:
                    return int(bsr)

        return None

    except Exception as e:
        # Restaurar modo normal en caso de error
        os.environ.pop('PIPELINE_QUIET_MODE', None)
        return None


def get_products_batch(asins: list, include_data: str = "summaries") -> dict:
    """
    Obtiene datos de múltiples ASINs en una sola llamada (hasta 20 ASINs).
    Usa el endpoint searchCatalogItems con identifiers.

    Args:
        asins: Lista de ASINs a consultar (máximo 20)
        include_data: Datos a incluir (default: "summaries" para marca/título)

    Returns:
        dict: {asin: product_data} - Mapeo de ASIN a datos del producto
    """
    if not asins:
        return {}

    if len(asins) > 20:
        raise ValueError(f"Máximo 20 ASINs por batch (recibido: {len(asins)})")

    # Limpiar ASINs
    asins = [asin.strip().upper() for asin in asins]

    token = get_amazon_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "x-amz-access-token": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    url = f"{SPAPI_BASE}/catalog/2022-04-01/items"
    params = {
        "marketplaceIds": MARKETPLACE_ID,
        "identifiers": ",".join(asins),
        "identifiersType": "ASIN",
        "includedData": include_data
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"❌ Error obteniendo batch de ASINs: {e}")

    # Parsear respuesta - formato: {"items": [{asin: ..., summaries: ...}, ...]}
    items = data.get("items", [])

    result = {}
    for item in items:
        asin = item.get("asin")
        if asin:
            result[asin] = item

    return result


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