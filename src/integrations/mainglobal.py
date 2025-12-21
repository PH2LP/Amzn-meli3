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

# Helper para quiet mode
QUIET_MODE = os.getenv('PIPELINE_QUIET_MODE') == '1'
def qprint(*args, **kwargs):
    """Print solo si no está en quiet mode"""
    if not QUIET_MODE:
        print(*args, **kwargs)
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

# ============ AUTO TOKEN REFRESH ============
_last_token_refresh = 0  # Timestamp del último refresh
_token_lock_file = "storage/.token_refresh.lock"

def refresh_ml_token(force=False):
    """Renueva automáticamente el token de MercadoLibre cuando expira (con lock file para procesos paralelos)"""
    global _last_token_refresh, ML_ACCESS_TOKEN, HEADERS
    import time as time_module
    from pathlib import Path

    # Evitar múltiples refreshes en menos de 10 segundos (salvo que sea forzado)
    if not force and (time_module.time() - _last_token_refresh) < 10:
        print("⏭️  Refresh reciente (<10s), usando token actual")
        return True

    lock_path = Path(_token_lock_file)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    # 🔒 Esperar si otro proceso está refrescando el token
    max_wait = 30  # segundos
    wait_start = time_module.time()
    while lock_path.exists():
        if time_module.time() - wait_start > max_wait:
            print("⚠️  Timeout esperando lock de token, forzando refresh...")
            break
        print("⏳ Otro proceso está refrescando el token, esperando...")
        time_module.sleep(2)

    # Si esperamos y el lock desapareció, recargar .env y continuar sin refrescar
    if not force and lock_path.exists() is False and (time_module.time() - wait_start) > 0:
        print("✅ Token ya refrescado por otro proceso, recargando .env...")
        load_dotenv(override=True)
        ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")
        return True

    # 🔒 Crear lock file
    try:
        lock_path.write_text(str(os.getpid()))
    except Exception as e:
        print(f"⚠️  Error creando lock file: {e}")

    print("🔄 Token expirado, renovando automáticamente...")

    env_path = ".env"
    from dotenv import dotenv_values
    env = dotenv_values(env_path)

    client_id = env.get("ML_CLIENT_ID")
    client_secret = env.get("ML_CLIENT_SECRET")
    refresh_token = env.get("ML_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        print("❌ Faltan credenciales ML en .env para renovar token")
        return False

    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token
    }

    try:
        r = requests.post(url, data=payload, timeout=10)
        r.raise_for_status()
        data = r.json()

        new_access_token = data.get("access_token")
        new_refresh_token = data.get("refresh_token", refresh_token)

        if not new_access_token:
            print("❌ ML no devolvió access_token en la respuesta")
            return False

        # Actualizar .env
        with open(env_path, "r") as f:
            lines = f.readlines()
        new_lines = []
        for line in lines:
            if line.startswith("ML_ACCESS_TOKEN="):
                new_lines.append(f"ML_ACCESS_TOKEN={new_access_token}\n")
            elif line.startswith("ML_REFRESH_TOKEN="):
                new_lines.append(f"ML_REFRESH_TOKEN={new_refresh_token}\n")
            else:
                new_lines.append(line)
        with open(env_path, "w") as f:
            f.writelines(new_lines)

        # Actualizar variables globales en memoria
        ML_ACCESS_TOKEN = new_access_token
        HEADERS = {"Authorization": f"Bearer {new_access_token}"}
        os.environ["ML_ACCESS_TOKEN"] = new_access_token
        os.environ["ML_REFRESH_TOKEN"] = new_refresh_token

        _last_token_refresh = time_module.time()
        print(f"✅ Token renovado: {new_access_token[:40]}...")

        # 🔓 Eliminar lock file
        try:
            if lock_path.exists():
                lock_path.unlink()
        except Exception as e:
            print(f"⚠️  Error eliminando lock file: {e}")

        return True

    except Exception as e:
        print(f"❌ Error renovando token: {e}")

        # 🔓 Eliminar lock file incluso si falla
        try:
            if lock_path.exists():
                lock_path.unlink()
        except:
            pass

        return False

# ============ HTTP ============
def http_get(url, params=None, extra_headers=None, timeout=30, _retry_count=0):
    h = dict(HEADERS)
    if extra_headers:
        h.update(extra_headers)
    r = requests.get(url, headers=h, params=params, timeout=timeout)

    # Si el token expiró (401), renovar y reintentar UNA vez
    if r.status_code == 401 and _retry_count == 0:
        if "invalid_token" in r.text or "expired" in r.text.lower():
            if refresh_ml_token():
                # Reintentar con el nuevo token
                return http_get(url, params, extra_headers, timeout, _retry_count=1)

    if not r.ok:
        raise RuntimeError(f"GET {url} → {r.status_code} {r.text}")
    return r.json()

