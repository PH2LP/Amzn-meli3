#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CORRECCIÓN AUTOMÁTICA DE FOTOS PAUSADAS
========================================
Detecta publicaciones pausadas por problemas de imágenes,
procesa las fotos con IA (rembg) y las re-sube para reactivar.

Flujo:
1. Buscar listings pausados con moderation_penalty o poor_quality_thumbnail
2. Verificar detalles de moderación (watermark, texto, mala calidad)
3. Descargar imagen problemática
4. Procesarla con rembg (remover fondo/texto)
5. Re-subir imagen mejorada
6. Reactivar publicación
7. Notificar por Telegram
"""

import os
import sys
import json
import requests
import io
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from rembg import remove
from PIL import Image

# Cargar variables de entorno
load_dotenv(override=True)

# Configuración
ML_API = "https://api.mercadolibre.com"
ML_TOKEN = os.getenv("ML_ACCESS_TOKEN")
USER_ID = os.getenv("ML_USER_ID", "2629793984")

# Directorio temporal para imágenes
TEMP_DIR = Path("storage/temp_images")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Log
LOG_FILE = Path("logs/fix_paused_pictures.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Importar notificaciones Telegram
try:
    from telegram_notifier import send_message, is_configured as telegram_configured
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    def send_message(*args, **kwargs): pass
    def telegram_configured(): return False


def log(msg):
    """Log con timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_msg + '\n')


def get_paused_items_with_picture_issues():
    """
    Obtiene items pausados con problemas de imágenes.

    Busca items con:
    - status: paused
    - tags: moderation_penalty OR poor_quality_thumbnail

    Returns:
        Lista de item_ids con problemas de fotos
    """
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}
    paused_items = []

    # Búsqueda 1: Items con moderation_penalty
    try:
        url = f"{ML_API}/users/{USER_ID}/items/search"
        params = {
            "status": "paused",
            "tags": "moderation_penalty",
            "limit": 50
        }

        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        results = r.json().get("results", [])

        log(f"🔍 Encontrados {len(results)} items pausados con moderation_penalty")
        paused_items.extend(results)

    except Exception as e:
        log(f"❌ Error buscando items con moderation_penalty: {e}")

    # Búsqueda 2: Items con poor_quality_thumbnail
    try:
        url = f"{ML_API}/users/{USER_ID}/items/search"
        params = {
            "tags": "poor_quality_thumbnail",
            "limit": 50
        }

        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        results = r.json().get("results", [])

        log(f"🔍 Encontrados {len(results)} items con poor_quality_thumbnail")
        paused_items.extend(results)

    except Exception as e:
        log(f"❌ Error buscando items con poor_quality_thumbnail: {e}")

    # Deduplicar
    paused_items = list(set(paused_items))

    return paused_items


def get_item_details(item_id):
    """Obtiene detalles completos de un item"""
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    try:
        url = f"{ML_API}/items/{item_id}"
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"❌ Error obteniendo detalles de {item_id}: {e}")
        return None


def check_picture_quality(picture_id):
    """
    Verifica la calidad de una imagen específica.

    Endpoint: GET /quality/picture?picture_id={PICTURE_ID}

    Returns:
        Dict con detalles de problemas de calidad
    """
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    try:
        url = f"{ML_API}/quality/picture"
        params = {"picture_id": picture_id}

        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"⚠️ No se pudo verificar calidad de picture {picture_id}: {e}")
        return None


def download_image(image_url):
    """
    Descarga una imagen desde URL.

    Returns:
        PIL.Image o None si falla
    """
    try:
        r = requests.get(image_url, timeout=30)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content))
        log(f"✅ Imagen descargada: {image_url[:50]}...")
        return img
    except Exception as e:
        log(f"❌ Error descargando imagen {image_url}: {e}")
        return None


