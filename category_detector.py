import requests
import os
import json

def detect_category_from_api(title: str, access_token: str) -> dict:
    """
    Usa el predictor oficial de categorías para Global Selling (CBT)
    utilizando el endpoint /marketplace/domain_discovery/search.
    Devuelve la categoría más probable con id, name, domain y atributos sugeridos.
    """
    query = title.strip()
    url = f"https://api.mercadolibre.com/marketplace/domain_discovery/search?q={query}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    print(f"🔍 Consultando categoría oficial CBT (domain_discovery) para: '{title}'...")

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        if not isinstance(data, list) or len(data) == 0:
            raise ValueError("Respuesta vacía del predictor")

        # Tomamos el primer resultado (el más confiable)
        best = data[0]
        cat_id = best.get("category_id")
        cat_name = best.get("category_name")
        domain_id = best.get("domain_id")
        domain_name = best.get("domain_name")
        attributes = best.get("attributes", [])

        print(f"✅ Categoría detectada: {cat_id} ({cat_name}) | Dominio: {domain_name}")

        return {
            "category_id": cat_id,
            "category_name": cat_name,
            "domain_id": domain_id,
            "domain_name": domain_name,
            "attributes": attributes
        }

    except Exception as e:
        print(f"❌ Error detectando categoría desde API oficial: {e}")
        return {"category_id": "CBT1953", "category_name": "Other categories", "domain": "fallback"}


# ======================================================
# 🧪 TEST MANUAL
# ======================================================

if __name__ == "__main__":
    token = os.getenv("ML_ACCESS_TOKEN")
    if not token:
        print("❌ Falta ML_ACCESS_TOKEN en el entorno (.env).")
        exit()

    while True:
        title = input("\n👉 Ingresá un título de producto (o Enter para salir): ").strip()
        if not title:
            break
        result = detect_category_from_api(title, token)
        print(json.dumps(result, indent=2))