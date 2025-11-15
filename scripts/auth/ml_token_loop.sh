#!/bin/bash
# ============================================================
# 🔄 LOOP AUTOMÁTICO DE RENOVACIÓN DE TOKEN MERCADOLIBRE
# ============================================================
# Script wrapper para ejecutar el loop de renovación en background
# ============================================================

cd "$(dirname "$0")/../.." || exit 1

# Activar venv si existe
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Log file
LOG_FILE="logs/ml_token_refresh.log"
mkdir -p logs

echo "🚀 Iniciando loop de renovación automática de MercadoLibre Token"
echo "📝 Log: $LOG_FILE"
echo "⏳ Renovará cada 5.5 horas automáticamente"
echo ""
echo "Para detener el proceso:"
echo "  pkill -f ml_token_loop.py"
echo ""

# Ejecutar el loop
python3 scripts/auth/ml_token_loop.py
