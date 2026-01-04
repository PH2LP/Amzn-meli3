#!/usr/bin/env python3
"""
Script para eliminar items CBT que NO tienen marketplace items locales (MLA, MLB, etc).
Estos son items "huérfanos" que quedaron sin completar la publicación.
"""

import requests
import os
import time
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

ML_ACCESS_TOKEN = os.getenv('ML_ACCESS_TOKEN')

def delete_item(cbt_id):
    """
    Elimina un item de MercadoLibre usando DELETE.
    """
    url = f"https://api.mercadolibre.com/items/{cbt_id}"
    headers = {
        'Authorization': f'Bearer {ML_ACCESS_TOKEN}'
    }

    try:
        response = requests.delete(url, headers=headers, timeout=10)

        if response.status_code == 200:
            return {'success': True, 'cbt_id': cbt_id, 'message': 'Eliminado'}
        elif response.status_code == 404:
            return {'success': False, 'cbt_id': cbt_id, 'message': 'No encontrado'}
        elif response.status_code == 204:
            return {'success': True, 'cbt_id': cbt_id, 'message': 'Eliminado (204)'}
        else:
            return {'success': False, 'cbt_id': cbt_id, 'message': f'Error {response.status_code}: {response.text[:100]}'}
    except Exception as e:
        return {'success': False, 'cbt_id': cbt_id, 'message': f'Exception: {str(e)}'}

def main():
    """
    Función principal.
    """
    if not ML_ACCESS_TOKEN:
        print("❌ Error: ML_ACCESS_TOKEN no encontrado en .env")
        return

    # Leer lista de CBT IDs sin marketplace
    cbt_ids = []
    with open('cbt_sin_mp_PRECISO.txt', 'r') as f:
        cbt_ids = [line.strip() for line in f if line.strip()]

    print(f"📋 Items CBT sin marketplace items a eliminar: {len(cbt_ids)}")
    print(f"⚠️  ADVERTENCIA: Se van a eliminar {len(cbt_ids)} items de MercadoLibre")
    print(f"   Estos son items que NO tienen IDs locales (MLA, MLB, MLM, etc)")
    print()

    # Confirmar
    response = input("¿Continuar? (escribe 'SI' para confirmar): ")
    if response != 'SI':
        print("❌ Cancelado por el usuario")
        return

    print(f"\n🗑️  Iniciando eliminación con 10 workers paralelos...")
    print()

    deleted = 0
    failed = 0

    # Eliminar en paralelo
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(delete_item, cbt_id): cbt_id for cbt_id in cbt_ids}

        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()

            if result['success']:
                deleted += 1
                print(f"   ✅ [{i}/{len(cbt_ids)}] {result['cbt_id']} - {result['message']}")
            else:
                failed += 1
                print(f"   ❌ [{i}/{len(cbt_ids)}] {result['cbt_id']} - {result['message']}")

            # Pequeño delay cada 50 items para evitar rate limiting
            if i % 50 == 0:
                time.sleep(1)

    print()
    print(f"{'='*80}")
    print(f"✅ Proceso completado:")
    print(f"   Eliminados exitosamente: {deleted}")
    print(f"   Fallidos: {failed}")
    print(f"   Total procesados: {deleted + failed}")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
