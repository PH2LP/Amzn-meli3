#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# DOWNLOAD SALES DB FROM SERVER - DAILY BACKUP
# ═══════════════════════════════════════════════════════════════════════════════
# Descarga la base de datos de ventas del servidor VPS a este Mac como backup
#
# USO:
#   ./scripts/backup/download_sales_db.sh
#
# CRON (diariamente a las 6:00 AM):
#   0 6 * * * /Users/felipemelucci/Desktop/revancha/scripts/backup/download_sales_db.sh >> /Users/felipemelucci/Desktop/revancha/logs/sales_backup.log 2>&1
# ═══════════════════════════════════════════════════════════════════════════════

SERVER_IP="138.197.32.67"
SERVER_USER="root"
SERVER_PASSWORD="koqven-1regka-nyfXiw"
REMOTE_DB="/opt/amz-ml-system/storage/sales_tracking.db"
LOCAL_BACKUP_DIR="/Users/felipemelucci/Desktop/revancha/backups/sales_db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}BACKUP DIARIO DE SALES DB - $(date)${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"

# Crear directorio de backups si no existe
mkdir -p "$LOCAL_BACKUP_DIR"

# Descargar DB del servidor
echo -e "${YELLOW}📥 Descargando sales_tracking.db desde servidor...${NC}"
sshpass -p "$SERVER_PASSWORD" scp -o StrictHostKeyChecking=no \
    "$SERVER_USER@$SERVER_IP:$REMOTE_DB" \
    "$LOCAL_BACKUP_DIR/sales_tracking_${TIMESTAMP}.db"

if [ $? -eq 0 ]; then
    FILE_SIZE=$(ls -lh "$LOCAL_BACKUP_DIR/sales_tracking_${TIMESTAMP}.db" | awk '{print $5}')
    echo -e "${GREEN}✅ Backup descargado: sales_tracking_${TIMESTAMP}.db (${FILE_SIZE})${NC}"

    # Contar ventas en el backup
    SALES_COUNT=$(sqlite3 "$LOCAL_BACKUP_DIR/sales_tracking_${TIMESTAMP}.db" "SELECT COUNT(*) FROM sales" 2>/dev/null)
    if [ ! -z "$SALES_COUNT" ]; then
        echo -e "${GREEN}📊 Total ventas en backup: ${SALES_COUNT}${NC}"
    fi

    # Mantener solo los últimos 30 backups (1 mes)
    echo -e "${YELLOW}🗑️  Limpiando backups antiguos (manteniendo últimos 30)...${NC}"
    cd "$LOCAL_BACKUP_DIR"
    ls -t sales_tracking_*.db | tail -n +31 | xargs -r rm
    BACKUPS_COUNT=$(ls -1 sales_tracking_*.db 2>/dev/null | wc -l)
    echo -e "${GREEN}📦 Backups totales: ${BACKUPS_COUNT}${NC}"

else
    echo -e "${RED}❌ Error descargando backup${NC}"
    exit 1
fi

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Backup completado${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
