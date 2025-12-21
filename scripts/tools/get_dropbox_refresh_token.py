#!/usr/bin/env python3
"""
Script para obtener Dropbox Refresh Token usando OAuth2 flow.
Solo necesitas correrlo UNA VEZ para obtener el refresh token.
"""

import sys
from pathlib import Path
import urllib.parse
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
import os

# Load environment
load_dotenv(PROJECT_ROOT / '.env')

APP_KEY = os.getenv('DROPBOX_APP_KEY')
APP_SECRET = os.getenv('DROPBOX_APP_SECRET')

if not APP_KEY or not APP_SECRET:
    print("❌ Error: DROPBOX_APP_KEY y DROPBOX_APP_SECRET no están en .env")
    sys.exit(1)


def get_authorization_url():
    """Generate OAuth2 authorization URL"""
    auth_url = "https://www.dropbox.com/oauth2/authorize"
    params = {
        'client_id': APP_KEY,
        'response_type': 'code',
        'token_access_type': 'offline'  # This requests a refresh token
    }

    url = f"{auth_url}?{urllib.parse.urlencode(params)}"
    return url


def exchange_code_for_tokens(authorization_code):
    """Exchange authorization code for access token + refresh token"""
    import requests

    token_url = "https://api.dropboxapi.com/oauth2/token"

    data = {
        'code': authorization_code,
        'grant_type': 'authorization_code',
        'client_id': APP_KEY,
        'client_secret': APP_SECRET
    }

    response = requests.post(token_url, data=data)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error al obtener tokens: {response.status_code}")
        print(response.text)
        return None


def main():
    print("=" * 80)
    print("  🔐 DROPBOX OAUTH2 - OBTENER REFRESH TOKEN")
    print("=" * 80)
    print()

    # Step 1: Generate authorization URL
    auth_url = get_authorization_url()

    print("PASO 1: Autorizar la aplicación")
    print("-" * 80)
    print()
    print("Abrí esta URL en tu navegador:")
    print()
    print(f"  {auth_url}")
    print()
    print("Después de autorizar, Dropbox te mostrará un código de autorización.")
    print()

    # Step 2: Get authorization code from user
    # Support both command line argument and interactive input
    auth_code = None
    if len(sys.argv) > 1:
        auth_code = sys.argv[1].strip()
        print(f"Usando código desde argumento: {auth_code[:10]}...")
    else:
        try:
            auth_code = input("PASO 2: Pegá el código de autorización aquí: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("❌ Operación cancelada")
            print()
            print("Podés ejecutar con el código como argumento:")
            print(f"  python3 {sys.argv[0]} <código>")
            sys.exit(1)

    if not auth_code:
        print("❌ No ingresaste ningún código")
        sys.exit(1)

    print()
    print("Obteniendo tokens...")

    # Step 3: Exchange code for tokens
    tokens = exchange_code_for_tokens(auth_code)

    if not tokens:
        print("❌ Error al obtener tokens")
        sys.exit(1)

    # Step 4: Display results
    print()
    print("=" * 80)
    print("  ✅ TOKENS OBTENIDOS EXITOSAMENTE")
    print("=" * 80)
    print()

    access_token = tokens.get('access_token')
    refresh_token = tokens.get('refresh_token')

    print(f"Access Token (válido por ~4 horas):")
    print(f"  {access_token}")
    print()
    print(f"Refresh Token (NUNCA expira):")
    print(f"  {refresh_token}")
    print()

    # Step 5: Update .env file
    print("Actualizando .env...")

    env_path = PROJECT_ROOT / '.env'
    env_content = env_path.read_text()

    # Update or add tokens
    if 'DROPBOX_ACCESS_TOKEN=' in env_content:
        lines = env_content.split('\n')
        new_lines = []
        refresh_token_exists = False

        for line in lines:
            if line.startswith('DROPBOX_ACCESS_TOKEN='):
                new_lines.append(f'DROPBOX_ACCESS_TOKEN={access_token}')
            elif line.startswith('DROPBOX_REFRESH_TOKEN='):
                new_lines.append(f'DROPBOX_REFRESH_TOKEN={refresh_token}')
                refresh_token_exists = True
            else:
                new_lines.append(line)

        # Add refresh token if it doesn't exist
        if not refresh_token_exists:
            # Find DROPBOX_ACCESS_TOKEN line and add refresh token after it
            for i, line in enumerate(new_lines):
                if line.startswith('DROPBOX_ACCESS_TOKEN='):
                    new_lines.insert(i + 1, f'DROPBOX_REFRESH_TOKEN={refresh_token}')
                    break

        env_content = '\n'.join(new_lines)
    else:
        # Add both tokens at the end
        env_content += f'\n\n# Dropbox OAuth2 Tokens\n'
        env_content += f'DROPBOX_ACCESS_TOKEN={access_token}\n'
        env_content += f'DROPBOX_REFRESH_TOKEN={refresh_token}\n'

    env_path.write_text(env_content)

    print("✅ .env actualizado con los nuevos tokens")
    print()
    print("=" * 80)
    print("  🎉 CONFIGURACIÓN COMPLETA")
    print("=" * 80)
    print()
    print("El refresh token NUNCA expira (a menos que lo revokes).")
    print("El sistema ahora puede auto-refrescar el access token automáticamente.")
    print()
    print("Próximo paso:")
    print("  python3 21_deploy_sales_tracking.py")
    print()


if __name__ == '__main__':
    main()
