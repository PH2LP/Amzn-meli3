#!/bin/bash
# ============================================================
# 📢 BOT DE TELEGRAM - NOTIFICACIONES DE PUBLICACIONES
# ============================================================
# Notifica cuando se publican productos nuevos en MercadoLibre
# ============================================================

cd "$(dirname "$0")" || exit 1

# Activar venv
if [ -d "venv" ]; then
    source venv/bin/activate
fi

LOG_FILE="logs/telegram_publishing.log"
mkdir -p logs

echo "📢 Iniciando bot de notificaciones de publicaciones por Telegram"
echo "📝 Log: $LOG_FILE"
echo ""
echo "Este bot está integrado con el pipeline principal."
echo "Envía notificaciones automáticamente cuando main2.py publica productos."
echo ""
echo "No requiere loop, funciona desde el pipeline."
echo ""
