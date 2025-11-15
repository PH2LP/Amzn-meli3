#!/bin/bash
# ============================================================
# 🚀 INSTALADOR DEL SERVICIO DE RENOVACIÓN AUTOMÁTICA ML TOKEN
# ============================================================
# Este script configura el loop de renovación para que se ejecute
# automáticamente al iniciar el sistema (usando LaunchAgent de macOS)
# ============================================================

set -e

echo "=================================================="
echo "🚀 Instalador del Servicio ML Token Auto-Refresh"
echo "=================================================="
echo ""

# Verificar que estamos en macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ Este script es solo para macOS"
    echo "   En Linux, usa systemd en su lugar"
    exit 1
fi

# Paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PLIST_FILE="$SCRIPT_DIR/com.revancha.ml_token_refresh.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
INSTALLED_PLIST="$LAUNCH_AGENTS_DIR/com.revancha.ml_token_refresh.plist"

echo "📁 Directorio del proyecto: $PROJECT_DIR"
echo "📄 Archivo plist: $PLIST_FILE"
echo ""

# Verificar que existe el plist
if [ ! -f "$PLIST_FILE" ]; then
    echo "❌ Error: No se encuentra el archivo plist"
    echo "   Esperado en: $PLIST_FILE"
    exit 1
fi

# Crear directorio de LaunchAgents si no existe
mkdir -p "$LAUNCH_AGENTS_DIR"

# Copiar plist a LaunchAgents
echo "📋 Copiando plist a LaunchAgents..."
cp "$PLIST_FILE" "$INSTALLED_PLIST"

# Dar permisos correctos
chmod 644 "$INSTALLED_PLIST"

echo "✅ Plist instalado en: $INSTALLED_PLIST"
echo ""

# Cargar el servicio
echo "🔄 Cargando el servicio..."
launchctl unload "$INSTALLED_PLIST" 2>/dev/null || true
launchctl load "$INSTALLED_PLIST"

echo ""
echo "=================================================="
echo "✅ Instalación completada"
echo "=================================================="
echo ""
echo "El servicio de renovación automática de ML Token está ahora activo."
echo ""
echo "Características:"
echo "  • Se ejecuta automáticamente al iniciar el sistema"
echo "  • Renueva el token cada 5.5 horas"
echo "  • Se reinicia automáticamente si falla"
echo ""
echo "Logs:"
echo "  • Principal: $PROJECT_DIR/logs/ml_token_refresh.log"
echo "  • Stdout: $PROJECT_DIR/logs/ml_token_refresh_stdout.log"
echo "  • Stderr: $PROJECT_DIR/logs/ml_token_refresh_stderr.log"
echo ""
echo "Comandos útiles:"
echo "  • Ver status: launchctl list | grep ml_token"
echo "  • Ver logs: tail -f logs/ml_token_refresh.log"
echo "  • Detener: launchctl unload $INSTALLED_PLIST"
echo "  • Iniciar: launchctl load $INSTALLED_PLIST"
echo "  • Desinstalar: rm $INSTALLED_PLIST && launchctl unload $INSTALLED_PLIST"
echo ""
