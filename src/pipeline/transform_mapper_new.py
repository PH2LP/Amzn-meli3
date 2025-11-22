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
from pathlib import Path

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
# Leer markup de PRICE_MARKUP (nuevo nombre) o MARKUP_PCT (legacy)
MARKUP_PCT = float(os.getenv("PRICE_MARKUP") or os.getenv("MARKUP_PCT", "35")) / 100.0

# Helper para quiet mode
QUIET_MODE = os.getenv('PIPELINE_QUIET_MODE') == '1'
def qprint(*args, **kwargs):
    """Print solo si no está en quiet mode"""
    if not QUIET_MODE:
        print(*args, **kwargs)

from openai import OpenAI
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Category matcher V2 (embeddings + IA)
try:
    from src.pipeline.category_matcher_v2 import CategoryMatcherV2
except ModuleNotFoundError:
    from category_matcher_v2 import CategoryMatcherV2

# Singleton de CategoryMatcherV2 (para no inicializar múltiples veces)
_category_matcher_v2_instance = None

def get_category_matcher():
    """Retorna instancia singleton de CategoryMatcherV2"""
    global _category_matcher_v2_instance
    if _category_matcher_v2_instance is None:
        qprint("🚀 Inicializando CategoryMatcherV2...")
        _category_matcher_v2_instance = CategoryMatcherV2()
    return _category_matcher_v2_instance

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
    qprint(f"💾 Equivalencias guardadas → {path}")

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
    # Para peso, buscar en item_package_weight (no dimensions)
    # Para dimensiones, buscar en item_package_dimensions
    if kind == "weight":
        unit_keys = [
            "attributes.item_package_weight[0].unit",
            "item_package_weight.unit",
            "attributes.item_weight[0].unit",
            "item_weight.unit",
            f"{kind}.unit"
        ]
    else:
        unit_keys = [
            f"attributes.item_package_dimensions[0].{kind}.unit",
            f"item_package_dimensions.{kind}.unit",
            f"package_dimensions.{kind}.unit",
            f"{kind}.unit"
        ]

    for unit_key in unit_keys:
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
    # Primero buscar en prime_pricing (agregado por main2.py)
    if 'prime_pricing' in amazon_json and 'price' in amazon_json['prime_pricing']:
        price = amazon_json['prime_pricing']['price']
        if price and price > 0:
            return round(float(price), 2)

    # Si no hay prime_pricing, buscar en el JSON de catálogo (fallback)
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

    # ⚠️ CRÍTICO: Sin precio válido - Este caso NO debería ocurrir en producción
    # main2.py rechaza productos sin prime_pricing antes de llegar aquí
    print(f"❌ ERROR CRÍTICO: No se encontró precio válido para el producto")
    print(f"   Este producto debió ser rechazado en DownloadPhase (main2.py)")
    print(f"   Usando fallback $10 para evitar crash, pero REVISAR")
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
    1. costo_total = precio_base + tax + 3pl_fee (lo que el seller paga)
    2. net_proceeds = costo_total * (1 + markup) (lo que el seller quiere ganar)

    ML se encarga automáticamente de:
    - Agregar comisiones
    - Agregar shipping costs
    - Calcular el precio final que ve el comprador

    TAX_EXEMPT: Si es True, NO se suma el tax al costo (para sellers con excepción de impuestos)
    """
    # Costo del 3PL (almacenamiento y fulfillment) - configurable en .env
    THREE_PL_FEE = float(os.getenv("THREE_PL_FEE", "4.0"))

    # Verificar si el seller tiene excepción de tax
    TAX_EXEMPT = os.getenv("TAX_EXEMPT", "false").lower() == "true"

    # Si hay excepción de tax, no sumar el tax al costo
    tax_to_add = 0.0 if TAX_EXEMPT else tax

    cost = round(base + tax_to_add + THREE_PL_FEE, 2)
    net_proceeds = round(cost * (1.0 + MARKUP_PCT), 2)
    return {
        "base_usd": round(base, 2),
        "tax_usd": round(tax, 2),
        "tax_exempt": TAX_EXEMPT,
        "3pl_fee_usd": THREE_PL_FEE,
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

def _get_brand_protection_level(brand_name, product_title=""):
    """
    Determina el nivel de protección que requiere una marca.

    Returns:
        str: Nivel de protección
            - "safe": Marca no requiere protección especial (usar normalmente)
            - "original": Marca conocida - verificar si es producto original
            - "always_compatible": SIEMPRE usar lenguaje de compatibilidad (lujo/entretenimiento)
    """
    if not brand_name:
        return "safe"

    # Cargar clasificación de marcas
    try:
        brands_path = "config/protected_brands.json"
        if os.path.exists(brands_path):
            with open(brands_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                # Marcas de lujo - SIEMPRE compatibilidad (riesgo MUY alto)
                luxury = [b.lower() for b in data.get("luxury_brands", [])]
                if brand_name.lower() in luxury:
                    return "always_compatible"

                # Marcas de entretenimiento - SIEMPRE compatibilidad (licencias estrictas)
                entertainment = [b.lower() for b in data.get("entertainment_brands", [])]
                if brand_name.lower() in entertainment:
                    return "always_compatible"

                # Marcas de moda - preferir compatibilidad
                fashion = [b.lower() for b in data.get("fashion_brands", [])]
                if brand_name.lower() in fashion:
                    return "always_compatible"

                # Marcas conocidas - evaluar si es original
                known = [b.lower() for b in data.get("known_major_brands", [])]
                if brand_name.lower() in known:
                    return "original"
        else:
            # Fallback básico
            known = ["xbox", "playstation", "sony", "nintendo", "apple", "iphone",
                    "ipad", "macbook", "airpods", "samsung", "galaxy", "microsoft",
                    "lego", "canon", "nikon", "logitech", "razer"]
            if brand_name.lower() in known:
                return "original"
    except:
        pass

    return "safe"


def _detect_target_brand(product_title, bullets):
    """
    Detecta si el producto es un accesorio PARA una marca conocida (Xbox, PlayStation, Nintendo, Apple, etc.)
    aunque la marca del fabricante sea genérica (PowerA, Anker, etc.)

    Returns:
        str or None: Nombre de la marca objetivo si se detecta (ej: "Xbox", "iPhone"), None si no aplica
    """
    if not product_title:
        return None

    title_lower = product_title.lower()

    # Manejar bullets que pueden ser strings o dicts
    bullets_list = []
    if bullets:
        for b in bullets:
            if isinstance(b, str):
                bullets_list.append(b)
            elif isinstance(b, dict):
                bullets_list.append(b.get("value", ""))

    bullets_text = " ".join(bullets_list).lower() if bullets_list else ""
    combined_text = f"{title_lower} {bullets_text}"

    # Patrones que indican "para" una marca conocida
    for_patterns = [
        " for ", " para ", "compatible with", "compatible con", "works with",
        "funciona con", "designed for", "diseñado para"
    ]

    is_accessory_for = any(pattern in combined_text for pattern in for_patterns)

    if not is_accessory_for:
        return None

    # Detectar marcas objetivo en orden de prioridad
    target_brands = {
        # Gaming consoles
        "xbox series x": "Xbox Series X/S",
        "xbox series s": "Xbox Series X/S",
        "xbox series": "Xbox Series X/S",
        "xbox one": "Xbox One",
        "xbox": "Xbox",
        "playstation 5": "PlayStation 5",
        "playstation 4": "PlayStation 4",
        "ps5": "PlayStation 5",
        "ps4": "PlayStation 4",
        "playstation": "PlayStation",
        "nintendo switch": "Nintendo Switch",
        "switch oled": "Nintendo Switch OLED",
        "nintendo": "Nintendo",

        # Apple devices
        "iphone 15": "iPhone 15",
        "iphone 14": "iPhone 14",
        "iphone 13": "iPhone 13",
        "iphone": "iPhone",
        "ipad pro": "iPad Pro",
        "ipad": "iPad",
        "macbook pro": "MacBook Pro",
        "macbook air": "MacBook Air",
        "macbook": "MacBook",
        "airpods pro": "AirPods Pro",
        "airpods": "AirPods",
        "apple watch": "Apple Watch",

        # Other major brands
        "samsung galaxy": "Samsung Galaxy",
        "galaxy s24": "Samsung Galaxy S24",
        "galaxy s23": "Samsung Galaxy S23",
        "steam deck": "Steam Deck",
        "gopro": "GoPro",
        "oculus quest": "Meta Quest",
        "meta quest": "Meta Quest"
    }

    # Buscar en orden de especificidad (más específico primero)
    for brand_key, brand_display in sorted(target_brands.items(), key=lambda x: len(x[0]), reverse=True):
        if brand_key in combined_text:
            return brand_display

    return None


def _is_original_product(brand_name, product_title, bullets):
    """
    Determina si el producto es ORIGINAL de la marca o un accesorio/compatible.

    Heurística:
    - Si el título contiene "compatible", "para", "accesorio" → NO es original
    - Si contiene palabras del producto (controlador, funda, cable, etc.) → probablemente NO es original
    - Si es un producto electrónico de la marca en el título → probablemente SÍ es original

    Returns:
        bool: True si el producto parece ser original de la marca
    """
    if not brand_name or not product_title:
        return False

    title_lower = product_title.lower()
    brand_lower = brand_name.lower()

    # ESTRATEGIA CONSERVADORA: Para evitar problemas con ML Brasil y otros mercados
    # Solo consideramos "original" si es un dispositivo PRINCIPAL de la marca
    # NUNCA consideramos accesorios como originales (incluso si dicen "oficial")
    # Esto es más seguro porque evita problemas de "distribuidor no autorizado"

    # Palabras que SIEMPRE indican accesorio (no pueden ser originales)
    always_accessory_keywords = [
        "compatible", "para", "accesorio", "accesorios", "replacement", "reemplazo",
        "genérico", "generico", "alternativo", "aftermarket", "third party",
        "funda", "case", "cover", "protector", "cable", "cargador", "charger",
        "adaptador", "adapter", "soporte", "holder", "mount", "correa", "strap",
        "repuesto", "spare", "skin", "sticker", "calcomanía",
        "cristal templado", "pantalla", "screen protector", "stylus", "lapiz", "lápiz"
    ]

    if any(keyword in title_lower for keyword in always_accessory_keywords):
        return False

    # Para gaming: verificar productos principales vs accesorios
    if brand_lower in ["xbox", "playstation", "nintendo", "sony"]:
        # Productos principales (consolas, etc.)
        main_products = [
            "console", "consola",
            # Modelos específicos de consolas
            "playstation 5", "playstation 4", "ps5", "ps4", "ps3",
            "xbox series x", "xbox series s", "xbox one",
            "nintendo switch", "switch oled"
        ]
        if any(prod in title_lower for prod in main_products):
            return True

        # Accesorios gaming (sin "oficial" ya se filtraron arriba)
        gaming_accessories = [
            "controlador", "controller", "mando", "gamepad", "joystick",
            "auriculares", "headset", "audífonos", "audifonos",
            "micrófono", "microfono", "webcam",
            "teclado", "keyboard", "ratón", "raton", "mouse",
            "batería", "bateria", "battery", "pila",
            "memoria", "memory card", "tarjeta de memoria",
            "volante", "steering wheel", "pedales"
        ]
        if any(acc in title_lower for acc in gaming_accessories):
            return False

    # Para Apple
    if brand_lower in ["apple", "iphone", "ipad", "macbook", "airpods"]:
        # Solo si es el dispositivo principal
        main_products = ["iphone", "ipad", "macbook", "airpods", "apple watch"]
        if any(prod in title_lower for prod in main_products):
            # Verificar que no sea accesorio
            if not any(acc in title_lower for acc in ["funda", "case", "cargador", "cable"]):
                return True

    # Para LEGO - sets oficiales suelen tener número de modelo de 5 dígitos
    if brand_lower == "lego":
        # Si tiene "building kit", "set", "pieces", probablemente es original
        lego_keywords = ["building kit", "set", "pieces", "piezas", "bloques"]
        if any(keyword in title_lower for keyword in lego_keywords):
            # Verificar que no sea accesorio genérico
            if not any(acc in title_lower for acc in ["compatible", "storage", "organizador", "caja"]):
                return True

    # Para marcas de electrónica (Sony, Samsung, etc.) - detectar productos principales
    electronics_brands = {
        "sony": ["wh-1000xm", "wh-ch", "wf-1000xm", "srs-", "bravia", "playstation", "alpha", "cybershot"],
        "samsung": ["galaxy s", "galaxy z", "galaxy note", "galaxy a", "galaxy tab", "qled", "the frame"],
        "bose": ["quietcomfort", "soundlink", "noise cancelling", "frames"],
        "jbl": ["flip", "charge", "xtreme", "partybox", "tune"],
        "canon": ["eos", "powershot", "pixma", "imageclass"],
        "nikon": ["d850", "z9", "z6", "coolpix"],
        "logitech": ["mx master", "mx keys", "g pro", "g502", "streamcam"],
        "razer": ["blade", "deathadder", "blackwidow", "kraken", "viper"]
    }

    if brand_lower in electronics_brands:
        model_patterns = electronics_brands[brand_lower]
        # Si el título contiene el modelo/serie del producto, probablemente es original
        if any(pattern in title_lower for pattern in model_patterns):
            # Y tiene palabras de dispositivo principal
            main_device_words = ["headphone", "speaker", "camera", "laptop", "mouse", "keyboard",
                               "monitor", "auricular", "altavoz", "cámara", "ratón", "teclado", "inalámbrico", "wireless"]
            if any(word in title_lower for word in main_device_words):
                return True

    # Para productos que explícitamente dicen ser oficiales/originales
    if any(word in title_lower for word in ["oficial", "official", "original", "authentic", "genuine"]):
        return True

    # Por defecto, asumir que NO es original (más seguro)
    return False


def _load_brand_generic_mapping():
    """Carga el mapeo de marcas a términos genéricos para CBT."""
    try:
        mapping_path = "config/brand_generic_terms.json"
        if os.path.exists(mapping_path):
            with open(mapping_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        qprint(f"⚠️ Error cargando brand_generic_terms.json: {e}")

    # Fallback básico
    return {
        "brand_to_generic_device": {
            "Nintendo": "Consola Portátil",
            "Switch": "Consola Portátil",
            "PlayStation": "Consola de Videojuegos",
            "PS5": "Consola de Videojuegos",
            "Xbox": "Consola de Videojuegos",
            "iPhone": "Smartphone",
            "iPad": "Tablet",
            "Apple": "Dispositivo"
        }
    }


def _detect_accessory_type(product_title, bullets):
    """
    Detecta el tipo de accesorio para usar el término genérico correcto.

    Returns:
        dict: {
            "type": str,  # Tipo de accesorio (charging_dock, controller, case, etc.)
            "features": dict  # Características detectadas (ports, power, material, etc.)
        }
    """
    title_lower = product_title.lower() if product_title else ""
    bullets_text = " ".join(bullets).lower() if bullets else ""
    combined = f"{title_lower} {bullets_text}"

    mapping = _load_brand_generic_mapping()
    patterns = mapping.get("accessory_patterns", {})

    # Detectar tipo de accesorio
    for acc_type, pattern_info in patterns.items():
        keywords = pattern_info.get("keywords", [])
        if any(kw in combined for kw in keywords):
            # Extraer características relevantes
            features = {}

            # Detectar número de puertos
            import re
            port_match = re.search(r'(\d+)[\s-]?(port|puerto)', combined)
            if port_match:
                features["ports"] = f"{port_match.group(1)} Puertos"

            # Detectar potencia de carga
            power_match = re.search(r'(\d+)w\b', combined)
            if power_match:
                features["power"] = f"{power_match.group(1)}W"

            # Detectar longitud de cable
            length_match = re.search(r'(\d+\.?\d*)\s*(m|metro|ft|feet)', combined)
            if length_match:
                length = length_match.group(1)
                unit = "m" if "m" in length_match.group(2) or "metro" in length_match.group(2) else "ft"
                features["length"] = f"{length}{unit}"

            # Detectar material
            materials = {
                "silicona": "Silicona",
                "silicone": "Silicona",
                "tpu": "TPU",
                "leather": "Cuero",
                "piel": "Cuero",
                "metal": "Metal",
                "aluminum": "Aluminio",
                "aluminio": "Aluminio",
                "plastic": "Plástico",
                "plastico": "Plástico"
            }
            for mat_key, mat_display in materials.items():
                if mat_key in combined:
                    features["material"] = mat_display
                    break

            # Detectar características especiales
            if "wireless" in combined or "inalámbrico" in combined or "inalambrico" in combined:
                features["wireless"] = "Inalámbrico"

            if "bluetooth" in combined:
                features["bluetooth"] = "Bluetooth"

            if "magnetic" in combined or "magnético" in combined or "magnetico" in combined:
                features["magnetic"] = "Magnético"

            if "360" in combined:
                features["degrees"] = "360"

            if "rechargeable" in combined or "recargable" in combined:
                features["rechargeable"] = "Recargable"

            return {
                "type": acc_type,
                "generic_term": pattern_info.get("generic_term", "Accesorio"),
                "features": features
            }

    # Si no se detecta tipo específico, retornar genérico
    return {
        "type": "unknown",
        "generic_term": "Accesorio",
        "features": {}
    }


def _remove_brand_from_title_cbt(title, protected_brands):
    """
    Elimina COMPLETAMENTE cualquier mención de marcas protegidas del título.

    Esta función es CRÍTICA para CBT - las marcas NO deben aparecer en títulos
    de productos que no son originales.

    Args:
        title: Título a limpiar
        protected_brands: Lista de marcas protegidas a remover

    Returns:
        str: Título sin marcas protegidas
    """
    if not title:
        return ""

    title_clean = title

    # Cargar frases prohibidas
    mapping = _load_brand_generic_mapping()
    forbidden_phrases = mapping.get("strict_cbt_rules", {}).get("forbidden_title_phrases", [])

    # Eliminar frases prohibidas completas primero
    for phrase in forbidden_phrases:
        # Case insensitive replace
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        title_clean = pattern.sub("", title_clean)

    # Eliminar marcas individuales
    for brand in protected_brands:
        if not brand:
            continue

        # Crear patrón que capture la marca con límites de palabra
        pattern = re.compile(r'\b' + re.escape(brand) + r'\b', re.IGNORECASE)
        title_clean = pattern.sub("", title_clean)

    # Limpiar espacios múltiples y guiones sueltos
    title_clean = re.sub(r'\s+', ' ', title_clean)
    title_clean = re.sub(r'\s*-\s*-\s*', ' - ', title_clean)  # Dobles guiones
    title_clean = re.sub(r'^\s*-\s*', '', title_clean)  # Guion al inicio
    title_clean = re.sub(r'\s*-\s*$', '', title_clean)  # Guion al final
    title_clean = title_clean.strip()

    return title_clean


def _build_generic_title_cbt(base_title, brand, model, bullets, detected_brands, max_chars=60):
    """
    Construye un título genérico siguiendo las reglas ESTRICTAS de CBT.

    NO menciona marcas protegidas en el título.
    Usa términos genéricos descriptivos.

    Args:
        base_title: Título original de Amazon
        brand: Marca del fabricante
        model: Modelo del producto
        bullets: Bullet points del producto
        detected_brands: Lista de marcas protegidas detectadas
        max_chars: Máximo de caracteres

    Returns:
        str: Título genérico optimizado para CBT
    """
    # Detectar tipo de accesorio y características
    accessory_info = _detect_accessory_type(base_title, bullets)
    generic_term = accessory_info["generic_term"]
    features = accessory_info["features"]

    # Construir título base con el término genérico
    title_parts = [generic_term]
    added_terms = {generic_term.lower()}  # Track para evitar duplicados

    # Función auxiliar para agregar sin duplicar
    def add_if_unique(term):
        term_lower = term.lower()
        # Evitar duplicados completos o palabras que ya están en el título
        if term_lower not in added_terms:
            # Verificar si alguna palabra clave ya existe
            words_in_term = set(term_lower.split())
            if not words_in_term.intersection(added_terms):
                title_parts.append(term)
                added_terms.add(term_lower)
                added_terms.update(words_in_term)
                return True
        return False

    # Agregar características en orden de importancia
    # Verificar que el término genérico no incluya ya "Inalámbrico" o "Bluetooth"
    if "wireless" in features and "inalámbrico" not in generic_term.lower():
        add_if_unique(features["wireless"])

    if "bluetooth" in features and "bluetooth" not in generic_term.lower():
        add_if_unique(features["bluetooth"])

    if "power" in features:
        add_if_unique(features["power"])

    if "ports" in features:
        add_if_unique(features["ports"])

    if "length" in features:
        add_if_unique(features["length"])

    if "material" in features:
        add_if_unique(features["material"])

    if "magnetic" in features:
        add_if_unique(features["magnetic"])

    if "degrees" in features:
        add_if_unique(features["degrees"] + "°")

    if "rechargeable" in features:
        add_if_unique(features["rechargeable"])

    # Agregar "Genérico" o "Universal" al final
    if accessory_info["type"] != "unknown":
        add_if_unique("Universal")

    # Construir título final
    title = " ".join(title_parts)

    # Si es muy corto, agregar información del título original (sin marcas)
    # Pero traducida al español
    if len(title) < 30 and base_title:
        clean_base = _remove_brand_from_title_cbt(base_title, detected_brands + [brand])
        if clean_base:
            # Diccionario de traducción de palabras comunes en inglés
            translations = {
                "controller": "Control",
                "controllers": "Controles",
                "charging": "Carga",
                "dock": "Base",
                "station": "Estación",
                "charger": "Cargador",
                "cable": "Cable",
                "adapter": "Adaptador",
                "case": "Funda",
                "cover": "Protector",
                "screen": "Pantalla",
                "protector": "Protector",
                "mount": "Soporte",
                "stand": "Base",
                "holder": "Soporte",
                "wireless": "Inalámbrico",
                "bluetooth": "Bluetooth",
                "fast": "Rápida",
                "quick": "Rápida",
                "magnetic": "Magnético",
                "portable": "Portátil",
                "pack": "Pack",
                "set": "Set",
                "led": "LED",
                "oled": "OLED",
                "usb": "USB",
                "type": "Tipo",
                "port": "Puerto",
                "ports": "Puertos",
                "for": "para",
                "with": "con",
                "and": "y",
                "joycon": "",  # Eliminar completamente
                "joycons": "",
                "joy-con": "",
                "joy-cons": ""
            }

            # Extraer palabras relevantes del título limpio y traducirlas
            words = clean_base.split()
            for word in words[:8]:  # Revisar hasta 8 palabras
                word_clean = word.lower().strip(',:;-')
                # Traducir si está en el diccionario
                word_spanish = translations.get(word_clean, word)
                word_spanish_lower = word_spanish.lower()

                # Solo agregar si no está ya en el título y es relevante (más de 2 chars)
                if len(word_spanish_lower) > 2 and word_spanish_lower not in title.lower():
                    # Verificar que agregando esta palabra no excedemos max_chars
                    test_title = f"{title} {word_spanish}"
                    if len(test_title) <= max_chars:
                        title = test_title
                        added_terms.add(word_spanish_lower)
                    else:
                        break

    # Truncar si es necesario
    if len(title) > max_chars:
        title = title[:max_chars].rsplit(' ', 1)[0].rstrip(',-')

    return title.strip()


def ai_title_es(base_title, brand, model, bullets, max_chars=60):
    """
    Genera títulos optimizados para MercadoLibre Global Selling.
    Diseñado con mejores prácticas de copywriting y SEO de marketplace.
    Sistema inteligente que decide cuándo incluir el número de modelo.
    PROTECCIÓN INTELIGENTE: Detecta si el producto es original o accesorio.
    """
    if not client:
        return _smart_truncate(base_title or "Producto", max_chars)

    # Convertir bullets a lista si es necesario
    if isinstance(bullets, str):
        bullets = [bullets]
    elif not isinstance(bullets, list):
        bullets = []

    # ============================================================
    # REGLAS CBT ESTRICTAS: Para accesorios de marcas protegidas
    # NO usar la marca en el título - usar términos genéricos
    # ============================================================

    # Cargar lista de marcas protegidas del blacklist
    protected_brands = []
    try:
        blacklist_path = "config/brand_blacklist.json"
        if os.path.exists(blacklist_path):
            with open(blacklist_path, "r", encoding="utf-8") as f:
                blacklist_data = json.load(f)
                protected_brands = [b.lower() for b in blacklist_data.get("blacklisted_brands", [])]
    except:
        pass

    # Detectar si es un accesorio para marca protegida
    target_brand = _detect_target_brand(base_title, bullets)
    brand_lower = brand.lower() if brand else ""
    target_brand_lower = target_brand.lower() if target_brand else ""

    # Caso 1: La marca del producto o la marca objetivo está en la lista de protegidas
    # Y el producto es un accesorio (no original)

    # Verificar si la marca del fabricante o la marca objetivo están protegidas
    is_brand_protected = False

    # Check si la marca del fabricante está en la lista
    if brand_lower in protected_brands:
        is_brand_protected = True

    # Check si la marca objetivo (o alguna palabra de ella) está en la lista
    if target_brand:
        # Verificar si alguna palabra de target_brand está en protected_brands
        target_words = target_brand_lower.split()
        for word in target_words:
            if word in protected_brands:
                is_brand_protected = True
                break

    # Verificar si es accesorio (no producto original)
    is_accessory = not _is_original_product(brand, base_title, bullets)

    if is_brand_protected and is_accessory:
        # MODO CBT ESTRICTO: Usar IA pero sin mencionar marcas protegidas
        qprint(f"🛡️ CBT STRICT MODE: Accesorio para marca protegida detectado ({target_brand or brand})")
        qprint(f"   Generando título genérico sin mencionar la marca...")

        # NO usar la función _build_generic_title_cbt() porque genera títulos raros
        # En su lugar, usar la IA normal pero reemplazando la marca por "Genérica"
        # y limpiando el título base de marcas protegidas

        # Detectar todas las marcas que necesitamos eliminar
        brands_to_remove = [brand]
        if target_brand:
            brands_to_remove.append(target_brand)
            # También agregar variantes de la marca
            if "nintendo" in target_brand_lower:
                brands_to_remove.extend(["Nintendo", "Switch", "Nintendo Switch", "JoyCon", "Joy-Con"])
            elif "playstation" in target_brand_lower or "ps5" in target_brand_lower:
                brands_to_remove.extend(["PlayStation", "PS5", "PS4", "Sony"])
            elif "xbox" in target_brand_lower:
                brands_to_remove.extend(["Xbox", "Microsoft"])
            elif "iphone" in target_brand_lower or "apple" in target_brand_lower:
                brands_to_remove.extend(["Apple", "iPhone", "iPad", "AirPods"])

        # Limpiar el título base eliminando marcas
        clean_title = _remove_brand_from_title_cbt(base_title, brands_to_remove)

        # Llamar a la IA con marca "Genérica" para que genere un título natural
        # sin mencionar marcas protegidas
        qprint(f"   Título limpio: {clean_title}")
        # Continuar con el flujo normal pero sin brand_instruction especial
        # La IA generará un título genérico basado en el título limpio
        brand = "Genérica"  # Reemplazar marca por "Genérica"

    # ============================================================
    # Casos regulares: Productos originales o marcas no protegidas
    # Usar el sistema de IA normal
    # ============================================================

    # Determinar nivel de protección de la marca
    protection_level = _get_brand_protection_level(brand, base_title)

    # Determinar si el modelo es relevante para el comprador
    model_is_relevant = _is_model_searchable(brand, model, base_title)

    # Prompt diseñado por experto en copywriting MercadoLibre
    brand_instruction = ""

    if protection_level == "always_compatible":
        # Marcas de lujo/entretenimiento - usar descripción genérica
        brand_instruction = f"""
