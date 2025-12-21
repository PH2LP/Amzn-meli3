#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refresh_ml_token.py
═══════════════════════════════════════════════════════════════════════════════
REFRESH ML TOKEN: Actualiza el token de MercadoLibre manualmente
═══════════════════════════════════════════════════════════════════════════════

Refresca el access token de MercadoLibre y lo guarda en el .env

USO:
    python3 16_refresh_ml_token.py
═══════════════════════════════════════════════════════════════════════════════
"""

import sys
sys.path.insert(0, 'src/integrations')

def main():
    from mainglobal import refresh_ml_token

    print("🔄 Refrescando token de MercadoLibre...")
    print()

    if refresh_ml_token(force=True):
        print()
        print("✅ Token actualizado exitosamente")
        print("   El nuevo token se guardó en .env")
        return 0
    else:
        print()
        print("❌ Error al actualizar token")
        return 1

if __name__ == "__main__":
    sys.exit(main())
