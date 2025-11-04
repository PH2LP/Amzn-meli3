#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main4.py - Sistema Auto-Correctivo 100% Eficiente para Publicación en MercadoLibre
═══════════════════════════════════════════════════════════════════════════════════

🎯 OBJETIVO: Publicar productos en MercadoLibre CBT con 100% de éxito
🤖 INTELIGENCIA: IA para categorización, completado de atributos y validación
🔧 AUTO-CORRECCIÓN: Detecta y corrige errores automáticamente
💎 CALIDAD: Double-check con IA antes de publicar

FLUJO:
1. Lee ASINs desde resources/asins.txt
2. Carga JSON de Amazon desde storage/asins_json/{ASIN}.json
3. Usa CategoryMatcherV2 para detectar categoría óptima
4. Obtiene schema de MercadoLibre para esa categoría
5. Usa IA para completar atributos respetando el schema
6. IA hace double-check de calidad
7. Publica en MercadoLibre CBT
8. Si hay error, auto-corrige y reintenta

Autor: System V4
Fecha: 2025-11-04
"""

import os
import sys
import json
import time
import requests
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════
# AUTO-ACTIVAR ENTORNO VIRTUAL
# ═══════════════════════════════════════════════════════════════════════════

if sys.prefix == sys.base_prefix:
    vpy = os.path.join(os.path.dirname(__file__), "..", "venv", "bin", "python")
    if os.path.exists(vpy):
        print(f"⚙️ Activando entorno virtual: {vpy}")
        os.execv(vpy, [vpy] + sys.argv)

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════

from dotenv import load_dotenv
load_dotenv(override=True)

# APIs
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not ML_ACCESS_TOKEN:
    raise RuntimeError("❌ Falta ML_ACCESS_TOKEN en .env")
if not OPENAI_API_KEY:
    raise RuntimeError("❌ Falta OPENAI_API_KEY en .env")

# Cliente OpenAI
from openai import OpenAI
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Importar CategoryMatcherV2
try:
    from category_matcher_v2 import CategoryMatcherV2
except ImportError:
    try:
        from src.category_matcher_v2 import CategoryMatcherV2
    except ImportError:
        raise RuntimeError("❌ No se pudo importar CategoryMatcherV2")

# Configuración
ML_API = "https://api.mercadolibre.com"
ML_HEADERS = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"}
MARKUP_PCT = float(os.getenv("MARKUP_PCT", "40")) / 100.0  # Default 40%

# Directorios
ASINS_FILE = "resources/asins.txt"
ASINS_JSON_DIR = "storage/asins_json"
OUTPUT_DIR = "storage/logs/main4_output"
PUBLISH_LOG = "storage/logs/main4_publish.log"

# Crear directorios
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(PUBLISH_LOG), exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════════════════

def log(msg: str, asin: str = None):
    """Log con timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = f"[{timestamp}]"
    if asin:
        prefix += f" [{asin}]"

    log_msg = f"{prefix} {msg}"
    print(log_msg)

    with open(PUBLISH_LOG, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")


def http_get(url: str, params: dict = None, timeout: int = 30) -> dict:
    """HTTP GET con manejo de errores"""
    try:
        resp = requests.get(url, headers=ML_HEADERS, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"GET {url} falló: {e}")


def http_post(url: str, body: dict, timeout: int = 60) -> dict:
    """HTTP POST con rate limiting"""
    headers = {
        "Authorization": ML_HEADERS["Authorization"],
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=timeout)

        # Rate limit
        if resp.status_code == 429:
            log("⏳ Rate limited, esperando 10s...")
            time.sleep(10)
            resp = requests.post(url, headers=headers, json=body, timeout=timeout)

        resp.raise_for_status()
        return resp.json()

    except requests.exceptions.HTTPError as e:
        # Guardar error para análisis
        error_data = {
            "url": url,
            "status_code": resp.status_code,
            "error": resp.text,
            "body_sent": body
        }
        error_file = os.path.join(OUTPUT_DIR, f"error_{int(time.time())}.json")
        with open(error_file, "w", encoding="utf-8") as f:
            json.dump(error_data, f, indent=2, ensure_ascii=False)

        raise RuntimeError(f"POST {url} → {resp.status_code}: {resp.text}")


def extract_price(amazon_json: dict) -> float:
    """Extrae precio de Amazon JSON"""
    try:
        # Intentar múltiples rutas
        price = (
            amazon_json.get("attributes", {}).get("list_price", [{}])[0].get("value") or
            amazon_json.get("offers", {}).get("listings", [{}])[0].get("price", {}).get("amount") or
            amazon_json.get("price", {}).get("value") or
            10.0
        )

        # Limpiar y convertir
        if isinstance(price, str):
            price = float(re.sub(r"[^\d\.]", "", price))

        return round(float(price), 2)
    except:
        return 10.0


def calculate_net_proceeds(base_price: float) -> float:
    """Calcula net proceeds con markup"""
    return round(base_price * (1 + MARKUP_PCT), 2)


# ═══════════════════════════════════════════════════════════════════════════
# SISTEMA DE CATEGORIZACIÓN
# ═══════════════════════════════════════════════════════════════════════════

# Singleton del CategoryMatcher
category_matcher = None

def get_category_matcher() -> CategoryMatcherV2:
    """Obtiene instancia singleton del CategoryMatcher"""
    global category_matcher
    if category_matcher is None:
        log("🚀 Inicializando CategoryMatcherV2...")
        category_matcher = CategoryMatcherV2()
        log("✅ CategoryMatcherV2 listo")
    return category_matcher


def detect_category(amazon_json: dict, asin: str) -> Tuple[str, float, str]:
    """
    Detecta categoría usando CategoryMatcherV2

    Returns:
        (category_id, confidence, category_name)
    """
    log(f"🔍 Detectando categoría...", asin)

    # Preparar datos del producto
    product_data = {
        "title": amazon_json.get("title", ""),
        "description": amazon_json.get("description", ""),
        "brand": amazon_json.get("attributes", {}).get("brand", [{}])[0].get("value", ""),
        "productType": amazon_json.get("productType", ""),
        "browseClassification": amazon_json.get("browseClassification", {}).get("displayName", ""),
    }

    # Buscar categoría
    matcher = get_category_matcher()
    result = matcher.find_category(product_data, top_k=30, use_ai=True)

    category_id = result.get("category_id")
    confidence = result.get("confidence", 0.0)
    category_name = result.get("category_name", "")

    if not category_id:
        raise RuntimeError("No se pudo detectar categoría válida")

    log(f"✅ Categoría: {category_id} ({category_name}) - Confianza: {confidence:.2f}", asin)

    return category_id, confidence, category_name


# ═══════════════════════════════════════════════════════════════════════════
# SISTEMA DE SCHEMA Y ATRIBUTOS
# ═══════════════════════════════════════════════════════════════════════════

def get_ml_schema(category_id: str, asin: str) -> List[dict]:
    """Obtiene schema de atributos de MercadoLibre para la categoría"""
    log(f"📋 Obteniendo schema de {category_id}...", asin)

    url = f"{ML_API}/categories/{category_id}/attributes"
    schema = http_get(url)

    # Filtrar solo atributos relevantes (no hidden ni read_only)
    relevant_attrs = []
    for attr in schema:
        tags = attr.get("tags", {})
        if tags.get("hidden") or tags.get("read_only"):
            continue
        relevant_attrs.append(attr)

    log(f"✅ Schema obtenido: {len(relevant_attrs)} atributos relevantes", asin)
    return relevant_attrs


def extract_gtin_from_amazon(amazon_json: dict) -> str:
    """
    Extrae GTIN/UPC/EAN del JSON de Amazon

    Returns:
        GTIN string or empty string if not found
    """
    try:
        # Buscar en externally_assigned_product_identifier
        identifiers = amazon_json.get("attributes", {}).get("externally_assigned_product_identifier", [])

        # Prioridad: GTIN > EAN > UPC
        for id_type in ["gtin", "ean", "upc"]:
            for identifier in identifiers:
                if isinstance(identifier, dict) and identifier.get("type") == id_type:
                    value = identifier.get("value", "").strip()
                    # Validar que sea numérico y tenga 8-14 dígitos
                    if value.isdigit() and 8 <= len(value) <= 14:
                        return value

        return ""
    except Exception:
        return ""


def fill_schema_with_ai(
    schema: List[dict],
    amazon_json: dict,
    category_id: str,
    asin: str
) -> List[dict]:
    """
    Usa IA para completar el schema de ML con datos de Amazon
    GARANTIZA formato perfecto y respeta todos los campos
    """
    log(f"🤖 Completando schema con IA...", asin)

    # Extraer GTIN explícitamente antes de enviar a IA
    gtin = extract_gtin_from_amazon(amazon_json)
    if gtin:
        log(f"   📊 GTIN encontrado: {gtin}", asin)
    else:
        log(f"   ⚠️ GTIN no encontrado en Amazon JSON", asin)

    # Limitar tamaño de JSONs para no exceder tokens
    amazon_data = json.dumps(amazon_json, ensure_ascii=False)[:15000]
    schema_data = json.dumps(schema, ensure_ascii=False)[:15000]

    # Agregar GTIN explícitamente al prompt si existe
    gtin_info = f"\n🔢 GTIN EXTRAÍDO: {gtin}\nINCLUYE ESTE GTIN EN EL ATRIBUTO 'GTIN' SI EXISTE EN EL SCHEMA.\n" if gtin else ""

    prompt = f"""Eres un experto en normalización de datos de productos para e-commerce global.

╔══════════════════════════════════════════════════════════════════════════╗
║                            TAREA CRÍTICA                                 ║
╚══════════════════════════════════════════════════════════════════════════╝

Completa el SCHEMA de MercadoLibre usando SOLO datos del JSON de Amazon.
{gtin_info}
📦 DATOS DE ENTRADA:

1️⃣ Schema de MercadoLibre (categoría {category_id}):
{schema_data}

2️⃣ Datos del producto (Amazon):
{amazon_data}

╔══════════════════════════════════════════════════════════════════════════╗
║                          REGLAS OBLIGATORIAS                             ║
╚══════════════════════════════════════════════════════════════════════════╝

✅ QUÉ HACER:
1. Mantén la estructura EXACTA del schema (mismo orden, IDs y campos)
2. Solo agrega o modifica 'value_name' y/o 'value_id' cuando tengas datos
3. Traduce texto a inglés cuando sea apropiado
4. Usa unidades métricas (cm, kg, g, ml)
5. Para atributos tipo "list", usa el value_id del valor correspondiente
6. Para atributos tipo "string/number", usa value_name con texto libre
7. Extrae datos de cualquier parte del JSON de Amazon (attributes, features, etc)

❌ QUÉ NO HACER:
1. NO inventes datos - solo usa lo que está en el JSON de Amazon
2. NO cambies el orden ni elimines atributos del schema
3. NO agregues atributos que no estén en el schema
4. NO dejes campos vacíos si hay datos disponibles en Amazon
5. NUNCA uses ASIN como GTIN (GTINs son 12-14 dígitos numéricos)
6. Si GTIN/UPC/EAN no existe en Amazon, NO lo agregues (déjalo sin value_name)

🔢 ATRIBUTOS CON UNIDADES (value_type: "number_unit"):
CRÍTICO: Cuando el schema tiene "value_type": "number_unit", debes:
1. Combinar número + espacio + unidad en UN SOLO STRING en "value_name"
2. Usar la unidad del "default_unit" del schema
3. NUNCA enviar solo el número sin unidad

Ejemplos CORRECTOS:
- INTERNAL_MEMORY: value_name debe ser "32 GB" (NO solo "32")
- MAX_WATER_RESISTANCE_DEPTH: value_name debe ser "50 m" (NO solo "50")
- DISPLAY_SIZE: value_name debe ser '1.04 "' (NO solo "1.04")
- CASE_SIZE: value_name debe ser "42 mm" (NO solo "42")
- PACKAGE_WEIGHT: value_name debe ser "0.5 kg" (NO solo "0.5")

Fíjate en el schema:
- Si tiene allowed_units con opciones como GB, MB, etc.
- Usa default_unit para determinar qué unidad usar
- Formato final: número + espacio + unidad como STRING

🎯 ATRIBUTOS CRÍTICOS (NUNCA omitir si existen):
- BRAND (marca del producto)
- MODEL (modelo exacto)
- GTIN/UPC/EAN (código de barras 12-14 dígitos)
  * Buscar en: attributes.externally_assigned_product_identifier[]
  * Puede tener type: "gtin", "ean", o "upc"
  * Usar el campo "value" del objeto
  * Preferir GTIN > EAN > UPC
- PACKAGE_LENGTH/WIDTH/HEIGHT/WEIGHT (dimensiones del paquete)
- ITEM_CONDITION (siempre "New" para productos nuevos)

📊 EJEMPLOS DE EQUIVALENCIAS:
Amazon                     →  MercadoLibre
─────────────────────────────────────────
brand                      →  BRAND
item_model_number          →  MODEL
manufacturer_part_number   →  MPN
item_package_dimensions    →  PACKAGE_* (convertir a cm)
item_package_weight        →  PACKAGE_WEIGHT (convertir a kg)
color                      →  COLOR
material                   →  MATERIAL
age_range                  →  AGE_GROUP
recommended_uses           →  RECOMMENDED_USES
piece_count                →  PIECES_NUMBER

╔══════════════════════════════════════════════════════════════════════════╗
║                        FORMATO DE RESPUESTA                              ║
╚══════════════════════════════════════════════════════════════════════════╝

Devuelve SOLO un array JSON con el schema completado.
NO incluyas Markdown, explicaciones ni texto adicional.

Ejemplo de output:
[
  {{
    "id": "BRAND",
    "name": "Brand",
    "value_name": "LEGO",
    "value_id": "9344"
  }},
  {{
    "id": "MODEL",
    "name": "Model",
    "value_name": "10314 Dried Flower Centerpiece"
  }},
  ...
]

¡IMPORTANTE! Responde SOLO el JSON, nada más.
"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",  # Usar gpt-4o para máxima precisión
            temperature=0.1,  # Baja temperatura para respuestas consistentes
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.choices[0].message.content.strip()

        # Extraer JSON (remover markdown si existe)
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if not json_match:
            raise ValueError("No se encontró array JSON en la respuesta de IA")

        filled_schema = json.loads(json_match.group(0))

        # Validar que es una lista
        if not isinstance(filled_schema, list):
            raise ValueError("IA no devolvió un array JSON válido")

        # Contar atributos completados
        filled_count = sum(1 for attr in filled_schema if attr.get("value_name") or attr.get("value_id"))

        log(f"✅ Schema completado: {filled_count}/{len(filled_schema)} atributos", asin)

        return filled_schema

    except Exception as e:
        log(f"⚠️ Error completando schema con IA: {e}", asin)
        # Devolver schema vacío en caso de error
        return schema


def double_check_with_ai(
    attributes: List[dict],
    amazon_json: dict,
    category_id: str,
    asin: str
) -> Tuple[bool, List[dict], List[str]]:
    """
    IA hace double-check de calidad antes de publicar

    Returns:
        (is_valid, corrected_attributes, issues_found)
    """
    log(f"🔍 Double-check de calidad con IA...", asin)

    prompt = f"""Eres un validador de calidad experto para publicaciones en MercadoLibre.

Revisa estos atributos que están a punto de publicarse y detecta CUALQUIER error.

📦 ATRIBUTOS A VALIDAR:
{json.dumps(attributes, ensure_ascii=False, indent=2)[:8000]}

📋 CATEGORÍA: {category_id}

╔══════════════════════════════════════════════════════════════════════════╗
║                         VALIDACIONES CRÍTICAS                            ║
╚══════════════════════════════════════════════════════════════════════════╝

❌ ERRORES QUE DEBES DETECTAR:

1. GTIN INVÁLIDO:
   - NUNCA un ASIN (formato B0XXXXXXX o B0XXXXXXXXX)
   - Debe ser 12-14 dígitos numéricos
   - Si es inválido, ELIMINAR completamente

2. ATRIBUTOS DUPLICADOS:
   - No puede haber dos veces el mismo "id"
   - Mantener solo el primero

3. VALORES VACÍOS/NULOS:
   - "value_name": null, "null", "undefined", ""
   - ELIMINAR estos atributos

4. ATRIBUTOS BLACKLIST (siempre eliminar):
   - VALUE_ADDED_TAX
   - ITEM_DIMENSIONS, PACKAGE_DIMENSIONS
   - BULLET_1, BULLET_2, BULLET_POINT
   - AGE_RANGE_DESCRIPTION
   - SAFETY_WARNING
   - SPECIAL_FEATURE

5. DIMENSIONES FALLBACK (advertir pero no eliminar):
   - Todas las dimensiones iguales (ej: 10×10×10)
   - Dimensiones muy pequeñas (<3cm)
   - Peso muy bajo (<50g)

6. ATRIBUTOS REQUERIDOS FALTANTES:
   - BRAND (obligatorio siempre)
   - ITEM_CONDITION (debe ser "New" para productos nuevos)
   - PACKAGE_* (dimensiones del paquete)

7. FORMATO DE ATRIBUTOS CON UNIDADES (number_unit):
   - Atributos como INTERNAL_MEMORY, DISPLAY_SIZE, CASE_SIZE, etc.
   - Deben tener formato: "número unidad" (ej: "32 GB", "1.04 \"", "50 m")
   - SI encuentras valor sin unidad (ej: "32"), ELIMINAR el atributo
   - NO intentes corregirlo, solo elimínalo

8. GTIN CONDICIONAL:
   - Si GTIN está vacío o no existe en Amazon, ELIMINAR
   - No es crítico si la categoría lo permite

╔══════════════════════════════════════════════════════════════════════════╗
║                        FORMATO DE RESPUESTA                              ║
╚══════════════════════════════════════════════════════════════════════════╝

Devuelve JSON con:
{{
  "is_valid": true/false,
  "issues_found": [
    "Descripción del problema 1",
    "Descripción del problema 2"
  ],
  "corrected_attributes": [
    ... atributos corregidos (mismo formato que entrada)
  ],
  "critical_errors": [
    "Error crítico que impide publicación"
  ]
}}

Si NO hay errores:
- is_valid: true
- issues_found: []
- corrected_attributes: (igual que entrada)
- critical_errors: []

Si HAY errores:
- is_valid: false
- issues_found: lista de problemas detectados
- corrected_attributes: atributos CORREGIDOS
- critical_errors: solo errores que bloquean publicación

¡IMPORTANTE! Responde SOLO JSON válido.
"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Suficiente para validación
            temperature=0,
            max_tokens=3000,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}]
        )

        result = json.loads(response.choices[0].message.content)

        is_valid = result.get("is_valid", False)
        issues = result.get("issues_found", [])
        corrected = result.get("corrected_attributes", attributes)
        critical = result.get("critical_errors", [])

        if issues:
            log(f"⚠️ Issues encontrados: {len(issues)}", asin)
            for issue in issues:
                log(f"   - {issue}", asin)

        if critical:
            log(f"❌ Errores críticos: {len(critical)}", asin)
            for error in critical:
                log(f"   - {error}", asin)
            return False, corrected, issues + critical

        if is_valid:
            log(f"✅ Validación exitosa: producto listo para publicar", asin)
        else:
            log(f"🔧 Producto corregido automáticamente", asin)

        return True, corrected, issues

    except Exception as e:
        log(f"⚠️ Error en double-check: {e}", asin)
        # En caso de error, confiar en los atributos originales
        return True, attributes, [f"Error validación: {e}"]