⚠️ CRÍTICO - MARCA DE ALTO RIESGO:
La marca "{brand}" requiere MÁXIMA PRECAUCIÓN (lujo/entretenimiento/moda).

REGLAS OBLIGATORIAS:
1. SIEMPRE usar lenguaje descriptivo genérico
2. NUNCA usar "{brand}" en el título
3. Describir el producto por sus características, no por la marca

EJEMPLOS CORRECTOS:
✅ "Reloj Cronógrafo Estilo Deportivo Acero Inoxidable"
✅ "Bolso Tote Piel Sintética Negro Diseño Clásico"
✅ "Figura Coleccionable Superhéroe 15cm Articulada"
"""

    elif protection_level == "original":
        # Marcas conocidas - verificar si es original
        is_original = _is_original_product(brand, base_title, bullets)

        if is_original:
            # Producto ORIGINAL - usar marca normalmente
            brand_instruction = f"""
✅ PRODUCTO ORIGINAL DETECTADO:
El producto parece ser ORIGINAL de "{brand}".

REGLAS:
1. Usar la marca normalmente al inicio del título
2. Enfatizar que es ORIGINAL/NUEVO
3. Incluir modelo si es relevante
4. NO usar palabras como "compatible" (confunde al comprador)

EJEMPLOS CORRECTOS:
✅ "{brand} Lego Icons 10314 Floristería 2870 Piezas Adultos"
✅ "{brand} WH-1000XM5 Audífonos Noise Cancelling Negro"
✅ "{brand} Series X Console 1TB Negro Nueva Generación"
"""
        else:
            # Accesorio - esto debería haberse capturado arriba, pero por seguridad
            brand_instruction = f"""
