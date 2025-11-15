#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# start_autonomous.sh
# Inicia el sistema autónomo de búsqueda y publicación
# ═══════════════════════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════════════════════════════════════"
echo "🤖 INICIANDO SISTEMA AUTÓNOMO DE BÚSQUEDA Y PUBLICACIÓN"
echo "═══════════════════════════════════════════════════════════════════════════"

# Verificar que no esté corriendo ya
if [ -f "storage/autonomous.pid" ]; then
    PID=$(cat storage/autonomous.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "❌ Error: El sistema ya está corriendo (PID: $PID)"
        echo "   Usa ./stop_autonomous.sh para detenerlo primero"
        exit 1
    else
        echo "⚠️ PID file existe pero proceso no está corriendo, limpiando..."
        rm storage/autonomous.pid
    fi
fi

# Remover emergency stop si existe
if [ -f "storage/STOP_AUTONOMOUS" ]; then
    echo "🗑️ Removiendo emergency stop file..."
    rm storage/STOP_AUTONOMOUS
fi

# Crear directorios necesarios
mkdir -p storage/autonomous_logs
mkdir -p config

# Verificar archivos de configuración
if [ ! -f "config/autonomous_config.json" ]; then
    echo "❌ Error: No se encontró config/autonomous_config.json"
    exit 1
fi

if [ ! -f "config/keywords.json" ]; then
    echo "❌ Error: No se encontró config/keywords.json"
    exit 1
fi

if [ ! -f "config/brand_blacklist.json" ]; then
    echo "❌ Error: No se encontró config/brand_blacklist.json"
    exit 1
fi

echo "✅ Configuración verificada"

# Determinar modo
MODE="production"
if [ "$1" == "--dry-run" ]; then
    MODE="dry-run"
    echo "🧪 Modo: DRY-RUN (no publicará productos)"
    EXTRA_ARGS="--dry-run"
else
    echo "🚀 Modo: PRODUCCIÓN (publicará productos reales)"
    EXTRA_ARGS=""
fi

# Confirmar inicio
if [ "$MODE" == "production" ]; then
    echo ""
    echo "⚠️  ADVERTENCIA: Esto iniciará el sistema en modo PRODUCCIÓN"
    echo "   El sistema buscará y publicará productos automáticamente"
    echo ""
    read -p "   ¿Continuar? [s/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
        echo "❌ Cancelado por usuario"
        exit 0
    fi
fi

echo ""
echo "🔄 Iniciando sistema autónomo en background..."

# Ejecutar en background
nohup python3 scripts/autonomous/autonomous_search_and_publish.py $EXTRA_ARGS \
    >> storage/autonomous_logs/autonomous_system.log 2>&1 &

PID=$!
echo $PID > storage/autonomous.pid

echo "✅ Sistema iniciado (PID: $PID)"
echo ""
echo "📋 Comandos útiles:"
echo "   • Ver logs en tiempo real:"
echo "     tail -f storage/autonomous_logs/autonomous_system.log"
echo ""
echo "   • Ver métricas:"
echo "     cat storage/autonomous_logs/metrics.json | jq"
echo ""
echo "   • Detener sistema:"
echo "     ./stop_autonomous.sh"
echo ""
echo "   • Emergency stop (detención inmediata):"
echo "     touch storage/STOP_AUTONOMOUS"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