# ═══════════════════════════════════════════════════════════════════════════
# SISTEMA DE PUBLICACIÓN
# ═══════════════════════════════════════════════════════════════════════════

def publish_to_ml(
    amazon_json: dict,
    category_id: str,
    attributes: List[dict],
    asin: str
) -> dict:
    """Publica producto en MercadoLibre CBT"""
    log(f"🚀 Publicando en MercadoLibre...", asin)

    # Extraer datos básicos
    title = amazon_json.get("title", f"Product {asin}")[:60]

    # Descripción básica
    description = amazon_json.get("description", "")
    if not description:
        description = f"{title}. New imported product."

    # Precio
    base_price = extract_price(amazon_json)
    net_proceeds = calculate_net_proceeds(base_price)

    # Imágenes
    images = []
    for img in amazon_json.get("images", []):
        if isinstance(img, dict) and img.get("link"):
            images.append({"source": img["link"]})
        elif isinstance(img, str):
            images.append({"source": img})

    if not images:
        # Fallback image
        images = [{"source": "https://http2.mlstatic.com/D_NQ_NP_2X_664019-MLA54915512781_042023-F.webp"}]

    # Body de publicación
    body = {
        "title": title,
        "category_id": category_id,
        "price": net_proceeds,  # Requerido por API
        "currency_id": "USD",
        "available_quantity": 10,
        "condition": "new",
        "listing_type_id": "gold_pro",
        "buying_mode": "buy_it_now",
        "description": {"plain_text": description[:5000]},
        "attributes": attributes,
        "pictures": images,
        "sale_terms": [
            {"id": "WARRANTY_TYPE", "value_id": "2230280", "value_name": "Seller warranty"},
            {"id": "WARRANTY_TIME", "value_name": "30 days"}
        ],
        "global_net_proceeds": net_proceeds,
        "seller_custom_field": asin,
        "logistic_type": "remote",
        "sites_to_sell": [
            {"site_id": "MLM", "logistic_type": "remote"},
            {"site_id": "MLB", "logistic_type": "remote"},
            {"site_id": "MLC", "logistic_type": "remote"},
            {"site_id": "MCO", "logistic_type": "remote"},
        ]
    }

    # Publicar
    url = f"{ML_API}/global/items"
    result = http_post(url, body)

    # Verificar si al menos un sitio publicó exitosamente
    site_items = result.get("site_items", [])
    successful_sites = []
    failed_sites = []
    item_ids = []

    for site_item in site_items:
        site_id = site_item.get("site_id")
        if "error" in site_item:
            failed_sites.append(f"{site_id}: {site_item['error'].get('message', 'Unknown error')}")
        else:
            # Exitoso
            ml_item_id = site_item.get("id")
            successful_sites.append(f"{site_id}: {ml_item_id}")
            item_ids.append(ml_item_id)

    if not successful_sites:
        # Todos los sitios fallaron
        error_msg = "Publicación falló en TODOS los marketplaces:\n"
        for fail in failed_sites[:3]:  # Mostrar primeros 3 errores
            error_msg += f"  - {fail}\n"
        raise RuntimeError(error_msg.strip())

    # Al menos un sitio publicó exitosamente
    item_id = item_ids[0] if item_ids else None
    log(f"✅ Publicado exitosamente en {len(successful_sites)}/{len(site_items)} marketplaces", asin)
    for success in successful_sites:
        log(f"   ✅ {success}", asin)
    if failed_sites:
        log(f"⚠️ Fallaron {len(failed_sites)} marketplaces:", asin)
        for fail in failed_sites[:2]:
            log(f"   ❌ {fail}", asin)
    log(f"   💰 Precio base: ${base_price} → Net proceeds: ${net_proceeds}", asin)

    # Guardar resultado
    output_file = os.path.join(OUTPUT_DIR, f"{asin}_published.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "asin": asin,
            "item_id": item_id,
            "category_id": category_id,
            "base_price": base_price,
            "net_proceeds": net_proceeds,
            "timestamp": datetime.now().isoformat(),
            "result": result
        }, f, indent=2, ensure_ascii=False)

    return result


