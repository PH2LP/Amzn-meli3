#!/bin/bash

# Monitor continuo de productos que pasan a catálogo
# Revisa cada 30 minutos si algún producto fue asociado a catálogo por ML

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

LOG_FILE="logs/catalog_monitor.log"
mkdir -p logs

echo "🔍 Iniciando monitor de productos catálogo..."
echo "   Revisando cada 30 minutos"
echo "   Log: $LOG_FILE"
echo ""

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
    echo "[$TIMESTAMP] Revisando productos..." | tee -a "$LOG_FILE"

    # Ejecutar check de catálogo
    ./venv/bin/python3 scripts/tools/check_catalog_items.py 2>&1 | tee -a "$LOG_FILE"

    # Si encontró productos de catálogo, ejecutar ajuste de precios
    CATALOG_COUNT=$(sqlite3 storage/listings_database.db "SELECT COUNT(*) FROM listings WHERE es_catalogo = 1 AND asin NOT LIKE 'TEST%';")

    if [ "$CATALOG_COUNT" -gt 0 ]; then
        echo "" | tee -a "$LOG_FILE"
        echo "🏷️  Encontrados $CATALOG_COUNT productos de catálogo" | tee -a "$LOG_FILE"
        echo "💡 Puedes ejecutar:" | tee -a "$LOG_FILE"
        echo "   python3 scripts/tools/adjust_catalog_prices.py --dry-run" | tee -a "$LOG_FILE"
    fi

    echo "" | tee -a "$LOG_FILE"
    echo "⏰ Próxima revisión en 30 minutos..." | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"

    # Esperar 30 minutos
    sleep 1800
done
