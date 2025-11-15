#!/bin/bash
# ============================================================
# Auto Cleanup Loop - Limpia archivos JSON cada 24 horas
# ============================================================

cd "$(dirname "$0")/../.."

echo "🧹 Sistema de limpieza automática iniciado"
echo "   Limpiará archivos JSON cada 24 horas"
echo "   Presiona Ctrl+C para detener"

while true; do
    echo ""
    echo "════════════════════════════════════════════════════"
    echo "🕐 $(date '+%Y-%m-%d %H:%M:%S') - Ejecutando limpieza..."
    echo "════════════════════════════════════════════════════"

    # Ejecutar limpieza
    python3 scripts/cleanup/clean_old_json_files.py --force

    echo ""
    echo "⏰ Próxima limpieza en 24 horas..."
    sleep 86400  # 24 horas
done
