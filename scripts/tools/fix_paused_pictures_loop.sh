#!/bin/bash
# Loop automático para corrección de fotos pausadas
# Ejecuta cada 30 minutos

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT" || exit 1

# Log
LOG_FILE="logs/fix_paused_pictures_loop.log"
mkdir -p logs

echo "════════════════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "🔧 LOOP DE CORRECCIÓN AUTOMÁTICA DE FOTOS PAUSADAS" | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "📂 Proyecto: $PROJECT_ROOT" | tee -a "$LOG_FILE"
echo "⏱️  Intervalo: Cada 30 minutos" | tee -a "$LOG_FILE"
echo "🛑 Para detener: Ctrl+C" | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$TIMESTAMP] 🔍 Ejecutando corrección de fotos..." | tee -a "$LOG_FILE"

    # Ejecutar script de corrección
    ./venv/bin/python3 scripts/tools/fix_paused_pictures.py 2>&1 | tee -a "$LOG_FILE"

    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$TIMESTAMP] ✅ Ciclo completado. Esperando 30 minutos..." | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"

    # Esperar 30 minutos
    sleep 1800
done
