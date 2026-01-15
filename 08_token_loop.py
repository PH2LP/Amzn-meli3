#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 08_token_loop.py - RENOVACIÓN AUTOMÁTICA TOKEN MERCADOLIBRE
# ═══════════════════════════════════════════════════════════════════════════════
#
# ¿Qué hace?
#   Renueva automáticamente el token de MercadoLibre en horarios configurables.
#   Los horarios se configuran en .env con ML_TOKEN_REFRESH_SCHEDULED_TIMES
#   Default: "00:00,06:00,12:00,18:00" (cada 6 horas)
#   Actualiza el .env con el nuevo token.
#
# Comando:
#   python3 08_token_loop.py
#
# Configuración:
#   Editar ML_TOKEN_REFRESH_SCHEDULED_TIMES en .env
#   Ejemplo: "00:00,05:00,10:00,15:00,20:00" (cada 5 horas)
#
# Ctrl+C para detener
# ═══════════════════════════════════════════════════════════════════════════════
import subprocess

# Colores
class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

def main():
    print(f"{Colors.BLUE}╔════════════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BLUE}║          ML TOKEN REFRESH LOOP                               ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.NC}\n")

    print(f"{Colors.CYAN}⏰ Horarios configurados en .env (ML_TOKEN_REFRESH_SCHEDULED_TIMES){Colors.NC}")
    print(f"{Colors.YELLOW}⚠️  Presioná Ctrl+C para detener{Colors.NC}\n")
    print(f"{Colors.BLUE}{'─' * 64}{Colors.NC}\n")

    # Ejecutar en foreground mostrando output
    try:
        subprocess.run(["python3", "_token_loop.py"])
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}🛑 Loop detenido por usuario{Colors.NC}")

if __name__ == "__main__":
    main()