⚠️ ACCESORIO DETECTADO - USAR TÉRMINOS GENÉRICOS
Este es un ACCESORIO, NO es un producto original.
REGLAS OBLIGATORIAS:
1. NO mencionar la marca objetivo en el título (ejemplo: NO poner "Nintendo", "PlayStation", "Apple")
2. Usar términos genéricos descriptivos (Cargador, Cable, Funda, Control, Base, etc.)
3. Describir características físicas (color, material, tamaño, conectores)
4. La compatibilidad con marcas se mencionará SOLO en la descripción, NUNCA en el título

EJEMPLOS CORRECTOS:
✅ "Base Cargadora Magnética USB-C Negro Universal"
✅ "Cable HDMI 2m Alta Velocidad 4K Trenzado"
✅ "Control Inalámbrico Bluetooth Negro Ergonómico"
✅ "Funda Protectora Silicona Transparente Antigolpes"

EJEMPLOS INCORRECTOS (PROHIBIDOS):
❌ "Charging Dock for Nintendo Switch"
❌ "Cable para iPhone"
❌ "Control tipo Xbox"
❌ "Funda compatible con PlayStation"
"""

    else:
        # Marca segura - verificar si es accesorio de marca conocida
        if target_brand:
            # Esto también debería haberse capturado arriba
            brand_instruction = f"""
