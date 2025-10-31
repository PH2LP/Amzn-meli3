#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, json, time, requests, argparse, shutil
from urllib.parse import urlparse

API = "https://api.mercadolibre.com"
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"}

DL_TMP_DIR = "logs/images_tmp"
os.makedirs(DL_TMP_DIR, exist_ok=True)

def download_image(url, asin, idx):
    try:
        ext = os.path.splitext(urlparse(url).path)[1] or ".jpg"
        filename = f"{asin}_{idx}{ext}"
        path = os.path.join(DL_TMP_DIR, filename)

        r = requests.get(url, timeout=15)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)

        return path
    except Exception as e:
        print(f"  ⚠️ Error descargando imagen {idx}: {e} → {url}")
        return None

def upload_image_to_ml(path):
    try:
        with open(path, "rb") as f:
            files = {
                "file": (
                    os.path.basename(path),
                    f,
                    "image/jpeg"
                )
            }
            r = requests.post(
                f"{API}/pictures?access_token={ML_ACCESS_TOKEN}",
                files=files,
                timeout=30
            )
        r.raise_for_status()
        data = r.json()
        return data.get("secure_url") or data.get("url")
    except Exception as e:
        print(f"  ❌ Error subiendo a ML: {e}")
        return None

def process_mini_ml(path):
    mini = json.load(open(path, "r", encoding="utf-8"))
    asin = mini.get("asin")
    images = mini.get("images", [])

    if not images:
        print(f"🖼️  {asin}: No hay imágenes en mini_ml. Saltando.")
        return

    print(f"📸 Procesando imágenes para ASIN {asin} ({len(images)} imágenes)…")

    new_images = []
    for idx, img in enumerate(images):
        if not isinstance(img, dict): continue
        url = img.get("url")
        if not url: continue

        print(f"  🔽 Descargando {idx+1}/{len(images)} → {url}")
        local_path = download_image(url, asin, idx)
        if not local_path:
            continue

        print(f"  ⬆️ Subiendo a MercadoLibre…")
        new_url = upload_image_to_ml(local_path)

        # borrar la local si se subió bien
        try:
            os.remove(local_path)
        except:
            pass

        if new_url:
            print(f"  ✅ Imagen subida: {new_url}")
            img["url"] = new_url
            new_images.append(img)
        else:
            print(f"  ❌ Falló -> manteniendo URL original")
            new_images.append(img)

        time.sleep(0.7)  # rate-limit seguro

    mini["images"] = new_images
    mini["images_count"] = len(new_images)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(mini, f, indent=2, ensure_ascii=False)

    print(f"✅ ASIN {asin}: Imágenes actualizadas correctamente.\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input_dir", 
        default="logs/publish_ready", 
        help="Carpeta con archivos *_mini_ml.json"
    )
    parser.add_argument(
        "--max",
        type=int,
        default=999,
        help="Máximo de productos a procesar"
    )
    args = parser.parse_args()

    if not ML_ACCESS_TOKEN:
        print("❌ ML_ACCESS_TOKEN no configurado en environment.")
        sys.exit(1)

    files = [f for f in os.listdir(args.input_dir) if f.endswith("_mini_ml.json")]
    if not files:
        print("⚠️ No hay mini_ml en la carpeta.")
        return

    print(f"🚀 Iniciando subida de imágenes a ML ({len(files)} productos)…\n")

    for i, fname in enumerate(files):
        if i >= args.max: break
        path = os.path.join(args.input_dir, fname)
        process_mini_ml(path)

    print("🎯 Proceso de imágenes completo.")

if __name__ == "__main__":
    main()