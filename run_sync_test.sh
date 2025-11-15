#!/bin/bash
# Script para ejecutar sync manualmente con logs visibles

echo "🔄 EJECUTANDO SYNC MANUALMENTE"
echo "════════════════════════════════════════════════════════════════════════════════"
echo "Este script:"
echo "  1. Carga variables de entorno"
echo "  2. Ejecuta sync_amazon_ml.py"
echo "  3. Muestra logs en tiempo real"
echo "  4. Guarda log completo en logs/sync/"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

# Ir al directorio correcto
cd /Users/felipemelucci/Desktop/revancha

# Python cargará las variables de entorno automáticamente con python-dotenv
# No necesitamos hacer source .env (causa errores con tokens largos)
if [ ! -f .env ]; then
    echo "❌ No se encontró archivo .env"
    exit 1
fi
echo "✅ Archivo .env encontrado (Python lo cargará automáticamente)"

# Verificar que existe la BD
if [ ! -f storage/listings_database.db ]; then
    echo "❌ No se encontró storage/listings_database.db"
    echo "   Ejecuta primero main2.py para publicar productos"
    exit 1
fi

# Mostrar cuántos listings hay en BD
echo ""
echo "📊 Verificando listings en base de datos..."
TOTAL_LISTINGS=$(sqlite3 storage/listings_database.db "SELECT COUNT(*) FROM listings WHERE item_id IS NOT NULL;")
echo "   Total de listings publicados: $TOTAL_LISTINGS"
echo ""

if [ "$TOTAL_LISTINGS" -eq 0 ]; then
    echo "⚠️  No hay listings publicados en la base de datos"
    echo "   Ejecuta main2.py primero para publicar productos"
    exit 0
fi

# Crear directorio de logs si no existe
mkdir -p logs/sync

# Timestamp para el log
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/sync_manual_${TIMESTAMP}.log"

echo "════════════════════════════════════════════════════════════════════════════════"
echo "🚀 Iniciando sincronización..."
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

# Ejecutar sync y mostrar logs en tiempo real (y guardar en archivo)
python3 scripts/tools/sync_amazon_ml.py 2>&1 | tee "$LOG_FILE"

# Resumen final
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo "✅ Sincronización completada"
echo "════════════════════════════════════════════════════════════════════════════════"
echo "📄 Log guardado en: $LOG_FILE"
echo ""

# Mostrar últimos logs JSON si existen
LATEST_JSON=$(ls -t logs/sync/sync_*.json 2>/dev/null | head -1)
if [ -n "$LATEST_JSON" ]; then
    echo "📊 Resumen JSON (último):"
    echo "════════════════════════════════════════════════════════════════════════════════"
    cat "$LATEST_JSON" | jq '.statistics'
    echo ""

    echo "🔍 Productos pausados por filtro fast fulfillment:"
    echo "────────────────────────────────────────────────────────────────────────────────"
    cat "$LATEST_JSON" | jq -r '.changes[] | select(.action == "paused") | "  • \(.asin) → \(.message)"'
    echo ""
fi

echo "💡 Para ver el log completo:"
echo "   cat $LOG_FILE"
echo ""
echo "💡 Para ver el JSON con detalles:"
echo "   cat $LATEST_JSON | jq"
echo ""