⚠️ ACCESORIO DETECTADO - USAR TÉRMINOS GENÉRICOS
Este es un ACCESORIO, NO es un producto original.
REGLAS OBLIGATORIAS:
1. NO mencionar la marca objetivo en el título (ejemplo: NO poner "{target_brand}")
2. Usar términos genéricos descriptivos (Cargador, Cable, Funda, Control, Base, etc.)
3. Describir características físicas (color, material, tamaño, conectores)
4. La compatibilidad con "{target_brand}" se mencionará SOLO en la descripción, NUNCA en el título

EJEMPLOS CORRECTOS:
✅ "Base Cargadora Magnética USB-C Negro Universal"
✅ "Cable USB 2m Carga Rápida Trenzado Nylon"
✅ "Control Inalámbrico Bluetooth Negro Ergonómico"

EJEMPLOS INCORRECTOS (PROHIBIDOS):
❌ "Charging Dock for {target_brand}"
❌ "Cable para {target_brand}"
❌ "Control compatible {target_brand}"
"""
        else:
            # Marca segura normal - usar normalmente
            brand_instruction = f"""
Marca: {brand}
Esta marca es segura. Usa la marca normalmente al inicio del título.
"""

    model_instruction = ""
    if model_is_relevant and model:
        model_instruction = f"""
IMPORTANTE: El modelo "{model}" es un identificador clave que los compradores buscan.
DEBES incluirlo en el título de forma natural."""
    else:
        model_instruction = f"""
IMPORTANTE: El modelo "{model}" es un código técnico interno (SKU/part number).
NO lo incluyas en el título. Prioriza atributos visuales y funcionales."""

    prompt = f"""Eres un experto copywriter de MercadoLibre Global Selling. Crea un título de producto optimizado para conversión y búsqueda.

{brand_instruction}

REGLAS ESTRICTAS:
1. Máximo {max_chars} caracteres (CRÍTICO: los primeros 45 son los más importantes)
2. Estructura para productos ORIGINALES: Marca + [Modelo] + Tipo + Atributos + Beneficio
   Estructura para ACCESORIOS: Tipo de Producto + Características + Color + Material
3. SIEMPRE incluye: color, tamaño, material, género (hombre/mujer), característica principal
4. Lenguaje: Natural, comercial, orientado al beneficio del comprador
5. Sin emojis, sin HTML, sin comillas, sin puntos finales
6. Español LATAM neutro y profesional
7. ⚠️ CRÍTICO - PROHIBIDO ABSOLUTO (Violaciones causan suspensión ML):
   - NUNCA incluir links, URLs, sitios web, dominios (.com, .net, etc.)
   - NUNCA incluir emails (usuario@dominio.com)
   - NUNCA incluir teléfonos (+54, 011, WhatsApp, etc.)
   - NUNCA incluir referencias a Amazon, tiendas externas, redes sociales
   - NUNCA incluir palabras como: "visita", "contacta", "llama", "escribe"
   - NUNCA usar palabras prohibidas para marcas: "tipo", "similar", "igual", "estilo" (solo en contexto de marca)
   - Ejemplo prohibido: "Controlador tipo Xbox", "Similar a Apple", "Igual que Samsung"
8. ⚠️ CRÍTICO PARA ACCESORIOS - NO MENCIONAR MARCAS EN EL TÍTULO:
   - Si el producto es un accesorio (cable, cargador, funda, control genérico, base, etc.)
   - NO menciones marcas conocidas como Nintendo, PlayStation, Xbox, Apple, Samsung, etc.
   - Usa términos genéricos descriptivos solamente
   - La compatibilidad se menciona SOLO en la descripción
{model_instruction}

DATOS DEL PRODUCTO:
Título original: {base_title}
Marca: {brand}
Modelo: {model}
Características: {bullets[:500] if bullets else "N/A"}

EJEMPLOS DE BUENOS TÍTULOS CON MODELO RELEVANTE:
- "LEGO Icons 10314 Floristería Tienda 2870 Piezas Adultos"
- "iPhone 15 Pro Max 256GB Titanio Azul Nuevo Sellado"
- "Canon EOS R5 Cámara Mirrorless 45MP 8K Video Profesional"
- "PlayStation 5 Slim 1TB Digital Console Nueva Generación"

EJEMPLOS DE BUENOS TÍTULOS SIN MODELO (cuando es código técnico):
- "Reloj Casio Hombre Dorado Digital Resistente Agua 100m"
- "Audífonos Sony Bluetooth Negro Cancelación Ruido 30h"
- "Perfume Chanel N°5 Mujer 100ml Eau de Parfum Original"
- "Mochila North Face 40L Impermeable Senderismo Camping"

EJEMPLOS CORRECTOS PARA ACCESORIOS (sin mencionar marca compatible):
- "Base Cargadora Magnética USB-C Negro Doble Posición"
- "Cable USB 2m Carga Rápida 3A Trenzado Nylon Negro"
- "Control Inalámbrico Bluetooth Ergonómico Negro Vibración"
- "Funda Protectora Silicona Transparente Antigolpes"
- "Cargador Pared 20W USB-C Compacto Carga Rápida"

EJEMPLOS INCORRECTOS PARA ACCESORIOS (NUNCA hacer esto):
- "Base Cargadora para Nintendo Switch" ❌
- "Cable compatible iPhone" ❌
- "Control tipo Xbox" ❌
- "Funda PlayStation 5" ❌

