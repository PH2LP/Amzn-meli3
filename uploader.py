import os
import sys
from dotenv import load_dotenv

if sys.prefix == sys.base_prefix:
    venv_python = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
    if os.path.exists(venv_python):
        print(f"⚙️ Activando entorno virtual automáticamente desde {venv_python}...")
        os.execv(venv_python, [venv_python] + sys.argv)
    else:
        print("⚠️ No se encontró el entorno virtual (venv). Créalo con: python3.11 -m venv venv")
        sys.exit(1)

load_dotenv()


def select_best_images(amazon_json):
    """
    Selecciona las mejores imágenes desde el JSON de Amazon, eliminando duplicados.
    Amazon provee 3 resoluciones por imagen (ej: MAIN 2000px, 500px, 75px).
    Esta función selecciona SOLO la de mayor resolución por cada variante.
    """
    if not amazon_json:
        return []

    # Extraer todas las imágenes del JSON
    images_data = []

    # Buscar en la estructura de Amazon SP-API
    if "images" in amazon_json and isinstance(amazon_json["images"], list):
        for marketplace_data in amazon_json["images"]:
            if isinstance(marketplace_data, dict) and "images" in marketplace_data:
                images_list = marketplace_data["images"]
                if isinstance(images_list, list):
                    images_data.extend(images_list)

    if not images_data:
        return []

    # Agrupar por variant name (MAIN, PT01, PT02, etc.)
    variants_dict = {}
    for img in images_data:
        if not isinstance(img, dict):
            continue

        variant = img.get("variant", "UNKNOWN")
        link = img.get("link", "")
        width = img.get("width", 0)
        height = img.get("height", 0)

        if not link or not link.startswith("http"):
            continue

        # Calcular resolución total (width * height)
        resolution = width * height

        # Si esta variante no existe o tiene menor resolución, actualizar
        if variant not in variants_dict or variants_dict[variant]["resolution"] < resolution:
            variants_dict[variant] = {
                "link": link,
                "resolution": resolution,
                "width": width,
                "height": height
            }

    # Ordenar variantes: MAIN primero, luego PT01, PT02, etc.
    def variant_sort_key(variant_name):
        if variant_name == "MAIN":
            return (0, "")
        elif variant_name.startswith("PT"):
            try:
                # Extraer número de PT01, PT02, etc.
                num = int(variant_name[2:])
                return (1, num)
            except:
                return (2, variant_name)
        else:
            return (3, variant_name)

    sorted_variants = sorted(variants_dict.keys(), key=variant_sort_key)

    # Obtener solo las URLs en el orden correcto
    best_images = [variants_dict[v]["link"] for v in sorted_variants]

    return best_images

def extract_images(amazon_json):
    """
    Extrae todas las URLs de imágenes desde cualquier formato:
    Compatible con formato Amazon SP-API (images -> [0].images[*].link)
    """
    if not amazon_json:
        return []

    candidates = []

    possible_keys = ["images", "image_list", "image_urls", "main_images", "pictures", "media"]
    for key in possible_keys:
        if key in amazon_json:
            value = amazon_json[key]
            if isinstance(value, list):
                candidates.extend(value)
            elif isinstance(value, dict):
                candidates.append(value)

    deep_links = []
    for item in candidates:
        if isinstance(item, str) and item.startswith("http"):
            deep_links.append(item)
        elif isinstance(item, dict):
            for k in ["url", "source", "link", "secure_url"]:
                if k in item and isinstance(item[k], str) and item[k].startswith("http"):
                    deep_links.append(item[k])
                    break
            if "images" in item and isinstance(item["images"], list):
                for img in item["images"]:
                    if isinstance(img, dict) and "link" in img and isinstance(img["link"], str):
                        deep_links.append(img["link"])

    urls = [u for u in deep_links if isinstance(u, str) and u.startswith("http")]
    clean = list(dict.fromkeys(urls))
    return clean


def upload_images_to_meli(amazon_json):
    """
    En modo CBT, no se suben imágenes directamente.
    En su lugar, se devuelven las URLs optimizadas para incluir en el body.
    Selecciona automáticamente la mejor resolución por cada variante.
    """
    best_images = select_best_images(amazon_json)
    print(f"🧠 Imágenes seleccionadas (sin duplicados): {len(best_images)}")

    if not best_images:
        raise ValueError("No se encontraron imágenes válidas para incluir.")

    pictures = [{"source": url} for url in best_images]
    print(f"✅ Imágenes preparadas para publicación CBT ({len(pictures)} total)")
    return pictures