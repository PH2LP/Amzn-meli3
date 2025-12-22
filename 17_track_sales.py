#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
17_track_sales.py
═══════════════════════════════════════════════════════════════════════════════
RASTREAR Y REGISTRAR VENTAS DE MERCADOLIBRE
═══════════════════════════════════════════════════════════════════════════════

¿Qué hace?
    Registra ventas manualmente de MercadoLibre y calcula ganancias

USO:
    python3 17_track_sales.py                # Trackear nuevas
    python3 17_track_sales.py --stats        # Ver estadísticas

Monitorea ventas automáticamente y registra:
- Ingresos de MercadoLibre
- Costos de Amazon + 3PL
- Ganancia neta por venta
═══════════════════════════════════════════════════════════════════════════════
"""

import subprocess
import sys

# Ejecutar el script principal
result = subprocess.run(
    ["python3", "scripts/tools/track_sales.py"] + sys.argv[1:],
    cwd="/Users/felipemelucci/Desktop/revancha"
)

sys.exit(result.returncode)