RESPONDE ÚNICAMENTE CON EL TÍTULO OPTIMIZADO (sin explicaciones, sin comillas):"""

    try:
        r = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.3,  # Más creatividad para copywriting
            messages=[
                {"role": "system", "content": "Eres un experto copywriter de MercadoLibre. Responde SOLO con el título final optimizado."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
        )
        t = (r.choices[0].message.content or "").strip().replace("\n", " ").strip('"').strip("'")

        # ⚠️ CRÍTICO: Eliminar cualquier link o URL (MercadoLibre los prohíbe)
        t = _remove_links_and_urls(t)

        # Truncado inteligente por palabras
        return _smart_truncate(t, max_chars) if t else _smart_truncate(base_title or "Producto", max_chars)
    except Exception as e:
        print(f"⚠️ Error generando título: {e}")
        return _smart_truncate(base_title or "Producto", max_chars)


def _is_model_searchable(brand, model, title):
    """
    Determina si el número de modelo es un identificador que los compradores buscan
    o si es solo un código técnico interno (SKU/part number).

    Returns:
        bool: True si el modelo debe ir en el título, False si no
    """
    if not model:
        return False

    model_upper = str(model).upper()
    brand_upper = str(brand).upper() if brand else ""
    title_upper = str(title).upper() if title else ""

    # ✅ CASOS DONDE EL MODELO SÍ ES IMPORTANTE (debe ir en título)

    # 1. LEGO - Los números son clave (ej: 10314, 21348)
    if "LEGO" in brand_upper and model_upper.isdigit() and len(model_upper) >= 4:
        return True

    # 2. Apple - Modelos son el producto (iPhone 15, MacBook Pro M3, iPad Air)
    if "APPLE" in brand_upper or any(x in title_upper for x in ["IPHONE", "IPAD", "MACBOOK", "AIRPODS"]):
        # Modelos tipo: "15 Pro Max", "M3", "Air 5"
        if any(char.isdigit() for char in model_upper):
            return True

    # 3. Gaming (PlayStation, Xbox, Nintendo) - Incluye modelos muy cortos como "5", "X", "OLED"
    gaming_keywords = ["PLAYSTATION", "PS5", "PS4", "XBOX", "NINTENDO", "SWITCH"]
    if any(kw in brand_upper or kw in title_upper for kw in gaming_keywords):
        # Para gaming, incluso números cortos son válidos (PS "5", Xbox "X")
        return True

    # 4. Cámaras profesionales (Canon EOS R5, Sony A7, Nikon Z8)
    camera_brands = ["CANON", "NIKON", "SONY", "FUJIFILM", "PANASONIC"]
    camera_keywords = ["EOS", "ALPHA", "A7", "Z8", "Z9", "R5", "R6"]
    if brand_upper in camera_brands or any(kw in model_upper for kw in camera_keywords):
        if len(model_upper) <= 10 and not model_upper.startswith("B0"):  # No es ASIN
            return True

    # 5. Laptops/Tablets - Modelos específicos
    if any(x in title_upper for x in ["LAPTOP", "NOTEBOOK", "TABLET", "CHROMEBOOK"]):
        # Modelos tipo: "M3", "i7-13700K", "Ryzen 9"
        if any(x in model_upper for x in ["M1", "M2", "M3", "I5", "I7", "I9", "RYZEN"]):
            return True

    # 6. Smartphones (Samsung Galaxy S24, Xiaomi 13 Pro)
    phone_keywords = ["GALAXY", "REDMI", "POCO", "ONEPLUS", "PIXEL"]
    if any(kw in title_upper for kw in phone_keywords):
        if any(char.isdigit() for char in model_upper) and len(model_upper) <= 15:
            return True

    # 7. Consolas de juego portátiles (Steam Deck, ROG Ally)
    if any(x in title_upper for x in ["STEAM DECK", "ROG ALLY", "SWITCH OLED"]):
        return True

    # 8. Modelos cortos y alfanuméricos reconocibles (no códigos técnicos)
    # Ejemplo: "MX Master 3", "K380", "AirPods Pro 2"
    if len(model_upper) <= 8 and model_upper[0].isalpha():
        # Si el modelo aparece en el título original, probablemente sea relevante
        if model_upper in title_upper:
            return True

    # ❌ CASOS DONDE EL MODELO NO ES IMPORTANTE (códigos técnicos)

    # 1. ASINs de Amazon (B0XXXXX)
    if model_upper.startswith("B0") and len(model_upper) == 10:
        return False

    # 2. SKUs largos con muchos caracteres especiales
    if len(model_upper) > 15 or model_upper.count("-") > 2 or model_upper.count("_") > 1:
        return False

    # 3. Códigos que parecen part numbers (AE/1000GNGN, XT-2024-B, etc)
    if "/" in model_upper or model_upper.count("-") >= 2:
        return False

    # 4. UPCs, EANs (códigos numéricos muy largos)
    if model_upper.isdigit() and len(model_upper) >= 10:
        return False

    # Por defecto: si es corto y simple, podría ser relevante
    # Si es largo o complejo, probablemente sea código técnico
    return len(model_upper) <= 10 and not any(c in model_upper for c in ["_", "/"])


def _remove_links_and_urls(text):
    """
    Elimina TODOS los links, URLs, emails, teléfonos y referencias prohibidas del texto.
    MercadoLibre prohíbe en títulos y descripciones:
    - Links y URLs de cualquier tipo
    - Emails y teléfonos
    - Referencias a sitios externos
    - Información de contacto (WhatsApp, Telegram, etc.)

    Elimina:
    - URLs completas: http://example.com, https://amazon.com
    - URLs sin protocolo: www.example.com, amazon.com
    - Dominios: .com, .net, .org, etc.
    - Emails: usuario@dominio.com
    - Teléfonos: +54 11 1234-5678, (011) 1234-5678
    - Palabras como: "link", "url", "website", "email", "teléfono", "WhatsApp"
    - Referencias a Amazon: "amazon.com", "amzn.to"
    """
    if not text:
        return text

    import re

    # 1. Eliminar URLs completas con protocolo
    text = re.sub(r'https?://[^\s]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'ftp://[^\s]+', '', text, flags=re.IGNORECASE)

    # 2. Eliminar URLs sin protocolo (www.example.com)
    text = re.sub(r'www\.[^\s]+', '', text, flags=re.IGNORECASE)

    # 3. Eliminar dominios con doble extensión (.com.ar, .com.br, .com.mx)
    text = re.sub(r'\b\w+\.com\.(ar|br|mx|es|co|uk|au)\b', '', text, flags=re.IGNORECASE)

    # 4. Eliminar dominios comunes (.com, .net, etc.)
    text = re.sub(r'\b\w+\.(com|net|org|edu|gov|co|io|ai|app|store|shop|online|info|site|web|es|mx|ar|br)\b', '', text, flags=re.IGNORECASE)

    # 5. Eliminar referencias a Amazon específicamente
    text = re.sub(r'\b(amazon|amzn)\.(com|to|es|mx|com\.br|com\.ar)\b', '', text, flags=re.IGNORECASE)

    # 6. Eliminar emails (usuario@dominio.com) - completo incluyendo @ sobrante
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
    text = re.sub(r'\b\w+@', '', text)  # Eliminar cualquier palabra seguida de @

    # 7. Eliminar teléfonos con prefijos internacionales
    text = re.sub(r'\+?\d{1,4}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{1,4}[\s\-]?\d{1,9}', '', text)

    # 8. Eliminar teléfonos formato (011) 1234-5678
    text = re.sub(r'\(\d{2,4}\)\s*\d{4,8}[-\s]?\d{0,4}', '', text)

    # 9. Eliminar palabras relacionadas con links
    link_words = r'\b(link|url|website|sitio\s*web|página\s*web|web\s*site|click\s*here|haz\s*clic|visita|visit)\b'
    text = re.sub(link_words, '', text, flags=re.IGNORECASE)

    # 10. Eliminar palabras relacionadas con contacto
    contact_words = r'\b(email|e-mail|correo|teléfono|telefono|phone|celular|whatsapp|telegram|instagram|facebook|twitter|contacto|contact|llamar|call)\b'
    text = re.sub(contact_words, '', text, flags=re.IGNORECASE)

    # 11. Eliminar @ y # que puedan quedar de redes sociales
    text = re.sub(r'[@#]\w*', '', text)

    # 12. Eliminar palabras prohibidas de ML para marcas ("tipo X", "similar a X", "igual que X")
    # Esto previene infracciones de uso impropio de marcas
    text = re.sub(r'\btipo\s+[A-Z][\w\s]{2,15}\b', '', text)  # "tipo Xbox"
    text = re.sub(r'\bsimilar\s+(a|to)\s+[A-Z][\w\s]{2,15}\b', '', text, flags=re.IGNORECASE)  # "similar a Apple"
    text = re.sub(r'\bigual\s+(que|a|to)\s+[A-Z][\w\s]{2,15}\b', '', text, flags=re.IGNORECASE)  # "igual que Samsung"
    text = re.sub(r'\bcomo\s+[A-Z][\w\s]{2,15}\b', '', text)  # "como iPhone"
    text = re.sub(r'\bsuch\s+as\s+[A-Z][\w\s]{2,15}\b', '', text, flags=re.IGNORECASE)  # "such as Xbox"
    text = re.sub(r'\bestilo\s+[A-Z][\w\s]{2,15}\b', '', text)  # "estilo Apple" (cuando menciona marca)

    # 13. Limpiar espacios múltiples resultantes
    text = re.sub(r'\s+', ' ', text)

    # 14. Limpiar puntuación duplicada
    text = re.sub(r'[,;.]{2,}', '.', text)

    # 15. Limpiar espacios al inicio y final
    text = text.strip()

    # 16. Limpiar puntuación al inicio
    text = re.sub(r'^[,;.\s]+', '', text)

    return text


def _smart_truncate(text, max_chars):
    """
    Trunca texto de forma inteligente respetando palabras completas.
    Evita cortar en medio de palabras como "Dor..." de "Dorado".
    """
    if len(text) <= max_chars:
        return text

    # Buscar el último espacio antes del límite
    truncated = text[:max_chars]
    last_space = truncated.rfind(' ')

    if last_space > max_chars * 0.8:  # Si el último espacio está en el último 20%
        return truncated[:last_space].rstrip(',;.')
    else:
        # Si no hay espacio cercano, cortar en el límite y limpiar
        return truncated.rstrip(' ,;.')

def _add_cbt_compatibility_note(description, product_title, brand, bullets):
    """
    Agrega nota de compatibilidad CBT al FINAL de una descripción ya generada.

    Esta función NO modifica la descripción original, solo agrega al final
    la sección de compatibilidad si detecta que es un accesorio de marca protegida.

    Args:
        description: Descripción ya generada (texto completo)
        product_title: Título del producto
        brand: Marca del fabricante
        bullets: Bullets del producto

    Returns:
        str: Descripción con nota de compatibilidad agregada (si aplica)
    """
    if not description:
        return description

    # Detectar marca objetivo
    target_brand = _detect_target_brand(product_title, bullets)

    # Verificar si es marca protegida
    protected_brands = []
    try:
        blacklist_path = "config/brand_blacklist.json"
        if os.path.exists(blacklist_path):
            with open(blacklist_path, "r", encoding="utf-8") as f:
                blacklist_data = json.load(f)
                protected_brands = [b.lower() for b in blacklist_data.get("blacklisted_brands", [])]
    except:
        pass

    brand_lower = brand.lower() if brand else ""

    # Check si es marca protegida
    is_brand_protected = False
    detected_brand = None

    if brand_lower in protected_brands:
        is_brand_protected = True
        detected_brand = brand

    if target_brand:
        target_words = target_brand.lower().split()
        for word in target_words:
            if word in protected_brands:
                is_brand_protected = True
                detected_brand = target_brand
                break

    # Verificar si es accesorio
    is_accessory = not _is_original_product(brand, product_title, bullets)

    # Solo agregar nota si es accesorio de marca protegida
    if is_brand_protected and is_accessory and detected_brand:
        # Agregar nota de compatibilidad AL PRINCIPIO
        compatibility_note = f"""COMPATIBILIDAD
