#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
mainglobal.py — v14.2 (IA híbrida + dimensiones de paquete + limpieza total)
──────────────────────────────────────────────────────────────────────────────
✔ Basado en v14.1 (mantiene toda la funcionalidad)
✔ Dimensiones del paquete (item_package_dimensions + IA GPT-4o)
✔ Limpieza total: sin duplicaciones ni indentaciones erróneas
✔ IA híbrida: GPT-4o (copy/model/categoría/dimensiones), GPT-4o-mini (GTIN)
✔ SKU aplicado global + marketplaces
✔ MARKUP_PCT desde .env → sólo global_net_proceeds
✔ Títulos/descripciones con Mayúscula inicial
──────────────────────────────────────────────────────────────────────────────
"""
from dotenv import load_dotenv
import os, sys, json, glob, time, requests, re
from typing import Tuple, Dict, Any, List

# ============ Inicialización ============
if sys.prefix == sys.base_prefix:
    vpy = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
    if os.path.exists(vpy):
        print(f"⚙️ Activando entorno virtual automáticamente desde: {vpy}")
        os.execv(vpy, [vpy] + sys.argv)

# Recargar .env con override para asegurar token actualizado
load_dotenv(override=True)
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
INPUT_DIR = "outputs/json"
API = "https://api.mercadolibre.com"

if not ML_ACCESS_TOKEN:
    raise RuntimeError("Falta ML_ACCESS_TOKEN en .env")

HEADERS = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"}

# ============ Configuración ============
def _get_markup():
    try:
        return float(os.getenv("MARKUP_PCT", "0.40"))
    except:
        return 0.40

# ============ HTTP ============
def http_get(url, params=None, extra_headers=None, timeout=30):
    h = dict(HEADERS)
    if extra_headers:
        h.update(extra_headers)
    r = requests.get(url, headers=h, params=params, timeout=timeout)
    if not r.ok:
        raise RuntimeError(f"GET {url} → {r.status_code} {r.text}")
    return r.json()

def autofill_required_attrs(cid: str, attributes: list) -> list:
    """Consulta el schema oficial de la categoría y agrega los atributos obligatorios que falten."""
    try:
        schema = http_get(f"https://api.mercadolibre.com/categories/{cid}/attributes")
    except Exception as e:
        print(f"⚠️ No se pudo obtener schema de {cid}: {e}")
        return attributes

    existing_ids = {a["id"] for a in attributes if "id" in a}
    added = 0

    for field in schema:
        tags = field.get("tags", {})
        if not tags.get("required"):
            continue
        aid = field["id"]
        if aid in existing_ids:
            continue

        vals = field.get("values", [])
        val_id = val_name = None
        if vals:
            val_id = str(vals[0].get("id")) if vals[0].get("id") else None
            val_name = vals[0].get("name")

        # Si el valor es nulo, aplicar defaults seguros
        if aid == "IS_KIT" and not val_id:
            val_id, val_name = "242084", "No"
        if aid == "IS_COLLECTIBLE" and not val_id:
            val_id, val_name = "242084", "No"

        attributes.append({
            "id": aid,
            "value_id": val_id,
            "value_name": val_name or "Default"
        })
        added += 1

    if added:
        print(f"🧩 Se agregaron {added} atributos requeridos automáticamente para {cid}")
    return attributes

def http_post(url, body, extra_headers=None, timeout=60):
    h = {"Authorization": HEADERS["Authorization"], "Content-Type": "application/json"}
    if extra_headers:
        h.update(extra_headers)
    r = requests.post(url, headers=h, json=body, timeout=timeout)
    # Retry con delay si rate limited
    if r.status_code == 429:
        print("⏳ Rate limited, esperando 10s y reintentando...")
        time.sleep(10)
        r = requests.post(url, headers=h, json=body, timeout=timeout)
    if not r.ok:
        raise RuntimeError(f"POST {url} → {r.status_code} {r.text}")
    return r.json()

def http_put(url, body, extra_headers=None, timeout=60):
    h = {"Authorization": HEADERS["Authorization"], "Content-Type": "application/json"}
    if extra_headers:
        h.update(extra_headers)
    r = requests.put(url, headers=h, json=body, timeout=timeout)
    if r.status_code == 429:
        time.sleep(5)
        r = requests.put(url, headers=h, json=body, timeout=timeout)
    if not r.ok:
        raise RuntimeError(f"PUT {url} → {r.status_code} {r.text}")
    return r.json() if r.text else {}

# ============ Utilidades numéricas ============
def _read_number(x, default=None):
    try:
        if isinstance(x, (int, float)):
            return float(x)
        return float(str(x).replace("$", "").strip())
    except:
        return default

def _try_paths(d, paths: List[str]):
    """Busca en múltiples rutas del JSON de Amazon posibles precios."""
    for p in paths:
        cur = d
        ok = True
        for step in p.split("."):
            if step.endswith("]"):
                name, idx = re.match(r"(.+)\[(\d+)\]", step).groups()
                cur = cur.get(name, [])
                if not isinstance(cur, list) or len(cur) <= int(idx):
                    ok = False
                    break
                cur = cur[int(idx)]
            else:
                if not isinstance(cur, dict) or step not in cur:
                    ok = False
                    break
                cur = cur[step]
        if ok:
            val = _read_number(cur)
            if val is not None:
                return val
    return None

# ============ Precio base y markup ============
def get_amazon_base_price(amazon_json) -> float:
    """Detecta el precio base desde varios caminos posibles del JSON de Amazon."""
    candidates = [
        "attributes.list_price[0].value",
        "offers.listings[0].price.amount",
        "price.value",
        "price",
    ]
    price = _try_paths(amazon_json, candidates)
    if price is None:
        raw = amazon_json.get("attributes", {}).get("list_price", [{}])[0].get("value", 10.0)
        price = _read_number(raw, 10.0)
    return round(float(price), 2)

def compute_net_proceeds_from_amazon(amazon_json) -> Tuple[float, float, float]:
    """Devuelve (precio_base, markup_pct, net_proceeds)."""
    base = get_amazon_base_price(amazon_json)
    mk = _get_markup()
    net = round(base * (1.0 + mk), 2)
    return base, mk, net

# ============ Dimensiones del paquete ============
def extract_dimensions(amazon_json):
    """Lee directamente las medidas del paquete desde item_package_dimensions."""
    try:
        pkg = amazon_json.get("attributes", {})
        dims = pkg.get("item_package_dimensions", [{}])[0]
        weight = pkg.get("item_package_weight", [{}])[0]
        L = dims.get("length", {}).get("value")
        W = dims.get("width", {}).get("value")
        H = dims.get("height", {}).get("value")
        KG = weight.get("value")
        if all([L, W, H, KG]):
            print(f"📦 Dimensiones del paquete directas: {round(L,2)}×{round(W,2)}×{round(H,2)} cm – {round(KG,3)} kg")
            return round(L, 2), round(W, 2), round(H, 2), round(KG, 3)
    except Exception as e:
        print(f"⚠️ Error leyendo item_package_dimensions: {e}")

    # Fallback: búsqueda recursiva
    values = {}
    def walk(o, p=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{p}.{k}" if p else k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{p}[{i}]")
        else:
            k = p.lower()
            if any(x in k for x in ["length", "width", "height", "depth", "weight"]):
                try:
                    num = float(re.findall(r"[-+]?\d*\.\d+|\d+", str(o))[0])
                    values[k] = num
                except:
                    pass
    walk(amazon_json)
    l = next((v for k, v in values.items() if "length" in k), None)
    w = next((v for k, v in values.items() if "width" in k), None)
    h = next((v for k, v in values.items() if "height" in k), None)
    kg = next((v for k, v in values.items() if "weight" in k), None)
    if all([l, w, h, kg]):
        print(f"📏 Dimensiones detectadas por búsqueda: {l}×{w}×{h} cm – {kg} kg")
        return round(l, 2), round(w, 2), round(h, 2), round(kg, 3)
    return None, None, None, None

def get_package_dimensions_ai(amazon_json):
    """Usa GPT-4o para detectar medidas del paquete si no existen."""
    if not OPENAI_API_KEY:
        return None, None, None, None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = f"""
