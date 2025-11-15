#!/bin/bash
# Script para generar reporte anual automáticamente
# Se ejecuta el 1 de Enero de cada año

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_DIR/logs/annual_reports.log"

cd "$PROJECT_DIR" || exit 1

# Función para enviar notificación Telegram
send_telegram() {
    local message="$1"
    source .env 2>/dev/null

    if [ -n "$TELEGRAM_SYNC_BOT_TOKEN" ] && [ -n "$TELEGRAM_SYNC_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_SYNC_BOT_TOKEN}/sendMessage" \
            -d chat_id="${TELEGRAM_SYNC_CHAT_ID}" \
            -d text="$message" \
            -d parse_mode="HTML" > /dev/null 2>&1
    fi
}

# Calcular año anterior
LAST_YEAR=$(date -d 'last year' +%Y 2>/dev/null || date -v-1y +%Y 2>/dev/null)
CURRENT_DATE=$(date "+%Y-%m-%d %H:%M:%S")

echo "════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "📊 GENERACIÓN AUTOMÁTICA DE REPORTE ANUAL - $CURRENT_DATE" | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Notificar inicio
send_telegram "📊 <b>Generando Reporte Anual $LAST_YEAR</b>

⏳ Analizando datos históricos del año..."

# Generar reporte
echo "📈 Generando reporte del año $LAST_YEAR..." | tee -a "$LOG_FILE"
REPORT_OUTPUT=$(./venv/bin/python3 scripts/reports/generate_annual_report.py $LAST_YEAR 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "$REPORT_OUTPUT" >> "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    echo "✅ Reporte generado exitosamente" | tee -a "$LOG_FILE"

    # Extraer métricas del reporte JSON
    REPORT_FILE="reports/annual_report_${LAST_YEAR}.json"

    if [ -f "$REPORT_FILE" ]; then
        # Usar Python para extraer datos del JSON
        SUMMARY=$(./venv/bin/python3 -c "
import json
import sys

try:
    with open('$REPORT_FILE', 'r') as f:
        data = json.load(f)

    metrics = data.get('sync_metrics', {})
    db_stats = data.get('database_stats', {})

    print(f\"Total Syncs: {metrics.get('total_syncs', 0)}\")
    print(f\"Actualizaciones Precio: {metrics.get('total_price_updates', 0)}\")
    print(f\"Productos Pausados: {metrics.get('total_paused', 0)}\")
    print(f\"Productos Reactivados: {metrics.get('total_reactivated', 0)}\")
    print(f\"Productos Activos: {db_stats.get('total_products', 0)}\")

    # Precio promedio
    price_range = db_stats.get('price_range', {})
    if price_range:
        print(f\"Precio Promedio: \${price_range.get('avg', 0):.2f}\")

except Exception as e:
    print(f\"Error: {e}\")
    sys.exit(1)
")

        # Parsear el resumen
        TOTAL_SYNCS=$(echo "$SUMMARY" | grep "Total Syncs" | cut -d: -f2 | xargs)
        PRICE_UPDATES=$(echo "$SUMMARY" | grep "Actualizaciones Precio" | cut -d: -f2 | xargs)
        PAUSED=$(echo "$SUMMARY" | grep "Productos Pausados" | cut -d: -f2 | xargs)
        REACTIVATED=$(echo "$SUMMARY" | grep "Productos Reactivados" | cut -d: -f2 | xargs)
        ACTIVE_PRODUCTS=$(echo "$SUMMARY" | grep "Productos Activos" | cut -d: -f2 | xargs)
        AVG_PRICE=$(echo "$SUMMARY" | grep "Precio Promedio" | cut -d: -f2 | xargs)

        # Calcular tamaño del reporte
        REPORT_SIZE=$(du -h "$REPORT_FILE" | cut -f1)

        # Enviar resumen por Telegram
        send_telegram "✅ <b>Reporte Anual $LAST_YEAR Generado</b>

📊 <b>Resumen del Año:</b>
━━━━━━━━━━━━━━━━━━━━
🔄 Syncs realizados: $TOTAL_SYNCS
💰 Actualizaciones de precio: $PRICE_UPDATES
⏸️ Productos pausados: $PAUSED
▶️ Productos reactivados: $REACTIVATED
📦 Productos activos: $ACTIVE_PRODUCTS
💵 Precio promedio: $AVG_PRICE

📄 Archivo: <code>$REPORT_FILE</code>
📏 Tamaño: $REPORT_SIZE

⏱️ Generado: $(date +\"%d/%m/%Y %H:%M\")"

        echo "" | tee -a "$LOG_FILE"
        echo "📊 RESUMEN:" | tee -a "$LOG_FILE"
        echo "   Syncs: $TOTAL_SYNCS" | tee -a "$LOG_FILE"
        echo "   Actualizaciones precio: $PRICE_UPDATES" | tee -a "$LOG_FILE"
        echo "   Productos pausados: $PAUSED" | tee -a "$LOG_FILE"
        echo "   Productos reactivados: $REACTIVATED" | tee -a "$LOG_FILE"
        echo "   Productos activos: $ACTIVE_PRODUCTS" | tee -a "$LOG_FILE"
        echo "   Precio promedio: $AVG_PRICE" | tee -a "$LOG_FILE"
    fi
else
    echo "❌ Error generando reporte" | tee -a "$LOG_FILE"
    echo "$REPORT_OUTPUT" | tee -a "$LOG_FILE"

    send_telegram "❌ <b>Error Generando Reporte Anual $LAST_YEAR</b>

No se pudo generar el reporte. Revisar logs/annual_reports.log"
fi

echo "" | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "✅ Proceso completado - $(date)" | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