Compatible con dispositivos de la línea {detected_brand}.
Este es un producto genérico y no es fabricado por {detected_brand.split()[0]}.

"""

        return compatibility_note + description.strip()

    return description


def ai_desc_es(datos, mini_ml=None):
    """
    Genera descripción optimizada para MercadoLibre Global Selling.
    Usa el formato estructurado: intro + beneficios + cierre + specs + footer.
    Con post-procesamiento robusto para eliminar espacios extra y normalizar saltos de línea.
    PROTECCIÓN: Maneja marcas registradas usando lenguaje de compatibilidad.
    """
    if not client:
        return ""

    # Construir datos completos del producto para el prompt
    amazon_json = datos.get("full_json", {}) if isinstance(datos, dict) else {}

    # Si no tenemos el JSON completo, construirlo desde datos y mini_ml
    if not amazon_json:
        amazon_json = {
            "brand": datos.get("brand", ""),
            "model": datos.get("model", ""),
            "bullets": datos.get("bullets", []),
            "attributes": {},
            "summaries": []
        }
        if mini_ml:
            amazon_json.update({
                "brand": mini_ml.get("brand", ""),
                "model": mini_ml.get("model", ""),
                "main_characteristics": mini_ml.get("main_characteristics", []),
                "second_characteristics": mini_ml.get("second_characteristics", []),
                "package": mini_ml.get("package", {})
            })

    # Verificar nivel de protección de la marca
    brand = datos.get("brand", "") or (mini_ml.get("brand", "") if mini_ml else "")
    protection_level = _get_brand_protection_level(brand, amazon_json.get("title", ""))

    # Construir datos de producto para el prompt
    product_data = json.dumps(amazon_json, ensure_ascii=False)[:15000]

    # Instrucción de protección de marca si aplica
    brand_warning = ""

    if protection_level == "always_compatible":
        # Marcas de alto riesgo - SIEMPRE compatibilidad
        brand_warning = f"""
⚠️ CRÍTICO - MARCA DE ALTO RIESGO:
La marca "{brand}" es de ALTO RIESGO (lujo/entretenimiento/moda).

REGLAS OBLIGATORIAS:
1. NUNCA presentes el producto como si fuera fabricado por "{brand}"
2. Usa descripciones genéricas sin mencionar la marca directamente
3. Si DEBES mencionar compatibilidad, usa: "Compatible con productos estilo...", "Inspirado en..."
4. Enfócate en características del producto, NO en la marca

EJEMPLOS CORRECTOS:
✅ "Este reloj deportivo presenta diseño elegante en acero..."
✅ "Bolso de diseño clásico con acabado premium..."
✅ "Figura coleccionable articulada de 15cm con..."
"""

    elif protection_level == "original":
        # Marcas conocidas - evaluar si es original
        is_original = _is_original_product(brand, amazon_json.get("title", ""),
                                          amazon_json.get("attributes", {}).get("bullet_point", []))

        if is_original:
            # Producto ORIGINAL
            brand_warning = f"""
✅ PRODUCTO ORIGINAL:
Este producto parece ser ORIGINAL de "{brand}".

REGLAS:
1. Usa la marca normalmente en la descripción
2. Enfatiza que es producto ORIGINAL/NUEVO de la marca
3. Menciona garantía oficial si aplica
4. NO uses lenguaje de compatibilidad (el producto ES de la marca)

EJEMPLO:
✅ "{brand} presenta este producto original con todas las características premium que esperas..."
"""
        else:
            # Producto COMPATIBLE/ACCESORIO
            # Detectar marca objetivo para accesorios
            base_title = amazon_json.get("title", "")
            bullets = amazon_json.get("attributes", {}).get("bullet_point", [])
            target_brand = _detect_target_brand(base_title, bullets)

            # Usar la marca detectada o la marca del fabricante
            compat_brand = target_brand if target_brand else brand

            brand_warning = f"""
⚠️ ACCESORIO/COMPATIBLE - REGLAS CRÍTICAS CBT:
Este producto es un accesorio compatible con "{compat_brand}".

ESTRUCTURA OBLIGATORIA DE LA DESCRIPCIÓN:

1. PRIMERA LÍNEA (título con tagline):
   Formato EXACTO: "Producto compatible con {compat_brand} – Tagline breve"

   EJEMPLOS CORRECTOS:
   ✅ "Producto compatible con Nintendo Switch – Carga hasta 4 controles simultáneamente"
   ✅ "Producto compatible con PlayStation 5 – Control inalámbrico de alta precisión"
   ✅ "Producto compatible con iPhone 14/15 – Cable USB-C de carga rápida 20W"

   EJEMPLOS INCORRECTOS:
   ❌ "PURBHE NSC01 – Carga rápida..." (NO empezar con marca del fabricante)
   ❌ "Cargador para JoyCon..." (NO omitir la compatibilidad al inicio)

2. RESTO DE LA DESCRIPCIÓN:
   - Describe QUÉ es el producto y sus características
   - Menciona beneficios y especificaciones
   - NO vuelvas a repetir la marca protegida en el cuerpo

REGLAS ABSOLUTAS:
1. SIEMPRE empezar con "Producto compatible con {compat_brand}"
2. NO presentar el producto como si fuera fabricado por "{compat_brand}"
3. La marca solo aparece en la primera línea para indicar compatibilidad
4. El resto de la descripción es sobre el producto genérico

EJEMPLOS INCORRECTOS (PROHIBIDOS):
❌ Empezar con marca del fabricante: "PURBHE NSC01 – ..."
❌ No mencionar compatibilidad al inicio: "Cargador rápido para..."
❌ Presentarlo como original: "Nintendo Switch JoyCon Charger..."
"""

    prompt = f"""Eres un copywriter experto en Mercado Libre Global Selling.

{brand_warning}

# ============================================================
# GENERADOR DE DESCRIPCIÓN (INSTRUCCIONES BASE)
# ============================================================
# Estructura estándar para descripciones de Mercado Libre Global Selling.
# Formato: texto plano (SIN HTML, SIN emojis, SIN markdown)
# ============================================================

Datos del producto desde Amazon:
{product_data}

ESTRUCTURA EXACTA A SEGUIR:

1. TÍTULO CON TAGLINE (primera línea)