Eres un analista experto en Amazon SP-API. 
Extrae las dimensiones del **paquete de venta**, NO del producto suelto.

Busca en prioridad:
1️⃣ item_package_dimensions (length/width/height)
2️⃣ item_package_weight (value)

Devuelve solo JSON con decimales y unidades métricas:

{{
  "length_cm": 0,
  "width_cm": 0,
  "height_cm": 0,
  "weight_kg": 0
}}

JSON de producto (recortado):
{json.dumps(amazon_json)[:12000]}
"""
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        txt = resp.choices[0].message.content.strip()
        data = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
        L = round(float(data.get("length_cm", 0)), 2)
        W = round(float(data.get("width_cm", 0)), 2)
        H = round(float(data.get("height_cm", 0)), 2)
        KG = round(float(data.get("weight_kg", 0)), 3)
        if all([L, W, H, KG]) and L > 0 and W > 0 and H > 0 and KG > 0:
            print(f"🤖 Dimensiones IA: {L}×{W}×{H} cm – {KG} kg")
            return L, W, H, KG
    except Exception as e:
        print(f"⚠️ Error IA dimensiones: {e}")
    return None, None, None, None

# ============ Formato de texto ============
def _mayuscula_inicial(s: str) -> str:
    if not s:
        return s
    s = s.strip()
    s = re.sub(r"\blego\b", "LEGO", s, flags=re.I)
    return s[0].upper() + s[1:]

    # ============ IA: LEGO helpers ============
def _ensure_lego_number_in_title(title: str, model: str, amazon_json: dict) -> str:
    """Si es LEGO y hay número 4–6 dígitos, inclúyelo en el título si falta."""
    brand = str(amazon_json.get("attributes", {}).get("brand", [{}])[0].get("value", "")).lower()
    if "lego" not in brand:
        return _mayuscula_inicial(title[:60])
    m = re.search(r"\b(\d{4,6})\b", f"{model or ''} {title or ''}")
    if not m:
        t = amazon_json.get("title", "") or ""
        m = re.search(r"\b(\d{4,6})\b", t)
    if m and m.group(1) not in title:
        title = f"{m.group(1)} {title}".strip()
    return _mayuscula_inicial(title[:60])

# ============ IA: Copys ES (+ categoría + modelo) ============
def get_ai_copy_and_category(amazon_json) -> Tuple[str, str, str, str]:
    """
    Devuelve: (title_es, desc_es, model_name, category_keyword)
    Usa GPT-4o con prompt robusto para español natural + keyword canónica de categoría.
    """
    fallback_title = amazon_json.get("title") or amazon_json.get("asin") or "Producto"
    fallback_desc = (f"{fallback_title}. Producto nuevo e importado. "
                     "Ideal para regalar o ampliar tu colección.\n\n"
                     "🔎 Información importante para compras internacionales\n\n"
                     "• Producto nuevo y original\n"
                     "• Envío desde Estados Unidos con seguimiento\n"
                     "• Impuestos y aduana incluidos en el precio\n"
                     "• Compra protegida por Mercado Libre\n"
                     "• Garantía de 30 días desde la entrega\n"
                     "• Factura emitida por Mercado Libre (no factura local del país)\n"
                     "• Productos eléctricos: 110-120V + clavija americana\n"
                     "• Puede requerir adaptador o transformador, según el país\n"
                     "• Medidas y peso pueden aparecer en sistema imperial\n"
                     "• Si incluye baterías, pueden enviarse retiradas por normas aéreas\n"
                     "• Atención al cliente en español e inglés\n\n"
                     "Somos ONEWORLD 🌎")
    fallback_model = amazon_json.get("attributes", {}).get("model", [{}])[0].get("value", "") or "Genérico"
    fallback_kw = "juego de construcción lego" if "lego" in (amazon_json.get("title","").lower()) else "producto genérico"

    if not OPENAI_API_KEY:
        return _mayuscula_inicial(fallback_title[:60]), fallback_desc, fallback_model[:60], fallback_kw

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = f"""
Eres un copywriter experto en Amazon/Mercado Libre. Devuelve SOLO JSON válido:

