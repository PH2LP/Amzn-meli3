#!/bin/bash
# ============================================================
# LOOP CONTINUO DE SINCRONIZACIÓN AMAZON → MERCADOLIBRE
# ============================================================
# Ejecuta sync_amazon_ml.py cada 3 días (72 horas) en loop infinito
# Uso: ./scripts/tools/sync_loop.sh

PROJECT_DIR="/Users/felipemelucci/Desktop/revancha"
cd "$PROJECT_DIR" || exit 1

# Configuración
SYNC_INTERVAL=$((72 * 60 * 60))  # 72 horas = 3 días en segundos
LOG_FILE="logs/sync_loop.log"

echo "🔄 Iniciando loop de sincronización Amazon → ML" | tee -a "$LOG_FILE"
echo "⏰ Intervalo: cada 3 días (72 horas)" | tee -a "$LOG_FILE"
echo "📅 $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

while true; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
    echo "🔄 Ejecutando sincronización: $(date)" | tee -a "$LOG_FILE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"

    # Ejecutar sincronización
    ./venv/bin/python3 scripts/tools/sync_amazon_ml.py 2>&1 | tee -a "$LOG_FILE"

    SYNC_STATUS=$?

    if [ $SYNC_STATUS -eq 0 ]; then
        echo "✅ Sincronización completada exitosamente" | tee -a "$LOG_FILE"
    else
        echo "❌ Error en sincronización (código: $SYNC_STATUS)" | tee -a "$LOG_FILE"
    fi

    echo "" | tee -a "$LOG_FILE"
    echo "⏰ Próxima ejecución en 72 horas (3 días)" | tee -a "$LOG_FILE"
    echo "⏸️  Esperando... (puedes detener con Ctrl+C)" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"

    # Esperar 3 días
    sleep $SYNC_INTERVAL
done