⚠️ SI ES ACCESORIO/COMPATIBLE (según instrucciones arriba):
Formato OBLIGATORIO: "Producto compatible con [MARCA] – Tagline persuasivo corto"
Ejemplo: "Producto compatible con Nintendo Switch – Carga hasta 4 controles simultáneamente"

⚠️ SI ES PRODUCTO ORIGINAL:
Formato: MARCA MODELO – Tagline persuasivo corto
Ejemplo: "GOZVRPUS TW-05 – Comunicación nítida y profesional"
- Usar MAYÚSCULAS para marca y modelo
- Guion largo (–) separando
- Tagline: 3-5 palabras que describan el beneficio principal
- NO repetir información del título del producto

2. LÍNEA EN BLANCO

3. PÁRRAFO INTRODUCTORIO (3-4 líneas)
- Introducir el producto con su beneficio principal
- Tono natural, comercial y humano
- Mencionar para quién es ideal (profesionales, estudiantes, etc.)
- Evitar: "Descubre", "Increíble", "Perfecto para ti"

4. LÍNEA EN BLANCO

5. BLOQUE DE CARACTERÍSTICAS (6-8 bullets COMPACTOS)
Formato EXACTO (SIN líneas vacías entre bullets):
• Característica 1: Beneficio corto en una línea
• Característica 2: Beneficio corto en una línea
• Característica 3: Beneficio corto en una línea

Ejemplos correctos (ESPAÑOL + Title Case):
• Diseño Vintage: Refleja tu estilo único con un acabado clásico
• Silencioso Y Potente: Motor de alto rendimiento sin ruido excesivo
• Batería De Litio: Más de 80 minutos de autonomía continua
• Ideal Para Todo Tipo De Pelo: Eficaz en todo tipo de cabello y barba
• Cuchillas Desmontables: Fácil limpieza y mantenimiento

REGLAS CRÍTICAS:
- Cada bullet: MÁXIMO 1 línea (80 caracteres)
- Usar dos puntos (:) para separar característica de beneficio
- SIN líneas vacías entre bullets
- Texto conciso y directo
- Característica SIEMPRE en ESPAÑOL (nunca en inglés)
- Formato Title Case: Primera Letra De Cada Palabra En Mayúscula
- NO TODO EN MAYÚSCULAS (ejemplo incorrecto: "VINTAGE DESIGN")
- Formato final: "Característica En Español: descripción del beneficio"

6. LÍNEA EN BLANCO

7. PÁRRAFO FINAL (2-3 líneas)
- Mensaje persuasivo breve
- Resumir beneficios principales
- Evitar: "No esperes más", "Cómpralo ya"

8. DOS LÍNEAS EN BLANCO

9. ESPECIFICACIONES TÉCNICAS
Formato EXACTO:
══════════════════════════════════════════════════
ESPECIFICACIONES TÉCNICAS
══════════════════════════════════════════════════
• Modelo: valor
• Atributo: valor
• Atributo: valor

REGLAS:
- Separador: 50 caracteres de ═
- SIN líneas vacías entre specs
- Formato: "• Nombre: Valor"
- Valores concisos (sin texto innecesario)
- Incluir: modelo, dimensiones, peso, material, color, conectividad, etc.
- Excluir: ASIN, SKU, GTIN, UPC, price, seller info

# REGLAS CRÍTICAS DE FORMATO
- SIN emojis (ni 📦, ni 🔎, ni 🌎, ni ninguno)
- SIN líneas vacías entre bullets
- SIN líneas vacías entre specs
- Separadores: solo ═ (50 caracteres)
- Bullets: solo • (punto medio)
- Dos puntos (:) para separar característica de beneficio en bullets
- NO incluir el bloque de "INFORMACIÓN IMPORTANTE" (se agregará automáticamente)

⛔ NO INCLUIR:
Amazon, ASIN, códigos, precios, enlaces, HTML, markdown, emojis,
frases genéricas ("increíble", "perfecto", "descubre")

