#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# BACKUP LOCAL AUTOMÁTICO
# ═══════════════════════════════════════════════════════════════════════
# Crea backups de datos críticos en tu Mac y los sube al VPS
#
# Uso:
#   ./backup_local.sh
#
# Backups incluidos:
#   - Base de datos (listings_database.db)
#   - ASINs JSON (datos de Amazon)
#   - Logs importantes
#   - Configuración (.env)
# ═══════════════════════════════════════════════════════════════════════

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuración
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="backups/local_backup_${TIMESTAMP}"
VPS_USER="root"
VPS_HOST="138.197.32.67"
VPS_PASSWORD="koqven-1regka-nyfXiw"
VPS_BACKUP_DIR="/opt/amz-ml-system/backups/from_mac"

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}📦 BACKUP LOCAL AUTOMÁTICO${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Fecha: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BLUE}Backup: ${BACKUP_DIR}${NC}"
echo ""

# 1. Crear directorio de backup
echo -e "${YELLOW}1. Creando directorio de backup...${NC}"
mkdir -p "${BACKUP_DIR}"
echo -e "${GREEN}   ✅ Directorio creado${NC}"
echo ""

# 2. Backup de base de datos
echo -e "${YELLOW}2. Respaldando base de datos...${NC}"
if [ -f "storage/listings_database.db" ]; then
    cp storage/listings_database.db "${BACKUP_DIR}/"
    SIZE=$(du -h "${BACKUP_DIR}/listings_database.db" | cut -f1)
    echo -e "${GREEN}   ✅ Base de datos respaldada (${SIZE})${NC}"
else
    echo -e "${RED}   ⚠️  Base de datos no encontrada${NC}"
fi
echo ""

# 3. Backup de pipeline state
echo -e "${YELLOW}3. Respaldando pipeline state...${NC}"
if [ -f "storage/pipeline_state.db" ]; then
    cp storage/pipeline_state.db "${BACKUP_DIR}/"
    SIZE=$(du -h "${BACKUP_DIR}/pipeline_state.db" | cut -f1)
    echo -e "${GREEN}   ✅ Pipeline state respaldado (${SIZE})${NC}"
else
    echo -e "${RED}   ⚠️  Pipeline state no encontrado${NC}"
fi
echo ""

# 4. Backup de configuración
echo -e "${YELLOW}4. Respaldando configuración (.env)...${NC}"
if [ -f ".env" ]; then
    cp .env "${BACKUP_DIR}/"
    echo -e "${GREEN}   ✅ Configuración respaldada${NC}"
else
    echo -e "${RED}   ⚠️  .env no encontrado${NC}"
fi
echo ""

# 5. Backup de ASINs JSON (solo los últimos 100)
echo -e "${YELLOW}5. Respaldando ASINs JSON (últimos 100)...${NC}"
if [ -d "storage/asins_json" ]; then
    mkdir -p "${BACKUP_DIR}/asins_json"

    # Copiar solo los 100 más recientes para no ocupar mucho espacio
    ls -t storage/asins_json/*.json 2>/dev/null | head -100 | while read file; do
        cp "$file" "${BACKUP_DIR}/asins_json/"
    done

    COUNT=$(ls "${BACKUP_DIR}/asins_json/" 2>/dev/null | wc -l | tr -d ' ')
    SIZE=$(du -sh "${BACKUP_DIR}/asins_json/" | cut -f1)
    echo -e "${GREEN}   ✅ ${COUNT} ASINs JSON respaldados (${SIZE})${NC}"
else
    echo -e "${RED}   ⚠️  Directorio asins_json no encontrado${NC}"
fi
echo ""

# 6. Backup de asins.txt
echo -e "${YELLOW}6. Respaldando lista de ASINs...${NC}"
if [ -f "asins.txt" ]; then
    cp asins.txt "${BACKUP_DIR}/"
    LINES=$(wc -l < asins.txt | tr -d ' ')
    echo -e "${GREEN}   ✅ Lista de ${LINES} ASINs respaldada${NC}"
else
    echo -e "${RED}   ⚠️  asins.txt no encontrado${NC}"
fi
echo ""

# 7. Comprimir backup
echo -e "${YELLOW}7. Comprimiendo backup...${NC}"
BACKUP_TAR="backups/local_backup_${TIMESTAMP}.tar.gz"
tar -czf "${BACKUP_TAR}" -C backups "local_backup_${TIMESTAMP}" 2>/dev/null
COMPRESSED_SIZE=$(du -h "${BACKUP_TAR}" | cut -f1)
echo -e "${GREEN}   ✅ Backup comprimido (${COMPRESSED_SIZE})${NC}"
echo ""

# 8. Subir backup al VPS
echo -e "${YELLOW}8. Subiendo backup al VPS...${NC}"

# Crear directorio en VPS si no existe
sshpass -p "${VPS_PASSWORD}" ssh -o StrictHostKeyChecking=no ${VPS_USER}@${VPS_HOST} \
    "mkdir -p ${VPS_BACKUP_DIR}" 2>/dev/null

# Subir archivo
sshpass -p "${VPS_PASSWORD}" scp -o StrictHostKeyChecking=no \
    "${BACKUP_TAR}" ${VPS_USER}@${VPS_HOST}:${VPS_BACKUP_DIR}/ 2>/dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}   ✅ Backup subido al VPS${NC}"
    echo -e "${BLUE}   📍 Ubicación VPS: ${VPS_BACKUP_DIR}/$(basename ${BACKUP_TAR})${NC}"
else
    echo -e "${YELLOW}   ⚠️  No se pudo subir al VPS (no crítico)${NC}"
fi
echo ""

# 9. Limpiar backups viejos (mantener solo últimos 7)
echo -e "${YELLOW}9. Limpiando backups viejos (manteniendo últimos 7)...${NC}"

# Locales
BACKUP_COUNT=$(ls -1 backups/local_backup_*.tar.gz 2>/dev/null | wc -l | tr -d ' ')
if [ "${BACKUP_COUNT}" -gt 7 ]; then
    ls -t backups/local_backup_*.tar.gz | tail -n +8 | xargs rm -f
    DELETED=$((BACKUP_COUNT - 7))
    echo -e "${GREEN}   ✅ ${DELETED} backups locales viejos eliminados${NC}"
else
    echo -e "${BLUE}   ℹ️  Solo ${BACKUP_COUNT} backups, no hay nada que limpiar${NC}"
fi

# VPS
sshpass -p "${VPS_PASSWORD}" ssh -o StrictHostKeyChecking=no ${VPS_USER}@${VPS_HOST} \
    "cd ${VPS_BACKUP_DIR} 2>/dev/null && ls -t local_backup_*.tar.gz 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null" 2>/dev/null

echo ""

# Resumen
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ BACKUP COMPLETADO EXITOSAMENTE${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}📦 Backup local:${NC}"
echo -e "   ${BACKUP_TAR} (${COMPRESSED_SIZE})"
echo ""
echo -e "${BLUE}📦 Backup en VPS:${NC}"
echo -e "   ${VPS_BACKUP_DIR}/$(basename ${BACKUP_TAR})"
echo ""
echo -e "${BLUE}💾 Contenido respaldado:${NC}"
echo -e "   • Base de datos (listings_database.db)"
echo -e "   • Pipeline state (pipeline_state.db)"
echo -e "   • Configuración (.env)"
echo -e "   • Lista de ASINs (asins.txt)"
echo -e "   • Últimos 100 ASINs JSON"
echo ""
echo -e "${GREEN}🎉 Tus datos están seguros!${NC}"
echo ""