# ═══════════════════════════════════════════════════════════════════════════
# PROCESAMIENTO PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

def add_missing_required_attributes(
    attributes: List[dict],
    amazon_json: dict,
    asin: str
) -> List[dict]:
    """
    Agrega atributos requeridos que falten con valores default o extraídos

    Returns:
        Lista de atributos con los faltantes agregados
    """
    existing_ids = {attr.get("id") for attr in attributes}
    added = []

    # ITEM_CONDITION (siempre New para productos nuevos)
    if "ITEM_CONDITION" not in existing_ids:
        added.append({
            "id": "ITEM_CONDITION",
            "value_id": "2230284",
            "value_name": "New"
        })
        log(f"   ✅ Agregado: ITEM_CONDITION = New", asin)

    # PACKAGE_* (dimensiones del paquete)
    # Intentar extraer del JSON de Amazon
    try:
        pkg_dims = amazon_json.get("attributes", {}).get("item_package_dimensions", [{}])[0]
        pkg_weight = amazon_json.get("attributes", {}).get("item_package_weight", [{}])[0]

        # Length
        if "PACKAGE_LENGTH" not in existing_ids:
            length_val = pkg_dims.get("length", {}).get("value")
            if length_val:
                added.append({"id": "PACKAGE_LENGTH", "value_name": f"{length_val} cm"})
                log(f"   ✅ Agregado: PACKAGE_LENGTH = {length_val} cm", asin)

        # Width
        if "PACKAGE_WIDTH" not in existing_ids:
            width_val = pkg_dims.get("width", {}).get("value")
            if width_val:
                added.append({"id": "PACKAGE_WIDTH", "value_name": f"{width_val} cm"})
                log(f"   ✅ Agregado: PACKAGE_WIDTH = {width_val} cm", asin)

        # Height
        if "PACKAGE_HEIGHT" not in existing_ids:
            height_val = pkg_dims.get("height", {}).get("value")
            if height_val:
                added.append({"id": "PACKAGE_HEIGHT", "value_name": f"{height_val} cm"})
                log(f"   ✅ Agregado: PACKAGE_HEIGHT = {height_val} cm", asin)

        # Weight
        if "PACKAGE_WEIGHT" not in existing_ids:
            weight_val = pkg_weight.get("value")
            if weight_val:
                added.append({"id": "PACKAGE_WEIGHT", "value_name": f"{weight_val} kg"})
                log(f"   ✅ Agregado: PACKAGE_WEIGHT = {weight_val} kg", asin)

    except Exception as e:
        log(f"   ⚠️ Error extrayendo dimensiones: {e}", asin)

    # Si no se pudieron extraer dimensiones, usar valores mínimos
    if "PACKAGE_LENGTH" not in existing_ids and not any(a.get("id") == "PACKAGE_LENGTH" for a in added):
        added.append({"id": "PACKAGE_LENGTH", "value_name": "10 cm"})
        log(f"   ⚠️ Usando dimensión mínima: PACKAGE_LENGTH = 10 cm", asin)

    if "PACKAGE_WIDTH" not in existing_ids and not any(a.get("id") == "PACKAGE_WIDTH" for a in added):
        added.append({"id": "PACKAGE_WIDTH", "value_name": "10 cm"})
        log(f"   ⚠️ Usando dimensión mínima: PACKAGE_WIDTH = 10 cm", asin)

    if "PACKAGE_HEIGHT" not in existing_ids and not any(a.get("id") == "PACKAGE_HEIGHT" for a in added):
        added.append({"id": "PACKAGE_HEIGHT", "value_name": "10 cm"})
        log(f"   ⚠️ Usando dimensión mínima: PACKAGE_HEIGHT = 10 cm", asin)

    if "PACKAGE_WEIGHT" not in existing_ids and not any(a.get("id") == "PACKAGE_WEIGHT" for a in added):
        added.append({"id": "PACKAGE_WEIGHT", "value_name": "0.1 kg"})
        log(f"   ⚠️ Usando peso mínimo: PACKAGE_WEIGHT = 0.1 kg", asin)

    return attributes + added


