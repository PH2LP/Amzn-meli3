#!/bin/bash
# Script para limpiar logs antiguos automáticamente
# Mantiene solo los últimos 30 días de logs y rota archivos grandes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_DIR/logs/cleanup.log"

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
echo "🧹 LIMPIEZA AUTOMÁTICA DE LOGS - $(date)" | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Contador de archivos eliminados
DELETED_COUNT=0
FREED_SPACE=0

# 1. MANTENER logs de sync para reportes anuales
# Los archivos sync_*.json contienen datos valiosos: cambios de precio, productos pausados, etc.
# Se mantienen TODOS para análisis anual, solo se comprimen los antiguos
echo "📂 Procesando logs de sync para mantener datos históricos..." | tee -a "$LOG_FILE"
if [ -d "logs/sync" ]; then
    # Comprimir logs de sync mayores a 30 días (pero NO eliminar)
    COMPRESSED_COUNT=0

    while IFS= read -r file; do
        # Solo comprimir si no está comprimido
        if [[ ! "$file" =~ \.gz$ ]]; then
            gzip "$file"
            COMPRESSED_COUNT=$((COMPRESSED_COUNT + 1))
            echo "   📦 Comprimido: $(basename "$file")" >> "$LOG_FILE"
        fi
    done < <(find logs/sync -name "sync_*.json" -type f -mtime +30 2>/dev/null)

    echo "   ✅ Comprimidos: $COMPRESSED_COUNT archivos (datos históricos preservados)" | tee -a "$LOG_FILE"
else
    echo "   ⏭️  No hay directorio logs/sync" | tee -a "$LOG_FILE"
fi

# 2. Rotar log de sync_cron si es muy grande (>10MB)
echo "" | tee -a "$LOG_FILE"
echo "📋 Verificando tamaño de sync_cron.log..." | tee -a "$LOG_FILE"
if [ -f "logs/sync/sync_cron.log" ]; then
    SIZE_MB=$(du -m logs/sync/sync_cron.log | cut -f1)

    if [ "$SIZE_MB" -gt 10 ]; then
        echo "   ⚠️  sync_cron.log tiene ${SIZE_MB}MB (>10MB)" | tee -a "$LOG_FILE"

        # Hacer backup con timestamp
        BACKUP_NAME="logs/sync/sync_cron_$(date +%Y%m%d_%H%M%S).log"
        mv logs/sync/sync_cron.log "$BACKUP_NAME"

        # Comprimir el backup
        gzip "$BACKUP_NAME"

        echo "   ✅ Rotado y comprimido: $(basename "$BACKUP_NAME").gz" | tee -a "$LOG_FILE"

        FREED_SPACE=$((FREED_SPACE + SIZE_MB * 1024))
        DELETED_COUNT=$((DELETED_COUNT + 1))
    else
        echo "   ✅ Tamaño OK: ${SIZE_MB}MB" | tee -a "$LOG_FILE"
    fi
else
    echo "   ℹ️  No existe sync_cron.log" | tee -a "$LOG_FILE"
fi

# 3. Limpiar logs antiguos de DB sync (>30 días)
echo "" | tee -a "$LOG_FILE"
echo "💾 Limpiando logs de DB sync antiguos (>30 días)..." | tee -a "$LOG_FILE"
if [ -f "logs/db_sync.log" ]; then
    SIZE_MB=$(du -m logs/db_sync.log | cut -f1)

    if [ "$SIZE_MB" -gt 5 ]; then
        echo "   ⚠️  db_sync.log tiene ${SIZE_MB}MB (>5MB)" | tee -a "$LOG_FILE"

        # Mantener solo las últimas 500 líneas
        tail -500 logs/db_sync.log > logs/db_sync.log.tmp
        mv logs/db_sync.log.tmp logs/db_sync.log

        echo "   ✅ Truncado a últimas 500 líneas" | tee -a "$LOG_FILE"

        FREED_SPACE=$((FREED_SPACE + SIZE_MB * 1024))
    else
        echo "   ✅ Tamaño OK: ${SIZE_MB}MB" | tee -a "$LOG_FILE"
    fi
else
    echo "   ℹ️  No existe db_sync.log" | tee -a "$LOG_FILE"
fi

# 4. Limpiar backups antiguos de sync_cron comprimidos (>60 días)
echo "" | tee -a "$LOG_FILE"
echo "📦 Limpiando backups comprimidos antiguos (>60 días)..." | tee -a "$LOG_FILE"
if [ -d "logs/sync" ]; then
    BACKUP_COUNT=$(find logs/sync -name "sync_cron_*.log.gz" -type f -mtime +60 2>/dev/null | wc -l)

    if [ "$BACKUP_COUNT" -gt 0 ]; then
        while IFS= read -r file; do
            SIZE=$(du -k "$file" | cut -f1)
            FREED_SPACE=$((FREED_SPACE + SIZE))
            DELETED_COUNT=$((DELETED_COUNT + 1))
            rm "$file"
            echo "   🗑️  Eliminado: $(basename "$file") (${SIZE}KB)" >> "$LOG_FILE"
        done < <(find logs/sync -name "sync_cron_*.log.gz" -type f -mtime +60 2>/dev/null)

        echo "   ✅ Eliminados: $BACKUP_COUNT backups antiguos" | tee -a "$LOG_FILE"
    else
        echo "   ✅ No hay backups antiguos" | tee -a "$LOG_FILE"
    fi
fi

# 5. Limpiar backups de base de datos antiguos (>7 días en VPS)
# Nota: Solo se ejecuta en VPS, en local no hace nada
echo "" | tee -a "$LOG_FILE"
echo "🗄️  Verificando backups de base de datos..." | tee -a "$LOG_FILE"
if [ -d "storage" ]; then
    DB_BACKUPS=$(find storage -name "listings_database.db.backup.*" -type f -mtime +7 2>/dev/null | wc -l)

    if [ "$DB_BACKUPS" -gt 0 ]; then
        while IFS= read -r file; do
            SIZE=$(du -k "$file" | cut -f1)
            FREED_SPACE=$((FREED_SPACE + SIZE))
            DELETED_COUNT=$((DELETED_COUNT + 1))
            rm "$file"
            echo "   🗑️  Eliminado: $(basename "$file") (${SIZE}KB)" >> "$LOG_FILE"
        done < <(find storage -name "listings_database.db.backup.*" -type f -mtime +7 2>/dev/null)

        echo "   ✅ Eliminados: $DB_BACKUPS backups de BD antiguos" | tee -a "$LOG_FILE"
    else
        echo "   ✅ No hay backups de BD antiguos (>7 días)" | tee -a "$LOG_FILE"
    fi
fi

# Convertir KB a MB
FREED_MB=$((FREED_SPACE / 1024))

echo "" | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "📊 RESUMEN DE LIMPIEZA" | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "Archivos eliminados: $DELETED_COUNT" | tee -a "$LOG_FILE"
echo "Espacio liberado: ${FREED_MB}MB" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Enviar notificación si se eliminó algo significativo
if [ "$FREED_MB" -gt 5 ]; then
    send_telegram "🧹 <b>Limpieza de logs completada</b>

📁 Archivos eliminados: $DELETED_COUNT
💾 Espacio liberado: ${FREED_MB}MB
⏱️ $(date +%H:%M)"
fi

echo "✅ Limpieza completada - $(date)" | tee -a "$LOG_FILE"
echo "════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
