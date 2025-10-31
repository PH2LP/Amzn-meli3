# normalize_ml_attrs.py
# 🧠 Versión 4.1 EXTENDED — Cobertura máxima
# Completa todos los atributos válidos del schema de Mercado Libre con IA,
# filtrando los internos y manteniendo campos críticos vacíos (GTIN y certificaciones).

import os
import json
import re
import requests
import time
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# ─────────────────────────────────────────────
# ⚙️ Configuración base
# ─────────────────────────────────────────────
API_URL = "https://api.mercadolibre.com"
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

HEADERS = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"}
client = OpenAI(api_key=OPENAI_API_KEY)

LOG_DIR = Path("logs/ai_filled_attrs")
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# 1️⃣ Obtener schema de categoría
# ─────────────────────────────────────────────
def get_schema(category_id: str):
    """Descarga el schema completo y filtra los atributos no editables ni de paquete."""
    r = requests.get(f"{API_URL}/categories/{category_id}/attributes",
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    schema = r.json()
    filtered = []
    for s in schema:
        tags = s.get("tags", {})
        if s["id"].startswith(("PACKAGE_", "SELLER_PACKAGE_")):
            continue
        if tags.get("read_only") is True:
            continue
        if s.get("hierarchy") == "PRODUCT_IDENTIFIER" and s["id"] != "GTIN":
            continue
        filtered.append(s)
    return filtered


# ─────────────────────────────────────────────
# 2️⃣ IA: completar atributos
# ─────────────────────────────────────────────
def fill_attributes_with_ai(category_id: str, amazon_json: dict, asin: str = "UNKNOWN"):
    schema = get_schema(category_id)

    prompt = f"""
You are an **AI assistant specialized in Mercado Libre e-commerce attribute completion**.
Your task is to fill the Mercado Libre attribute schema based on the Amazon product JSON.

──────────────────────────────
🧩 GENERAL RULES
──────────────────────────────
1. Return ONLY valid JSON (array of objects). No extra text.
2. Each object must have: "id" and "value_name". Add "value_id" only when the schema defines it.
3. Translate values into **neutral Latin American Spanish**.
4. Use **metric system** (cm, kg, etc.).
5. Skip all "PACKAGE_*" and "SELLER_PACKAGE_*" fields.
6. Skip any hidden or read_only attributes.
7. Leave the following fields EMPTY (value_name = ""):
   GTIN,
   INMETRO_CERTIFICATION_REGISTRATION_NUMBER,
   APPROVAL_CERTIFICATION_NUMBER,
   PRODUCT_AUTHORIZATION_RPIN_NUMBER,
   SIC_ESTABLISHMENT_REGISTRY_NUMBER,
   REGISTRATION_LICENSE_ESTABLISHMENT_NUMBER.
8. For boolean fields → use "Sí" or "No".
9. If not sure of a value, leave it empty rather than inventing.
10. Keep JSON compact, without line breaks inside strings.

──────────────────────────────
💡 ATTRIBUTE-SPECIFIC LOGIC
──────────────────────────────
- ITEM_CONDITION → "Nuevo"
- IS_FLAMMABLE → "No"
- IS_SUITABLE_FOR_SHIPMENT → "Sí"
- IS_KIT → "No"
- HAS_COMPATIBILITIES → "No"
- IS_COLLECTIBLE → "Sí" if it's LEGO, coleccionable o decorativo
- FILTRABLE_RECOMMENDED_AGE_GROUP → derivar de edad o dificultad
- MIN_RECOMMENDED_AGE → derivar de edad mínima del producto
- MAX_RECOMMENDED_AGE → dejar vacío si no aplica
- COLOR → usar color principal o predominante
- TOY_MATERIALS → inferir del material del producto
- COLLECTION / LINE → derivar del título o tema
- TOY_COMPONENTS → "Piezas", "Manual", "Base", etc., si aplica
- HEIGHT, WIDTH, LENGTH → usar medidas aproximadas del producto (no paquete)
- EMPTY_GTIN_REASON → "Producto artesanal o sin código de fábrica"

──────────────────────────────
📦 AMAZON PRODUCT JSON
──────────────────────────────
{json.dumps(amazon_json)[:12000]}

──────────────────────────────
📘 MERCADO LIBRE CATEGORY SCHEMA
──────────────────────────────
{json.dumps(schema)[:12000]}
"""

    # ────────────── Llamada IA con reintentos ──────────────
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                temperature=0.2,
                messages=[
                    {"role": "system", "content": "Return only valid JSON array of Mercado Libre attributes."},
                    {"role": "user", "content": prompt},
                ],
            )
            content = response.choices[0].message.content.strip()
            match = re.search(r"\[.*\]", content, re.S)
            if not match:
                raise ValueError("Respuesta sin JSON válido")
            result = json.loads(match.group(0))
            break
        except Exception as e:
            print(f"⚠️ Error intento {attempt + 1}: {e}")
            time.sleep(3)
            if attempt == 2:
                raise RuntimeError("❌ No se pudo obtener JSON válido tras 3 intentos")

    # ────────────── Campos vacíos forzados ──────────────
    empty_fields = [
        "GTIN",
        "INMETRO_CERTIFICATION_REGISTRATION_NUMBER",
        "APPROVAL_CERTIFICATION_NUMBER",
        "PRODUCT_AUTHORIZATION_RPIN_NUMBER",
        "SIC_ESTABLISHMENT_REGISTRY_NUMBER",
        "REGISTRATION_LICENSE_ESTABLISHMENT_NUMBER"
    ]
    for field in empty_fields:
        result = [r for r in result if r.get("id") != field]
        result.append({"id": field, "value_name": ""})

    # ────────────── Guardar log ──────────────
    output_path = LOG_DIR / f"{category_id}_{asin}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"💾 Log guardado: {output_path}")

    return result


# ─────────────────────────────────────────────
# 3️⃣ Test manual (ejecución directa)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    amazon_json = {
        "asin": "B0BGQLZ921",
        "title": "LEGO Icons Dried Flower Centerpiece 10314 Botanical Collection",
        "attributes": {
            "brand": [{"value": "LEGO"}],
            "model": [{"value": "10314"}],
            "material": [{"value": "Plastic"}],
            "theme": [{"value": "Botanical"}],
            "color": [{"value": "Beige"}],
        },
        "product_information": {
            "pieces": "812",
            "recommended_age": "18+",
            "dimensions": {"height": "13 cm", "width": "38 cm", "length": "26 cm"}
        }
    }

    category_id = "MLC1157"
    asin = amazon_json["asin"]
    print("\n🚀 Iniciando test del módulo normalize_ml_attrs (v4.1 EXTENDED)...\n")
    result = fill_attributes_with_ai(category_id, amazon_json, asin)
    print(f"✅ Atributos totales completados: {len(result)}\n")
    print("──────────────────────────────")
    for attr in result[:50]:
        print(f"• {attr['id']}: {attr.get('value_name', '')}")
    print("──────────────────────────────\n")
    print("🔎 Resultado completo:")
    print(json.dumps(result, indent=2, ensure_ascii=False))