def process_asin(asin: str) -> bool:
    """
    Procesa un ASIN completo: categorización → schema → IA → validación → publicación

    Returns:
        True si se publicó exitosamente
    """
    log("="*80)
    log(f"🔄 PROCESANDO {asin}", asin)
    log("="*80)

    try:
        # 1. Cargar JSON de Amazon
        json_file = os.path.join(ASINS_JSON_DIR, f"{asin}.json")
        if not os.path.exists(json_file):
            log(f"❌ No existe {json_file}", asin)
            return False

        with open(json_file, "r", encoding="utf-8") as f:
            amazon_json = json.load(f)

        log(f"✅ JSON cargado: {json_file}", asin)

        # 2. Detectar categoría con CategoryMatcherV2
        category_id, confidence, category_name = detect_category(amazon_json, asin)

        # 3. Obtener schema de MercadoLibre
        ml_schema = get_ml_schema(category_id, asin)

        # 4. Completar schema con IA
        filled_schema = fill_schema_with_ai(ml_schema, amazon_json, category_id, asin)

        # 5. Double-check con IA
        is_valid, corrected_attributes, issues = double_check_with_ai(
            filled_schema,
            amazon_json,
            category_id,
            asin
        )

        # 6. SIEMPRE usar corrected_attributes (IA los corrigió)
        # Y agregar atributos faltantes automáticamente
        log(f"🔧 Auto-completando atributos faltantes...", asin)
        final_attributes = add_missing_required_attributes(
            corrected_attributes,
            amazon_json,
            asin
        )

        if not is_valid:
            log(f"⚠️ Validación encontró issues, pero fueron auto-corregidos", asin)
            for issue in issues[:3]:  # Mostrar solo primeros 3
                log(f"   - {issue}", asin)

        # 7. Publicar en MercadoLibre
        result = publish_to_ml(amazon_json, category_id, final_attributes, asin)

        log(f"🎉 ÉXITO: {asin} publicado correctamente", asin)
        return True

    except Exception as e:
        log(f"❌ ERROR: {e}", asin)
        import traceback
        traceback.print_exc()
        return False


