import os
import json
import requests

# ============================================================
# 🧩 CONFIGURACIÓN GENERAL
# ============================================================

def _have_ai():
    """Verifica si hay API Key de OpenAI configurada."""
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _chat(system, user, max_tokens=600, temperature=0.3):
    """Envía un prompt a la API de OpenAI y devuelve el texto generado."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY').strip()}"}
    data = {
        "model": "gpt-4o-mini",
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
    }

    r = requests.post(url, headers=headers, json=data, timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


# ============================================================
# 🚀 FUNCIÓN PRINCIPAL
# ============================================================

def interpret_amazon_json_with_ai(amz_json):
    """
    Toma el JSON crudo de Amazon y usa IA para detectar los campos clave requeridos por Mercado Libre.
    Devuelve un dict con los campos limpios: brand, model, gtin, color, material, dimensiones, precio, etc.
    """
    if not _have_ai():
        raise RuntimeError("❌ Falta OPENAI_API_KEY en el entorno (.env)")

    prompt = f"""
You are an expert at mapping Amazon Catalog API JSONs into Mercado Libre CBT fields.
From the input JSON below, extract and normalize the following fields:

- brand (string)
- model (string)
- gtin (string: EAN, UPC, or GTIN-13)
- color (string)
- material (string)
- title_seed (string)
- bullet_points (list of strings)
- description_seed (string)
- price (float in USD)
- package_dimensions: length_cm, width_cm, height_cm, weight_kg (numeric)

Rules:
- If dimensions are in inches, convert to centimeters (1 inch = 2.54 cm).
- If weight is in pounds, convert to kilograms (1 lb = 0.45359237 kg).
- Keep it clean JSON, no commentary, no text outside the object.
- If something is missing, put "N/A" or null.

Input JSON (truncated to 8000 chars for safety):
{json.dumps(amz_json)[:8000]}
"""

    system = (
        "You are a structured data interpreter for ecommerce platforms. "
        "You extract and normalize product attributes from JSONs into a clean JSON output."
    )

    try:
        content = _chat(system, prompt, max_tokens=800)
        cleaned = content.strip()
        # Algunos modelos devuelven ```json ... ```
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`json\n ")
        parsed = json.loads(cleaned)
        return parsed
    except Exception as e:
        raise RuntimeError(f"⚠️ Error interpretando JSON con IA: {e}")


# ============================================================
# 🧪 TEST LOCAL
# ============================================================

if __name__ == "__main__":
    # Ejemplo de uso rápido (lee un archivo de prueba)
    sample_path = "asins_json/B0DRW69H11.json"
    if not os.path.exists(sample_path):
        print(f"⚠️ No se encontró el archivo de ejemplo {sample_path}")
    else:
        with open(sample_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = interpret_amazon_json_with_ai(data)
        print(json.dumps(result, indent=2, ensure_ascii=False))