#!/bin/bash

# Monitor keyword discovery progress

LOG_FILE="/tmp/keyword_discovery_final.log"
PID=88400

echo "🔍 Monitoreando keyword discovery (PID: $PID)..."
echo ""

while ps -p $PID > /dev/null 2>&1; do
    clear
    echo "════════════════════════════════════════════════════════════"
    echo "📊 KEYWORD DISCOVERY - PROGRESO EN TIEMPO REAL"
    echo "════════════════════════════════════════════════════════════"
    echo ""

    # Última keyword procesada
    LAST_SEED=$(tail -20 "$LOG_FILE" | grep "📥 Semilla" | tail -1)
    echo "📍 $LAST_SEED"
    echo ""

    # Estadísticas
    TOTAL_LINES=$(wc -l < "$LOG_FILE")
    SEEDS_PROCESSED=$(grep -c "✅.*keywords descubiertas" "$LOG_FILE")

    echo "📈 Keywords semilla procesadas: $SEEDS_PROCESSED / 415"
    echo "📝 Líneas de log: $TOTAL_LINES"
    echo ""

    # Progreso porcentual
    PERCENT=$((SEEDS_PROCESSED * 100 / 415))
    echo "⏳ Progreso: $PERCENT%"

    # Barra de progreso
    FILLED=$((PERCENT / 2))
    printf "["
    for i in $(seq 1 50); do
        if [ $i -le $FILLED ]; then
            printf "█"
        else
            printf "░"
        fi
    done
    printf "]\n"
    echo ""

    # Últimas 3 keywords
    echo "🔄 Últimas keywords procesadas:"
    tail -50 "$LOG_FILE" | grep "📥 Semilla" | tail -3
    echo ""

    echo "Actualizando en 10 segundos... (Ctrl+C para salir)"
    sleep 10
done

echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ PROCESO COMPLETADO"
echo "════════════════════════════════════════════════════════════"
echo ""

# Mostrar resumen final
if [ -f "$LOG_FILE" ]; then
    echo "📊 RESUMEN FINAL:"
    tail -30 "$LOG_FILE" | grep -A 20 "Total keywords"
fi