def process_image_with_ai(image):
    """
    Procesa imagen con rembg para limpiar fondo/texto.

    Args:
        image: PIL.Image

    Returns:
        PIL.Image procesada o None si falla
    """
    try:
        log("🤖 Procesando imagen con IA (rembg)...")

        # Convertir PIL Image a bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()

        # Remover fondo con rembg
        output = remove(img_byte_arr)

        # Convertir de bytes a PIL Image
        processed_img = Image.open(io.BytesIO(output))

        # Agregar fondo blanco (requerido por ML)
        white_bg = Image.new("RGB", processed_img.size, (255, 255, 255))
        white_bg.paste(processed_img, mask=processed_img.split()[3] if processed_img.mode == 'RGBA' else None)

        log("✅ Imagen procesada exitosamente")
        return white_bg

    except Exception as e:
        log(f"❌ Error procesando imagen con IA: {e}")
        return None


def upload_image_to_ml(image, item_id):
    """
    Sube una imagen a MercadoLibre.

    Endpoint: POST /pictures/items/upload

    Returns:
        picture_id de la imagen subida o None si falla
    """
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    try:
        log("📤 Subiendo imagen mejorada a MercadoLibre...")

        # Convertir imagen a bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG', quality=95)
        img_byte_arr.seek(0)

        # Subir
        url = f"{ML_API}/pictures/items/upload"
        files = {'file': ('image.jpg', img_byte_arr, 'image/jpeg')}

        r = requests.post(url, headers=headers, files=files, timeout=60)
        r.raise_for_status()

        result = r.json()
        picture_id = result.get('id')

        if picture_id:
            log(f"✅ Imagen subida exitosamente. Picture ID: {picture_id}")
            return picture_id
        else:
            log(f"❌ Respuesta sin picture_id: {result}")
            return None

    except Exception as e:
        log(f"❌ Error subiendo imagen: {e}")
        return None


def update_item_pictures(item_id, new_picture_id, keep_old_pictures=True):
    """
    Actualiza las imágenes de un item.

    Args:
        item_id: ID del item
        new_picture_id: ID de la nueva imagen
        keep_old_pictures: Si True, mantiene las imágenes antiguas

    Returns:
        True si exitoso, False si falla
    """
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    try:
        # Obtener imágenes actuales
        item = get_item_details(item_id)
        if not item:
            return False

        current_pictures = item.get('pictures', [])

        # Construir lista de imágenes
        if keep_old_pictures:
            # Reemplazar la primera (problemática) con la nueva
            new_pictures = [{"id": new_picture_id}]
            # Agregar el resto de las antiguas (saltando la primera)
            for pic in current_pictures[1:]:
                new_pictures.append({"id": pic['id']})
        else:
            # Solo la nueva imagen
            new_pictures = [{"id": new_picture_id}]

        # Actualizar item
        url = f"{ML_API}/items/{item_id}"
        data = {"pictures": new_pictures}

        r = requests.put(url, headers=headers, json=data, timeout=30)
        r.raise_for_status()

        log(f"✅ Imágenes actualizadas en item {item_id}")
        return True

    except Exception as e:
        log(f"❌ Error actualizando imágenes de {item_id}: {e}")
        return False


def reactivate_item(item_id):
    """
    Reactiva un item pausado.

    Returns:
        True si exitoso, False si falla
    """
    headers = {"Authorization": f"Bearer {ML_TOKEN}"}

    try:
        url = f"{ML_API}/items/{item_id}"
        data = {"status": "active"}

        r = requests.put(url, headers=headers, json=data, timeout=30)
        r.raise_for_status()

        log(f"✅ Item {item_id} reactivado exitosamente")
        return True

    except Exception as e:
        log(f"❌ Error reactivando {item_id}: {e}")
        return False