def parse_ml_error_for_missing_fields(error_text: str) -> list:
    """
    Parsea errores de MercadoLibre para detectar campos faltantes.

    Ejemplos de errores:
    - "attribute [SIZE_GRID_ID] is missing"
    - "Attribute HEIGHT with value Default is required and was omitted"

    Returns:
        Lista de field_ids faltantes
    """
    import re
    missing_fields = []

    # Patrón 1: "attribute [FIELD_ID] is missing"
    matches = re.findall(r'attribute\s+\[(\w+)\]\s+is\s+missing', error_text, re.IGNORECASE)
    missing_fields.extend(matches)

    # Patrón 2: "Attribute FIELD_ID with value Default is required"
    matches = re.findall(r'Attribute\s+(\w+)\s+with\s+value\s+Default', error_text, re.IGNORECASE)
    missing_fields.extend(matches)

    # Patrón 3: "Attribute FIELD_ID ... was omitted"
    matches = re.findall(r'Attribute\s+(\w+)\s+.*?was\s+omitted', error_text, re.IGNORECASE)
    missing_fields.extend(matches)

    # Deduplicar
    missing_fields = list(set(missing_fields))

    if missing_fields:
        qprint(f"🔍 Detectados campos faltantes en error de ML: {missing_fields}")

    return missing_fields