⚠️ CRÍTICO - PROHIBIDO ABSOLUTO (violaciones causan suspensión de MercadoLibre):
- NUNCA incluir links o URLs (http://, https://, www., ftp://)
- NUNCA incluir dominios (.com, .net, .org, .io, .es, .mx, .ar, .br)
- NUNCA incluir emails (usuario@dominio.com, info@tienda.com)
- NUNCA incluir teléfonos (+54 11 1234-5678, WhatsApp, celular, llamar)
- NUNCA mencionar redes sociales (Instagram, Facebook, Twitter, Telegram)
- NUNCA mencionar "Amazon", "amazon.com", "amzn.to" u otras tiendas
- NUNCA usar palabras: "visita", "contacta", "llama", "escribe", "link", "email"
- NUNCA incluir @ o # seguido de texto (redes sociales)
- NUNCA usar para marcas: "tipo", "similar a", "igual que", "como", "such as"
  Ejemplo prohibido: "Este controlador tipo Xbox", "Similar a productos Apple"

Devuelve SOLO el texto plano formateado, sin explicaciones adicionales."""

    try:
        r = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.3,
            messages=[
                {"role": "system", "content": "Eres un experto copywriter de e-commerce. Devuelve SOLO texto plano formateado con saltos de línea simples y bullets •. SIN HTML, SIN markdown, SIN símbolos decorativos, SIN explicaciones."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
        )
        texto = (r.choices[0].message.content or "").strip()

        # ============================================================
        # POST-PROCESAMIENTO ROBUSTO (soluciona todos los problemas)
        # ============================================================
        import re

        # 1. Eliminar marcadores de código que pueda haber agregado la IA
        texto = texto.replace("```", "").replace("```text", "").replace("```plain", "")

        # 2. Eliminar cualquier versión del footer que la IA haya agregado (con o sin separadores)
        texto = re.sub(
            r'[═─]{5,}.*?INFORMACIÓN IMPORTANTE.*?ONEWORLD.*?🌎',
            '',
            texto,
            flags=re.DOTALL | re.IGNORECASE
        )
        texto = re.sub(
            r'INFORMACIÓN IMPORTANTE PARA COMPRAS INTERNACIONALES.*?ONEWORLD.*?🌎',
            '',
            texto,
            flags=re.DOTALL | re.IGNORECASE
        )

        # 3. Eliminar separadores decorativos que la IA pueda haber agregado (excepto los correctos)
        # Mantener solo separadores de exactamente 50 caracteres ═
        texto = re.sub(r'[═─]{51,}', '══════════════════════════════════════════════════', texto)
        texto = re.sub(r'[═─]{5,49}', '', texto)

        # 4. Eliminar TODOS los emojis (MercadoLibre los rechaza)
        # Rango Unicode de emojis comunes
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # símbolos y pictogramas
            "\U0001F680-\U0001F6FF"  # transporte y símbolos de mapa
            "\U0001F1E0-\U0001F1FF"  # banderas
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        texto = emoji_pattern.sub('', texto)

        # 5. Eliminar espacios al final de cada línea (problema principal)
        texto = re.sub(r'[ \t]+$', '', texto, flags=re.MULTILINE)

        # 6. Eliminar líneas que solo tienen espacios en blanco
        texto = re.sub(r'^\s+$', '', texto, flags=re.MULTILINE)

        # 7. Normalizar saltos múltiples: máximo 2 saltos consecutivos (\n\n = 1 línea vacía)
        texto = re.sub(r'\n{3,}', '\n\n', texto)

        # 8. Limpiar inicio y final
        texto = texto.strip()

        # 9. Forzar formato correcto de ESPECIFICACIONES TÉCNICAS
        # Buscar "ESPECIFICACIONES TÉCNICAS" y asegurar que tenga separadores antes y después
        separador = '══════════════════════════════════════════════════'
        if 'ESPECIFICACIONES TÉCNICAS' in texto or 'ESPECIFICACIONES TECNICAS' in texto:
            # Reemplazar cualquier variante sin separadores
            texto = re.sub(
                r'(\n\n)(ESPECIFICACIONES TÉ?CNICAS)(\n)',
                f'\n\n{separador}\n\\2\n{separador}',
                texto,
                flags=re.IGNORECASE
            )
            # Si ya tiene un separador, no duplicar
            texto = re.sub(
                f'{separador}\n{separador}\nESPECIFICACIONES',
                f'{separador}\nESPECIFICACIONES',
                texto,
                flags=re.IGNORECASE
            )
            # Eliminar línea vacía después del separador inferior de specs
            texto = re.sub(
                f'{separador}\n\n•',
                f'{separador}\n•',
                texto
            )

        # ============================================================
        # AGREGAR FOOTER FIJO (idéntico para todos los productos)
        # ============================================================
        footer_text = """

══════════════════════════════════════════════════
INFORMACIÓN IMPORTANTE PARA COMPRAS INTERNACIONALES
══════════════════════════════════════════════════
• Producto nuevo y original
• Envío desde EE.UU. con seguimiento
• Mercado Libre gestiona los impuestos y la aduana; el precio mostrado ya los incluye
• Compra protegida por Mercado Libre
• Garantía del vendedor: 30 días
• Facturación: su factura local la emite Mercado Libre. Nosotros tributamos en EE.UU.
• Productos eléctricos: 110-120V + clavija americana (puede requerir adaptador)
• Medidas y peso pueden estar en sistema imperial
• Atención al cliente en español e inglés

Somos ONEWORLD"""

        texto += footer_text

        # ⚠️ CRÍTICO: Eliminar cualquier link o URL (MercadoLibre los prohíbe)
        texto = _remove_links_and_urls(texto)

        # Agregar nota de compatibilidad CBT si aplica (AL PRINCIPIO, antes del footer)
        product_title = amazon_json.get("title", "")
        bullets_raw = amazon_json.get("attributes", {}).get("bullet_point", [])
        texto = _add_cbt_compatibility_note(texto, product_title, brand, bullets_raw)

        return texto

    except Exception as e:
        print(f"⚠️ Error generando descripción con IA: {e}")
        # Fallback básico con footer limpio
        return """Producto de alta calidad.

══════════════════════════════════════════════════
INFORMACIÓN IMPORTANTE PARA COMPRAS INTERNACIONALES
══════════════════════════════════════════════════
• Producto nuevo y original
• Envío desde EE.UU. con seguimiento
• Mercado Libre gestiona los impuestos y la aduana; el precio mostrado ya los incluye
• Compra protegida por Mercado Libre
• Garantía del vendedor: 30 días
• Facturación: su factura local la emite Mercado Libre. Nosotros tributamos en EE.UU.
• Productos eléctricos: 110-120V + clavija americana (puede requerir adaptador)
• Medidas y peso pueden estar en sistema imperial
• Atención al cliente en español e inglés

Somos ONEWORLD"""

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

# ---------- 8) Categoría (CategoryMatcherV2: embeddings + IA) ----------
def detect_category(amazon_json, excluded_categories=None)->Tuple[str,str,float]:
    asin = amazon_json.get("asin") or amazon_json.get("ASIN") or ""
    excluded_categories = excluded_categories or []

    # Extraer título
    title = amazon_json.get("title") or \
        amazon_json.get("product_title") or \
        (amazon_json.get("attributes",{}).get("item_name",[{}])[0].get("value", "") \
        if amazon_json.get("attributes",{}).get("item_name") else "Generic Product")

    qprint("🧭 Detectando categoría con CategoryMatcherV2 (embeddings + IA)…")

    # 📌 Cache por ASIN - DESHABILITADO PERMANENTEMENTE
    CAT_CACHE_PATH = "storage/logs/category_cache.json"
    try:
        cat_cache = json.load(open(CAT_CACHE_PATH, "r", encoding="utf-8"))
    except:
        cat_cache = {}

    # ❌ CACHÉ DESHABILITADO - Siempre usar CategoryMatcherV2 con fix LEAF
    # if asin in cat_cache:
    #     cat_id = cat_cache[asin]["id"]
    #     cat_name = cat_cache[asin]["name"]
    #     sim = cat_cache[asin]["sim"]
    #     print(f"🧠 Cache encontrado → IA OFF ✅")
    #     return cat_id, cat_name, sim

    # ✅ Nueva categorización con CategoryMatcherV2
    try:
        # Construir product_data para CategoryMatcherV2
        product_data = {
            'title': title,
            'brand': None,
            'description': None,
            'features': [],
            'productType': None,
            'browseClassification': None
        }

        # Extraer brand
        attributes = amazon_json.get("attributes", {})
        if attributes.get("brand_name"):
            brand_list = attributes["brand_name"]
            if brand_list and isinstance(brand_list, list):
                product_data['brand'] = brand_list[0].get("value", "")

        # Extraer description (de bullet_point)
        if attributes.get("bullet_point"):
            bullets = attributes["bullet_point"]
            if bullets and isinstance(bullets, list):
                product_data['features'] = [b.get("value", "") for b in bullets if b.get("value")]
                product_data['description'] = " ".join(product_data['features'][:3])

        # Extraer productType de Amazon (muy importante para CategoryMatcherV2)
        if amazon_json.get("productTypes"):
            product_types = amazon_json["productTypes"]
            if product_types and isinstance(product_types, list) and len(product_types) > 0:
                product_data['productType'] = product_types[0].get("productType", "")

        # Extraer browseClassification si existe
        if attributes.get("item_type_keyword"):
            item_type = attributes["item_type_keyword"]
            if item_type and isinstance(item_type, list):
                product_data['browseClassification'] = item_type[0].get("value", "")

        # Llamar a CategoryMatcherV2 con exclusión de categorías bloqueadas
        matcher = get_category_matcher()
        result = matcher.find_category(product_data, use_ai=True, excluded_categories=excluded_categories)

        cat_id = result.get("category_id", "CBT1157")
        cat_name = result.get("category_name", "Default")
        sim = float(result.get("confidence", 0.0))

        qprint(f"🤖 CategoryMatcherV2 → {cat_name} (confidence: {sim:.2f})")
        qprint(f"   Método: {result.get('method', 'unknown')}")

        # Guardar en cache
        cat_cache[asin] = {"id": cat_id, "name": cat_name, "sim": sim}
        os.makedirs("storage/logs", exist_ok=True)
        with open(CAT_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cat_cache, f, indent=2, ensure_ascii=False)

        return cat_id, cat_name, sim

    except Exception as e:
        import traceback
        print(f"⚠️ CategoryMatcherV2 error: {e}")
        traceback.print_exc()
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

        qprint(f"📘 Schema {category_id}: {len(schema)} atributos descargados.")
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
def build_mini_ml(amazon_json: dict, excluded_categories=None) -> dict:
    asin = amazon_json.get("asin") or amazon_json.get("ASIN") or ""

    # Leer categorías bloqueadas del mini_ml anterior si existe
    if excluded_categories is None:
        mini_path = Path("storage/logs/publish_ready") / f"{asin}_mini_ml.json"
        if mini_path.exists():
            try:
                with open(mini_path, "r", encoding="utf-8") as f:
                    old_mini = json.load(f)
                    excluded_categories = old_mini.get("blocked_categories", [])
                    if excluded_categories:
                        print(f"🚫 Excluyendo categorías bloqueadas previas: {excluded_categories}")
            except:
                pass

    excluded_categories = excluded_categories or []
    cat_id, cat_name, sim = detect_category(amazon_json, excluded_categories)

    # ✅ Si la categoría ya está en caché → IA de equivalencias OFF
    CAT_CACHE_PATH = "storage/logs/category_cache.json"
    try:
        cat_cache = json.load(open(CAT_CACHE_PATH, "r", encoding="utf-8"))
    except:
        cat_cache = {}

    category_cached = asin in cat_cache

    if category_cached:
        qprint("🧠 Categoría caché → saltando aprendizaje IA de equivalencias ✅")
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
    # Preparar datos para descripción con JSON completo de Amazon
    datos_desc = {
        "brand": brand,
        "model": model,
        "bullets": bullets[:8],
        "full_json": amazon_json  # Incluir JSON completo para el nuevo prompt
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

    # Validar que TODAS las dimensiones existan - SIN FALLBACKS
    if not all([length_cm, width_cm, height_cm, weight_kg]):
        missing = []
        if not length_cm: missing.append("length")
        if not width_cm: missing.append("width")
        if not height_cm: missing.append("height")
        if not weight_kg: missing.append("weight")

        error_msg = f"❌ ERROR: Dimensiones de paquete faltantes en {asin}: {', '.join(missing)}"
        print(error_msg)
        print(f"   Length: {length_cm}, Width: {width_cm}, Height: {height_cm}, Weight: {weight_kg}")
        print("   Las dimensiones del paquete DEBEN estar en item_package_dimensions del JSON de Amazon")
        print("   NO se permiten fallbacks - el producto será rechazado")

        # Retornar None para que el pipeline lo marque como fallido
        return None

    # Usar dimensiones reales de Amazon
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
        if price.get('tax_exempt'):
            qprint(f"💰 Precio: ${base_price} + tax ${tax} (EXENTO) + 3PL $4.00 = costo ${price['cost_usd']} → net proceeds ${price['net_proceeds_usd']} (markup {price['markup_pct']}%)")
        else:
            qprint(f"💰 Precio: ${base_price} + tax ${tax} + 3PL $4.00 = costo ${price['cost_usd']} → net proceeds ${price['net_proceeds_usd']} (markup {price['markup_pct']}%)")
    else:
        qprint(f"💰 Precio: ${base_price} (sin tax) + 3PL $4.00 = costo ${price['cost_usd']} → net proceeds ${price['net_proceeds_usd']} (markup {price['markup_pct']}%)")

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
        qprint(f"📡 Descargando schema {cat_id} desde API…")
        schema = get_category_schema(cat_id)
        if schema:
            os.makedirs("data/schemas", exist_ok=True)
            with open(f"data/schemas/{cat_id}.json", "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2, ensure_ascii=False)
            qprint(f"💾 Schema {cat_id} guardado localmente.")

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
        qprint(f"📊 Mapeo actualizado: {bar} {total_filled}/{total_schema} ({progress}%)")

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
    # Solo si no estaba en caché
    if asin not in desc_cache:
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
        # Actualizar caché con la versión final
        desc_cache[asin] = desc_es
        _save_cache(DESC_CACHE_PATH, desc_cache)

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
    schema_path = f"data/schemas/{out['category_id']}.json"
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