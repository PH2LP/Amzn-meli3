#!/bin/bash

# Script que mantiene el sistema autónomo corriendo siempre
# Se ejecuta cada 5 minutos via cron

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

PIDFILE="storage/autonomous.pid"
LOGFILE="storage/autonomous_logs/production.log"

# Verificar si ya está corriendo
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "$(date): Sistema autónomo ya está corriendo (PID: $PID)"
        exit 0
    else
        echo "$(date): PID file existe pero proceso no corre, limpiando..."
        rm -f "$PIDFILE"
    fi
fi

# Iniciar el sistema autónomo
echo "$(date): Iniciando sistema autónomo..."

nohup ./venv/bin/python3 scripts/autonomous/autonomous_search_and_publish.py \
    --config config/autonomous_config.json \
    --max-cycles 0 \
    >> "$LOGFILE" 2>&1 &

echo $! > "$PIDFILE"

echo "$(date): Sistema autónomo iniciado con PID $(cat $PIDFILE)"
