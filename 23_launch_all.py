#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 23_launch_all.py - LAUNCHER DE TODOS LOS SCRIPTS
# ═══════════════════════════════════════════════════════════════════════════════
#
# ¿Qué hace?
#   - Abre Terminal.app con pestañas organizadas
#   - Ejecuta cada script en su propia pestaña
#   - Layout: mismo orden que tu setup actual
#
# Comando:
#   python3 23_launch_all.py
#
# ═══════════════════════════════════════════════════════════════════════════════

import subprocess
import os
from pathlib import Path

# Colores
class Colors:
    GREEN = '\033[0;32m'
    CYAN = '\033[0;36m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'

def main():
    print(f"{Colors.CYAN}╔════════════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.CYAN}║          LAUNCHER DE TODOS LOS SCRIPTS                       ║{Colors.NC}")
    print(f"{Colors.CYAN}╚════════════════════════════════════════════════════════════════╝{Colors.NC}\n")

    # Obtener la ruta absoluta del directorio actual
    project_dir = Path(__file__).parent.absolute()

    print(f"{Colors.GREEN}📂 Directorio del proyecto: {project_dir}{Colors.NC}\n")
    print(f"{Colors.YELLOW}🚀 Abriendo Terminal con todas las pestañas...{Colors.NC}\n")

    # CÁLCULO EXACTO para ventanas pegadas:
    # - Píxeles por fila: 20px
    # - Barra título: 22px
    # - Ancho ventana 87 cols: ~580px

    PX_PER_ROW = 20
    TITLE_BAR = 22
    COL_WIDTH = 580  # Ancho de ventana de 87 columnas

    # COLUMNA IZQUIERDA (x=0) - calcular Y para que estén pegadas
    y1 = 25  # Primera ventana
    y2 = y1 + (11 * PX_PER_ROW) + TITLE_BAR  # 25 + 220 + 22 = 267
    y3 = y2 + (11 * PX_PER_ROW) + TITLE_BAR  # 267 + 220 + 22 = 509
    y4 = y3 + (11 * PX_PER_ROW) + TITLE_BAR  # 509 + 220 + 22 = 751

    # COLUMNA DERECHA (x=580) - calcular Y para que estén pegadas
    y5 = 25  # Primera ventana derecha
    y6 = y5 + (21 * PX_PER_ROW) + TITLE_BAR  # 25 + 420 + 22 = 467
    y7 = y6 + (20 * PX_PER_ROW) + TITLE_BAR  # 467 + 400 + 22 = 889

    scripts_layout = [
        # Columna izquierda (x=0)
        ("11_auto_answer.py", 87, 11, 0, y1),              # 87x11
        ("18_price_automate_loop.py", 87, 11, 0, y2),      # 87x11
        ("09_sales_tracking.py", 87, 11, 0, y3),           # 87x11
        ("10_telegram_notifier.py", 87, 10, 0, y4),        # 87x10

        # Columna derecha (x=580)
        ("06_sync_loop.py", 87, 21, COL_WIDTH, y5),        # 87x21
        ("22_system_monitor.py", 87, 20, COL_WIDTH, y6),   # 87x20
        ("08_token_loop.py", 87, 8, COL_WIDTH, y7),        # 87x8
    ]

    # AppleScript para abrir Terminal con tamaños en columnas/filas
    applescript = f'''
tell application "Terminal"
    activate
    set projectDir to "{project_dir}"

'''

    # Crear cada ventana con tamaño en columnas y filas
    for idx, (script, cols, rows, x, y) in enumerate(scripts_layout):
        if idx == 0:
            # Primera ventana
            applescript += f'''
    -- VENTANA 1: {script} ({cols}x{rows})
    do script "cd " & quoted form of projectDir & " && python3 {script}" in window 1
    tell front window
        set number of columns to {cols}
        set number of rows to {rows}
        set position to {{{x}, {y}}}
    end tell
    delay 1

'''
        else:
            # Nuevas ventanas
            applescript += f'''
    -- VENTANA {idx + 1}: {script} ({cols}x{rows})
    do script "cd " & quoted form of projectDir & " && python3 {script}"
    tell front window
        set number of columns to {cols}
        set number of rows to {rows}
        set position to {{{x}, {y}}}
    end tell
    delay 1

'''

    applescript += '''
end tell
'''

    # Ejecutar AppleScript
    subprocess.run(['osascript', '-e', applescript])

    print(f"\n{Colors.GREEN}✅ Todas las ventanas creadas y scripts iniciados{Colors.NC}\n")
    print(f"{Colors.CYAN}📋 Layout optimizado (7 ventanas):{Colors.NC}")
    print(f"\n  IZQUIERDA              DERECHA")
    print(f"  ┌─────────────────┐    ┌─────────────────┐")
    print(f"  │ 11_auto_answer  │    │                 │")
    print(f"  ├─────────────────┤    │ 06_sync_loop    │")
    print(f"  │ 18_price_auto   │    │ (alto)          │")
    print(f"  ├─────────────────┤    ├─────────────────┤")
    print(f"  │ 09_sales_track  │    │                 │")
    print(f"  ├─────────────────┤    │ 22_monitor      │")
    print(f"  │ 10_telegram     │    │ (alto)          │")
    print(f"  └─────────────────┘    ├─────────────────┤")
    print(f"                         │ 08_token_loop   │")
    print(f"                         └─────────────────┘")
    print(f"\n{Colors.YELLOW}💡 Tamaños: 87x11 (chicas), 87x20-21 (altas){Colors.NC}\n")

if __name__ == "__main__":
    main()