{{
  "title": "string (<=60, español, Mayúscula inicial, natural; si es LEGO incluye número de set si existe)",
  "description": "string (3–5 párrafos, sin HTML ni emojis, \\n entre párrafos, cierre persuasivo) + bloque fijo al final",
  "model": "modelo real (NO ASIN). Si LEGO: número 4–6 dígitos + nombre corto si aplica (<=60).",
  "category_keyword": "2–5 palabras en español (tipo de producto canónico para domain_discovery)"
}}

Reglas de estilo:
- Español neutro (LatAm) y humano, evita traducción literal.
- Sin HTML, sin emojis. No inventes especificaciones.
- Título natural (no lista de keywords), con Mayúscula inicial. Asegura acrónimos (LEGO) en mayúsculas.
- Si el título original sirve, condénsalo a 60 caracteres en buen español.
- Al final de la descripción agrega EXACTO:
"🔎 Información importante para compras internacionales

• Producto nuevo y original
• Envío desde Estados Unidos con seguimiento
• Impuestos y aduana incluidos en el precio
• Compra protegida por Mercado Libre
• Garantía de 30 días desde la entrega
• Factura emitida por Mercado Libre (no factura local del país)
• Productos eléctricos: 110-120V + clavija americana
• Puede requerir adaptador o transformador, según el país
• Medidas y peso pueden aparecer en sistema imperial
• Si incluye baterías, pueden enviarse retiradas por normas aéreas
• Atención al cliente en español e inglés

Somos ONEWORLD 🌎"

JSON DE AMAZON (recortado):
{json.dumps(amazon_json)[:15000]}
"""
        resp = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.7,
            messages=[
                {"role": "system", "content": "Devuelve SOLO JSON válido. Sin texto extra ni backticks."},
                {"role": "user", "content": prompt},
            ],
        )
        txt = resp.choices[0].message.content.strip()
        data = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
        title_es = data.get("title") or fallback_title
        desc_es = data.get("description") or fallback_desc
        model_name = data.get("model") or fallback_model
        cat_kw = data.get("category_keyword") or fallback_kw

        title_es = _mayuscula_inicial(title_es[:60])
        model_name = model_name.strip()[:60]
        cat_kw = re.sub(r"\s+", " ", cat_kw.strip().lower())
        title_es = _ensure_lego_number_in_title(title_es, model_name, amazon_json)

        print(f"🤖 Título ES IA: {title_es}")
        print("📝 Descripción ES generada ✔️")
        print(f"🏷️ Modelo IA: {model_name}")
        print(f"🔎 Keyword categoría IA: {cat_kw}")
        return title_es, desc_es, model_name, cat_kw
    except Exception as e:
        print(f"⚠️ Error IA (ES copy/categoría): {e}")
        t = _ensure_lego_number_in_title(fallback_title[:60], fallback_model, amazon_json)
        return t, fallback_desc, fallback_model[:60], fallback_kw

# ============ IA: GTIN ============
def detect_gtin_with_ai(amazon_json):
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = f"Extract GTIN/UPC/EAN from this JSON, respond only JSON like {{\"gtin\":\"digits\"}}. JSON: {json.dumps(amazon_json)[:8000]}"
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        txt = resp.choices[0].message.content.strip()
        m = re.search(r"\{.*\}", txt, re.S)
        if m:
            data = json.loads(m.group(0))
            gtin = data.get("gtin") or data.get("upc") or data.get("ean")
            if gtin and re.match(r"^\d{8,14}$", str(gtin)):
                print(f"🤖 GTIN detectado: {gtin}")
                return str(gtin)
    except Exception:
        pass
    matches = re.findall(r"\b\d{12,14}\b", json.dumps(amazon_json))
    if matches:
        print(f"🔍 GTIN detectado (heurística): {matches[0]}")
        return matches[0]
    return None

# ============ IA: Modelo real (fallback heurístico) ============
def detect_model_name(amazon_json):
    brand = str(amazon_json.get("attributes", {}).get("brand", [{}])[0].get("value", "")).lower()
    title = amazon_json.get("title", "") or ""
    candidates = []
    attrs = amazon_json.get("attributes", {})
    for key in ["model_number", "model", "item_model_number", "manufacturer_part_number"]:
        v = attrs.get(key, [{}])
        if isinstance(v, list) and v and isinstance(v[0], dict):
            val = v[0].get("value")
            if val:
                candidates.append(str(val))

    lego_num = None
    m = re.search(r"\b(\d{4,6})\b", title)
    if m:
        lego_num = m.group(1)

    # Último intento con mini si hay API
    if OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            prompt = f"""