def fix_item_pictures(item_id):
    """
    Flujo completo de corrección de fotos para un item.

    Returns:
        True si se corrigió exitosamente, False si no
    """
    log(f"\n{'='*70}")
    log(f"🔧 PROCESANDO ITEM: {item_id}")
    log(f"{'='*70}")

    # 1. Obtener detalles del item
    item = get_item_details(item_id)
    if not item:
        log(f"❌ No se pudo obtener detalles del item {item_id}")
        return False

    title = item.get('title', 'Sin título')[:50]
    status = item.get('status', 'unknown')
    pictures = item.get('pictures', [])

    log(f"📦 Título: {title}")
    log(f"📊 Status: {status}")
    log(f"🖼️  Fotos: {len(pictures)}")

    if not pictures:
        log(f"⚠️ Item sin fotos - nada que corregir")
        return False

    # 2. Obtener primera imagen (usualmente la problemática)
    first_picture = pictures[0]
    picture_id = first_picture.get('id')
    picture_url = first_picture.get('url')

    if not picture_url:
        log(f"❌ No se pudo obtener URL de la imagen")
        return False

    log(f"🖼️  Picture ID: {picture_id}")

    # 3. Verificar calidad (opcional, para diagnóstico)
    quality_info = check_picture_quality(picture_id)
    if quality_info:
        log(f"📊 Info de calidad: {json.dumps(quality_info, indent=2)}")

    # 4. Descargar imagen
    original_image = download_image(picture_url)
    if not original_image:
        log(f"❌ No se pudo descargar la imagen")
        return False

    # 5. Procesar con IA
    processed_image = process_image_with_ai(original_image)
    if not processed_image:
        log(f"❌ No se pudo procesar la imagen con IA")
        return False

    # 6. Subir imagen mejorada
    new_picture_id = upload_image_to_ml(processed_image, item_id)
    if not new_picture_id:
        log(f"❌ No se pudo subir la imagen mejorada")
        return False

    # 7. Actualizar item con nueva imagen
    if not update_item_pictures(item_id, new_picture_id, keep_old_pictures=True):
        log(f"❌ No se pudo actualizar las imágenes del item")
        return False

    # 8. Reactivar si está pausado
    if status == "paused":
        if not reactivate_item(item_id):
            log(f"⚠️ No se pudo reactivar el item automáticamente")
            log(f"💡 Intenta reactivarlo manualmente desde ML")

    # 9. Notificar éxito
    log(f"✅ ¡CORRECCIÓN EXITOSA!")

    if telegram_configured():
        message = f"""
✅ <b>Foto Corregida Automáticamente</b>

🆔 Item: <code>{item_id}</code>
📦 {title}
🖼️ Foto procesada con IA y re-subida
{'✅ Reactivado' if status == 'paused' else '✅ Actualizado'}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        send_message(message)

    return True


def run_fix_cycle():
    """Ejecuta un ciclo completo de corrección"""
    log("\n" + "="*70)
    log("🚀 INICIANDO CICLO DE CORRECCIÓN DE FOTOS")
    log("="*70)

    # 1. Buscar items con problemas de fotos
    paused_items = get_paused_items_with_picture_issues()

    if not paused_items:
        log("✅ No hay items con problemas de fotos")
        return

    log(f"📋 Total items a procesar: {len(paused_items)}")

    # 2. Procesar cada item
    success_count = 0
    failed_count = 0

    for item_id in paused_items:
        try:
            if fix_item_pictures(item_id):
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            log(f"❌ Error inesperado procesando {item_id}: {e}")
            failed_count += 1

    # 3. Resumen
    log("\n" + "="*70)
    log("📊 RESUMEN DE CORRECCIÓN")
    log("="*70)
    log(f"✅ Exitosos: {success_count}")
    log(f"❌ Fallidos: {failed_count}")
    log(f"📋 Total: {len(paused_items)}")

    if telegram_configured():
        message = f"""
📊 <b>Resumen de Corrección de Fotos</b>

✅ Corregidos: {success_count}
❌ Fallidos: {failed_count}
📋 Total procesados: {len(paused_items)}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        send_message(message)


if __name__ == "__main__":
    if not ML_TOKEN:
        print("❌ Error: ML_ACCESS_TOKEN no configurado en .env")
        sys.exit(1)

    run_fix_cycle()
