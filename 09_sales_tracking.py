#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 09_sales_tracking.py - TRACKING DE VENTAS
# ═══════════════════════════════════════════════════════════════════════════════
#
# ¿Qué hace?
#   - Trackea ventas nuevas en MercadoLibre cada 60 segundos
#   - Genera Excel profesional con dashboard de ventas
#   - Sube Excel y DBs a Dropbox automáticamente
#
# Comando:
#   python3 09_sales_tracking.py
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
    print(f"{Colors.BLUE}║          SALES TRACKING DAEMON                               ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.NC}\n")

    print(f"{Colors.CYAN}📊 El daemon monitoreará ventas cada 60 segundos{Colors.NC}\n")
    print(f"{Colors.YELLOW}⚠️  Presioná Ctrl+C para detener{Colors.NC}\n")
    print(f"{Colors.BLUE}{'─' * 64}{Colors.NC}\n")

    # Ejecutar en foreground mostrando output
    try:
        subprocess.run(["python3", "scripts/server/sales_tracking_daemon.py"])
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}🛑 Daemon detenido por usuario{Colors.NC}")

if __name__ == "__main__":
    main()
