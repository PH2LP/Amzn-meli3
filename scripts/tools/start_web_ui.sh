#!/bin/bash
# ============================================================
# Iniciar Web UI
# ============================================================

cd "$(dirname "$0")"

echo "════════════════════════════════════════════════════════"
echo "🚀 Iniciando Web UI"
echo "════════════════════════════════════════════════════════"
echo ""

# Activar venv
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Entorno virtual activado"
else
    echo "⚠️  No se encontró venv, usando Python global"
fi

# Verificar Flask
if ! python3 -c "import flask" 2>/dev/null; then
    echo "❌ Flask no instalado"
    echo "   Instalando dependencias..."
    pip install -r requirements.txt
fi

echo ""
echo "════════════════════════════════════════════════════════"
echo "🌐 Web UI disponible en:"
echo "   http://localhost:5000"
echo ""
echo "Páginas:"
echo "   • Modo Simple:  http://localhost:5000/"
echo "   • Modo Pro:     http://localhost:5000/pro"
echo "   • Logs:         http://localhost:5000/logs"
echo ""
echo "🛑 Para detener: Ctrl+C"
echo "════════════════════════════════════════════════════════"
echo ""

# Ejecutar
python3 web_ui/app.py
