#!/usr/bin/env python3
"""
Dropbox authentication with automatic token refresh.
All scripts should use get_dropbox_client() to get a valid Dropbox client.
"""

import os
import sys
from pathlib import Path
import time
import json
from datetime import datetime, timedelta

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv, set_key

# Load environment
ENV_PATH = PROJECT_ROOT / '.env'
load_dotenv(ENV_PATH, override=True)

# File to store token expiration time
TOKEN_CACHE_FILE = PROJECT_ROOT / 'storage' / '.dropbox_token_cache.json'

# Cache for token expiration time
_token_cache = {
    'expires_at': None
}

def get_access_token_from_env():
    """Get the current access token from .env file"""
    load_dotenv(ENV_PATH, override=True)
    return os.getenv('DROPBOX_ACCESS_TOKEN')

def load_token_cache():
    """Load token cache from file"""
    global _token_cache
    try:
        if TOKEN_CACHE_FILE.exists():
            with open(TOKEN_CACHE_FILE, 'r') as f:
                data = json.load(f)
                if 'expires_at' in data:
                    # Parse ISO format datetime
                    _token_cache['expires_at'] = datetime.fromisoformat(data['expires_at'])
    except Exception as e:
        # If cache is corrupted, ignore and continue
        pass

def save_token_cache():
    """Save token cache to file"""
    try:
        TOKEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if _token_cache['expires_at']:
            data['expires_at'] = _token_cache['expires_at'].isoformat()
        with open(TOKEN_CACHE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        # Non-critical error, just print warning
        pass

# Load cache on module import
load_token_cache()


def refresh_access_token():
    """
    Use refresh token to get a new access token.
    Returns the new access token or None if failed.
    """
    load_dotenv(ENV_PATH, override=True)
    refresh_token = os.getenv('DROPBOX_REFRESH_TOKEN')
    app_key = os.getenv('DROPBOX_APP_KEY')
    app_secret = os.getenv('DROPBOX_APP_SECRET')

    if not refresh_token or not refresh_token.strip():
        print("⚠️  DROPBOX_REFRESH_TOKEN no está configurado en .env")
        print("   Ejecutá: python3 scripts/tools/get_dropbox_refresh_token.py")
        return None

    import requests

    token_url = "https://api.dropboxapi.com/oauth2/token"

    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': app_key,
        'client_secret': app_secret
    }

    try:
        response = requests.post(token_url, data=data)

        if response.status_code == 200:
            token_data = response.json()
            new_access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 14400)  # Default 4 hours

            # Update .env file with new token
            set_key(ENV_PATH, 'DROPBOX_ACCESS_TOKEN', new_access_token)

            # Reload .env to update os.environ
            load_dotenv(ENV_PATH, override=True)

            # Update cache (expiration only, token is in .env)
            _token_cache['expires_at'] = datetime.now() + timedelta(seconds=expires_in - 300)  # Refresh 5min before expiry

            # Save cache to file
            save_token_cache()

            print(f"✅ Access token refrescado automáticamente (válido por {expires_in/3600:.1f}h)")
            return new_access_token
        else:
            print(f"❌ Error al refrescar token: {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Exception al refrescar token: {e}")
        return None


def get_valid_access_token():
    """
    Get a valid access token, refreshing if necessary.
    Returns the current valid token or None if unable to refresh.
    """
    # If we don't know when token expires, refresh it proactively
    if _token_cache['expires_at'] is None:
        print("🔄 Token sin expiración conocida, refrescando proactivamente...")
        new_token = refresh_access_token()
        if new_token:
            return new_token
        else:
            # Refresh failed, try using current token anyway
            return get_access_token_from_env()

    # Check if token is about to expire or already expired
    if datetime.now() >= _token_cache['expires_at']:
        # Token expired or about to expire, refresh it
        new_token = refresh_access_token()
        if new_token:
            return new_token
        else:
            # Refresh failed, try using current token anyway
            return get_access_token_from_env()

    # Token is still valid
    return get_access_token_from_env()


def get_dropbox_client():
    """
    Get a Dropbox client with a valid access token.
    Automatically handles token refresh.
    """
    try:
        import dropbox
    except ImportError:
        print("❌ dropbox library no instalada")
        print("   Ejecutá: pip3 install dropbox")
        return None

    # Get valid token (will auto-refresh if needed)
    access_token = get_valid_access_token()

    if not access_token:
        print("❌ No hay access token válido")
        return None

    # Create Dropbox client
    try:
        dbx = dropbox.Dropbox(access_token)

        # Test the connection by getting account info
        # This will fail if token is invalid
        try:
            dbx.users_get_current_account()
            return dbx
        except dropbox.exceptions.AuthError as e:
            # Token is invalid/expired, try to refresh
            print(f"⚠️  Token inválido, intentando refrescar...")

            # Mark token as expired to force refresh
            _token_cache['expires_at'] = datetime.now() - timedelta(seconds=1)

            # Try to refresh
            new_token = refresh_access_token()
            if new_token:
                # Create new client with refreshed token
                dbx = dropbox.Dropbox(new_token)
                dbx.users_get_current_account()  # Verify it works
                return dbx
            else:
                print(f"❌ No se pudo refrescar el token: {e}")
                return None

    except Exception as e:
        print(f"❌ Error al crear cliente Dropbox: {e}")
        return None


def test_auth():
    """Test Dropbox authentication"""
    print("=" * 80)
    print("  🔐 PROBANDO AUTENTICACIÓN DROPBOX")
    print("=" * 80)
    print()

    dbx = get_dropbox_client()

    if dbx:
        try:
            account = dbx.users_get_current_account()
            print(f"✅ Autenticación exitosa")
            print(f"   Usuario: {account.name.display_name}")
            print(f"   Email: {account.email}")
            print()
            print("=" * 80)
            print("  ✅ TODO OK - Dropbox conectado correctamente")
            print("=" * 80)
            return True
        except Exception as e:
            print(f"❌ Error al obtener cuenta: {e}")
            return False
    else:
        print("❌ No se pudo crear cliente Dropbox")
        print()
        print("Verificá que:")
        print("  1. DROPBOX_REFRESH_TOKEN esté en .env")
        print("  2. DROPBOX_APP_KEY y DROPBOX_APP_SECRET sean correctos")
        print()
        print("Si no tenés refresh token, ejecutá:")
        print("  python3 scripts/tools/get_dropbox_refresh_token.py")
        return False


if __name__ == '__main__':
    test_auth()
