#!/usr/bin/env python3
"""
Script para cerrar (eliminar) TODAS las publicaciones de TODOS los países

Uso:
    python3 delete_all_items.py [--force]

Sin --force: Pedirá confirmación
Con --force: Ejecutará automáticamente sin confirmación

Este script elimina TODO de:
MLA (Argentina), MLB (Brasil), MCO (Colombia), MLC (Chile), MLM (México),
y todos los demás marketplaces.
"""

import os
import sys
import time
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# Cargar variables de entorno
load_dotenv(override=True)

ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")
ML_API = "https://api.mercadolibre.com"

if not ML_ACCESS_TOKEN:
    print("❌ Error: ML_ACCESS_TOKEN no encontrado en .env")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {ML_ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def get_user_id():
    """Obtiene el user_id del token actual"""
    try:
        response = requests.get(f"{ML_API}/users/me", headers=HEADERS, timeout=10)
        response.raise_for_status()
        user_data = response.json()
        return user_data["id"]
    except Exception as e:
        print(f"❌ Error obteniendo user_id: {e}")
        sys.exit(1)

def get_all_user_items(user_id, status="active"):
    """
    Obtiene TODOS los items del usuario usando paginación
    Maneja el límite de 1000 items de la API
    """
    all_items = []
    offset = 0
    limit = 100

    print(f"\n📋 Obteniendo items con status='{status}'...")

    while offset < 1000:  # API limita a 1000 items máximo
        try:
            url = f"{ML_API}/users/{user_id}/items/search"
            params = {
                "status": status,
                "limit": limit,
                "offset": offset
            }

            response = requests.get(url, headers=HEADERS, params=params, timeout=30)

            # Si llegamos al límite de 1000, la API retorna error 400
            if response.status_code == 400:
                print(f"\n⚠️  Límite de API alcanzado en offset={offset}")
                break

            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])

            if not results:
                break

            all_items.extend(results)

            total = data.get("paging", {}).get("total", len(all_items))
            print(f"   📦 Obtenidos: {len(all_items)}/{min(total, 1000)} items", end="\r")

            if len(results) < limit:
                break

            offset += limit
            time.sleep(0.5)

        except Exception as e:
            print(f"\n⚠️  Error obteniendo items (offset={offset}): {e}")
            break

    print(f"\n✅ Total items obtenidos: {len(all_items)}")

    if offset >= 1000:
        print(f"\n⚠️  NOTA: La API de ML limita a 1000 items por búsqueda")
        print(f"   Después de cerrar estos, ejecuta el script nuevamente para los siguientes 1000")

    return all_items

def close_item(item_id):
    """
    Cierra (elimina) un item cambiando su status a 'closed'
    """
    try:
        url = f"{ML_API}/items/{item_id}"
        payload = {"status": "closed"}

        response = requests.put(url, headers=HEADERS, json=payload, timeout=15)
        response.raise_for_status()

        return True, None

    except requests.exceptions.HTTPError as e:
        error_msg = e.response.text if hasattr(e.response, 'text') else str(e)
        return False, error_msg
    except Exception as e:
        return False, str(e)

def main():
    force_mode = "--force" in sys.argv

    print("\n" + "="*70)
    print("🗑️  ELIMINAR TODAS LAS PUBLICACIONES DE TODOS LOS PAÍSES")
    print("="*70)

    # Confirmar acción
    print(f"\n⚠️  ADVERTENCIA CRÍTICA:")
    print(f"   Este script cerrará TODAS tus publicaciones activas")
    print(f"   de TODOS los marketplaces (MLA, MLB, MCO, MLC, MLM, etc.)")
    print(f"   Las publicaciones cerradas NO se pueden reactivar")
    print(f"   (pero se pueden republicar)")

    if not force_mode:
        print(f"\n❗ Esta es una operación IRREVERSIBLE")
        confirm = input(f"\n¿Deseas continuar? Escribe 'SI ELIMINAR TODO' para confirmar: ")

        if confirm != "SI ELIMINAR TODO":
            print("\n❌ Operación cancelada")
            sys.exit(0)
    else:
        print(f"\n⚡ Modo --force activado: Saltando confirmación inicial")

    # Obtener user_id
    user_id = get_user_id()
    print(f"\n👤 User ID: {user_id}")

    # Crear directorio de logs
    log_dir = Path("logs/delete_items")
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"delete_ALL_{timestamp}.json"
    progress_log = log_dir / f"delete_ALL_{timestamp}_progress.txt"

    # Obtener todos los items activos
    all_items = get_all_user_items(user_id, status="active")

    if not all_items:
        print(f"\n✅ No hay items activos para procesar")
        sys.exit(0)

    # Confirmar nuevamente con el número exacto
    print(f"\n⚠️  Se cerrarán {len(all_items)} publicaciones")
    print(f"   (Máximo 1000 por ejecución debido a límites de API)")

    if not force_mode:
        confirm2 = input("¿Continuar? (si/no): ")

        if confirm2.lower() != "si":
            print("\n❌ Operación cancelada")
            sys.exit(0)
    else:
        print("⚡ Modo --force: Continuando automáticamente...")

    # Cerrar items
    print(f"\n🗑️  Cerrando {len(all_items)} items...")
    print(f"📄 Progreso guardándose en: {progress_log}\n")

    results = {
        "timestamp": timestamp,
        "total_items": len(all_items),
        "success": [],
        "failed": []
    }

    # Abrir archivo de progreso
    with open(progress_log, 'w', encoding='utf-8') as plog:
        plog.write(f"Inicio: {datetime.now()}\n")
        plog.write(f"Total items a cerrar: {len(all_items)}\n")
        plog.write("="*70 + "\n\n")

        for i, item_id in enumerate(all_items, 1):
            status_msg = f"[{i}/{len(all_items)}] Cerrando {item_id}..."
            print(status_msg, end=" ", flush=True)
            plog.write(status_msg + " ")
            plog.flush()

            success, error = close_item(item_id)

            if success:
                print("✅")
                plog.write("✅\n")
                results["success"].append(item_id)
            else:
                print(f"❌ {error}")
                plog.write(f"❌ {error}\n")
                results["failed"].append({
                    "item_id": item_id,
                    "error": error
                })

            plog.flush()
            time.sleep(0.5)  # Pausa entre requests

        plog.write(f"\n{'='*70}\n")
        plog.write(f"Fin: {datetime.now()}\n")

    # Guardar resultados finales
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Resumen final
    print("\n" + "="*70)
    print("📊 RESUMEN")
    print("="*70)
    print(f"Total items procesados: {len(all_items)}")
    print(f"✅ Cerrados exitosamente: {len(results['success'])}")
    print(f"❌ Errores: {len(results['failed'])}")
    print(f"\n📄 Log JSON guardado en: {log_file}")
    print(f"📄 Log progreso guardado en: {progress_log}")

    if len(all_items) >= 1000:
        print(f"\n⚠️  IMPORTANTE: Se procesaron 1000 items (límite de API)")
        print(f"   Ejecuta el script nuevamente para eliminar los siguientes:")
        print(f"   python3 delete_all_items.py --force")

    print("="*70)

if __name__ == "__main__":
    main()
