#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 11_auto_answer.py - AUTO-RESPUESTA DE PREGUNTAS
# ═══════════════════════════════════════════════════════════════════════════════
#
# ¿Qué hace?
#   Responde automáticamente preguntas de clientes en MercadoLibre usando IA.
#   Chequea cada 60 segundos y responde preguntas pendientes con contexto del producto.
#
# Comando:
#   python3 11_auto_answer.py
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
    print(f"{Colors.BLUE}║          AUTO-ANSWER DAEMON                                  ║{Colors.NC}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.NC}\n")

    print(f"{Colors.CYAN}💬 El daemon monitoreará y responderá preguntas automáticamente{Colors.NC}\n")
    print(f"{Colors.YELLOW}⚠️  Presioná Ctrl+C para detener{Colors.NC}\n")
    print(f"{Colors.BLUE}{'─' * 64}{Colors.NC}\n")

    # Ejecutar en foreground mostrando output
    try:
        subprocess.run(["python3", "scripts/tools/auto_answer_questions.py"])
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}🛑 Daemon detenido por usuario{Colors.NC}")

if __name__ == "__main__":
    main()