From this Amazon JSON, extract the real model (short). If LEGO, prefer the 4–6 digit set number plus a short label.
Return ONLY the model string, <= 60 chars.
JSON: {json.dumps(amazon_json)[:9000]}
"""
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.choices[0].message.content.strip().replace('"', '')
            if text and len(text) <= 60 and "\n" not in text:
                candidates.insert(0, text)
        except Exception as e:
            print(f"⚠️ Error IA detectando modelo (mini): {e}")

    for c in candidates:
        c = c.strip()
        if not c:
            continue
        if "lego" in brand and lego_num:
            if lego_num in c or re.fullmatch(r"\d{4,6}", c):
                return c if len(c) <= 60 else c[:60]
            short = " ".join(title.split()[:4]).strip()
            return f"{lego_num} {short}"[:60]
        if len(c) <= 60:
            return c
    if lego_num:
        short = " ".join(title.split()[:4]).strip()
        return f"{lego_num} {short}"[:60]
    return title[:60] if title else "Genérico"

# ============ Categorías ============
SITES_FALLBACK = ["CBT", "MLM", "MLB", "MLC", "MCO"]

def predict_category_id(query_or_title):
    """Usa domain_discovery con la keyword de IA (o título si no hay keyword)."""
    q = (query_or_title or "").strip()
    for site in SITES_FALLBACK:
        try:
            res = http_get(f"{API}/sites/{site}/domain_discovery/search", params={"q": q})
            if isinstance(res, list) and res:
                cid = res[0].get("category_id")
                cname = res[0].get("category_name")
                if cid:
                    print(f"🧭 Categoría ({site} | '{q}'): {cid} → {cname}")
                    return cid
        except Exception as e:
            print(f"⚠️ domain_discovery {site} falló: {e}")
    return "CBT1157"

def validate_category_with_ai(title, cid):
    t = title.lower()
    if "lego" in t and cid != "CBT1157":
        print("🔧 Corrigiendo categoría a CBT1157 (LEGO Building Sets)")
        return "CBT1157"
    return cid

# ============ Sites ============
def get_user_id():
    return http_get(f"{API}/users/me").get("id")

def get_sites_to_sell(uid):
    res = http_get(f"{API}/marketplace/users/{uid}")
    out = [{"site_id": m.get("site_id"), "logistic_type": m.get("logistic_type", "remote")}
           for m in res.get("marketplaces", []) if m.get("site_id")]
    return out or [{"site_id": "MLM", "logistic_type": "remote"}]

def fill_ml_attributes_with_ai(cid: str, ml_schema: list, amazon_json: dict):
    """
    Usa IA para completar dinámicamente los atributos oficiales de Mercado Libre (schema)
    según los datos del producto en Amazon.
    El resultado mantiene la estructura del schema exacta, pero con 'value_name' rellenado.
    """
    if not OPENAI_API_KEY:
        return ml_schema

    try:
        from openai import OpenAI
        import re, json, os
        client = OpenAI(api_key=OPENAI_API_KEY)

        # 🔹 Convertimos a JSON limitado para no exceder tokens
        amazon_data = json.dumps(amazon_json)[:15000]
        ml_schema_json = json.dumps(ml_schema)[:15000]

        prompt = f"""
You are an expert AI system specialized in product data normalization for global e-commerce platforms.

──────────────────────────────
🎯 GOAL:
Analyze the following two JSON objects:
1. Mercado Libre attribute schema for category {cid}.
2. The Amazon product JSON for the same product.

Your task is to FILL the Mercado Libre schema by inserting the best possible 'value_name' for each attribute,
using data from the Amazon JSON.

──────────────────────────────
📋 RULES:
- Keep the Mercado Libre schema structure **exactly as received** (same order, ids, and fields).
- Only add or modify 'value_name'.
- NEVER delete, rename, or re-order any element.
- Fill every field that can be reasonably derived from the Amazon JSON.
- Translate or normalize text to English where appropriate.
- Use metric units (cm, kg, g, ml, etc.) when possible.
- Avoid hallucinations — only fill when evidence exists.
- If no data is available, leave 'value_name' empty or null.
- Always return a pure JSON array (no Markdown, text, or backticks).

──────────────────────────────
🧠 INTELLIGENCE GUIDELINES:
- Understand that attribute IDs may have different names but equivalent meanings.
  Match by meaning, not by literal key.
- Examples:
  - Brand → manufacturer, vendor, brand_name
  - Model → item_model_number, mpn, part_number
  - Material → material, composition, base_material
  - Weight → item_weight, shipping_weight
  - Dimensions → item_dimensions, package_dimensions
  - Color → color_name, variant_color
  - Age → recommended_age, target_age
  - Pieces → piece_count, number_of_pieces, count
  - Franchise / Collection → theme, line, series
  - Power, Voltage, Connectivity, Capacity, Compatibility, etc.

──────────────────────────────
🧾 INPUT:
Amazon Product JSON:
{amazon_data}

Mercado Libre Schema JSON:
{ml_schema_json}

