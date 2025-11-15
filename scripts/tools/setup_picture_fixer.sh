#!/bin/bash
# Instalación rápida del sistema de corrección de fotos

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT" || exit 1

echo "════════════════════════════════════════════════════════════════════════"
echo "🔧 INSTALACIÓN: Sistema de Corrección Automática de Fotos"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# 1. Verificar entorno virtual
if [ ! -d "venv" ]; then
    echo "❌ Error: No se encontró el entorno virtual (venv/)"
    echo "💡 Ejecuta primero: python3 -m venv venv"
    exit 1
fi

echo "✅ Entorno virtual encontrado"
echo ""

# 2. Instalar dependencias
echo "📦 Instalando dependencias..."
echo ""

./venv/bin/pip install --quiet 'rembg[cli]' onnxruntime

if [ $? -eq 0 ]; then
    echo "✅ Dependencias instaladas correctamente"
else
    echo "❌ Error instalando dependencias"
    exit 1
fi

echo ""

# 3. Verificar configuración .env
echo "🔍 Verificando configuración..."
echo ""

if [ ! -f ".env" ]; then
    echo "❌ Error: Archivo .env no encontrado"
    exit 1
fi

if ! grep -q "ML_ACCESS_TOKEN" .env; then
    echo "⚠️  Advertencia: ML_ACCESS_TOKEN no encontrado en .env"
    echo "💡 Agrega: ML_ACCESS_TOKEN=APP_USR-..."
fi

if ! grep -q "ML_USER_ID" .env; then
    echo "⚠️  Advertencia: ML_USER_ID no encontrado en .env"
    echo "💡 Agrega: ML_USER_ID=tu_user_id"
fi

echo "✅ Configuración verificada"
echo ""

# 4. Crear directorios necesarios
echo "📁 Creando directorios..."
mkdir -p logs
mkdir -p storage/temp_images
echo "✅ Directorios creados"
echo ""

# 5. Dar permisos de ejecución
echo "🔐 Configurando permisos..."
chmod +x scripts/tools/fix_paused_pictures.py
chmod +x scripts/tools/fix_paused_pictures_loop.sh
echo "✅ Permisos configurados"
echo ""

# 6. Test rápido
echo "🧪 Ejecutando test..."
echo ""

./venv/bin/python3 scripts/tools/fix_paused_pictures.py

if [ $? -eq 0 ]; then
    echo ""
    echo "════════════════════════════════════════════════════════════════════════"
    echo "✅ ¡INSTALACIÓN COMPLETADA EXITOSAMENTE!"
    echo "════════════════════════════════════════════════════════════════════════"
    echo ""
    echo "📖 Uso:"
    echo ""
    echo "  • Ejecución manual (una vez):"
    echo "    ./venv/bin/python3 scripts/tools/fix_paused_pictures.py"
    echo ""
    echo "  • Loop automático (cada 30 min):"
    echo "    ./scripts/tools/fix_paused_pictures_loop.sh"
    echo ""
    echo "  • Ver logs:"
    echo "    tail -f logs/fix_paused_pictures.log"
    echo ""
    echo "📚 Documentación completa:"
    echo "    docs/FIX_PAUSED_PICTURES_README.md"
    echo ""
    echo "════════════════════════════════════════════════════════════════════════"
else
    echo ""
    echo "❌ Error en el test inicial"
    echo "💡 Revisa los logs para más detalles"
    exit 1
fi