def ai_extract_missing_fields(asin: str, amazon_json: dict, required_fields: list) -> dict:
    """
    Usa IA para extraer valores de campos requeridos faltantes del JSON completo de Amazon.

    Args:
        asin: ASIN del producto
        amazon_json: JSON completo de Amazon con toda la información del producto
        required_fields: Lista de campos requeridos con su schema info

    Returns:
        Dict con {attribute_id: extracted_value}
    """
    if not required_fields or not OPENAI_API_KEY:
        return {}

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Crear lista de campos a buscar CON sus valores permitidos del schema
    fields_to_find = []
    for field in required_fields:
        field_id = field.get("id", "")
        field_name = field.get("name", "")
        field_type = field.get("value_type", "string")
        field_values = field.get("values", [])

        # Si hay valores permitidos en el schema, incluirlos en el prompt
        if field_values:
            allowed_values = [v.get("name", "") for v in field_values if v.get("name")]
            if allowed_values:
                fields_to_find.append(f"- {field_id} ({field_name}): tipo {field_type}, VALORES PERMITIDOS: {', '.join(allowed_values)}")
            else:
                fields_to_find.append(f"- {field_id} ({field_name}): tipo {field_type}")
        else:
            fields_to_find.append(f"- {field_id} ({field_name}): tipo {field_type}")

    fields_text = "\n".join(fields_to_find)

    # Truncar JSON si es muy largo (solo datos relevantes)
    amazon_str = json.dumps(amazon_json, indent=2, ensure_ascii=False)
    if len(amazon_str) > 8000:
        # Priorizar atributos y dimensiones
        compact = {
            "title": amazon_json.get("title", ""),
            "attributes": amazon_json.get("attributes", {}),
            "dimensions": amazon_json.get("dimensions", {}),
            "item_dimensions": amazon_json.get("item_dimensions", {}),
            "package_dimensions": amazon_json.get("package_dimensions", {}),
            "productTypes": amazon_json.get("productTypes", [])
        }
        amazon_str = json.dumps(compact, indent=2, ensure_ascii=False)[:8000]

    prompt = f"""You are an expert in mapping product attributes between Amazon SP-API and MercadoLibre.

TASK: Extract the following MercadoLibre attributes from the Amazon product JSON.

Amazon Product JSON:
{amazon_str}

Required MercadoLibre fields to extract:
{fields_text}

⚠️ CRITICAL: If a field has "VALORES PERMITIDOS" (allowed values), you MUST return ONLY one of those exact values.
   - Do NOT invent new values or use variations
   - Choose the CLOSEST semantic match from the allowed list
   - If no good match exists, return null for that field

CRITICAL SEMANTIC MAPPING RULES:
1. Analyze the MEANING of each attribute name, not just literal text matches
2. Search in MULTIPLE locations in the JSON structure:
   - attributes.{{field_name}}[0].value
   - attributes.{{field_name}}[0]
   - summaries[0].{{field_name}}
   - Top-level fields

3. Common semantic mappings (use these patterns):
   - UNIT_VOLUME / VOLUME / LIQUID_VOLUME → liquid_volume, item_volume, size (extract ml/oz and convert)
   - HEIGHT / WIDTH / DEPTH / LENGTH → item_dimensions, package_dimensions, item_package_dimensions
   - WEIGHT / ITEM_WEIGHT → item_weight, item_package_weight, package_weight
   - BRAND / MANUFACTURER → brand, manufacturer
   - MODEL / PART_NUMBER → model_number, part_number, item_model_number
   - COLOR / MAIN_COLOR → color, color_name, main_color, variant_color
   - MATERIAL → material, material_type, composition, base_material
   - SIZE / ITEM_SIZE → size, item_size, dimensions
   - GENDER / TARGET_GENDER → target_gender, gender, recommended_gender
   - AGE / AGE_RANGE → target_age, recommended_age, age_range
   - SCENT / FRAGRANCE → scent, fragrance, fragrance_name

4. Unit conversions (apply automatically):
   - Volume: 1 fl oz = 29.57 ml, 1 oz (liquid) = 29.57 ml
   - Dimensions: 1 inch = 2.54 cm, 1 foot = 30.48 cm
   - Weight: 1 lb = 0.453592 kg, 1 oz = 28.35 g

5. Data extraction patterns:
   - If field is array format (like value/unit pairs), extract both parts or convert units
   - If value is in nested object, traverse the structure
   - Check title, bullet_points, and description as fallback for descriptive fields

6. Validation:
   - Return ONLY valid values, never "Default", "null", or placeholders
   - Return single string values, NOT arrays (e.g., "Unisex" not ["Unisex"])
   - Return boolean as true/false, NOT as strings like "true"
   - If you cannot find reliable data for a field, return null for that field

Return JSON format with extracted values only, no explanations or markdown.

Return ONLY the JSON object, no explanations or markdown."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500
        )

        result_text = response.choices[0].message.content.strip()

        # Limpiar markdown si existe
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        extracted = json.loads(result_text)
        qprint(f"🤖 IA extrajo {len(extracted)} campos faltantes del JSON de Amazon")
        return extracted

    except Exception as e:
        print(f"⚠️ Error al extraer campos con IA: {e}")
        return {}

def autofill_required_attrs(cid: str, attributes: list, asin: str = None, amazon_json: dict = None) -> list:
    """
    Consulta el schema oficial de la categoría y agrega los atributos obligatorios que falten.
    Si se pasa asin y amazon_json, usa IA para extraer valores faltantes.
    """
    try:
        schema = http_get(f"https://api.mercadolibre.com/categories/{cid}/attributes")
    except Exception as e:
        print(f"⚠️ No se pudo obtener schema de {cid}: {e}")
        return attributes

    existing_ids = {a["id"] for a in attributes if "id" in a}
    added = 0

    # Paso 1: Identificar campos requeridos faltantes
    missing_required = []
    for field in schema:
        tags = field.get("tags", {})
        if not tags.get("required"):
            continue
        aid = field["id"]
        if aid in existing_ids:
            continue
        missing_required.append(field)

    # Paso 2: Si hay campos faltantes y tenemos JSON de Amazon, usar IA
    ai_extracted = {}
    if missing_required and asin and amazon_json:
        print(f"🔍 Detectados {len(missing_required)} campos requeridos faltantes, extrayendo con IA...")
        ai_extracted = ai_extract_missing_fields(asin, amazon_json, missing_required)

    # Paso 3: Agregar campos faltantes con valores extraídos por IA o defaults
    for field in missing_required:
        aid = field["id"]
        vals = field.get("values", [])
        val_id = val_name = None

        # Intentar usar valor extraído por IA
        if aid in ai_extracted and ai_extracted[aid]:
            extracted_value = ai_extracted[aid]

            # Si es un diccionario con value/unit (común en volúmenes, dimensiones), convertir a string
            if isinstance(extracted_value, dict):
                if 'value' in extracted_value and 'unit' in extracted_value:
                    extracted_value = f"{extracted_value['value']} {extracted_value['unit']}"
                else:
                    # Si es otro tipo de dict, convertir a string o tomar primer valor
                    extracted_value = str(extracted_value)

            # Si es una lista, extraer el primer elemento
            if isinstance(extracted_value, list):
                if len(extracted_value) > 0:
                    extracted_value = extracted_value[0]
                else:
                    extracted_value = None

            # Si es booleano, convertir a string apropiado para ML
            if isinstance(extracted_value, bool):
                # Para ML, los booleanos se manejan como strings "Yes"/"No" o value_ids
                extracted_value = "Yes" if extracted_value else "No"

            if extracted_value:
                val_name = str(extracted_value).lower().strip()

                # Mapeo de valores comunes a valores del schema de MercadoLibre
                value_mappings = {
                    # GENDER mappings
                    "unisex": "gender neutral kid",
                    "neutral": "gender neutral",
                    "male": "man",
                    "female": "woman",
                    "boy": "boys",
                    "girl": "girls",

                    # BICYCLE_TYPE mappings
                    "balance bike": "kids",
                    "kids bike": "kids",
                    "children's bike": "kids",
                    "toddler bike": "kids",
                    "mtb": "mountain bike",
                    "city bike": "urban",
                    "road bike": "route",

                    # AGE_GROUP mappings
                    "children": "kids",
                    "child": "kids",
                    "adult": "adults",
                }

                # Aplicar mapeo si existe
                if val_name in value_mappings:
                    mapped_value = value_mappings[val_name]
                    print(f"   ✅ {aid} = {mapped_value} (extraído por IA, mapeado de '{val_name}')")
                    val_name = mapped_value
                else:
                    print(f"   ✅ {aid} = {val_name} (extraído por IA)")

        # Si no, usar primer valor del schema si existe
        elif vals:
            val_id = str(vals[0].get("id")) if vals[0].get("id") else None
            val_name = vals[0].get("name")

        # Defaults seguros para campos específicos
        if aid == "IS_KIT" and not val_id and not val_name:
            val_id, val_name = "242084", "No"
        if aid == "IS_COLLECTIBLE" and not val_id and not val_name:
            val_id, val_name = "242084", "No"
        # Para balance bikes/kids bikes sin wheel size, usar 12" como default estándar
        if aid == "WHEEL_SIZE" and not val_id and not val_name and cid in ["CBT12012", "CBT424974"]:
            val_name = "12\""
            print(f"   ℹ️ {aid} = {val_name} (default para kids bike)")

        # Solo agregar si tenemos un valor válido (no "Default")
        if val_id or (val_name and val_name != "Default"):
            attributes.append({
                "id": aid,
                "value_id": val_id,
                "value_name": val_name
            })
            added += 1
        else:
            print(f"   ⚠️ {aid}: No se pudo encontrar valor válido, omitiendo")

    if added:
        qprint(f"🧩 Se agregaron {added} atributos requeridos automáticamente para {cid}")
    return attributes

def fix_attributes_with_value_ids(cid: str, attributes: list) -> list:
    """
    Convierte atributos con value_name en texto a value_id consultando el schema.
    Descarta atributos que no tienen match válido.
    """
    try:
        schema = http_get(f"https://api.mercadolibre.com/categories/{cid}/attributes")
    except Exception as e:
        print(f"⚠️ No se pudo obtener schema para fix_attributes: {e}")
        return attributes

    # Crear mapa de atributos y sus valores permitidos
    schema_map = {}
    for field in schema:
        aid = field.get("id")
        if not aid:
            continue

        # Determinar si el atributo acepta valores libres o solo predefinidos
        value_type = field.get("value_type", "")
        allow_variations = field.get("tags", {}).get("allow_variations", False)
        values = field.get("values", [])

        schema_map[aid] = {
            "value_type": value_type,
            "allow_variations": allow_variations,
            "has_predefined_values": len(values) > 0,
            "values": {}
        }

        # Mapear name → id para búsqueda rápida (case-insensitive)
        for v in values:
            v_id = v.get("id")
            v_name = v.get("name", "")
            if v_id and v_name:
                schema_map[aid]["values"][v_name.lower().strip()] = str(v_id)

    # Procesar atributos
    fixed_attrs = []
    skipped = 0
    fixed = 0

    for attr in attributes:
        aid = attr.get("id")
        if not aid:
            continue

        # Si ya tiene value_id, mantenerlo
        if attr.get("value_id"):
            fixed_attrs.append(attr)
            continue

        value_name = attr.get("value_name")
        if not value_name:
            continue

        # Si el atributo no está en el schema, mantenerlo (atributo custom o de texto libre)
        if aid not in schema_map:
            fixed_attrs.append({"id": aid, "value_name": str(value_name)})
            continue

        field_info = schema_map[aid]

        # Si el atributo acepta valores libres (texto), mantenerlo
        if field_info["value_type"] in ["string", "number"] and not field_info["has_predefined_values"]:
            fixed_attrs.append({"id": aid, "value_name": str(value_name)})
            continue

        # Si tiene valores predefinidos, buscar el value_id
        if field_info["has_predefined_values"]:
            value_name_lower = str(value_name).lower().strip()
            value_id = field_info["values"].get(value_name_lower)

            if value_id:
                fixed_attrs.append({
                    "id": aid,
                    "value_id": value_id,
                    "value_name": str(value_name)
                })
                fixed += 1
            else:
                # CRITICAL ATTRIBUTES: NEVER discard, use value_name instead
                critical_attrs = ["BRAND", "MODEL", "MANUFACTURER", "COLOR"]
                if aid in critical_attrs:
                    fixed_attrs.append({"id": aid, "value_name": str(value_name)})
                    print(f"✅ Atributo crítico {aid}='{value_name}' mantenido (sin value_id)")
                else:
                    # No hay match → descartar este atributo
                    skipped += 1
                    print(f"⚠️ Atributo {aid} con valor '{value_name}' no encontrado en schema → descartado")
        else:
            # Atributo sin valores predefinidos pero tampoco es de texto libre → mantener
            fixed_attrs.append({"id": aid, "value_name": str(value_name)})

    if fixed > 0:
        print(f"✅ {fixed} atributos convertidos a value_id")
    if skipped > 0:
        print(f"🗑️  {skipped} atributos descartados (sin match en schema)")

    return fixed_attrs

def http_post(url, body, extra_headers=None, timeout=60, _retry_count=0):
    h = {"Authorization": HEADERS["Authorization"], "Content-Type": "application/json"}
    if extra_headers:
        h.update(extra_headers)
    r = requests.post(url, headers=h, json=body, timeout=timeout)

    # Si el token expiró (401), renovar y reintentar UNA vez
    if r.status_code == 401 and _retry_count == 0:
        if "invalid_token" in r.text or "expired" in r.text.lower():
            if refresh_ml_token():
                # Reintentar con el nuevo token
                return http_post(url, body, extra_headers, timeout, _retry_count=1)

    # Retry con delay si rate limited
    if r.status_code == 429:
        print("⏳ Rate limited, esperando 10s y reintentando...")
        time.sleep(10)
        r = requests.post(url, headers=h, json=body, timeout=timeout)
    if not r.ok:
        raise RuntimeError(f"POST {url} → {r.status_code} {r.text}")
    return r.json()

def http_put(url, body, extra_headers=None, timeout=60, _retry_count=0):
    h = {"Authorization": HEADERS["Authorization"], "Content-Type": "application/json"}
    if extra_headers:
        h.update(extra_headers)
    r = requests.put(url, headers=h, json=body, timeout=timeout)

    # Si el token expiró (401), renovar y reintentar UNA vez
    if r.status_code == 401 and _retry_count == 0:
        if "invalid_token" in r.text or "expired" in r.text.lower():
            if refresh_ml_token():
                # Reintentar con el nuevo token
                return http_put(url, body, extra_headers, timeout, _retry_count=1)

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
            qprint(f"📦 Dimensiones del paquete directas: {round(L,2)}×{round(W,2)}×{round(H,2)} cm – {round(KG,3)} kg")
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
                     "• PRODUCTOS ELÉCTRICOS: POR FAVOR LEA ATENTAMENTE LAS INDICACIONES DEL PRODUCTO. Si es solo 120V y no 220V, usted va a necesitar un adaptador a 220V, de lo contrario el equipo puede quemarse y no es reembolsable.\n"
                     "• Medidas y peso pueden aparecer en sistema imperial\n"
                     "• Si incluye baterías, pueden enviarse retiradas por normas aéreas\n"
                     "• Atención al cliente en español e inglés\n\n"
                     "¿No encontrás lo que buscás? ¡Envianos una pregunta e intentaremos conseguir el producto para usted!\n\n"
                     "Somos USA_NEXO")
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
• PRODUCTOS ELÉCTRICOS: POR FAVOR LEA ATENTAMENTE LAS INDICACIONES DEL PRODUCTO. Si es solo 120V y no 220V, usted va a necesitar un adaptador a 220V, de lo contrario el equipo puede quemarse y no es reembolsable.
• Medidas y peso pueden aparecer en sistema imperial
• Si incluye baterías, pueden enviarse retiradas por normas aéreas
• Atención al cliente en español e inglés

¿No encontrás lo que buscás? ¡Envianos una pregunta e intentaremos conseguir el producto para usted!

Somos USA_NEXO"

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
            qprint(f"🧩 IA detectó {len(main)} main y {len(second)} second characteristics.")
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
def publish_item(asin_json, excluded_sites=None):
    """
    asin_json puede venir de transform_mapper (mini_ml.json)
    excluded_sites: lista de site_ids (ej: ['MCO', 'MLB']) a NO publicar (evita duplicados en retry)
    """
    # from uploader import upload_images_to_meli  # ← YA NO SE USA

    # 🔹 Si el input viene del transform_mapper (mini_ml)
    if "title_ai" in asin_json and "attributes_mapped" in asin_json:
        mini = asin_json
        qprint(f"📦 Usando JSON transformado (mini_ml) para {mini.get('asin')}")

        # 🤖 VALIDACIÓN IA: DESHABILITADA
        # El sistema híbrido AI + Category Matcher ya validó las categorías
        qprint(f"✅ Usando categoría validada por sistema híbrido AI + Category Matcher")

        asin = mini.get("asin", "GENERIC")
        ai_title_es = mini.get("title_ai")
        ai_desc_es = mini.get("description_ai")
        model_name = mini.get("model")
        brand = mini.get("brand")
        gtins = mini.get("gtins", [])
        pkg = mini.get("package", {})
        price = mini.get("price", {})

        L, W, H, KG = pkg.get("length_cm"), pkg.get("width_cm"), pkg.get("height_cm"), pkg.get("weight_kg")

        # ✅ Validar que existan TODAS las dimensiones - SIN FALLBACKS
        if not all([L, W, H, KG]):
            missing = []
            if not L: missing.append("length_cm")
            if not W: missing.append("width_cm")
            if not H: missing.append("height_cm")
            if not KG: missing.append("weight_kg")

            error_msg = f"Dimensiones de paquete faltantes: {', '.join(missing)}"
            print(f"❌ ERROR: {error_msg}")
            print(f"   El producto {asin} no tiene dimensiones completas del paquete")
            print(f"   Dimensiones recibidas: {L}×{W}×{H} cm, {KG} kg")
            print(f"   NO se permiten fallbacks - abortando publicación")

            # Retornar None para indicar error fatal
            return None

        # Detectar dimensiones fallback/genéricas (rechazar SIEMPRE)
        is_fallback = False

        # Caso 1: Todas las dimensiones son EXACTAMENTE iguales Y son números redondos
        if L == W == H and L in [1, 5, 10, 15, 20, 25, 30]:
            is_fallback = True
            print(f"❌ Dimensiones fallback detectadas (todas iguales y redondas): {L}×{W}×{H}")

        # Caso 2: Todas las dimensiones muy pequeñas Y peso muy bajo
        if L < 2 and W < 2 and H < 2 and KG < 0.02:
            is_fallback = True
            print(f"❌ Dimensiones y peso extremadamente pequeños: {L}×{W}×{H} cm, {KG} kg")

        if is_fallback:
            print("❌ ERROR: Dimensiones parecen fallback genérico - abortando publicación")
            print("   El producto debe tener dimensiones reales del paquete en Amazon SP-API")
            return None

        base_price = price.get("base_usd", 0)
        tax = price.get("tax_usd", 0)
        cost = price.get("cost_usd", base_price)  # fallback si no hay tax
        net_amount = price.get("net_proceeds_usd") or price.get("final_usd", 0)  # soportar ambos formatos
        mk_pct = price.get("markup_pct", 35)

        # ✅ Si net_amount es 0, calcular con markup
        if not net_amount or net_amount == 0:
            net_amount = base_price * (1 + mk_pct / 100)
            qprint(f"💰 Calculando net_proceeds: ${base_price} + {mk_pct}% = ${net_amount:.2f}")

        # ✅ Redondear a 2 decimales (requerido por ML)
        net_amount = round(net_amount, 2)

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
            qprint(f"💰 Precio: ${base_price} + tax ${tax} = costo ${cost} + {mk_pct}% markup → net proceeds ${net_amount}")
        else:
            qprint(f"💰 Precio: ${base_price} (sin tax) + {mk_pct}% markup → net proceeds ${net_amount}")
        qprint(f"📦 {L}×{W}×{H} cm – {KG} kg")

        # 🔹 Atributos pre-mapeados
        attributes = []
        for aid, info in mini.get("attributes_mapped", {}).items():
            # ✅ Si force_no_gtin está activo, saltar GTIN en attributes_mapped
            if aid == "GTIN" and (mini.get("force_no_gtin") or mini.get("last_error") == "GTIN_REUSED"):
                continue
            val = info.get("value_name") or ""
            if val:
                # ✅ VALIDACIÓN CRÍTICA: Nunca enviar ASIN como GTIN
                if aid == "GTIN" and (str(val).startswith("B0") or len(str(val)) == 10):
                    print(f"⚠️ ASIN '{val}' detectado como GTIN → Omitiendo")
                    continue
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

        qprint(f"🧩 Atributos totales antes de filtrado: {len(attributes)}")

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
            "AGE_RANGE", "AGE_RANGE_DESCRIPTION", "AGE_GROUP",  # AGE_GROUP con valores texto causa error
            "TARGET_GENDER", "GENDER",  # GENDER con valores texto causa error 3510
            "SAFETY", "ASSEMBLY_REQUIRED", "IS_ASSEMBLY_REQUIRED",
            "IS_ADJUSTABLE",  # IS_ADJUSTABLE con valores texto causa error 3510
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
            "IS_STRENGTHENER", "DIAL_COLOR", "DIAL_WINDOW_MATERIAL",
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
            qprint(f"🧹 Filtrados {blacklist_filtered} atributos inválidos (blacklist)")

        # ✅ GARANTIZAR QUE BRAND SIEMPRE ESTÉ PRESENTE
        has_brand = any(a.get("id") == "BRAND" for a in attributes)
        if not has_brand and brand:
            qprint(f"✅ Agregando BRAND obligatorio: {brand}")
            attributes.append({"id": "BRAND", "value_name": brand.title()})
        elif not has_brand:
            print("⚠️ Sin BRAND - usando Generic como fallback")
            attributes.append({"id": "BRAND", "value_name": "Generic"})

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

        # Cargar JSON original de Amazon para extraer campos faltantes con IA
        amazon_json = None
        amazon_json_path = f"storage/asins_json/{asin}.json"
        if os.path.exists(amazon_json_path):
            try:
                with open(amazon_json_path, "r", encoding="utf-8") as f:
                    amazon_json = json.load(f)
            except Exception as e:
                print(f"⚠️ No se pudo cargar JSON de Amazon para {asin}: {e}")

        attributes = autofill_required_attrs(cid, attributes, asin=asin, amazon_json=amazon_json)

        # 🧠 Completar atributos IA (solo usando el JSON transformado mini_ml)
        try:
            qprint(f"🧠 Completando atributos IA (solo con JSON transformado) para categoría {cid}...")

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
                qprint(f"📋 Schema de categoría {cid} tiene {len(valid_attr_ids)} atributos válidos")

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

            # ✅ FILTRO FINAL: Eliminar GTIN si force_no_gtin está activo (evita que IA lo agregue)
            if mini.get("force_no_gtin") or mini.get("last_error") == "GTIN_REUSED":
                pre_gtin_count = len(attributes)
                attributes = [a for a in attributes if a.get("id") != "GTIN"]
                if len(attributes) < pre_gtin_count:
                    print(f"🚫 GTIN removido de atributos finales ({pre_gtin_count - len(attributes)} instancias)")

            if schema_filtered > 0:
                qprint(f"🧹 Filtrados (no en schema de categoría)")
            qprint(f"🧽 Atributos finales IA listos: {len(attributes)} válidos para publicar")

            # 🔧 Convertir value_name en texto a value_id cuando sea necesario
            qprint(f"🔧 Convirtiendo atributos con texto a value_id...")
            attributes = fix_attributes_with_value_ids(cid, attributes)

        except Exception as e:
            print(f"⚠️ Error completando atributos IA solo con mini_ml: {e}")

        # 🔹 Publicación
        body = {
            "title": ai_title_es[:60],
            "category_id": cid,
            "catalog_product": {
                "type": "PRODUCT_WITH_VARIANTS"
            },
            "price": net_amount,  # ← REQUERIDO por ML API
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

    # 🔧 Filtrar países excluidos (para evitar duplicados en retry)
    if excluded_sites:
        original_count = len(sites)
        sites = [s for s in sites if s.get("site_id") not in excluded_sites]
        qprint(f"🚫 Filtrando {original_count - len(sites)} países ya publicados: {', '.join(excluded_sites)}")
        qprint(f"   Publicando solo en: {', '.join([s.get('site_id') for s in sites])}")
        if not sites:
            print("⚠️ ADVERTENCIA: Todos los países fueron excluidos. No hay nada que publicar.")
            return None

    # 🔧 Agregar seller_custom_field (SKU = ASIN) a cada marketplace
    for site in sites:
        site["seller_custom_field"] = asin

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
    # Para CBT (Cross Border Trade), especificar site_id='CBT' + sites_to_sell
    body["site_id"] = "CBT"  # Requerido por ML API
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

    qprint("🚀 Publicando item desde mini_ml ...")

    # Retry inteligente: intentar hasta 2 veces si faltan campos
    max_retries = 2
    item_id = None  # Inicializar antes del loop
    res = None  # Inicializar antes del loop
    for retry_attempt in range(max_retries):
        try:
            res = http_post(f"{API}/global/items", body)
            item_id = res.get("item_id") or res.get("id")

            # Verificar si hay errores en site_items (por país)
            site_items = res.get("site_items", [])
            # ✅ Filtrar solo elementos dict válidos
            has_errors = any(item.get("error") for item in site_items if isinstance(item, dict))

            if not has_errors:
                qprint(f"✅ Publicado → {item_id}")
                break  # Éxito completo, salir del loop

            # Si todos los países tienen error, tratarlo como falla
            all_failed = all(item.get("error") for item in site_items if isinstance(item, dict))
            if not all_failed:
                qprint(f"✅ Publicado → {item_id} (con algunos errores por país)")

                # Mostrar detalles de países exitosos y fallidos
                # CRITERIO: Si tiene item_id → éxito (aunque tenga warnings)
                #           Si NO tiene item_id Y tiene error → falla real
                # NOTA: Un país puede aparecer múltiples veces (retry interno),
                #       priorizar las versiones con item_id
                success_countries_dict = {}  # site_id → True si tiene item_id
                failed_countries_dict = {}   # site_id → error info

                # Primerapasada: recopilar todos los estados por país
                for item in site_items:
                    # ✅ Saltar elementos que no son diccionarios
                    if not isinstance(item, dict):
                        continue
                    site_id = item.get("site_id", "Unknown")
                    has_item_id = bool(item.get("item_id"))
                    has_error = bool(item.get("error"))

                    # Si tiene item_id → éxito (marca país como exitoso)
                    if has_item_id:
                        success_countries_dict[site_id] = True
                        # Remover de fallidos si estaba ahí
                        failed_countries_dict.pop(site_id, None)
                    # Si NO tiene item_id pero SÍ tiene error → falla (pero solo si no hay éxito previo)
                    elif has_error and site_id not in success_countries_dict:
                        error_obj = item["error"]

                        # ✅ Verificar si error_obj es un dict o un string
                        if isinstance(error_obj, dict):
                            error_msg = error_obj.get("message", "Unknown error")
                            causes = error_obj.get("cause", [])
                        else:
                            # Si es un string, usarlo directamente
                            error_msg = str(error_obj)
                            causes = []

                        # Extraer detalles de los causes
                        cause_details = []
                        for cause in causes:
                            if isinstance(cause, dict):
                                cause_msg = cause.get("message", "")
                                cause_code = cause.get("code", "")
                                if cause_msg:
                                    cause_details.append(f"{cause_code}: {cause_msg}")

                        if cause_details:
                            failed_countries_dict[site_id] = {
                                "site": site_id,
                                "error": error_msg,
                                "causes": cause_details
                            }
                        else:
                            failed_countries_dict[site_id] = {
                                "site": site_id,
                                "error": error_msg,
                                "causes": []
                            }
                    # Ni item_id ni error → considerar éxito (caso raro)
                    elif site_id not in success_countries_dict:
                        success_countries_dict[site_id] = True

                # Convertir dicts a listas
                success_countries = list(success_countries_dict.keys())
                failed_countries = list(failed_countries_dict.values())

                if success_countries:
                    qprint(f"   ✅ Países exitosos: {', '.join(success_countries)}")
                if failed_countries:
                    qprint(f"   ❌ Países fallidos:")
                    for fc in failed_countries:
                        print(f"      • {fc['site']}: {fc['error']}")
                        if fc['causes']:
                            for cause in fc['causes']:
                                print(f"         → {cause}")

                break  # Publicación parcial, salir del loop

            # Todos fallaron - extraer errores para retry
            error_messages = []
            for item in site_items:
                # ✅ Saltar elementos que no son diccionarios
                if isinstance(item, dict) and item.get("error"):
                    error_messages.append(json.dumps(item["error"]))
            error_text = " | ".join(error_messages)

            print(f"⚠️ Todos los países fallaron: {error_text[:200]}...")

            # Crear RuntimeError artificial para activar retry logic
            raise RuntimeError(f"All countries failed: {error_text}")

        except RuntimeError as e:
            error_text = str(e)

            # Si es el último intento, re-raise el error
            if retry_attempt >= max_retries - 1:
                raise

            # Parsear error para detectar campos faltantes
            missing_field_ids = parse_ml_error_for_missing_fields(error_text)

            if not missing_field_ids:
                # No hay campos faltantes detectables, re-raise error
                raise

            # Intentar extraer campos faltantes con IA
            qprint(f"🤖 Reintento {retry_attempt + 1}/{max_retries}: Extrayendo campos faltantes con IA...")

            # Crear lista de "campos requeridos" ficticios para ai_extract_missing_fields
            fake_required_fields = [
                {"id": field_id, "name": field_id.replace("_", " ").title(), "value_type": "string"}
                for field_id in missing_field_ids
            ]

            extracted_values = ai_extract_missing_fields(asin, amazon_json, fake_required_fields)

            if not extracted_values:
                print("⚠️ IA no pudo extraer los campos faltantes")
                raise

            # Agregar campos extraídos a los atributos
            for field_id, value in extracted_values.items():
                if value:
                    qprint(f"   ✅ Agregando {field_id} = {value}")
                    body["attributes"].append({
                        "id": field_id,
                        "value_name": str(value)
                    })

            # Actualizar body y reintentar
            qprint("🔄 Reintentando publicación con campos agregados...")
            continue  # Volver al inicio del loop para reintentar

    # Guardar en la base de datos para sincronización
    try:
        from scripts.tools.save_listing_data import save_listing, init_database
        init_database()  # Asegurarse de que existe la BD

        # Extraer site_items de la respuesta (países donde se publicó exitosamente)
        site_items = res.get("site_items", []) if res else []

        save_listing(
            item_id=item_id,
            mini_ml=mini,
            marketplaces=mini.get("marketplaces", ["MLM", "MLB", "MLC", "MCO", "MLA"]),
            site_items=site_items
        )
        qprint(f"💾 Guardado en BD para sincronización: {mini.get('asin', 'N/A')} → {item_id}")
        if site_items:
            # País activo = tiene item_id (publicación exitosa)
            # ✅ Filtrar solo elementos dict válidos antes de acceder con .get()
            active_countries = [s.get("site_id") for s in site_items if isinstance(s, dict) and s.get("item_id")]
            if active_countries:
                print(f"   Países activos: {', '.join(active_countries)}")
    except Exception as e:
        print(f"⚠️ Error guardando en BD (no crítico): {e}")
        import traceback
        traceback.print_exc()  # Mostrar traceback completo para debugging

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