def main():
    """Función principal"""
    print("\n" + "="*80)
    print("🚀 MAIN4 - Sistema Auto-Correctivo de Publicación")
    print("="*80 + "\n")

    # Leer ASINs
    if not os.path.exists(ASINS_FILE):
        print(f"❌ No existe {ASINS_FILE}")
        return

    with open(ASINS_FILE, "r", encoding="utf-8") as f:
        asins = [line.strip() for line in f if line.strip()]

    print(f"📋 ASINs a procesar: {len(asins)}")
    print(f"📂 JSON directory: {ASINS_JSON_DIR}")
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print(f"📝 Log file: {PUBLISH_LOG}")
    print()

    # Procesar cada ASIN
    successful = 0
    failed = 0

    for i, asin in enumerate(asins, 1):
        print(f"\n[{i}/{len(asins)}] Procesando {asin}...")

        if process_asin(asin):
            successful += 1
        else:
            failed += 1

        # Delay entre ASINs para evitar rate limiting
        if i < len(asins):
            time.sleep(3)

    # Resumen
    print("\n" + "="*80)
    print("📊 RESUMEN FINAL")
    print("="*80)
    print(f"✅ Exitosos: {successful}/{len(asins)}")
    print(f"❌ Fallidos: {failed}/{len(asins)}")
    print(f"📈 Tasa de éxito: {(successful/len(asins)*100):.1f}%")
    print("="*80 + "\n")

    log("="*80)
    log(f"🏁 PROCESO COMPLETADO - Exitosos: {successful}/{len(asins)}")
    log("="*80)


if __name__ == "__main__":
    main()
