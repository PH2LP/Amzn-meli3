#!/bin/bash
# ============================================================
# DETENER TODOS LOS SERVICIOS DEL SISTEMA
# ============================================================

echo "🛑 Deteniendo todos los servicios del sistema..."
echo ""

# Detener todos los loops
echo "Deteniendo loops..."
pkill -f sync_amazon_ml_loop.sh
pkill -f monitor_catalog_loop.sh
pkill -f auto_adjust_catalog_prices_loop.sh
pkill -f auto_sync_loop.sh
pkill -f fix_paused_pictures_loop.sh
pkill -f auto_answer_questions.py
pkill -f telegram_sales_notifier.py

sleep 2

echo ""
echo "✅ Todos los servicios background detenidos"
echo ""
echo "ℹ️  El servicio de tokens ML (LaunchAgent) sigue corriendo"
echo "   Para detenerlo:"
echo "   launchctl unload ~/Library/LaunchAgents/com.revancha.ml_token_refresh.plist"
echo ""
echo "📊 Verificar estado:"
echo "   ./check_services_status.sh"
echo ""
