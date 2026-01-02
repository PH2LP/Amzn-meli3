#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 10_telegram_notifier.py - NOTIFICACIONES TELEGRAM DE VENTAS
# ═══════════════════════════════════════════════════════════════════════════════
#
# ¿Qué hace?
#   - Monitorea nuevas ventas en MercadoLibre cada 60 segundos
#   - Envía notificaciones por Telegram con info completa del producto
#   - Incluye enlace de Amazon para comprar el producto
#
# Comando:
#   python3 10_telegram_notifier.py
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
    print(f"{Colors.BLUE}║          TELEGRAM SALES NOTIFIER                             ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.NC}\n")

    print(f"{Colors.CYAN}📲 El daemon enviará notificaciones de ventas cada 60 segundos{Colors.NC}\n")
    print(f"{Colors.YELLOW}⚠️  Presioná Ctrl+C para detener{Colors.NC}\n")
    print(f"{Colors.BLUE}{'─' * 64}{Colors.NC}\n")

    # Ejecutar en foreground mostrando output
    try:
        subprocess.run(["python3", "scripts/tools/telegram_sales_notifier.py"])
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}🛑 Daemon detenido por usuario{Colors.NC}")

if __name__ == "__main__":
    main()