──────────────────────────────
✅ OUTPUT FORMAT:
Return ONLY the completed Mercado Libre schema as a JSON array.
Do NOT include Markdown, code fences, or explanations.
"""

        # 🔹 Ejecutamos la IA
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )

        txt = resp.choices[0].message.content.strip()
        m = re.search(r"\[.*\]", txt, re.S)
        if not m:
            print("⚠️ No valid JSON array found in AI response.")
            return ml_schema

        filled = json.loads(m.group(0))

        # Guardar logs para depuración
        asin = amazon_json.get("asin", "UNKNOWN")
        os.makedirs("storage/logs/ai_filled_attrs", exist_ok=True)
        with open(f"storage/logs/ai_filled_attrs/{cid}_{asin}.json", "w", encoding="utf-8") as f:
            json.dump(filled, f, indent=2, ensure_ascii=False)
        print(f"💾 Log guardado: storage/logs/ai_filled_attrs/{cid}_{asin}.json")
        print(f"✅ IA completó {sum(1 for a in filled if a.get('value_name'))}/{len(filled)} atributos")

        return filled

    except Exception as e:
        print(f"⚠️ Error IA al completar atributos: {e}")
        return ml_schema

def get_additional_characteristics_ai(amazon_json: dict):
        """
        Usa IA para generar un bloque de características descriptivas 'main_characteristics'
        y 'second_characteristics' a partir del JSON completo de Amazon.
        """
        if not OPENAI_API_KEY:
            return [], []

        try:
            from openai import OpenAI
            import re, json
            client = OpenAI(api_key=OPENAI_API_KEY)

            prompt = f"""
    You are an advanced product data enrichment AI for e-commerce marketplaces like Amazon and MercadoLibre.

    Your task is to extract every relevant descriptive and technical characteristic
    from the provided Amazon product JSON, even if it is indirect or nested.

    ──────────────────────────────
    🎯 GOAL:
    Generate two complete lists of characteristics, as they would appear
    in a product datasheet (main and secondary).

    ──────────────────────────────
    ✅ OUTPUT FORMAT (STRICT JSON ONLY):
    {{
    "main_characteristics": [
        {{"id": "BRAND", "name": "Brand", "value_name": "LEGO"}},
        {{"id": "MODEL", "name": "Model", "value_name": "10314 Dried Flower Centerpiece"}},
        {{"id": "PIECES_NUMBER", "name": "Number of Pieces", "value_name": "812"}}
    ],
    "second_characteristics": [
        {{"id": "MATERIAL", "name": "Material", "value_name": "Plastic"}},
        {{"id": "COLOR", "name": "Color", "value_name": "Beige"}},
        {{"id": "THEME", "name": "Theme", "value_name": "Botanical"}},
        {{"id": "FRANCHISE", "name": "Franchise", "value_name": "LEGO Icons"}}
    ]
    }}

    ──────────────────────────────
    📋 RULES:
    - Detect attributes from keys like title, description, bullet_points, features, product_information, etc.
    - Include all descriptive and technical data relevant to the buyer.
    - Do not invent; only infer when strongly supported by context.
    - Convert dimensions and weights to metric units.
    - Keep IDs in SCREAMING_SNAKE_CASE.
    - Always return JSON only (no text, no Markdown).
    - Minimum 10 total characteristics between both groups.

    ──────────────────────────────
    Amazon Product JSON (truncated):
    {json.dumps(amazon_json)[:15000]}
    """

            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.4,
                messages=[{"role": "user", "content": prompt}],
            )
            txt = resp.choices[0].message.content.strip()
            m = re.search(r"\{.*\}", txt, re.S)
            if not m:
                return [], []

            data = json.loads(m.group(0))
            main = data.get("main_characteristics", []) or []
            second = data.get("second_characteristics", []) or []
            print(f"🧩 IA detectó {len(main)} main y {len(second)} second characteristics.")
            return main, second

        except Exception as e:
            print(f"⚠️ Error IA (características): {e}")
            return [], []


def add_required_defaults(cid: str, attributes: list) -> list:
    """Agrega atributos obligatorios genéricos si no están."""
    existing = {a["id"] for a in attributes if "id" in a}
    defaults = []

    # Reglas genéricas aplicables a todas las categorías CBT
    if "ITEM_CONDITION" not in existing:
        defaults.append({"id": "ITEM_CONDITION", "value_id": "2230284", "value_name": "New"})
    if "IS_KIT" not in existing:
        defaults.append({"id": "IS_KIT", "value_id": "242084", "value_name": "No"})
    if "IS_COLLECTIBLE" not in existing:
        defaults.append({"id": "IS_COLLECTIBLE", "value_id": "242084", "value_name": "No"})

    # Reglas por categoría (ampliable)
    if cid == "CBT1157":  # LEGO Building Sets
        if "BRAND" not in existing:
            defaults.append({"id": "BRAND", "value_name": "LEGO"})

    # Agregar y limpiar duplicados
    all_attrs = attributes + defaults
    seen = {}
    for a in all_attrs:
        aid = a.get("id")
        if aid and aid not in seen:
            seen[aid] = a
    return list(seen.values())

# ============ Publicador principal ============
def publish_item(asin_json):
    """
    asin_json puede venir de transform_mapper (mini_ml.json)
    """
    from uploader import upload_images_to_meli

    # 🔹 Si el input viene del transform_mapper (mini_ml)
    if "title_ai" in asin_json and "attributes_mapped" in asin_json:
        mini = asin_json
        print(f"📦 Usando JSON transformado (mini_ml) para {mini.get('asin')}")

        asin = mini.get("asin", "GENERIC")
        ai_title_es = mini.get("title_ai")
        ai_desc_es = mini.get("description_ai")
        model_name = mini.get("model")
        brand = mini.get("brand")
        gtins = mini.get("gtins", [])
        pkg = mini.get("package", {})
        price = mini.get("price", {})

        L, W, H, KG = pkg.get("length_cm"), pkg.get("width_cm"), pkg.get("height_cm"), pkg.get("weight_kg")

        # ✅ Validar dimensiones - rechazar fallbacks genéricos
        # ML rechaza dimensiones que parecen fallbacks (10×10×10, 1×1×1, etc.)
        if L and W and H and KG:
            # Detectar dimensiones fallback/genéricas
            is_fallback = False

            # Caso 1: Todas las dimensiones son iguales (10×10×10, 1×1×1)
            if L == W == H:
                is_fallback = True
                print(f"⚠️ Dimensiones fallback detectadas (todas iguales): {L}×{W}×{H}")

            # Caso 2: Dimensiones muy pequeñas o muy genéricas
            if L < 5 or W < 5 or H < 5:
                if not (L == 1 and W > 10 and H > 10):  # Permitir productos muy delgados reales
                    is_fallback = True
                    print(f"⚠️ Dimensiones sospechosas (muy pequeñas): {L}×{W}×{H}")

            # Caso 3: Peso muy bajo y sospechoso
            if KG < 0.05:
                is_fallback = True
                print(f"⚠️ Peso sospechoso (muy bajo): {KG} kg")

            if is_fallback:
                print("❌ Dimensiones rechazadas - NO SE PUEDE PUBLICAR sin dimensiones reales")
                print("💡 Sugerencia: Obtener dimensiones reales del producto antes de publicar")
                return None  # Abortar publicación
        else:
            print("❌ Faltan dimensiones - NO SE PUEDE PUBLICAR")
            return None

        base_price = price.get("base_usd", 0)
        tax = price.get("tax_usd", 0)
        cost = price.get("cost_usd", base_price)  # fallback si no hay tax
        net_amount = price.get("net_proceeds_usd") or price.get("final_usd", 0)  # soportar ambos formatos
        mk_pct = price.get("markup_pct", 35)
        cid = mini.get("category_id", "CBT1157")

        # ✅ Validar y limpiar GTINs ANTES de construir attributes
        valid_gtins = []
        for g in gtins:
            g_str = str(g).strip()
            if g_str.isdigit() and 12 <= len(g_str) <= 14:
                valid_gtins.append(g_str)
        gtins = valid_gtins

        # ✅ Si fallo previo con GTIN → no enviar GTIN
        if mini.get("last_error") == "GTIN_REUSED" or mini.get("force_no_gtin"):
            gtins = []

        # ✅ Si no hay GTIN válido, no agregarlo (ML rechaza GTINs sintéticos)
        if not gtins:
            print("⚠️ Sin GTIN válido - algunos países pueden rechazar la publicación")

        # ✅ Si hay más de un GTIN → usar solo el primero
        if len(gtins) > 1:
            gtins = [gtins[0]]

        if tax > 0:
            print(f"💰 Precio: ${base_price} + tax ${tax} = costo ${cost} + {mk_pct}% markup → net proceeds ${net_amount}")
        else:
            print(f"💰 Precio: ${base_price} (sin tax) + {mk_pct}% markup → net proceeds ${net_amount}")
        print(f"📦 {L}×{W}×{H} cm – {KG} kg")

        # 🔹 Atributos pre-mapeados
        attributes = []
        for aid, info in mini.get("attributes_mapped", {}).items():
            # ✅ Si force_no_gtin está activo, saltar GTIN en attributes_mapped
            if aid == "GTIN" and (mini.get("force_no_gtin") or mini.get("last_error") == "GTIN_REUSED"):
                continue
            val = info.get("value_name") or ""
            if val:
                attributes.append({"id": aid, "value_name": str(val)})

        # 🔹 Agregar GTIN si está
        if gtins:
            attributes.append({"id": "GTIN", "value_name": str(gtins[0])})

        # 🔹 Agregar paquete físico
        for pid, val in [("PACKAGE_LENGTH", L), ("PACKAGE_WIDTH", W),
                         ("PACKAGE_HEIGHT", H), ("PACKAGE_WEIGHT", KG)]:
            if val:
                unit = "cm" if "WEIGHT" not in pid else "kg"
                attributes.append({"id": pid, "value_name": f"{val} {unit}"})

        # 🔹 Fusionar características
        main_chars = mini.get("main_characteristics", [])
        second_chars = mini.get("second_characteristics", [])

        for block in (main_chars + second_chars):
            if not isinstance(block, dict):
                continue
            # ✅ Si force_no_gtin está activo, saltar GTIN en características
            if block.get("id") == "GTIN" and (mini.get("force_no_gtin") or mini.get("last_error") == "GTIN_REUSED"):
                continue
            if block.get("id") and block.get("value_name"):
                attributes.append({
                    "id": block["id"],
                    "value_name": str(block["value_name"])
                })

        # 🔹 Deduplicar IDs
        seen = set()
        dedup = []
        for a in attributes:
            aid = a.get("id")
            if aid and aid not in seen:
                seen.add(aid)
                dedup.append(a)
        attributes = dedup

        # 🔧 Normalizar atributos mini_ml (convertir value_struct → value_name y limpiar basura)
        normalized = []
        for a in attributes:
            aid = a.get("id")
            if not aid:
                continue

            val = a.get("value_name")

            # Si viene con value_struct, convertirlo a texto
            if not val and "value_struct" in a:
                vs = a["value_struct"]
                num = vs.get("number")
                unit = vs.get("unit")
                if num is not None:
                    val = f"{num} {unit}".strip()

            # Limpiar valores peligrosos o inválidos
            if not val or str(val).lower() in ["none", "null", "undefined", ""]:
                continue
            if isinstance(val, list):
                val = val[0]

            # Evitar unidades raras tipo pulgadas con comillas
            val = str(val).replace('"', '').strip()

            normalized.append({"id": aid, "value_name": val})

        attributes = normalized

        print(f"🧩 Atributos totales antes de filtrado: {len(attributes)}")

        # ========================================
        # 🧹 FILTRADO CRÍTICO DE ATRIBUTOS (SIEMPRE)
        # ========================================
        # Este filtrado se ejecuta SIEMPRE, antes de IA y antes de publicar
        # Lista completa de atributos que NUNCA deben enviarse a ML
        BLACKLISTED_ATTRS = {
            "VALUE_ADDED_TAX",  # Causa error 3510 en MLA
            "ITEM_DIMENSIONS", "PACKAGE_DIMENSIONS", "ITEM_PACKAGE_DIMENSIONS",
            "ITEM_WEIGHT", "ITEM_PACKAGE_WEIGHT",
            "BULLET_1", "BULLET_2", "BULLET_3", "BULLET_POINT", "BULLET_POINTS",
            "Batteries_Included", "Batteries_Required", "BATTERIES_REQUIRED",
            "AGE_RANGE", "AGE_RANGE_DESCRIPTION",
            "TARGET_GENDER", "SAFETY", "ASSEMBLY_REQUIRED", "IS_ASSEMBLY_REQUIRED",
            "ITEM_QTY", "DESCRIPTIVE_TAGS", "NUMBER_OF_PIECES",
            "LIQUID_VOLUME", "ITEM_FORM", "PRODUCT_BENEFIT", "SPECIAL_INGREDIENTS",
            "ITEM_PACKAGE_QUANTITY", "IS_FLAMMABLE", "FINISH_TYPE", "CONTROL_METHOD",
            "HEADPHONES_FORM_FACTOR", "HEADPHONES_JACK", "RECOMMENDED_USES_FOR_PRODUCT",
            "INCLUDED_COMPONENTS", "SENT", "ITEM_TYPE_KEYWORD",
            "IS_CRUELTY_FREE", "IS_FRAGRANCE_FREE", "WITH_HYALURONIC_ACID",
            "EARPICE_SHAPE", "EARPIECE_SHAPE", "AUDIO_DRIVER_TYPE", "NUMBER_OF_LITHIUM_ION_CELLS",
            "BATTERY_WEIGHT", "WATER_RESISTANCE_DEPTH", "MAIN_COLOR",
            "TOY_BUILDING_BLOCK_TYPE", "MATERIAL_TYPE_FREE", "SALE_FORMAT", "UNITS_PER_PACK",
            "UNSPSC_CODE", "IMPORT_DESIGNATION", "NUMBER_OF_ITEMS", "SCENT", "FRAGRANCE",
            "UNIT_VOLUME", "SAFETY_WARNING", "EDUCATIONAL_OBJECTIVE", "LIST_PRICE",
            "SPECIAL_FEATURE", "BATTERY", "SPECIAL_FEATURES", "RELEASE_DATE",
            "PACKAGE_QUANTITY", "WEBSITE_DISPLAY_GROUP_NAME", "TRADE_IN_ELIGIBLE",
            "WEBSITE_DISPLAY_GROUP", "MEMORABILIA", "ITEM_NAME", "ITEM_CLASSIFICATION",
            "BROWSE_CLASSIFICATION", "ADULT_PRODUCT", "AUTOGRAPHED", "ITEM_TYPE",
            "PACKAGING", "LITHIUM_BATTERY_ENERGY_CONTENT", "QUANTITY", "SKIN_TYPE",
            "GENDER", "IS_STRENGTHENER", "DIAL_COLOR", "DIAL_WINDOW_MATERIAL",
            "WATER_RESISTANCE_LEVEL"
        }

        # Filtrar atributos en blacklist
        pre_filter_count = len(attributes)
        attributes = [a for a in attributes if a.get("id") not in BLACKLISTED_ATTRS]

        # Filtrar atributos en español (nombres inválidos)
        spanish_prefixes = ["MARCA", "MODELO", "PESO", "DIMENSIONES", "CARACTERISTICAS",
                           "NUMERO_DE", "RANGO_DE", "GARANTIA", "TEMA", "BATERIA"]
        attributes = [a for a in attributes if not any(a.get("id","").startswith(p) for p in spanish_prefixes)]

        blacklist_filtered = pre_filter_count - len(attributes)
        if blacklist_filtered > 0:
            print(f"🧹 Filtrados {blacklist_filtered} atributos inválidos (blacklist)")

        # 🔹 Sale terms, imágenes desde mini_ml
        sale_terms = [
            {"id": "WARRANTY_TYPE", "value_id": "2230280", "value_name": "Seller warranty"},
            {"id": "WARRANTY_TIME", "value_name": "30 days"}
        ]

        # Cargar imágenes del mini_ml
        images = []
        for img in mini.get("images", []):
            if isinstance(img, dict) and img.get("url"):
                images.append({"source": img["url"]})
            elif isinstance(img, str):
                images.append({"source": img})

        if not images:
            print("❌ No hay imágenes en mini_ml - NO SE PUEDE PUBLICAR")
            print("💡 Sugerencia: Verificar que el transform_mapper cargue las imágenes correctamente")
            return None  # Abortar publicación

        attributes = add_required_defaults(cid, attributes)
        attributes = autofill_required_attrs(cid, attributes)

        # 🧠 Completar atributos IA (solo usando el JSON transformado mini_ml)
        try:
            print(f"🧠 Completando atributos IA (solo con JSON transformado) para categoría {cid}...")

            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)

            # Descargar schema de categoría para filtrado
            try:
                ml_schema = http_get(f"https://api.mercadolibre.com/categories/{cid}/attributes")
                # Crear mapa de IDs válidos del schema
                valid_attr_ids = {attr.get("id") for attr in ml_schema if attr.get("id")}
            except Exception as e:
                print(f"⚠️ No se pudo descargar schema de {cid}: {e}")
                print("   Se usará solo la blacklist para filtrar atributos")
                valid_attr_ids = None  # Desactivar filtrado por schema

            # ✅ Si force_no_gtin está activo, crear copia de mini_ml sin GTIN para evitar que la IA lo agregue
            mini_for_ai = mini.copy()
            if mini.get("force_no_gtin") or mini.get("last_error") == "GTIN_REUSED":
                # Eliminar GTINs del JSON que se pasa a la IA
                mini_for_ai.pop("gtins", None)
                if "attributes_mapped" in mini_for_ai and "GTIN" in mini_for_ai["attributes_mapped"]:
                    mini_for_ai["attributes_mapped"].pop("GTIN")
                if "main_characteristics" in mini_for_ai:
                    mini_for_ai["main_characteristics"] = [c for c in mini_for_ai["main_characteristics"] if c.get("id") != "GTIN"]
                if "second_characteristics" in mini_for_ai:
                    mini_for_ai["second_characteristics"] = [c for c in mini_for_ai["second_characteristics"] if c.get("id") != "GTIN"]

            prompt = f"""
