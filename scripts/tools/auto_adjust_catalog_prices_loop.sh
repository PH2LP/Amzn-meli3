#!/bin/bash

# Loop automático que:
# 1. Detecta productos de catálogo
# 2. Ajusta precios automáticamente respetando margen mínimo 25%
# Ejecuta cada 6 horas (respeta límites de ML)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

LOG_FILE="logs/auto_adjust_prices.log"
mkdir -p logs

echo "💰 Iniciando ajuste automático de precios de catálogo..."
echo "   Revisando cada 6 horas"
echo "   Margen mínimo: 25%"
echo "   Log: $LOG_FILE"
echo ""

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
    echo "[$TIMESTAMP] Iniciando ajuste de precios..." | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"

    # Paso 1: Detectar productos de catálogo
    echo "🔍 Paso 1: Detectando productos de catálogo..." | tee -a "$LOG_FILE"
    ./venv/bin/python3 scripts/tools/check_catalog_items.py 2>&1 | tee -a "$LOG_FILE"

    # Paso 2: Ajustar precios de productos de catálogo
    CATALOG_COUNT=$(sqlite3 storage/listings_database.db "SELECT COUNT(*) FROM listings WHERE es_catalogo = 1 AND asin NOT LIKE 'TEST%';")

    if [ "$CATALOG_COUNT" -gt 0 ]; then
        echo "" | tee -a "$LOG_FILE"
        echo "💰 Paso 2: Ajustando precios de $CATALOG_COUNT productos..." | tee -a "$LOG_FILE"
        ./venv/bin/python3 scripts/tools/adjust_catalog_prices.py 2>&1 | tee -a "$LOG_FILE"
    else
        echo "" | tee -a "$LOG_FILE"
        echo "ℹ️  No hay productos de catálogo para ajustar" | tee -a "$LOG_FILE"
    fi

    echo "" | tee -a "$LOG_FILE"
    echo "⏰ Próxima ejecución en 6 horas ($(date -v+6H '+%Y-%m-%d %H:%M'))..." | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"

    # Esperar 6 horas
    sleep 21600
done
