#!/usr/bin/env python3
"""
Monitor de propagación de stock en MercadoLibre
Verifica cada 2 minutos si el cambio de stock se reflejó en el sitio web
"""
import os
import sys
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
ML_TOKEN = os.getenv('ML_ACCESS_TOKEN')

def check_item_status(item_id):
    """Verifica el status del item en la API"""
    url = f'https://api.mercadolibre.com/items/{item_id}'
    headers = {'Authorization': f'Bearer {ML_TOKEN}'}

    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            return {
                'status': data.get('status'),
                'stock': data.get('available_quantity'),
                'sub_status': data.get('sub_status', [])
            }
    except Exception as e:
        print(f"Error: {e}")

    return None

def main():
    item_id = "CBT2809400199"
    brasil_url = "https://produto.mercadolivre.com.br/MLB-4360767333"

    print("=" * 70)
    print("MONITOR DE PROPAGACIÓN DE STOCK - MERCADOLIBRE")
    print("=" * 70)
    print(f"Item ID: {item_id}")
    print(f"URL Brasil: {brasil_url}")
    print()
    print("Presiona Ctrl+C para detener")
    print("=" * 70)
    print()

    iteration = 0

    try:
        while True:
            iteration += 1
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print(f"[{now}] Check #{iteration}")

            # Verificar API
            status = check_item_status(item_id)
            if status:
                print(f"  API Status: {status['status']}")
                print(f"  API Stock: {status['stock']}")
                print(f"  API Sub-status: {status['sub_status']}")

                if status['stock'] == 0 and status['status'] == 'paused':
                    print(f"  ✅ API: Producto correctamente pausado")
                else:
                    print(f"  ⚠️  API: Stock no es 0 o no está pausado")
            else:
                print(f"  ❌ No se pudo consultar la API")

            print()
            print(f"  🌐 Abre esta URL en modo incógnito para verificar el sitio:")
            print(f"     {brasil_url}")
            print()
            print(f"  ⏰ Próximo check en 2 minutos...")
            print("-" * 70)
            print()

            # Esperar 2 minutos
            time.sleep(120)

    except KeyboardInterrupt:
        print()
        print("Monitor detenido")
        print()

if __name__ == "__main__":
    main()
