#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# 🧠 transform_mapper_new_v4.py
# Amazon → Mini-ML (compacto) para que lo consuma MainGlobal
# - Equivalencias + cache
# - Categoría por embeddings locales (CategoryMatcher)
# - Título/Descripción en ES (robusto, sin “Claro, por favor …”)
# - Características primarias/secundarias
# - Dimensiones/GTIN/Imágenes listas
# ============================================================

import os, sys, re, json, time, requests
from typing import Dict, List, Any, Tuple

# ---------- 0) Auto-activar venv ----------
if sys.prefix == sys.base_prefix:
    vpy = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
    if os.path.exists(vpy):
        print(f"⚙️ Activando entorno virtual automáticamente desde: {vpy}")
        os.execv(vpy, [vpy] + sys.argv)

# ---------- 1) Entorno ----------
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except Exception:
    pass

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MARKUP_PCT = float(os.getenv("MARKUP_PCT", "35")) / 100.0

from openai import OpenAI
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Category matcher local (embeddings)
try:
    from src.category_matcher import match_category
except ModuleNotFoundError:
    from category_matcher import match_category

API = "https://api.mercadolibre.com"
HEADERS = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"} if ML_ACCESS_TOKEN else {}

# ---------- 2) Cachés ----------
CACHE_EQ_PATH   = "storage/logs/ai_equivalences_cache.json"
TITLE_CACHE_PATH= "storage/logs/ai_title_cache.json"
DESC_CACHE_PATH = "storage/logs/ai_desc_cache.json"

def _load_cache(path, default=None):
    try:
        if os.path.exists(path):
            return json.load(open(path, "r", encoding="utf-8"))
    except:
        pass
    return default if default is not None else {}

