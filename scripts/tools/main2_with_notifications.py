#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WRAPPER DE MAIN2 CON NOTIFICACIONES TELEGRAM
=============================================
Ejecuta main2.py y envía notificaciones en tiempo real al Bot 2 de Telegram

Uso:
    python3 main2_with_notifications.py

El script:
1. Lee los ASINs a publicar
2. Notifica inicio del batch
3. Ejecuta main2.py monitoreando el output
4. Envía notificaciones según los logs
5. Notifica resumen final
"""

import os
import sys
import subprocess
import re
from datetime import datetime
from pathlib import Path

# Importar notificador de publicaciones (Bot 2)
sys.path.insert(0, str(Path(__file__).parent / "scripts" / "tools"))

try:
    from telegram_publishing_notifier import (
        notify_batch_start,
        notify_product_start,
        notify_download_complete,
        notify_transform_complete,
        notify_publish_success,
        notify_publish_error,
        notify_batch_complete,
        notify_category_detected,
        is_configured
    )
    TELEGRAM_AVAILABLE = is_configured()
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️  Bot de publicaciones no disponible")


def count_asins_to_publish():
    """Cuenta cuántos ASINs hay para publicar"""
    asins_file = Path("asins.txt")
    if not asins_file.exists():
        return 0

    with open(asins_file, 'r') as f:
        asins = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    return len(asins)


def parse_main2_output(line, stats):
    """
    Parsea el output de main2 y envía notificaciones

    Args:
        line: Línea de output de main2
        stats: Dict con estadísticas del batch
    """
    line = line.strip()

    # Detectar inicio de procesamiento de producto
    match = re.search(r'\[(\d+)/(\d+)\].*ASIN:\s*([A-Z0-9]{10})', line)
    if match:
        number, total, asin = match.groups()
        stats['current_asin'] = asin
        stats['current_number'] = int(number)
        stats['total'] = int(total)

        if TELEGRAM_AVAILABLE:
            notify_product_start(asin, int(number), int(total))
        return

    # Detectar descarga completada de Amazon
    if 'Descarga completada' in line or 'Download complete' in line:
        match = re.search(r'Title:\s*(.+?)\s*\|\s*Brand:\s*(.+?)$', line)
        if match and stats.get('current_asin'):
            title, brand = match.groups()
            if TELEGRAM_AVAILABLE:
                notify_download_complete(stats['current_asin'], title.strip(), brand.strip())
        return

    # Detectar categoría detectada
    match = re.search(r'Categoría detectada:\s*(.+?)\s*\(([A-Z0-9]+)\)', line)
    if match and stats.get('current_asin'):
        category_name, category_id = match.groups()

        # Detectar método y confianza
        method = "ai_validated"
        confidence = None

        if "embedding" in line.lower():
            method = "embedding"
            conf_match = re.search(r'(\d+)%', line)
            if conf_match:
                confidence = float(conf_match.group(1)) / 100
        elif "fallback" in line.lower():
            method = "fallback"

        if TELEGRAM_AVAILABLE:
            notify_category_detected(
                stats['current_asin'],
                category_name.strip(),
                method,
                confidence
            )
        return

    # Detectar transformación completada
    if 'Transformación completada' in line or 'Transform complete' in line:
        match = re.search(r'Categoría:\s*(.+?)\s*\(([A-Z0-9]+)\).*?(\d+)%', line)
        if match and stats.get('current_asin'):
            category_name, category_id, confidence = match.groups()
            if TELEGRAM_AVAILABLE:
                notify_transform_complete(
                    stats['current_asin'],
                    category_id,
                    category_name.strip(),
                    float(confidence) / 100
                )
        return

    # Detectar publicación exitosa
    match = re.search(r'Publicado exitosamente.*?Item ID:\s*([A-Z0-9]+)', line)
    if match and stats.get('current_asin'):
        item_id = match.group(1)

        # Detectar países exitosos y fallidos
        countries_ok = []
        countries_failed = []

        # Buscar países en la línea
        countries_match = re.search(r'Países:\s*(.+?)(?:\||$)', line)
        if countries_match:
            countries_text = countries_match.group(1)
            # MLM, MLB, MLC, MCO, MLA
            countries_ok = re.findall(r'ML[MBCOA]', countries_text)

        # Si no hay países en la línea, asumir todos
        if not countries_ok:
            countries_ok = ["MLM", "MLB", "MLC", "MCO", "MLA"]

        if TELEGRAM_AVAILABLE:
            notify_publish_success(
                stats['current_asin'],
                item_id,
                countries_ok,
                countries_failed
            )

        stats['success'] += 1
        return

    # Detectar error en publicación
    if ('Error publicando' in line or 'Publish error' in line) and stats.get('current_asin'):
        # Extraer mensaje de error
        error_match = re.search(r'Error:\s*(.+?)$', line)
        error_msg = error_match.group(1) if error_match else "Error desconocido"

        if TELEGRAM_AVAILABLE:
            notify_publish_error(stats['current_asin'], error_msg)

        stats['failed'] += 1
        return


def run_main2_with_notifications():
    """Ejecuta main2.py con notificaciones en tiempo real"""

    print("═" * 70)
    print("🚀 MAIN2 CON NOTIFICACIONES TELEGRAM")
    print("═" * 70)
    print(f"📱 Bot de publicaciones: {'✅ Activado' if TELEGRAM_AVAILABLE else '❌ Desactivado'}")
    print("═" * 70)
    print()

    # Contar ASINs
    total_asins = count_asins_to_publish()

    if total_asins == 0:
        print("❌ No hay ASINs en asins.txt")
        return

    print(f"📦 Total de productos a publicar: {total_asins}")
    print()

    # Notificar inicio de batch
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    if TELEGRAM_AVAILABLE:
        notify_batch_start(total_asins, run_id)

    # Estadísticas
    stats = {
        'total': total_asins,
        'success': 0,
        'failed': 0,
        'current_asin': None,
        'current_number': 0,
        'start_time': datetime.now()
    }

    # Ejecutar main2.py
    print("🚀 Ejecutando main2.py...")
    print("─" * 70)
    print()

    try:
        # Ejecutar main2.py y capturar output en tiempo real
        process = subprocess.Popen(
            ['python3', 'main2.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        # Leer output línea por línea
        for line in process.stdout:
            # Imprimir línea original
            print(line, end='')

            # Parsear y enviar notificaciones
            parse_main2_output(line, stats)

        process.wait()

    except KeyboardInterrupt:
        print()
        print("⚠️  Proceso interrumpido por usuario")
        process.terminate()
        return

    except Exception as e:
        print(f"❌ Error ejecutando main2: {e}")
        stats['failed'] = stats['total']

    # Calcular duración
    duration = (datetime.now() - stats['start_time']).total_seconds() / 60

    # Notificar resumen final
    print()
    print("═" * 70)
    print("🏁 BATCH COMPLETADO")
    print("═" * 70)
    print(f"✅ Exitosos: {stats['success']}")
    print(f"❌ Fallidos: {stats['failed']}")
    print(f"⏱️  Tiempo total: {duration:.1f} minutos")
    print("═" * 70)

    if TELEGRAM_AVAILABLE:
        notify_batch_complete(
            total=stats['total'],
            success=stats['success'],
            failed=stats['failed'],
            duration_minutes=duration
        )


if __name__ == "__main__":
    run_main2_with_notifications()
