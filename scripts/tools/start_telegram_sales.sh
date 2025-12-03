#!/bin/bash
# ============================================================
# 🔔 BOT DE TELEGRAM - NOTIFICACIONES DE VENTAS
# ============================================================
# Monitorea ventas cada 60 segundos y envía notificación por Telegram
# ============================================================

cd "$(dirname "$0")" || exit 1

# Activar venv
if [ -d "venv" ]; then
    source venv/bin/activate
fi

LOG_FILE="logs/telegram_sales.log"
mkdir -p logs

echo "🔔 Iniciando bot de notificaciones de ventas por Telegram"
echo "📝 Log: $LOG_FILE"
echo "⏳ Revisa ventas cada 60 segundos"
echo ""
echo "Para detener:"
echo "  pkill -f telegram_sales_notifier.py"
echo ""

# Loop infinito
iteration=1
while true; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔄 Iteración #$iteration - $(date '+%H:%M:%S')"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    python3 scripts/tools/telegram_sales_notifier.py 2>&1 | tee -a "$LOG_FILE"

    echo ""
    echo "⏳ Esperando 60 segundos hasta próxima revisión..."
    echo ""

    sleep 60
    iteration=$((iteration + 1))
done
