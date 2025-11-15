#!/bin/bash
# Script para sincronizar la base de datos de listings al VPS
# Se ejecuta diariamente a las 5:00 AM

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_DIR/logs/db_sync.log"

cd "$PROJECT_DIR" || exit 1

# Función para enviar notificación Telegram
send_telegram() {
    local message="$1"
    source .env 2>/dev/null

    if [ -n "$TELEGRAM_SYNC_BOT_TOKEN" ] && [ -n "$TELEGRAM_SYNC_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_SYNC_BOT_TOKEN}/sendMessage" \
            -d chat_id="${TELEGRAM_SYNC_CHAT_ID}" \
            -d text="$message" \
            -d parse_mode="HTML" > /dev/null 2>&1
    fi
}

echo "════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "📦 SINCRONIZACIÓN DE BASE DE DATOS AL VPS - $(date)" | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Notificar inicio
send_telegram "🔄 <b>Iniciando sync de BD</b>
Sincronizando base de datos al VPS..."

# Verificar que existe la base de datos local
if [ ! -f "storage/listings_database.db" ]; then
    echo "❌ Base de datos local no encontrada" | tee -a "$LOG_FILE"
    exit 1
fi

# Obtener tamaño de la DB local
LOCAL_SIZE=$(du -h storage/listings_database.db | cut -f1)
echo "📊 Tamaño DB local: $LOCAL_SIZE" | tee -a "$LOG_FILE"

# Cargar credenciales del VPS desde .env
source .env 2>/dev/null || {
    echo "❌ No se pudo cargar .env" | tee -a "$LOG_FILE"
    exit 1
}

VPS_HOST="138.197.32.67"
VPS_USER="root"
VPS_PASS="koqven-1regka-nyfXiw"
VPS_PATH="/opt/amz-ml-system/storage"

# Hacer backup en VPS antes de sobrescribir
echo "💾 Creando backup en VPS..." | tee -a "$LOG_FILE"
sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no $VPS_USER@$VPS_HOST \
    "cd $VPS_PATH && cp listings_database.db listings_database.db.backup.$(date +%Y%m%d) 2>/dev/null || true"

# Sincronizar DB al VPS
echo "📤 Subiendo base de datos al VPS..." | tee -a "$LOG_FILE"
sshpass -p "$VPS_PASS" scp -o StrictHostKeyChecking=no \
    storage/listings_database.db \
    $VPS_USER@$VPS_HOST:$VPS_PATH/

if [ $? -eq 0 ]; then
    # Verificar tamaño en VPS
    VPS_SIZE=$(sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no $VPS_USER@$VPS_HOST \
        "du -h $VPS_PATH/listings_database.db | cut -f1")
    
    echo "✅ Base de datos sincronizada exitosamente" | tee -a "$LOG_FILE"
    echo "   Local:  $LOCAL_SIZE" | tee -a "$LOG_FILE"
    echo "   VPS:    $VPS_SIZE" | tee -a "$LOG_FILE"

    # Contar registros en VPS
    RECORDS=$(sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no $VPS_USER@$VPS_HOST \
        "cd /opt/amz-ml-system && venv/bin/python3 -c \"import sqlite3; conn=sqlite3.connect('$VPS_PATH/listings_database.db'); cursor=conn.cursor(); cursor.execute('SELECT COUNT(*) FROM listings WHERE item_id IS NOT NULL'); print(cursor.fetchone()[0])\"")

    echo "   Registros: $RECORDS productos publicados" | tee -a "$LOG_FILE"

    # Notificar éxito
    send_telegram "✅ <b>BD sincronizada exitosamente</b>

📊 Tamaño: $VPS_SIZE
📦 Productos: $RECORDS
⏱️ $(date +%H:%M)"
else
    echo "❌ Error sincronizando base de datos" | tee -a "$LOG_FILE"

    # Notificar error
    send_telegram "❌ <b>Error sincronizando BD</b>

No se pudo subir la base de datos al VPS
⏱️ $(date +%H:%M)"

    exit 1
fi

echo "" | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "✅ Sincronización completada - $(date)" | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
