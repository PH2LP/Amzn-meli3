import os
import sys
from dotenv import load_dotenv
from image_selector import select_best_images

if sys.prefix == sys.base_prefix:
    venv_python = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
    if os.path.exists(venv_python):
        print(f"⚙️ Activando entorno virtual automáticamente desde {venv_python}...")
        os.execv(venv_python, [venv_python] + sys.argv)
    else:
        print("⚠️ No se encontró el entorno virtual (venv). Créalo con: python3.11 -m venv venv")
        sys.exit(1)

load_dotenv()

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
    """
    all_images = extract_images(amazon_json)
    print(f"📸 Imágenes detectadas en JSON: {len(all_images)}")

    best_images = select_best_images(all_images)
    print(f"🧠 Imágenes seleccionadas para incluir: {len(best_images)}")

    if not best_images:
        raise ValueError("No se encontraron imágenes válidas para incluir.")

    pictures = [{"source": url} for url in best_images]
    print(f"✅ Imágenes preparadas para publicación CBT ({len(pictures)} total)")
    return pictures