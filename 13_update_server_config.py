#!/usr/bin/env python3
"""
update_server_config.py
────────────────────────────────────────────────────────────────────
Actualiza configuraciones del servidor (markup, tax, fulfillment cost)
────────────────────────────────────────────────────────────────────
"""

import os
import subprocess
import sys
import argparse
from dotenv import load_dotenv

load_dotenv()

# Colores
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
RED = '\033[0;31m'
NC = '\033[0m'

# Configuración desde .env
VPS_HOST = os.getenv("REMOTE_DB_HOST", "138.197.32.67")
VPS_USER = os.getenv("REMOTE_DB_USER", "root")
VPS_PASSWORD = os.getenv("REMOTE_DB_PASSWORD")
VPS_PATH = "/opt/amz-ml-system"

def update_server_env(key, value):
    """Actualiza una variable en el .env del servidor"""
    cmd = f"sshpass -p '{VPS_PASSWORD}' ssh -o StrictHostKeyChecking=no {VPS_USER}@{VPS_HOST} \"sed -i 's/^{key}=.*/{key}={value}/' {VPS_PATH}/.env\""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def get_server_env(key):
    """Obtiene el valor actual de una variable en el servidor"""
    cmd = f"sshpass -p '{VPS_PASSWORD}' ssh -o StrictHostKeyChecking=no {VPS_USER}@{VPS_HOST} \"grep '^{key}=' {VPS_PATH}/.env | cut -d'=' -f2\""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def main():
    parser = argparse.ArgumentParser(description="Actualizar configuración del servidor")
    parser.add_argument("--markup", type=int, help="Nuevo markup porcentaje (ej: 40)")
    parser.add_argument("--use-tax", choices=['true', 'false'], help="Activar/desactivar tax 7%%")
    parser.add_argument("--fulfillment-fee", type=float, help="Nuevo costo de fulfillment (ej: 4.5)")
    parser.add_argument("--show", action="store_true", help="Mostrar configuración actual")

    args = parser.parse_args()

    print()
    print(f"{BLUE}═══════════════════════════════════════════════════════════════════{NC}")
    print(f"{BLUE}          ACTUALIZAR CONFIGURACIÓN DEL SERVIDOR{NC}")
    print(f"{BLUE}═══════════════════════════════════════════════════════════════════{NC}")
    print()

    if args.show:
        print(f"{YELLOW}Configuración actual en el servidor:{NC}")
        print()
        markup = get_server_env("PRICE_MARKUP")
        use_tax = get_server_env("USE_TAX")
        fulfillment = get_server_env("FULFILLMENT_FEE") or "4.0"

        print(f"  PRICE_MARKUP:     {markup}%")
        print(f"  USE_TAX:          {use_tax}")
        print(f"  FULFILLMENT_FEE:  ${fulfillment}")
        print()
        return

    if not any([args.markup, args.use_tax, args.fulfillment_fee]):
        parser.print_help()
        return

    print(f"{YELLOW}Conectando a {VPS_HOST}...{NC}")
    print()

    # Actualizar markup
    if args.markup:
        old_value = get_server_env("PRICE_MARKUP")
        print(f"📊 PRICE_MARKUP: {old_value}% → {args.markup}%")
        update_server_env("PRICE_MARKUP", args.markup)

    # Actualizar tax
    if args.use_tax:
        old_value = get_server_env("USE_TAX")
        print(f"💰 USE_TAX: {old_value} → {args.use_tax}")
        update_server_env("USE_TAX", args.use_tax)

    # Actualizar fulfillment fee
    if args.fulfillment_fee:
        old_value = get_server_env("FULFILLMENT_FEE") or "4.0"
        print(f"📦 FULFILLMENT_FEE: ${old_value} → ${args.fulfillment_fee}")
        # Agregar si no existe
        cmd = f"sshpass -p '{VPS_PASSWORD}' ssh -o StrictHostKeyChecking=no {VPS_USER}@{VPS_HOST} \"grep -q '^FULFILLMENT_FEE=' {VPS_PATH}/.env && sed -i 's/^FULFILLMENT_FEE=.*/FULFILLMENT_FEE={args.fulfillment_fee}/' {VPS_PATH}/.env || echo 'FULFILLMENT_FEE={args.fulfillment_fee}' >> {VPS_PATH}/.env\""
        subprocess.run(cmd, shell=True)

    print()
    print(f"{GREEN}✅ Configuración actualizada en el servidor{NC}")
    print()
    print(f"{YELLOW}⚠️  IMPORTANTE:{NC}")
    print(f"   Las nuevas configuraciones se aplicarán en el próximo sync (cada 3 horas)")
    print(f"   Para aplicar cambios inmediatamente, ejecutá sync manualmente:")
    print(f"   ssh root@{VPS_HOST} 'cd {VPS_PATH} && python3 scripts/tools/sync_amazon_ml.py'")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}⏸️  Operación cancelada{NC}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{RED}❌ Error: {e}{NC}")
        sys.exit(1)
