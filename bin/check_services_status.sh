#!/bin/bash
# ============================================================
# VERIFICAR ESTADO DE TODOS LOS SERVICIOS
# ============================================================

echo "════════════════════════════════════════════════════════════"
echo "📊 ESTADO DE SERVICIOS - $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════════"
echo ""

check_service() {
    local name=$1
    local pattern=$2

    if pgrep -f "$pattern" > /dev/null; then
        local pid=$(pgrep -f "$pattern" | head -1)
        echo "✅ $name - ACTIVO (PID: $pid)"
    else
        echo "❌ $name - INACTIVO"
    fi
}

# LaunchAgent
echo "🤖 SERVICIOS AUTOMÁTICOS (LaunchAgent):"
echo "────────────────────────────────────────────────────────────"
if launchctl list | grep -q "ml_token"; then
    echo "✅ Token MercadoLibre - ACTIVO"
    echo "   Log: logs/ml_token_refresh.log"
else
    echo "❌ Token MercadoLibre - INACTIVO"
    echo "   Instalar: ./scripts/auth/install_ml_token_service.sh"
fi
echo ""

# Background services
echo "🔄 SERVICIOS EN BACKGROUND (nohup):"
echo "────────────────────────────────────────────────────────────"
check_service "Sync Amazon-ML      " "sync_amazon_ml_loop"
check_service "Monitor Catálogo    " "monitor_catalog_loop"
check_service "Ajuste de Precios   " "auto_adjust_catalog_prices_loop"
check_service "Sync ML → BD        " "auto_sync_loop"
check_service "Corrección de Fotos " "fix_paused_pictures_loop"
check_service "Auto-respuestas     " "auto_answer_questions"
check_service "Notificaciones TG   " "telegram_sales_notifier"
echo ""

# Contadores
echo "📈 RESUMEN:"
echo "────────────────────────────────────────────────────────────"
ACTIVE_COUNT=$(ps aux | grep -E "(loop|auto_answer|telegram_sales)" | grep -v grep | wc -l | xargs)
EXPECTED=7

if [ "$ACTIVE_COUNT" -eq "$EXPECTED" ]; then
    echo "✅ Todos los servicios activos ($ACTIVE_COUNT/$EXPECTED)"
elif [ "$ACTIVE_COUNT" -gt 0 ]; then
    echo "⚠️  Servicios parcialmente activos ($ACTIVE_COUNT/$EXPECTED)"
else
    echo "❌ No hay servicios activos (0/$EXPECTED)"
fi
echo ""

# Comandos útiles
echo "💡 COMANDOS ÚTILES:"
echo "────────────────────────────────────────────────────────────"
echo "• Iniciar todos:  ./start_all_services.sh"
echo "• Detener todos:  ./stop_all_services.sh"
echo "• Ver logs:       tail -f logs/*.log"
echo "• Ver procesos:   ps aux | grep -E '(loop|sync|telegram|answer)'"
echo ""
echo "════════════════════════════════════════════════════════════"
