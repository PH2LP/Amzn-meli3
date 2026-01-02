#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 12_refresh_token.py - REFRESCAR TOKEN ML MANUALMENTE
# ═══════════════════════════════════════════════════════════════════════════════
#
# ¿Qué hace?
#   Refresca manualmente el access token de MercadoLibre.
#   Útil cuando necesitás renovar el token sin esperar el loop automático.
#
# Comando:
#   python3 12_refresh_token.py
# 
# ═══════════════════════════════════════════════════════════════════════════════
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