Eres un experto en estructura de categorías de Mercado Libre.
Tienes el siguiente SCHEMA de atributos para la categoría {cid} y un JSON transformado (mini_ml).
Rellena 'value_name' solo usando la información disponible en el JSON transformado.
No inventes valores ni uses datos externos. Si no hay información, déjalo vacío.

JSON transformado (mini_ml):
{json.dumps(mini_for_ai, ensure_ascii=False)[:14000]}

Schema de categoría:
{json.dumps(ml_schema, ensure_ascii=False)[:14000]}

Devuelve SOLO un array JSON con los atributos rellenados.
"""

            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )

            txt = resp.choices[0].message.content.strip()
            m = re.search(r"\[.*\]", txt, re.S)
            if not m:
                print("⚠️ No se recibió JSON válido del modelo, se usarán solo los atributos del mini_ml.")
            else:
                attributes_ai = json.loads(m.group(0))
                if isinstance(attributes_ai, list):
                    attributes.extend(attributes_ai)

            # Filtrado adicional contra schema oficial (si está disponible)
            cleaned_attrs = []
            seen_ids = set()
            schema_filtered = 0

            if valid_attr_ids:
                print(f"📋 Schema de categoría {cid} tiene {len(valid_attr_ids)} atributos válidos")

            for a in attributes:
                if not isinstance(a, dict) or "id" not in a:
                    continue
                aid = a["id"]

                # Filtrar contra schema oficial (solo si está disponible)
                if valid_attr_ids is not None and aid not in valid_attr_ids:
                    schema_filtered += 1
                    continue

                # Deduplicar
                if aid in seen_ids:
                    continue

                val = a.get("value_name")
                if isinstance(val, list) and val:
                    val = val[0]
                if isinstance(val, str) and "," in val:
                    val = val.split(",")[0].strip()
                if not val or str(val).lower() in ["null", "none", "undefined", ""]:
                    continue

                # ML API requiere value_name como STRING siempre
                cleaned_attrs.append({"id": aid, "value_name": str(val)})
                seen_ids.add(aid)

            attributes = cleaned_attrs

            if schema_filtered > 0:
                print(f"🧹 Filtrados {schema_filtered} atributos adicionales (no en schema de categoría)")
            print(f"🧽 Atributos finales IA listos: {len(attributes)} válidos para publicar")

        except Exception as e:
            print(f"⚠️ Error completando atributos IA solo con mini_ml: {e}")

        # 🔹 Publicación
        body = {
            "title": ai_title_es[:60],
            "category_id": cid,
            "catalog_product": {
                "type": "PRODUCT_WITH_VARIANTS"
            },
            "currency_id": "USD",
            "available_quantity": 10,
            "condition": "new",
            "listing_type_id": "gold_pro",
            "buying_mode": "buy_it_now",
            "description": {"plain_text": ai_desc_es},
            "package_length": L,
            "package_width": W,
            "package_height": H,
            "package_weight": KG,
            "attributes": attributes,
            "sale_terms": sale_terms,
            "global_net_proceeds": net_amount,
            "_source_price": base_price,
            "_net_proceeds": net_amount,
            "seller_custom_field": asin
        }

        # 🔹 Imágenes: usar directamente URLs del mini_ml
        pics = []
        for img in mini.get("images", []):
            if isinstance(img, dict) and img.get("url"):
                pics.append({"source": img["url"]})
            elif isinstance(img, str):
                pics.append({"source": img})

        # ML requiere mínimo una imagen
        if not pics:
            pics = [{"source": "https://http2.mlstatic.com/D_NQ_NP_2X_664019-MLA54915512781_042023-F.webp"}]

        body["pictures"] = pics

    # === Reforzar campos obligatorios ===
    uid = get_user_id()
    sites = get_sites_to_sell(uid)
    if not sites:
        sites = [{"site_id": "MLM", "logistic_type": "remote"}]  # fallback seguro

    # Asegurar imágenes
    pics = []
    if "pictures" in body and body["pictures"]:
        pics = body["pictures"]
    elif "images" in asin_json and asin_json["images"]:
        pics = [{"source": img} if isinstance(img, str) else img for img in asin_json["images"]]
    elif "pictures" in asin_json and asin_json["pictures"]:
        pics = asin_json["pictures"]

    # Fallback si no hay imágenes (requerido por API)
    if not pics:
        pics = [{"source": "https://http2.mlstatic.com/D_NQ_NP_2X_664019-MLA54915512781_042023-F.webp"}]

    body["pictures"] = pics
    # Para CBT (Cross Border Trade), NO especificar site_id para que se replique en todos los marketplaces
    # El array sites_to_sell define automáticamente dónde se publica
    body["logistic_type"] = "remote"  # CBT siempre usa logística remota (cross-border)
    body["sites_to_sell"] = sites

        # === 🔧 Corrección final de atributos requeridos antes del POST ===
    # Limpia duplicados y fuerza valores válidos de IS_KIT / IS_COLLECTIBLE
    final_attrs = []
    seen_ids = set()
    for a in attributes:
        aid = a.get("id")
        if not aid or aid in seen_ids:
            continue
        if aid == "IS_KIT":
            a["value_id"] = "242084"
            a["value_name"] = "No"
        elif aid == "IS_COLLECTIBLE":
            a["value_id"] = "242084"
            a["value_name"] = "No"
        elif aid == "ITEM_CONDITION":
            a["value_id"] = "2230284"
            a["value_name"] = "New"
        final_attrs.append(a)
        seen_ids.add(aid)
    attributes = final_attrs

    print("🚀 Publicando item desde mini_ml ...")
    res = http_post(f"{API}/global/items", body)
    item_id = res.get("id")
    print(f"✅ Publicado → {item_id}")
    return res
        
# ============ Main ============
def main():
    # Buscar directamente los archivos mini_ml procesados
    mini_ml_dir = "storage/logs/publish_ready"
    files = sorted(glob.glob(os.path.join(mini_ml_dir, "*_mini_ml.json")))

    print(f"\n🚀 Publicador CBT iniciado ({len(files)} productos)\n")
    if not files:
        print("⚠️ No hay archivos mini_ml para publicar.")
        print(f"   Busqué en: {mini_ml_dir}/")
        return

    for f in files:
        asin = os.path.basename(f).replace("_mini_ml.json", "")
        print(f"🔄 Procesando {asin}...")
        try:
            with open(f, "r", encoding="utf-8") as fh:
                mini_ml = json.load(fh)
            publish_item(mini_ml)
        except Exception as e:
            print(f"❌ Error {asin}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            time.sleep(2)  # Esperar entre publicaciones para evitar rate limiting
    print("\n✅ Proceso completo.")

if __name__ == "__main__":
    main()