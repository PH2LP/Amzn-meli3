#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# stop_autonomous.sh
# Detiene el sistema autónomo de búsqueda y publicación
# ═══════════════════════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════════════════════════════════════"
echo "🛑 DETENIENDO SISTEMA AUTÓNOMO"
echo "═══════════════════════════════════════════════════════════════════════════"

# Verificar si existe el PID file
if [ ! -f "storage/autonomous.pid" ]; then
    echo "❌ No se encontró PID file (storage/autonomous.pid)"
    echo "   El sistema no parece estar corriendo"
    exit 1
fi

PID=$(cat storage/autonomous.pid)

# Verificar si el proceso está corriendo
if ! ps -p $PID > /dev/null 2>&1; then
    echo "⚠️ El proceso con PID $PID no está corriendo"
    echo "🗑️ Limpiando PID file..."
    rm storage/autonomous.pid
    exit 0
fi

# Crear emergency stop file para detención limpia
echo "📝 Creando emergency stop file..."
touch storage/STOP_AUTONOMOUS

echo "⏱️ Esperando que el sistema se detenga limpiamente (máx 30 segundos)..."

# Esperar hasta 30 segundos para detención limpia
COUNTER=0
while ps -p $PID > /dev/null 2>&1 && [ $COUNTER -lt 30 ]; do
    sleep 1
    COUNTER=$((COUNTER + 1))
    echo -n "."
done
echo ""

# Si aún está corriendo, forzar detención
if ps -p $PID > /dev/null 2>&1; then
    echo "⚠️ El sistema no se detuvo limpiamente, forzando detención..."
    kill -9 $PID
    sleep 1
fi

# Verificar que se detuvo
if ps -p $PID > /dev/null 2>&1; then
    echo "❌ Error: No se pudo detener el proceso (PID: $PID)"
    exit 1
else
    echo "✅ Sistema detenido exitosamente (PID: $PID)"
fi

# Limpiar archivos
rm -f storage/autonomous.pid
rm -f storage/STOP_AUTONOMOUS

echo ""
echo "📊 Métricas finales:"
if [ -f "storage/autonomous_logs/metrics.json" ]; then
    cat storage/autonomous_logs/metrics.json | jq '{
        ciclos: .cycle_count,
        asins_buscados: .total_asins_searched,
        asins_publicados: .total_asins_published,
        asins_rechazados: .total_asins_rejected,
        uptime_minutos: .uptime_minutes
    }' 2>/dev/null || cat storage/autonomous_logs/metrics.json
else
    echo "   (no hay métricas disponibles)"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
