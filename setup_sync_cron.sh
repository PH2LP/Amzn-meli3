#!/bin/bash
# ============================================================
# Script para configurar el cron job de sincronización
# Amazon → MercadoLibre
# ============================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python3"
SYNC_SCRIPT="$PROJECT_DIR/sync_amazon_ml.py"
LOG_FILE="$PROJECT_DIR/logs/sync/sync_cron.log"

echo "============================================================"
echo "CONFIGURACIÓN DE CRON JOB - SINCRONIZACIÓN AMAZON → ML"
echo "============================================================"
echo ""

# Verificar que existe el script
if [ ! -f "$SYNC_SCRIPT" ]; then
    echo "❌ Error: No se encontró el script sync_amazon_ml.py"
    exit 1
fi

# Verificar que existe el intérprete de Python
if [ ! -f "$PYTHON_BIN" ]; then
    echo "❌ Error: No se encontró el intérprete de Python en $PYTHON_BIN"
    echo "   Asegúrate de tener el entorno virtual activado"
    exit 1
fi

# Crear directorio de logs si no existe
mkdir -p "$PROJECT_DIR/logs/sync"

# Hacer el script ejecutable
chmod +x "$SYNC_SCRIPT"

echo "📋 Configuración del cron job:"
echo "   - Script: $SYNC_SCRIPT"
echo "   - Python: $PYTHON_BIN"
echo "   - Log: $LOG_FILE"
echo ""

# Generar la línea del cron job
# Ejecutar cada 3 días a las 9:00 AM
CRON_LINE="0 9 */3 * * cd $PROJECT_DIR && $PYTHON_BIN $SYNC_SCRIPT >> $LOG_FILE 2>&1"

echo "📝 Línea del cron job:"
echo "   $CRON_LINE"
echo ""

# Backup del crontab actual
echo "💾 Creando backup del crontab actual..."
crontab -l > "$PROJECT_DIR/logs/sync/crontab_backup_$(date +%Y%m%d_%H%M%S).txt" 2>/dev/null || true

# Verificar si ya existe el cron job
if crontab -l 2>/dev/null | grep -q "sync_amazon_ml.py"; then
    echo "⚠️ Ya existe un cron job para sync_amazon_ml.py"
    echo ""
    echo "¿Deseas reemplazarlo? (s/n)"
    read -r response

    if [[ "$response" =~ ^[Ss]$ ]]; then
        # Eliminar líneas antiguas del sync
        crontab -l 2>/dev/null | grep -v "sync_amazon_ml.py" | crontab -
        echo "✅ Cron job antiguo eliminado"
    else
        echo "❌ Instalación cancelada"
        exit 0
    fi
fi

# Agregar el nuevo cron job
echo "📥 Instalando cron job..."
(crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -

echo "✅ Cron job instalado exitosamente"
echo ""

# Mostrar cron jobs actuales
echo "📋 Cron jobs actuales:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
crontab -l | grep -v "^#" | grep -v "^$"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "✅ Configuración completada"
echo ""
echo "ℹ️ El script se ejecutará cada 3 días a las 9:00 AM"
echo "ℹ️ Los logs se guardarán en: $LOG_FILE"
echo ""
echo "Para verificar el funcionamiento, puedes ejecutar manualmente:"
echo "   cd $PROJECT_DIR && $PYTHON_BIN $SYNC_SCRIPT"
echo ""
