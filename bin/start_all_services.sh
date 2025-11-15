#!/bin/bash
# ============================================================
# ACTIVAR TODOS LOS SERVICIOS DEL SISTEMA
# ============================================================

cd "$(dirname "$0")"

echo "🚀 Iniciando todos los servicios del sistema..."
echo ""

# 1. Token MercadoLibre (LaunchAgent - debe estar instalado previamente)
echo "1️⃣ Verificando servicio de tokens ML..."
if launchctl list | grep -q "ml_token"; then
    echo "   ✅ Servicio de tokens activo"
else
    echo "   ⚠️  Servicio no instalado. Ejecutar:"
    echo "      ./scripts/auth/install_ml_token_service.sh"
fi
echo ""

# 2. Sincronización Amazon → ML (cada 6h)
echo "2️⃣ Iniciando sincronización Amazon-ML..."
if pgrep -f "sync_amazon_ml_loop" > /dev/null; then
    echo "   ⚠️  Ya está corriendo"
else
    nohup ./scripts/tools/sync_amazon_ml_loop.sh > /dev/null 2>&1 &
    echo "   ✅ Iniciado (PID: $!)"
fi
echo ""

# 3. Monitor de catálogo (cada 30 min)
echo "3️⃣ Iniciando monitor de catálogo..."
if pgrep -f "monitor_catalog_loop" > /dev/null; then
    echo "   ⚠️  Ya está corriendo"
else
    nohup ./scripts/tools/monitor_catalog_loop.sh > /dev/null 2>&1 &
    echo "   ✅ Iniciado (PID: $!)"
fi
echo ""

# 4. Ajuste automático de precios (cada 6h)
echo "4️⃣ Iniciando ajuste de precios..."
if pgrep -f "auto_adjust_catalog_prices_loop" > /dev/null; then
    echo "   ⚠️  Ya está corriendo"
else
    nohup ./scripts/tools/auto_adjust_catalog_prices_loop.sh > /dev/null 2>&1 &
    echo "   ✅ Iniciado (PID: $!)"
fi
echo ""

# 5. Sync ML → BD (cada 1h)
echo "5️⃣ Iniciando sync ML → BD..."
if pgrep -f "auto_sync_loop" > /dev/null; then
    echo "   ⚠️  Ya está corriendo"
else
    nohup ./scripts/tools/auto_sync_loop.sh > /dev/null 2>&1 &
    echo "   ✅ Iniciado (PID: $!)"
fi
echo ""

# 6. Corrección de fotos (cada 30 min)
echo "6️⃣ Iniciando corrección de fotos..."
if pgrep -f "fix_paused_pictures_loop" > /dev/null; then
    echo "   ⚠️  Ya está corriendo"
else
    nohup ./scripts/tools/fix_paused_pictures_loop.sh > /dev/null 2>&1 &
    echo "   ✅ Iniciado (PID: $!)"
fi
echo ""

# 7. Auto-respuesta (cada 1 min)
echo "7️⃣ Iniciando auto-respuesta..."
if pgrep -f "auto_answer_questions" > /dev/null; then
    echo "   ⚠️  Ya está corriendo"
else
    nohup ./venv/bin/python3 scripts/tools/auto_answer_questions.py > logs/auto_answer.log 2>&1 &
    echo "   ✅ Iniciado (PID: $!)"
fi
echo ""

# 8. Notificaciones Telegram (cada 5 min)
echo "8️⃣ Iniciando notificaciones Telegram..."
if pgrep -f "telegram_sales_notifier" > /dev/null; then
    echo "   ⚠️  Ya está corriendo"
else
    nohup ./venv/bin/python3 scripts/tools/telegram_sales_notifier.py > logs/telegram_sales.log 2>&1 &
    echo "   ✅ Iniciado (PID: $!)"
fi
echo ""

echo "════════════════════════════════════════════════════════════"
echo "✅ TODOS LOS SERVICIOS INICIADOS"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "📊 Ver estado:"
echo "   ./check_services_status.sh"
echo ""
echo "📝 Ver logs:"
echo "   tail -f logs/*.log"
echo ""
echo "🛑 Detener todos:"
echo "   ./stop_all_services.sh"
echo ""
