#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# status_autonomous.sh
# Muestra el estado del sistema autónomo
# ═══════════════════════════════════════════════════════════════════════════

echo "═══════════════════════════════════════════════════════════════════════════"
echo "📊 ESTADO DEL SISTEMA AUTÓNOMO"
echo "═══════════════════════════════════════════════════════════════════════════"

# Estado del proceso
if [ -f "storage/autonomous.pid" ]; then
    PID=$(cat storage/autonomous.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ Sistema: CORRIENDO (PID: $PID)"

        # Tiempo de uptime
        START_TIME=$(ps -p $PID -o lstart=)
        echo "   Inicio: $START_TIME"
    else
        echo "❌ Sistema: NO CORRIENDO (PID file huérfano)"
    fi
else
    echo "❌ Sistema: NO CORRIENDO"
fi

echo ""

# Emergency stop
if [ -f "storage/STOP_AUTONOMOUS" ]; then
    echo "🛑 Emergency Stop: ACTIVADO"
else
    echo "✅ Emergency Stop: No activo"
fi

echo ""
echo "───────────────────────────────────────────────────────────────────────────"

# Métricas
if [ -f "storage/autonomous_logs/metrics.json" ]; then
    echo "📈 MÉTRICAS DEL SISTEMA:"
    echo ""

    # Intentar usar jq para formatear, si falla usar cat
    if command -v jq &> /dev/null; then
        cat storage/autonomous_logs/metrics.json | jq -r '
        "   Ciclos completados:     \(.cycle_count)",
        "   Tiempo activo:          \(.uptime_minutes) minutos",
        "   ASINs buscados:         \(.total_asins_searched)",
        "   ASINs publicados:       \(.total_asins_published)",
        "   ASINs rechazados:       \(.total_asins_rejected)",
        "   Errores consecutivos:   \(.consecutive_errors)",
        "",
        "   Keywords habilitadas:   \(.keyword_stats.enabled_keywords)/\(.keyword_stats.total_keywords)",
        "   ASINs por keywords:     \(.keyword_stats.total_asins_found)",
        "   Tasa éxito promedio:    \(.keyword_stats.avg_success_rate)%",
        "",
        "   Filtros aplicados:      \(.filter_stats.total_checked)",
        "   Productos rechazados:   \(.filter_stats.total_rejected)",
        "   Tasa de rechazo:        \(.filter_stats.rejection_rate)%"
        '
    else
        cat storage/autonomous_logs/metrics.json
    fi
else
    echo "⚠️ No hay métricas disponibles"
fi

echo ""
echo "───────────────────────────────────────────────────────────────────────────"

# Últimas líneas del log
if [ -f "storage/autonomous_logs/autonomous_system.log" ]; then
    echo "📋 ÚLTIMAS 10 LÍNEAS DEL LOG:"
    echo ""
    tail -10 storage/autonomous_logs/autonomous_system.log
else
    echo "⚠️ No hay logs disponibles"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "📋 Comandos útiles:"
echo "   • Ver logs en tiempo real:  tail -f storage/autonomous_logs/autonomous_system.log"
echo "   • Ver ASINs rechazados:     cat storage/autonomous_logs/rejected_asins.json | jq"
echo "   • Detener sistema:          ./stop_autonomous.sh"
echo ""