def _save_cache(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ---------- 3) Utils ----------
def load_json_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json_file(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def flatten(d, prefix="", out=None):
    if out is None: out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            flatten(v, f"{prefix}.{k}" if prefix else k, out)
    elif isinstance(d, list):
        for i, v in enumerate(d):
            flatten(v, f"{prefix}[{i}]", out)
    else:
        val = str(d).strip()
        if val and val.lower() not in {"none","null","default","n/a"} and len(val)<=400:
            out[prefix] = val
    return out

def normalize_key(k: str) -> str:
    return re.sub(r"[\s_\-\[\]\.]+","", str(k).lower())

def _read_number(x, default=None):
    try:
        if isinstance(x, (int, float)): return float(x)
        return float(re.sub(r"[^\d\.\-]", "", str(x)))
    except:
        return default

def extract_number(s):
    m = re.search(r"-?\d+(\.\d+)?", str(s))
    return float(m.group(0)) if m else None

# ---------- 4) Dimensiones (conversión) ----------
def _norm_unit(u: str) -> str:
    u = str(u or "").strip().lower()
    m = {
        "centimeters":"cm","centimeter":"cm","cm":"cm",
        "millimeters":"mm","millimeter":"mm","mm":"mm",
        "meters":"m","meter":"m","m":"m",
        "inches":"in","inch":"in","in":"in",
        "kilograms":"kg","kilogram":"kg","kg":"kg",
        "grams":"g","gram":"g","g":"g",
        "pounds":"lb","pound":"lb","lb":"lb","lbs":"lb",
        "ounces":"oz","ounce":"oz","oz":"oz"
    }
    return m.get(u, u)

def _to_cm(value, unit):
    unit = _norm_unit(unit)
    if value is None: return None
    if unit == "cm": return value
    if unit == "mm": return value/10.0
    if unit == "m": return value*100.0
    if unit == "in": return value*2.54
    return value

def _to_kg(value, unit):
    unit = _norm_unit(unit)
    if value is None: return None
    if unit == "kg": return value
    if unit == "g":  return value/1000.0
    if unit == "lb": return value*0.45359237
    if unit == "oz": return value*0.028349523125
    return value

# ---------- 5) Schemas y equivalencias extendidas ----------
SCHEMAS_DIR = "schemas"

def load_schema(category_id: str) -> dict:
    """Carga el schema de atributos de ML para la categoría dada"""
    path = os.path.join(SCHEMAS_DIR, f"{category_id}.json")
    if os.path.exists(path):
        try:
            return json.load(open(path, "r", encoding="utf-8"))
        except Exception as e:
            print(f"⚠️ Error al cargar schema {category_id}: {e}")
    return {}

def load_equivalences(category_id: str) -> dict:
    """Carga equivalencias aprendidas para la categoría"""
    path = os.path.join(SCHEMAS_DIR, f"{category_id}_equiv.json")
    if os.path.exists(path):
        try:
            return json.load(open(path, "r", encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_equivalences(category_id: str, data: dict):
    """Guarda nuevas equivalencias aprendidas por IA"""
    os.makedirs(SCHEMAS_DIR, exist_ok=True)
    path = os.path.join(SCHEMAS_DIR, f"{category_id}_equiv.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"💾 Equivalencias guardadas → {path}")

PACKAGE_DIMENSION_KEYS = {
    "length": [
        "attributes.item_package_dimensions[0].length.value",
        "item_package_dimensions.length.value",
        "package_dimensions.length", "item_package_length", "package_length",
        "shipping_dimensions.length","outer_dimensions.length","outer_package_length","box_length"
    ],
    "width": [
        "attributes.item_package_dimensions[0].width.value",
        "item_package_dimensions.width.value",
        "package_dimensions.width", "item_package_width", "package_width",
        "shipping_dimensions.width","outer_dimensions.width","outer_package_width","box_width"
    ],
    "height": [
        "attributes.item_package_dimensions[0].height.value",
        "item_package_dimensions.height.value",
        "package_dimensions.height", "item_package_height", "package_height",
        "shipping_dimensions.height","outer_dimensions.height","outer_package_height","box_height"
    ],
    "weight": [
        "attributes.item_package_weight[0].value",
        "item_package_weight","package_weight","shipping_weight","gross_weight","parcel_weight"
    ]
}

def _find_in_flat(flat: Dict[str, Any], keys: List[str]):
    norm = {normalize_key(k): v for k, v in flat.items()}
    for k in keys:
        nk = normalize_key(k)
        for fk, v in norm.items():
            if nk in fk or fk in nk:
                return v
    return None

def get_pkg_dim(flat, kind) -> Dict[str, Any] | None:
    kind = kind.lower()
    # 1) valor + unidad explícitas
    val = None; unit = None
    for val_key in [
        f"attributes.item_package_dimensions[0].{kind}.value",
        f"item_package_dimensions.{kind}.value",
        f"package_dimensions.{kind}.value",
        f"{kind}.value"
    ] + PACKAGE_DIMENSION_KEYS.get(kind, []):
        v = _find_in_flat(flat, [val_key])
        if v is not None:
            val = extract_number(v)
            if val is not None: break
    for unit_key in [
        f"attributes.item_package_dimensions[0].{kind}.unit",
        f"item_package_dimensions.{kind}.unit",
        f"package_dimensions.{kind}.unit",
        f"{kind}.unit"
    ]:
        u = _find_in_flat(flat, [unit_key])
        if u:
            unit = u
            break

    if val is not None:
        if kind == "weight":
            val = _to_kg(val, unit or "kg")
            return {"number": round(float(val), 3), "unit": "kg"}
        else:
            val = _to_cm(val, unit or "cm")
            return {"number": round(float(val), 2), "unit": "cm"}

    # 2) fallback por lista de candidatos
    for c in PACKAGE_DIMENSION_KEYS.get(kind, []):
        v = _find_in_flat(flat, [c])
        if v is not None:
            num = extract_number(v)
            if num is not None:
                if kind == "weight":
                    return {"number": round(float(_to_kg(num, "kg")), 3), "unit": "kg"}
                return {"number": round(float(_to_cm(num, "cm")), 2), "unit": "cm"}
    return None

# ---------- 5) Precio + Tax ----------
def get_amazon_base_price(amazon_json) -> float:
    """Extrae el precio base del producto (sin tax)"""
    flat = flatten(amazon_json)
    candidates = [
        "attributes.list_price[0].value",
        "offers.listings[0].price.amount",
        "price.value",
        "summaries[0].listprice.value",
        "attributes.suggested_lower_price_plus_shipping[0].value",
        "price",
    ]
    for p in candidates:
        v = _find_in_flat(flat, [p])
        if v is not None:
            num = _read_number(v)
            if num is not None:
                return round(num, 2)
    return 10.0

def get_amazon_tax(amazon_json) -> float:
    """
    Extrae el tax del producto de Amazon.
    El tax es lo que el seller paga por el producto (parte del costo).
    """
    flat = flatten(amazon_json)
    candidates = [
        "offers.listings[0].price.tax",
        "offers.listings[0].price.sales_tax",
        "price.tax",
        "summaries[0].listprice.tax",
        "estimated_fees[0].tax_amount",
        "tax_amount",
        "sales_tax",
    ]
    for p in candidates:
        v = _find_in_flat(flat, [p])
        if v is not None:
            num = _read_number(v)
            if num is not None and num > 0:
                return round(num, 2)
    # Si no se encuentra tax, asumir 0 (algunos productos pueden no tener tax)
    return 0.0

def compute_price(base, tax=0.0) -> Dict[str, float]:
    """
    Calcula el precio final para ML usando net_proceeds.

    Fórmula:
    1. costo_total = precio_base + tax (lo que el seller paga)
    2. net_proceeds = costo_total * (1 + markup) (lo que el seller quiere ganar)

    ML se encarga automáticamente de:
    - Agregar comisiones
    - Agregar shipping costs
    - Calcular el precio final que ve el comprador
    """
    cost = round(base + tax, 2)
    net_proceeds = round(cost * (1.0 + MARKUP_PCT), 2)
    return {
        "base_usd": round(base, 2),
        "tax_usd": round(tax, 2),
        "cost_usd": cost,
        "markup_pct": int(MARKUP_PCT * 100),
        "net_proceeds_usd": net_proceeds
    }

# ---------- 6) Brand / Model / GTIN / Images ----------
BASE_EQUIV = {
    "BRAND": ["brand","brand_name","attributes.brand[0].value","summaries[0].brandname","manufacturer","bylineinfo"],
    "MODEL": ["model","model_number","item_model_number","attributes.model_number[0].value","summaries[0].modelnumber","mpn","part_number"],
}

def first_of(amazon_json, keys):
    flat = flatten(amazon_json)
    norm_flat = {normalize_key(k): v for k, v in flat.items()}
    for k in keys:
        nk = normalize_key(k)
        for fk, v in norm_flat.items():
            # 🔹 Evitar tomar etiquetas de idioma, metadata, o IDs de marketplace
            # Filtrar por nombre de la key
            if "languagetag" in fk or "language_tag" in fk:
                continue
            if "marketplaceid" in fk or "marketplace_id" in fk:
                continue
            if not (nk in fk):
                continue

            val = str(v).strip()

            # Evitar valores triviales, marcadores de idioma, metadata y unidades sin valores
            invalid_values = {
                # Language tags y locales
                "en_us", "en-us", "es_mx", "pt_br", "language_tag",
                # Marketplace IDs
                "atvpdkikx0der", "a1am78c64um0y8", "marketplace_id",
                # Valores vacíos o genéricos
                "default", "none", "null", "n/a", "na", "not specified", "unknown",
                # Unidades solas (sin valores numéricos)
                "kilograms", "grams", "pounds", "ounces", "kg", "g", "lb", "oz",
                "centimeters", "millimeters", "inches", "meters", "cm", "mm", "in", "m",
                # Booleanos solos
                "true", "false", "yes", "no"
            }

            if val.lower() in invalid_values or len(val) == 0:
                continue

            # También evitar valores que sean solo unidades (números con unidades pegadas)
            if re.match(r'^\d+(\.\d+)?\s*(kg|g|lb|oz|cm|mm|in|m|kilograms|grams|pounds|ounces|centimeters|millimeters|inches|meters)$', val.lower()):
                continue

            # Evitar valores que sean solo IDs de marketplace
            if len(val) == 14 and val.isalnum() and val.isupper():
                continue

            return val
    return ""
def detect_gtin_with_ai(amazon_json):
    """
    Usa OpenAI para detectar GTIN/UPC/EAN en el JSON de Amazon.
    Fallback a búsqueda heurística si IA no está disponible.
    """
    if not OPENAI_API_KEY:
        print("⚠️ OPENAI_API_KEY no disponible, usando búsqueda heurística")
        matches = re.findall(r"\b\d{12,14}\b", json.dumps(amazon_json))
        if matches:
            return matches[0]
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = f"""Analiza este JSON de Amazon y extrae el GTIN/UPC/EAN del producto.
Responde SOLO con JSON: {{"gtin": "número de 12-14 dígitos"}}

Si no encuentras GTIN, responde: {{"gtin": null}}

JSON de Amazon:
{json.dumps(amazon_json, ensure_ascii=False)[:8000]}"""

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
                return str(gtin).strip()
    except Exception as e:
        print(f"⚠️ Error en detección IA de GTIN: {e}")

    # Fallback heurístico
    matches = re.findall(r"\b\d{12,14}\b", json.dumps(amazon_json))
    if matches:
        return matches[0]
    return None


def extract_gtins(amazon_json)->List[str]:
    """
    Extrae SOLO GTINs reales (UPC/EAN) del JSON de Amazon SP-API.
    NO extrae classificationId, unspsc_code, ni otros números.

    Si no encuentra GTINs, usa IA como fallback.
    """
    out = []

    # 1. Buscar en externally_assigned_product_identifier (lugar correcto)
    flat = flatten(amazon_json)
    for k, v in flat.items():
        lk = normalize_key(k)
        if "externallyassignedproductidentifier" in lk and lk.endswith("value"):
            g = re.sub(r"\D", "", str(v))
            if 12 <= len(g) <= 14:  # Solo GTINs válidos (12-14 dígitos)
                out.append(g)

    # 2. Buscar en attributes.item_package_upc (Amazon a veces lo pone ahí)
    attrs = amazon_json.get("attributes", {})
    for attr_name in ["item_package_upc", "upc", "ean", "gtin"]:
        if attr_name in attrs:
            values = attrs[attr_name]
            if isinstance(values, list):
                for item in values:
                    if isinstance(item, dict) and "value" in item:
                        g = re.sub(r"\D", "", str(item["value"]))
                        if 12 <= len(g) <= 14:
                            out.append(g)

    # 3. NO hacer fallback genérico - Si no encontramos GTIN, devolver lista vacía
    # Esto evita agarrar classificationId, unspsc_code, etc.

    # Normalizar y deduplicar
    clean, seen = [], set()
    for g in out:
        if g not in seen and 12 <= len(g) <= 14:
            seen.add(g)
            clean.append(g)

    # ✅ NUEVO: Si no se encontró GTIN → usar IA como fallback
    if not clean:
        print("⚠️ No se encontró GTIN en JSON → Intentando detectar con IA...")
        ai_gtin = detect_gtin_with_ai(amazon_json)
        if ai_gtin:
            clean.append(ai_gtin)
            print(f"✅ GTIN detectado con IA: {ai_gtin}")
        else:
            print("❌ IA no pudo detectar GTIN")

    return sorted(clean)

def extract_images(amazon_json, max_images=10):
    """
    Extrae imágenes de Amazon agrupadas por variante y devuelve solo
    la de mayor resolución por variante, manteniendo el orden original.
    No incluye imágenes low-res ni duplicadas.
    """
    flat = flatten(amazon_json)
    images_raw = []  # (variant, url, width, height, order_index)

    # Detectar estructuras típicas de Amazon SP-API
    # 1) images[…] — soportar estructura SP-API con "images" interna
    imgs = amazon_json.get("images") or []
    order = 0
    for item in imgs:
        if isinstance(item, dict):
            # Caso: SP-API → {"marketplaceId": "...", "images": [ {...}, {...} ]}
            inner = item.get("images")
            if isinstance(inner, list):
                for sub in inner:
                    if isinstance(sub, dict) and sub.get("link"):
                        w = sub.get("width") or 0
                        h = sub.get("height") or 0
                        variant = sub.get("variant") or "MAIN"
                        images_raw.append((variant, sub["link"], w, h, order))
                        order += 1
                        continue

            # Caso: Amazon simple → [{"variant": "...", "link": "..."}]
            link = item.get("link")
            if link and link.startswith("http"):
                w = item.get("width") or 0
                h = item.get("height") or 0
                variant = item.get("variant") or "MAIN"
                images_raw.append((variant, link, w, h, order))
                order += 1

    # 2) images[...] debajo de la clave "images" en flattened JSON
    for k, v in flat.items():
        if isinstance(v, str) and v.startswith("http") and "amazon" in v:
            if any(t in v for t in ["_SL75_", "_SX342_", "_SS100_", "_AC_UL75_", "_AC_SR75_"]):
                continue
            # intentar detectar variante del key
            vk = k.lower()
            variant = "MAIN"
            m = re.search(r"variant[^a-z0-9]?([a-z0-9]+)", vk)
            if m:
                variant = m.group(1).upper()
            images_raw.append((variant, v, 0, 0, order))
            order += 1

    if not images_raw:
        return []  # no hay nada

    # Agrupar por variante y elegir la de mayor resolución
    from collections import OrderedDict
    best_by_variant = OrderedDict()

    for variant, url, w, h, idx in images_raw:
        if variant not in best_by_variant:
            best_by_variant[variant] = (url, w, h, idx)
        else:
            old_url, old_w, old_h, old_idx = best_by_variant[variant]
            # Si la nueva tiene mayor resolución, reemplazar
            if (w * h) > (old_w * old_h):
                best_by_variant[variant] = (url, w, h, idx)

    # Mantener orden original según aparición del variant
    final = [
        {"variant": variant, "url": data[0]}
        for variant, data in best_by_variant.items()
    ]

    # Limitar a max_images
    return final[:max_images]

# ---------- 7) AI: equivalencias y copy ----------
def ask_gpt_equivalences(category_id, missing, amazon_json, cache: dict):
    """
    Busca equivalencias entre los atributos de MercadoLibre y las claves reales del JSON de Amazon.
    Usa IA solo si no existen en cache. Amplía el contexto a 800 claves y agrega coincidencia parcial.
    """
    if not client or not missing:
        return {}

    # solo preguntar los que no estén en cache
    to_ask = [m for m in missing if m not in cache]
    if not to_ask:
        print("♻️ Sin nuevas equivalencias a pedir (cache).")
        return {}

    # 🔹 Flatten del JSON con mayor contexto
    flat = flatten(amazon_json)
    sample = "\n".join(f"{k}: {v}" for k, v in list(flat.items())[:800])

    prompt = f"""
    Find equivalences between MercadoLibre attribute keys and real keys in the provided Amazon JSON.
    Category: {category_id}
    Missing attributes: {to_ask}
    Amazon JSON (flattened sample):
    {sample}

    Return ONLY JSON:
    {{"equivalences": {{"COLOR":["color","attributes.color[0].value"], "MATERIAL":["material"]}}}}
    Use only keys that exist in the sample (don't invent).
        """

    try:
        r = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.1,
            messages=[
                {"role": "system", "content": "Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
        )

        # intentar parsear respuesta
        m = re.search(r"\{.*\}", (r.choices[0].message.content or "").strip(), re.S)
        data = json.loads(m.group(0)) if m else {}
        eqs = data.get("equivalences", {})

        # 🔸 Guardar en cache principal
        for k, v in eqs.items():
            cache[k] = v
        _save_cache(CACHE_EQ_PATH, cache)
        if eqs:
            print(f"💾 Equivalencias aprendidas: +{len(eqs)}")

        # 🔸 Fallback: buscar coincidencias parciales en el JSON
        for miss in missing:
            if miss not in cache:
                nk = normalize_key(miss)
                for fk, fv in flat.items():
                    if nk in normalize_key(fk):
                        cache[miss] = [fk]
                        break

        if eqs or any(m not in to_ask for m in missing):
            print(f"💡 Coincidencias parciales añadidas: {len([m for m in missing if m in cache])}/{len(missing)}")

        return eqs

    except Exception as e:
        print(f"⚠️ IA equivalences error: {e}")
        return {}

def ai_title_es(base_title, brand, model, bullets, max_chars=60):
    if not client: return (base_title or "Producto")[:max_chars]
    prompt = f"""Devuelve SOLO el título final (sin explicaciones), en español LATAM, <= {max_chars} caracteres.
Incluye marca y modelo si existen. Natural, sin emojis ni HTML.
Base: {base_title}
Marca: {brand}
Modelo: {model}
Bullets (opcionales): {bullets}"""
    try:
        r = client.chat.completions.create(
            model=OPENAI_MODEL, temperature=0.2,
            messages=[{"role":"system","content":"Responde únicamente con el título final. Sin comillas."},
                      {"role":"user","content":prompt}],
            max_tokens=80,
        )
        t = (r.choices[0].message.content or "").strip().replace("\n"," ")
        return t[:max_chars] if t else (base_title or "Producto")[:max_chars]
    except:
        return (base_title or "Producto")[:max_chars]

def ai_desc_es(datos, mini_ml=None):
    if not client:
        return ""

    # 1) Descripción principal por IA
    prompt = f"""Escribe SOLO el texto (sin explicaciones) de una descripción clara en español LATAM (3-5 párrafos).
Incluye beneficios reales a partir de los datos. Sin HTML ni emojis.
Datos: {json.dumps(datos, ensure_ascii=False)[:2000]}"""

    try:
        r = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.3,
            messages=[
                {"role": "system", "content": "Devuelve solo texto plano. Sin títulos ni listas vacías."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=600,
        )
        texto = (r.choices[0].message.content or "").strip()
    except:
        texto = ""

    # 2) Mini-tabla de especificaciones (solo si hay datos)
    try:
        specs_lines = []
        if mini_ml:
            if mini_ml.get("brand"):
                specs_lines.append(f"• Marca: {mini_ml['brand']}")
            if mini_ml.get("model"):
                specs_lines.append(f"• Modelo: {mini_ml['model']}")
            if mini_ml.get("package"):
                pkg = mini_ml["package"]
                specs_lines.append(f"• Dimensiones del paquete: {pkg['length_cm']} x {pkg['width_cm']} x {pkg['height_cm']} cm")
                specs_lines.append(f"• Peso del paquete: {pkg['weight_kg']} kg")

            # Datos adicionales útiles si existen en mini_ml
            if mini_ml.get("main_characteristics"):
                for ch in mini_ml["main_characteristics"]:
                    if isinstance(ch, dict) and ch.get("name") and ch.get("value_name"):
                        val = str(ch["value_name"]).strip()
                        # Filtrar marcadores de idioma y valores inválidos
                        if val and val.lower() not in {"en_us", "en-us", "default", "null", "none", "n/a", "not specified"}:
                            specs_lines.append(f"• {ch['name']}: {val}")

        if specs_lines:
            texto += "\n\n📌 **Especificaciones del producto**\n" + "\n".join(specs_lines)

    except Exception:
        pass

    # 3) Bloque Global Selling (fijo)
    texto += """
\n\n🌍 **Información importante para compradores internacionales**
• Producto completamente nuevo y original.
• Pagamos impuestos en EE.UU. y podemos emitir factura desde EE.UU.  
• En caso de productos eléctricos, tenga en cuenta que en EE.UU. se utiliza 110-120V.  
• Si el producto incluye baterías, podrían ser removidas para cumplir normativas de transporte internacional.  
• Envío internacional asegurado con número de seguimiento.  
• Soporte en español e inglés.  
"""

    return texto

def ai_characteristics(amazon_json)->Tuple[List[dict], List[dict]]:
    """Extrae main/second characteristics con IA (robusto, JSON-only)."""
    if not client: return [], []

    # Extraer primero TODOS los atributos disponibles
    all_attrs = amazon_json.get("attributes", {})
    summaries = amazon_json.get("summaries", [{}])[0] if amazon_json.get("summaries") else {}

    prompt = f"""Extract ALL product characteristics from this Amazon product JSON. You MUST be VERY thorough and extract AT LEAST 20-30 characteristics total.

Divide them into TWO groups:
1. "main" - Most important specs (10-15 items): brand, model, weight, dimensions, quantity, part_number, age_range, theme, etc.
2. "second" - Additional details (10-15 items): material, color, style, features, battery info, packaging, compatibility, warnings, etc.

Format (STRICT JSON):
{{
 "main": [{{"id":"BRAND","name":"Marca","value_name":"Sony"}}, {{"id":"MODEL","name":"Modelo","value_name":"WH-1000XM5"}}, ...],
 "second": [{{"id":"MATERIAL","name":"Material","value_name":"Plastic, Leather"}}, {{"id":"COLOR","name":"Color","value_name":"Black"}}, ...]
}}

CRITICAL RULES:
- Extract AT LEAST 10 items for "main" and AT LEAST 10 items for "second" (minimum 20 total)
- Extract ONLY actual values from the JSON data, NEVER use metadata like "en_US", "language_tag", "marketplace_id"
- For array attributes like {{"color":[{{"value":"Red","language_tag":"en_US"}}]}}, extract ONLY "Red"
- Use descriptive Spanish names: "Marca", "Modelo", "Peso", "Dimensiones", "Material", "Color", etc.
- Convert measurements to metric (cm, kg, L, mL)
- Be EXHAUSTIVE - extract everything: specifications, features, dimensions, materials, compatibility, age ratings, warnings, packaging details, etc.
- Include data from both "attributes" and "summaries" sections

Available attributes: {list(all_attrs.keys())[:50]}
Available summaries: {list(summaries.keys())[:30]}

Full JSON (truncated):
{json.dumps(amazon_json)[:12000]}"""

    try:
        r = client.chat.completions.create(
            model=OPENAI_MODEL, temperature=0.3,
            messages=[{"role":"system","content":"You are an expert at extracting product specifications. Return ONLY valid JSON with AT LEAST 20 total characteristics. Extract actual values, never metadata."},
                      {"role":"user","content":prompt}],
        )
        m = re.search(r"\{.*\}", (r.choices[0].message.content or "").strip(), re.S)
        data = json.loads(m.group(0)) if m else {}

        # Filtrar valores inválidos
        def clean_chars(chars):
            cleaned = []
            for ch in chars:
                if isinstance(ch, dict) and ch.get("value_name"):
                    val = str(ch["value_name"]).strip()

                    # Lista completa de valores inválidos
                    invalid_values = {
                        # Language tags y locales
                        "en_us", "en-us", "es_mx", "pt_br", "language_tag",
                        # Marketplace IDs
                        "atvpdkikx0der", "a1am78c64um0y8", "marketplace_id",
                        # Valores vacíos o genéricos
                        "default", "none", "null", "n/a", "na", "not specified", "unknown",
                        # Unidades solas (sin valores numéricos) - CRÍTICO PARA DIMENSIONES
                        "kilograms", "grams", "pounds", "ounces", "kg", "g", "lb", "oz",
                        "centimeters", "millimeters", "inches", "meters", "cm", "mm", "in", "m",
                        # Booleanos solos
                        "true", "false", "yes", "no"
                    }

                    # Eliminar marcadores de idioma y valores inválidos
                    if val and val.lower() not in invalid_values:
                        if len(val) > 0 and not val.startswith("marketplaceId"):
                            cleaned.append(ch)
            return cleaned

        main = clean_chars(data.get("main", []) or [])
        second = clean_chars(data.get("second", []) or [])

        # Si aún son muy pocos, agregar fallback básico
        if len(main) + len(second) < 10:
            # Extraer atributos básicos directamente del JSON
            if summaries.get("brand"):
                main.append({"id": "BRAND", "name": "Marca", "value_name": str(summaries["brand"])})
            if summaries.get("modelNumber"):
                main.append({"id": "MODEL", "name": "Modelo", "value_name": str(summaries["modelNumber"])})
            if summaries.get("color"):
                second.append({"id": "COLOR", "name": "Color", "value_name": str(summaries["color"])})
            if summaries.get("manufacturer"):
                second.append({"id": "MANUFACTURER", "name": "Fabricante", "value_name": str(summaries["manufacturer"])})

        return main, second
    except Exception as e:
        print(f"⚠️ Error en ai_characteristics: {e}")
        return [], []

# ---------- 8) Categoría (embeddings locales) ----------
def detect_category(amazon_json)->Tuple[str,str,float]:
    asin = amazon_json.get("asin") or amazon_json.get("ASIN") or ""

    title = amazon_json.get("title") or \
        amazon_json.get("product_title") or \
        amazon_json.get("attributes",{}).get("item_name",[{"value":""}])[0]["value"] \
        if amazon_json.get("attributes",{}).get("item_name") else "Generic Product"

    print("🧭 Detectando categoría (embeddings locales)…")

    # 📌 Cache por ASIN
    CAT_CACHE_PATH = "storage/logs/category_cache.json"
    try:
        cat_cache = json.load(open(CAT_CACHE_PATH, "r", encoding="utf-8"))
    except:
        cat_cache = {}

    # ✅ Cache encontrado → sin IA
    if asin in cat_cache:
        cat_id = cat_cache[asin]["id"]
        cat_name = cat_cache[asin]["name"]
        sim = cat_cache[asin]["sim"]
        print(f"🧠 Cache encontrado → IA OFF ✅")
        return cat_id, cat_name, sim

    # ✅ Nueva categorización → guardar en cache
    try:
        res = match_category(title, asin)
        cat_id  = res.get("matched_category_id", "CBT1157")
        cat_name = res.get("matched_category_name", "Default")
        sim     = float(res.get("similarity", 0.0))

        print(f"🤖 Nueva categorización embeddings → IA ON")
        cat_cache[asin] = {"id": cat_id, "name": cat_name, "sim": sim}
        os.makedirs("logs", exist_ok=True)
        with open(CAT_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cat_cache, f, indent=2, ensure_ascii=False)

        return cat_id, cat_name, sim

    except Exception as e:
        print(f"⚠️ CategoryMatcher error: {e}")
        return "CBT1157","Default",0.0

# ---------- 9) Schema ML ----------
def get_category_schema(category_id):
    """
    Descarga schema de categoría desde ML API con reintentos.
    Incluye todos los campos necesarios del schema.
    """
    try:
        # Primero intenta sin token (público)
        r = requests.get(f"{API}/categories/{category_id}/attributes", timeout=15)
        if r.status_code == 401 and HEADERS:
            # Si falla, intenta con autenticación
            r = requests.get(f"{API}/categories/{category_id}/attributes", headers=HEADERS, timeout=15)

        r.raise_for_status()
        schema_raw = r.json()

        schema = {}
        for a in schema_raw:
            if a.get("id"):
                schema[a["id"]] = {
                    "value_type": a.get("value_type"),
                    "values": {v["name"].lower(): v["id"] for v in a.get("values",[]) if v.get("id") and v.get("name")},
                    "allowed_units": [u["id"] for u in a.get("allowed_units",[])] if a.get("allowed_units") else [],
                    "tags": a.get("tags", {}),
                    "hierarchy": a.get("hierarchy", ""),
                    "relevance": a.get("relevance", 0)
                }

        print(f"📘 Schema {category_id}: {len(schema)} atributos descargados.")
        return schema
    except requests.exceptions.HTTPError as e:
        print(f"⚠️ Error HTTP obteniendo schema {category_id}: {e.response.status_code}")
        return {}
    except Exception as e:
        print(f"⚠️ No se pudo obtener schema {category_id}: {e}")
        return {}

        # ---------- Filtro de valores sospechosos ----------
def is_suspicious_value(val: str) -> bool:
    """Menos agresivo: solo descarta basura real."""
    if val is None:
        return True
    s = str(val).strip().lower()
    if s in {"", "none", "null"}:
        return True

    # Ya NO descartamos:
    # - números cortos (ej: 2193 piezas)
    # - "no", "yes"
    # - códigos cortos
    # - idioma en_us
    # ML procesará el orden y lo ubicará bien

    return False

# ---------- 10) Armado Mini-ML ----------
def build_mini_ml(amazon_json: dict) -> dict:
    asin = amazon_json.get("asin") or amazon_json.get("ASIN") or ""
    cat_id, cat_name, sim = detect_category(amazon_json)

    # ✅ Si la categoría ya está en caché → IA de equivalencias OFF
    CAT_CACHE_PATH = "storage/logs/category_cache.json"
    try:
        cat_cache = json.load(open(CAT_CACHE_PATH, "r", encoding="utf-8"))
    except:
        cat_cache = {}

    category_cached = asin in cat_cache

    if category_cached:
        print("🧠 Categoría caché → saltando aprendizaje IA de equivalencias ✅")
        SKIP_EQ_AI = True
    else:
        SKIP_EQ_AI = False

    # brand & model por equivalencias base
    brand = first_of(amazon_json, BASE_EQUIV["BRAND"]) or ""
    model = first_of(amazon_json, BASE_EQUIV["MODEL"]) or ""

    # título/descr (con caché)
    title_cache = _load_cache(TITLE_CACHE_PATH, {})
    desc_cache  = _load_cache(DESC_CACHE_PATH, {})

    base_title = amazon_json.get("title") or \
        amazon_json.get("product_title") or \
        amazon_json.get("attributes",{}).get("item_name",[{"value":""}])[0]["value"] \
        if amazon_json.get("attributes",{}).get("item_name") else "Producto"

    bullets = []
    if amazon_json.get("attributes",{}).get("bullet_point"):
        bullets = [
            b.get("value")
            for b in amazon_json["attributes"]["bullet_point"]
            if isinstance(b, dict) and b.get("value")
        ]

    # ==== TÍTULO ====
    if asin in title_cache:
        title_es = title_cache[asin]
    else:
        title_es = ai_title_es(base_title, brand, model, bullets, 60)
        title_cache[asin] = title_es
        _save_cache(TITLE_CACHE_PATH, title_cache)

    # ==== DESCRIPCIÓN ====
    # Preparar datos para descripción (siempre, no solo si falta en caché)
    datos_desc = {
        "brand": brand,
        "model": model,
        "bullets": bullets[:8]
    }

    if asin in desc_cache:
        desc_es = desc_cache[asin]
    else:
        try:
            desc_es = ai_desc_es(datos_desc)
        except:
            desc_es = f"{title_es}. Producto nuevo e importado desde EE.UU."

        # Fallback final si está vacío
        if not desc_es or not isinstance(desc_es, str):
            desc_es = f"{title_es}. Producto nuevo e importado desde EE.UU."

        desc_cache[asin] = desc_es
        _save_cache(DESC_CACHE_PATH, desc_cache)

    # dimensiones del PAQUETE (shipping dimensions, NO product dimensions)
    flat = flatten(amazon_json)
    L = get_pkg_dim(flat, "length")
    W = get_pkg_dim(flat, "width")
    H = get_pkg_dim(flat, "height")
    KG= get_pkg_dim(flat, "weight")

    # Extraer valores directamente - SIN FALLBACKS
    # Las dimensiones del paquete SIEMPRE deben estar en el JSON de SP-API
    length_cm = (L or {}).get("number") if L else None
    width_cm = (W or {}).get("number") if W else None
    height_cm = (H or {}).get("number") if H else None
    weight_kg = (KG or {}).get("number") if KG else None

    # Validar que TODAS las dimensiones existan
    if not all([length_cm, width_cm, height_cm, weight_kg]):
        print(f"⚠️ ADVERTENCIA: Dimensiones de paquete incompletas en {asin}")
        print(f"   Length: {length_cm}, Width: {width_cm}, Height: {height_cm}, Weight: {weight_kg}")
        print("   Las dimensiones del paquete deben estar en item_package_dimensions del JSON de Amazon")
        # Usar mínimos de ML como último recurso (10cm, 0.1kg)
        length_cm = length_cm or 10.0
        width_cm = width_cm or 10.0
        height_cm = height_cm or 10.0
        weight_kg = weight_kg or 0.1

    # Usar dimensiones reales de Amazon (sin aplicar mínimos artificiales)
    # ML acepta dimensiones menores a 10cm si son las reales del producto
    pkg = {
        "length_cm": round(length_cm, 2),
        "width_cm": round(width_cm, 2),
        "height_cm": round(height_cm, 2),
        "weight_kg": round(weight_kg, 3)
    }

    # precio + tax (mini)
    base_price = get_amazon_base_price(amazon_json)
    tax = get_amazon_tax(amazon_json)
    price = compute_price(base_price, tax)

    if tax > 0:
        print(f"💰 Precio: ${base_price} + tax ${tax} = costo ${price['cost_usd']} → net proceeds ${price['net_proceeds_usd']} (markup {price['markup_pct']}%)")
    else:
        print(f"💰 Precio: ${base_price} (sin tax) → net proceeds ${price['net_proceeds_usd']} (markup {price['markup_pct']}%)")

    # ================== IMÁGENES (Amazon → mini_ml imágenes con metadata) ==================
    # Usamos extract_images (una por variante, ordenada, hi-res)
    images = extract_images(amazon_json, max_images=12)

    # Si no hay imágenes, dejamos vacío (tu elección fue A)
    if not images:
        images = []
    else:
        # Guardamos con metadata completa (tu elección fue B)
        # Por si extract_images en el futuro devuelve más campos
        enriched = []
        for idx, img in enumerate(images):
            if isinstance(img, dict):
                enriched.append({
                    "variant": img.get("variant", "MAIN"),
                    "url": img.get("url"),
                    "w": img.get("w") if "w" in img else None,
                    "h": img.get("h") if "h" in img else None,
                    "order": idx
                })
            else:
                # Si viniera como string, wrap
                enriched.append({
                    "variant": "MAIN",
                    "url": img,
                    "w": None, "h": None,
                    "order": idx
                })
        images = enriched
    # ==============================================================================
    # gtin
    gtins = extract_gtins(amazon_json)

    # characteristics (IA)
    main_ch, second_ch = ai_characteristics(amazon_json)

    # ✅ Ya NO filtramos ni eliminamos: dejamos toda la info
    # Esto se usará luego para completar atributos faltantes en ML


    # ======================================================
    # ✅ Mega extractor de características (sin IA primero)
    # ======================================================
    COMMON_ATTRS = [
        # --- MAIN HIGH PRIORITY ---
        ("BRAND", ["brand","attributes.brand[0].value"], "Marca", True),
        ("MODEL", ["model","item_model_number","attributes.model_number[0].value"], "Modelo", True),
        ("GTIN", ["externally_assigned_product_identifier"], "Código universal", True),

        # --- SECONDARY ---
        ("ITEM_DIMENSIONS", ["item_dimensions", "item_package_dimensions"], "Dimensiones del producto", False),
        ("PACKAGE_DIMENSIONS", ["package_dimensions", "shipping_dimensions"], "Dimensiones del paquete", False),
        ("MANUFACTURER", ["manufacturer"], "Fabricante", False),
        ("SUB_BRAND", ["sub_brand","attributes.sub_brand[0].value"], "Sub-marca", False),
        ("BULLET_1", ["attributes.bullet_point[0].value"], "Detalle destacado 1", False),
        ("BULLET_2", ["attributes.bullet_point[1].value"], "Detalle destacado 2", False),
        ("BULLET_3", ["attributes.bullet_point[2].value"], "Detalle destacado 3", False),
        ("ITEM_QTY", ["item_package_quantity"], "Contenido del paquete", False),
        ("IS_KIT", ["is_kit"], "Es un kit", False),
        ("Batteries_Included", ["batteries_included"], "Baterías incluidas", False),
        ("Batteries_Required", ["batteries_required"], "Requiere baterías", False),
        ("SAFETY", ["safety_warning"], "Advertencia de seguridad", False),
        ("COUNTRY_ORIGIN", ["country_of_origin"], "País de origen", False),
        ("ASSEMBLY_REQUIRED", ["is_assembly_required"], "Requiere ensamblaje", False),
        ("WARRANTY", ["warranty_description"], "Garantía", False),
        ("NUMBER_OF_PIECES", ["number_of_pieces","attributes.number_of_pieces[0].value"], "Número de piezas", True),
        ("THEME", ["theme","attributes.theme[0].value"], "Tema", True),
        ("AGE_RANGE", ["age_range_description"], "Edad recomendada", True),
        ("COLOR", ["color","attributes.color[0].value"], "Color", True),
        ("MATERIAL", ["material","attributes.material[0].value"], "Material", True),
        ("ITEM_WEIGHT", ["item_weight","attributes.item_weight[0].value"], "Peso", True),
        ("TARGET_GENDER", ["target_gender"], "Género objetivo", True),
    ]


    def add_characteristic(attr_id, keys, label, priority=False):
        # Evitar duplicados
        if any(c.get("id") == attr_id for c in main_ch + second_ch):
            return
        
        val = _find_in_flat(flat, keys)
        if val and not is_suspicious_value(val):
            obj = {"id": attr_id, "name": label, "value_name": str(val)}
            if priority:
                main_ch.append(obj)
            else:
                second_ch.append(obj)

    # Aplicar extracción directa
    for attr_id, keys, label, priority in COMMON_ATTRS:
        add_characteristic(attr_id, keys, label, priority)

    # Garantizar mínimo sólido en MAIN
    if len(main_ch) < 8:
        # Ascender algunos secundarios útiles
        promote = ["ITEM_WEIGHT","NUMBER_OF_PIECES","AGE_RANGE","TARGET_GENDER"]
        for aid in promote:
            for i,ch in enumerate(second_ch):
                if ch["id"] == aid:
                    main_ch.append(ch)
                    del second_ch[i]
                    break
        main_ch = main_ch[:12]
    second_ch = second_ch[:20]  # Limitar por limpieza

    
     # atributos ML mapeados a schema (opcional, por si lo querés usar luego)
    # Cargar schema local o desde API si no existe
    schema = load_schema(cat_id)
    if not schema:
        print(f"📡 Descargando schema {cat_id} desde API…")
        schema = get_category_schema(cat_id)
        if schema:
            os.makedirs("resources/schemas", exist_ok=True)
            with open(f"resources/schemas/{cat_id}.json", "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2, ensure_ascii=False)
            print(f"💾 Schema {cat_id} guardado localmente.")

    equivs = load_equivalences(cat_id)
    cache_eq = _load_cache(CACHE_EQ_PATH, {})
    merged_equivs = {**BASE_EQUIV, **equivs, **cache_eq}
    matched, missing = {}, []
    for aid, meta in schema.items():
        if aid in {"PACKAGE_LENGTH","PACKAGE_WIDTH","PACKAGE_HEIGHT","PACKAGE_WEIGHT"}:
            continue

        if aid == "BRAND" and brand:
            matched[aid] = {"value_name": brand}
            continue
        if aid == "MODEL" and model:
            matched[aid] = {"value_name": model}
            continue
        if aid == "SELLER_SKU":
            matched[aid] = {"value_name": asin}
            continue

        val = None
        if aid in merged_equivs:
            val = _find_in_flat(flat, merged_equivs[aid])

        # ⚠️ Filtro de valores sospechosos
        if val is not None and is_suspicious_value(val):
            print(f"⚠️ Valor sospechoso ignorado para {aid}: {val}")
            missing.append(aid)
            continue  # 👈 esto garantiza que no se agregue a matched

        if val is not None:
            vtype = meta.get("value_type")
            if vtype == "list":
                lower = str(val).lower()
                vid = meta.get("values", {}).get(lower)
                if vid:
                    matched[aid] = {"value_id": vid, "value_name": str(val)}
                else:
                    matched[aid] = {"value_name": str(val)}
            elif vtype == "number_unit":
                num = extract_number(val)
                u = re.search(r"(cm|mm|kg|g|m|in|lb|oz)", str(val).lower())
                unit = u.group(1) if u else (meta.get("allowed_units", [None])[0] or "cm")
                if num is not None:
                    if "WEIGHT" in aid:
                        num = _to_kg(num, unit); unit = "kg"
                    elif aid.endswith(("LENGTH", "WIDTH", "HEIGHT")):
                        num = _to_cm(num, unit); unit = "cm"
                    matched[aid] = {"value_struct": {"number": float(num), "unit": unit}}
            else:
                matched[aid] = {"value_name": str(val)}
        else:
            missing.append(aid)

    # si faltan y hay IA → aprender equivalencias y reintentar
    if missing and client and not SKIP_EQ_AI:
        print(f"🤖 Buscando equivalencias IA para {len(missing)} atributos…")
        new_eq = ask_gpt_equivalences(cat_id, missing, amazon_json, cache_eq)
        
        if new_eq:
            save_equivalences(cat_id, new_eq)
            print(f"💾 Nuevas equivalencias guardadas para {cat_id}: {len(new_eq)}")

        # 🔹 Incluir equivalencias parciales ya detectadas en cache
        for aid in missing:
            if aid in cache_eq and aid not in matched:
                val = _find_in_flat(flat, cache_eq[aid])
                if val and not is_suspicious_value(val):
                    matched[aid] = {"value_name": str(val)}

        for aid in missing:
            val = _find_in_flat(flat, (cache_eq.get(aid) or []))
            if not val and new_eq.get(aid):
                val = _find_in_flat(flat, new_eq[aid])
            if not val:
                continue  # sigue si no hay valor

            meta = schema.get(aid, {})
            vtype = meta.get("value_type")

            if vtype == "list":
                lower = str(val).lower()
                vid = meta.get("values", {}).get(lower)
                if vid:
                    matched[aid] = {"value_id": vid, "value_name": str(val)}
                else:
                    matched[aid] = {"value_name": str(val)}

            elif vtype == "number_unit":   # 👈 este bloque era el que faltaba
                num = extract_number(val)
                u = re.search(r"(cm|mm|kg|g|m|in|lb|oz)", str(val).lower())
                unit = u.group(1) if u else (meta.get("allowed_units", [None])[0] or "cm")
                if num is not None:
                    if "WEIGHT" in aid:
                        num = _to_kg(num, unit); unit = "kg"
                    elif aid.endswith(("LENGTH", "WIDTH", "HEIGHT")):
                        num = _to_cm(num, unit); unit = "cm"
                    matched[aid] = {"value_struct": {"number": float(num), "unit": unit}}

            else:
                matched[aid] = {"value_name": str(val)}

    # 🔄 Recalcular después de aplicar equivalencias nuevas
    if missing and client:
        total_filled = len(matched)
        total_schema = len(schema)
        progress = round(total_filled / total_schema * 100, 1) if total_schema else 0
        filled_blocks = int(progress // 10)
        bar = "🟩" * filled_blocks + "⬜" * (10 - filled_blocks)
        print(f"📊 Mapeo actualizado: {bar} {total_filled}/{total_schema} ({progress}%)")

    # ✅ Fusionar todas las características IA como atributos adicionales
    for block in (main_ch + second_ch):
        if not isinstance(block, dict):
            continue
        aid = block.get("id") or block.get("name")
        val = block.get("value_name") or block.get("value")
        if not aid or not val:
            continue

        aid = re.sub(r"[^A-Za-z0-9_]", "_", aid.upper()).strip("_")  # normalizar ID

        # Solo agregar si no existe ya
        if aid not in matched:
            matched[aid] = {"value_name": str(val)}


        # Ahora que tenemos todo, volver a generar descripción usando el mini_ml completo
    desc_es = ai_desc_es(datos_desc, mini_ml={
        "brand": brand,
        "model": model,
        "gtins": gtins,
        "package": pkg,
        "category_name": cat_name,
        "category_id": cat_id,
        "main_characteristics": main_ch,
        "second_characteristics": second_ch
})

    # salida mini-ML (lo que MainGlobal puede “chupar” sin tokens)
    return {
        "asin": asin,
        "brand": brand,
        "model": model,
        "category_id": cat_id,
        "category_name": cat_name,
        "category_similarity": round(sim, 3),
        "title_ai": title_es,
        "description_ai": desc_es,
        "package": pkg,
        "price": price,
        "gtins": gtins,
        "images": images,
        "attributes_mapped": matched,           # atributos listos si los querés usar
        "main_characteristics": main_ch,        # bloque para ficha
        "second_characteristics": second_ch     # bloque para ficha
    }

# ---------- 11) CLI ----------
def main():
    if len(sys.argv) < 2:
        print("Uso: python3 transform_mapper_new_v4.py <ruta_json_amazon>")
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        for base in ["outputs/json", "outputs"]:
            candidate = os.path.join(base, os.path.basename(path))
            if os.path.exists(candidate):
                path = candidate
                break
    if not os.path.exists(path):
        print(f"❌ No se encontró el archivo: {path}")
        sys.exit(1)

    amazon_json = load_json_file(path)
    out = build_mini_ml(amazon_json)

    out_dir = "storage/logs/publish_ready"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{out['asin'] or 'NOASIN'}_mini_ml.json")
    save_json_file(out_path, out)

    print(f"✅ Guardado: {out_path}")
    # Mostrar un resumen útil
    total_attrs = len(out.get("attributes_mapped", {}))
    schema_path = f"resources/schemas/{out['category_id']}.json"
    schema_total = 0
    if os.path.exists(schema_path):
        try:
            schema_total = len(json.load(open(schema_path, "r", encoding="utf-8")))
        except:
            pass

    print(json.dumps({
        "asin": out["asin"],
        "category": f"{out['category_name']} ({out['category_id']})",
        "brand": out["brand"], "model": out["model"],
        "title_ai": out["title_ai"],
        "pkg": out["package"], "price": out["price"],
        "gtins": out["gtins"][:2], "images_count": len(out["images"]),
        "main_char_count": len(out["main_characteristics"]),
        "second_char_count": len(out["second_characteristics"]),
        "attrs_mapped": f"{total_attrs}/{schema_total}" if schema_total else total_attrs
    }, indent=2, ensure_ascii=False))
if __name__ == "__main__":
    main()