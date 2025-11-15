#!/bin/bash
# ============================================================
# SYNC CONTINUO AMAZON → MERCADOLIBRE (CADA 6 HORAS)
# ============================================================
# Monitorea precios y stock de Amazon, actualiza MercadoLibre automáticamente
# - Detecta cambios de precio → Actualiza precio en ML
# - Detecta productos sin stock → Pausa en ML (stock=0)
# - Detecta productos disponibles de nuevo → Reactiva en ML (stock=10)
# - Actualiza BD automáticamente con cada cambio

PROJECT_DIR="/Users/felipemelucci/Desktop/revancha"
cd "$PROJECT_DIR" || exit 1

# Configuración: cada 6 horas
SYNC_INTERVAL=$((6 * 60 * 60))
LOG_FILE="logs/sync_amazon_ml_loop.log"

echo "🔄 Iniciando sincronización continua Amazon → MercadoLibre" | tee -a "$LOG_FILE"
echo "⏰ Frecuencia: cada 6 horas" | tee -a "$LOG_FILE"
echo "📅 Inicio: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

while true; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
    echo "🔄 Ejecutando sincronización: $(date)" | tee -a "$LOG_FILE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"

    # Ejecutar sincronización
    ./venv/bin/python3 scripts/tools/sync_amazon_ml.py 2>&1 | tee -a "$LOG_FILE"

    STATUS=$?

    echo "" | tee -a "$LOG_FILE"
    if [ $STATUS -eq 0 ]; then
        echo "✅ Sincronización completada exitosamente" | tee -a "$LOG_FILE"
    else
        echo "❌ Error en sincronización (código: $STATUS)" | tee -a "$LOG_FILE"
    fi

    echo "" | tee -a "$LOG_FILE"
    echo "⏰ Próxima sincronización en 6 horas ($(date -v+6H '+%Y-%m-%d %H:%M'))" | tee -a "$LOG_FILE"
    echo "⏸️  Esperando... (Ctrl+C para detener)" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"

    # Esperar 6 horas
    sleep $SYNC_INTERVAL
done
