#!/bin/bash
# ============================================================
# 📊 SALES TRACKING + EXCEL DROPBOX - DAEMON
# ============================================================
# Ejecuta tracking de ventas cada 1 hora y sube Excel a Dropbox
# ============================================================

cd "$(dirname "$0")" || exit 1

# Activar venv si existe
if [ -d "venv" ]; then
    source venv/bin/activate
fi

LOG_FILE="logs/sales_tracking_dropbox.log"
mkdir -p logs

echo "📊 Iniciando Sales Tracking + Dropbox daemon"
echo "📝 Log: $LOG_FILE"
echo "⏳ Ejecuta cada 1 hora"
echo ""
echo "Para detener:"
echo "  pkill -f auto_sales_tracking_loop.py"
echo ""

# Ejecutar daemon
python3 scripts/tools/auto_sales_tracking_loop.py 2>&1 | tee -a "$LOG_FILE"
