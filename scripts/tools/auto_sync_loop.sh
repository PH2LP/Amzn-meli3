#!/bin/bash
# ============================================================
# AUTO-SYNC LOOP: Sincroniza productos ML → BD cada 1 hora
# ============================================================

# Auto-detectar directorio del proyecto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR" || exit 1

SYNC_INTERVAL=$((60 * 60))  # 1 hora
LOG_FILE="logs/auto_sync_loop.log"

echo "🔄 Iniciando auto-sync ML → BD" | tee -a "$LOG_FILE"
echo "⏰ Intervalo: cada 1 hora" | tee -a "$LOG_FILE"
echo "📅 $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

while true; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
    echo "🔄 Ejecutando sync: $(date)" | tee -a "$LOG_FILE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"

    ./venv/bin/python3 scripts/tools/auto_sync_ml_db.py 2>&1 | tee -a "$LOG_FILE"

    STATUS=$?

    if [ $STATUS -eq 0 ]; then
        echo "✅ Sync completado" | tee -a "$LOG_FILE"
    else
        echo "❌ Error (código: $STATUS)" | tee -a "$LOG_FILE"
    fi

    echo "" | tee -a "$LOG_FILE"
    echo "⏰ Próxima ejecución en 1 hora" | tee -a "$LOG_FILE"
    echo "⏸️  Esperando..." | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"

    sleep $SYNC_INTERVAL
done
