import requests
import json
import os
import re

if sys.prefix == sys.base_prefix:
    venv_python = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
    if os.path.exists(venv_python):
        print(f"⚙️ Activando entorno virtual automáticamente desde {venv_python}...")
        os.execv(venv_python, [venv_python] + sys.argv)
    else:
        print("⚠️ No se encontró el entorno virtual (venv). Créalo con: python3.11 -m venv venv")
        sys.exit(1)

CACHE_DIR = "cache/categories"
os.makedirs(CACHE_DIR, exist_ok=True)


# ======================================================
# 🔍 Obtener estructura de atributos por categoría
# ======================================================

def get_required_attributes(category_id: str) -> list:
    """Devuelve todos los atributos requeridos y opcionales de una categoría CBT."""
    cache_path = os.path.join(CACHE_DIR, f"{category_id}.json")

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("all", [])
        except Exception:
            pass

    url = f"https://api.mercadolibre.com/categories/{category_id}/attributes"
    print(f"🔍 Consultando atributos para categoría {category_id}...")

    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ Error HTTP {r.status_code}: {r.text}")
            return []

        data = r.json()
        all_attrs = [a["id"] for a in data]
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"all": all_attrs}, f, indent=2, ensure_ascii=False)
        return all_attrs
    except Exception as e:
        print(f"❌ Error obteniendo atributos: {e}")
        return []


# ======================================================
# 🧠 Mapeo inteligente de atributos Amazon → MercadoLibre
# ======================================================

def map_amazon_to_meli_attrs(asin_data: dict, category_id: str) -> list:
    """Crea una lista de atributos reales usando los datos del JSON de Amazon."""
    attrs = []
    add = lambda _id, val: attrs.append({"id": _id, "value_name": str(val).strip()})

    # Campos base
    brand = asin_data.get("brand") or "Unbranded"
    add("BRAND", brand)

    color = asin_data.get("color") or detect_color_from_title(asin_data.get("title", ""))
    if color:
        add("COLOR", color)

    material = asin_data.get("material")
    if material:
        add("MATERIAL", material)

    model = asin_data.get("model")
    if model:
        add("MODEL", model)

    size = asin_data.get("size") or asin_data.get("dimensions")
    if size:
        add("SIZE", size)

    gender = detect_gender_from_title(asin_data.get("title", ""))
    if gender:
        add("GENDER", gender)

    gtin = asin_data.get("gtin") or asin_data.get("upc")
    if gtin:
        attrs.append({"id": "GTIN", "value_struct": {"number": str(gtin)}})
    else:
        attrs.append({"id": "EMPTY_GTIN_REASON", "value_name": "Kit or bundle"})

    # Dimensiones
    if asin_data.get("dimensions"):
        dims = asin_data["dimensions"]
        if isinstance(dims, dict):
            l = dims.get("length", "20 cm")
            w = dims.get("width", "20 cm")
            h = dims.get("height", "10 cm")
            add("PACKAGE_LENGTH", l)
            add("PACKAGE_WIDTH", w)
            add("PACKAGE_HEIGHT", h)
        else:
            add("PACKAGE_LENGTH", "20 cm")
            add("PACKAGE_WIDTH", "20 cm")
            add("PACKAGE_HEIGHT", "10 cm")

    # Peso
    weight = asin_data.get("weight", "1 kg")
    add("PACKAGE_WEIGHT", weight)

    # Garantía
    add("WARRANTY_TYPE", "Seller warranty")
    add("WARRANTY_TIME", "30 days")

    # Agregar los que falten según categoría (con placeholders)
    attrs = fill_missing_required_attrs(category_id, attrs, asin_data)

    return attrs


# ======================================================
# 🧩 Completar requeridos faltantes con inferencia
# ======================================================

def fill_missing_required_attrs(category_id: str, attrs: list, asin_data: dict) -> list:
    """Rellena automáticamente atributos requeridos faltantes usando datos reales o inferidos."""
    all_required = get_required_attributes(category_id)
    current = {a["id"] for a in attrs}
    missing = set(all_required) - current

    if not missing:
        return attrs

    print(f"⚙️ Completando {len(missing)} atributos faltantes: {', '.join(missing)}")

    for attr in missing:
        val = infer_value_for_attr(attr, asin_data)
        if val:
            attrs.append({"id": attr, "value_name": val})
    return attrs


# ======================================================
# 🔍 Inferencia básica de valores por nombre de atributo
# ======================================================

def infer_value_for_attr(attr_id: str, data: dict) -> str:
    """Intenta inferir valores realistas según el contenido del JSON."""
    title = data.get("title", "").lower()
    desc = " ".join(data.get("description", [])) if isinstance(data.get("description"), list) else str(data.get("description", "")).lower()

    if attr_id in ("GENDER", "TARGET_GENDER"):
        if "women" in title or "woman" in title:
            return "Women"
        if "men" in title or "man" in title:
            return "Men"
        if "unisex" in title:
            return "Unisex"
        return "Unisex"

    if attr_id in ("COLOR", "MAIN_COLOR"):
        return detect_color_from_title(title)

    if attr_id == "MATERIAL":
        for m in ["plastic", "metal", "wood", "steel", "silicone", "glass"]:
            if m in title:
                return m.capitalize()
        return "Plastic"

    if attr_id == "BRAND":
        return data.get("brand", "Unbranded")

    if attr_id == "MODEL":
        return data.get("model", "Standard")

    if attr_id == "SIZE":
        return data.get("size", "One size")

    if attr_id == "AGE_GROUP":
        if any(k in title for k in ["baby", "child", "kids"]):
            return "Kids"
        return "Adults"

    if attr_id == "WARRANTY_TYPE":
        return "Seller warranty"

    if attr_id == "WARRANTY_TIME":
        return "30 days"

    return None


# ======================================================
# 🎨 Utilidades simples de detección
# ======================================================

def detect_color_from_title(text: str) -> str:
    """Extrae color probable del título."""
    colors = ["black", "white", "blue", "red", "green", "yellow", "pink", "gray", "brown", "orange", "purple"]
    text = text.lower()
    for c in colors:
        if re.search(rf"\b{c}\b", text):
            return c.capitalize()
    return "Not specified"


def detect_gender_from_title(text: str) -> str:
    """Detecta género probable en el título."""
    t = text.lower()
    if "men" in t or "man's" in t:
        return "Men"
    if "women" in t or "woman" in t:
        return "Women"
    if "unisex" in t:
        return "Unisex"
    return None


# ======================================================
# 🧪 Test directo
# ======================================================

if __name__ == "__main__":
    import pprint
    cat = input("👉 Ingresá una categoría (ej. CBT1574): ").strip()
    test_json = {
        "title": "Reusable Bag Sealer Clip with Pour Spout - Blue Plastic",
        "brand": "Sealmate",
        "color": "Blue",
        "material": "Plastic",
        "model": "SM-2025",
        "gtin": "1234567890123",
        "weight": "0.5 kg"
    }
    attrs = map_amazon_to_meli_attrs(test_json, cat)
    pprint.pp(attrs)