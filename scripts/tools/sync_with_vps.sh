#!/bin/bash
# ============================================================
# sync_with_vps.sh
# Sincroniza bases de datos y archivos entre Mac y VPS
# ============================================================

VPS_HOST="root@138.197.32.67"
VPS_PATH="/opt/amz-ml-system"
LOCAL_PATH="/Users/felipemelucci/Desktop/revancha"
VPS_PASSWORD="koqven-1regka-nyfXiw"

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ============================================================
# Función: Sincronizar DESDE VPS (pull)
# ============================================================
sync_pull() {
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}📥 SINCRONIZANDO DESDE VPS → MAC${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo ""

    # 1. Bases de datos
    echo -e "${YELLOW}📊 Descargando bases de datos...${NC}"
    sshpass -p "$VPS_PASSWORD" scp -o StrictHostKeyChecking=no \
        "$VPS_HOST:$VPS_PATH/storage/listings_database.db" \
        "$LOCAL_PATH/storage/" 2>/dev/null && \
        echo -e "   ${GREEN}✓${NC} listings_database.db"

    sshpass -p "$VPS_PASSWORD" scp -o StrictHostKeyChecking=no \
        "$VPS_HOST:$VPS_PATH/storage/pipeline_state.db" \
        "$LOCAL_PATH/storage/" 2>/dev/null && \
        echo -e "   ${GREEN}✓${NC} pipeline_state.db"

    # 2. ASINs
    echo -e "${YELLOW}📝 Descargando lista de ASINs...${NC}"
    sshpass -p "$VPS_PASSWORD" scp -o StrictHostKeyChecking=no \
        "$VPS_HOST:$VPS_PATH/asins.txt" \
        "$LOCAL_PATH/" 2>/dev/null && \
        echo -e "   ${GREEN}✓${NC} asins.txt"

    # 3. Cache de tokens
    echo -e "${YELLOW}🔑 Descargando cache de tokens...${NC}"
    sshpass -p "$VPS_PASSWORD" scp -o StrictHostKeyChecking=no \
        "$VPS_HOST:$VPS_PATH/cache/amazon_token.json" \
        "$LOCAL_PATH/cache/" 2>/dev/null && \
        echo -e "   ${GREEN}✓${NC} amazon_token.json"

    sshpass -p "$VPS_PASSWORD" scp -o StrictHostKeyChecking=no \
        "$VPS_HOST:$VPS_PATH/cache/ml_token.json" \
        "$LOCAL_PATH/cache/" 2>/dev/null && \
        echo -e "   ${GREEN}✓${NC} ml_token.json"

    # 4. Datos de Amazon (solo si existen nuevos)
    echo -e "${YELLOW}📦 Sincronizando datos de Amazon...${NC}"
    sshpass -p "$VPS_PASSWORD" rsync -avz --progress \
        -e "sshpass -p $VPS_PASSWORD ssh -o StrictHostKeyChecking=no" \
        "$VPS_HOST:$VPS_PATH/storage/asins_json/" \
        "$LOCAL_PATH/storage/asins_json/" 2>/dev/null | grep -E "\.json$|sent|received" | tail -3

    # 5. Listings listos para publicar
    echo -e "${YELLOW}📋 Sincronizando listings listos...${NC}"
    sshpass -p "$VPS_PASSWORD" rsync -avz --progress \
        -e "sshpass -p $VPS_PASSWORD ssh -o StrictHostKeyChecking=no" \
        "$VPS_HOST:$VPS_PATH/storage/logs/publish_ready/" \
        "$LOCAL_PATH/storage/logs/publish_ready/" 2>/dev/null | grep -E "\.json$|sent|received" | tail -3

    echo ""
    echo -e "${GREEN}✅ Sincronización desde VPS completada${NC}"
    echo ""
}

# ============================================================
# Función: Sincronizar HACIA VPS (push)
# ============================================================
sync_push() {
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}📤 SINCRONIZANDO DESDE MAC → VPS${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo ""

    # 1. Bases de datos
    echo -e "${YELLOW}📊 Subiendo bases de datos...${NC}"
    sshpass -p "$VPS_PASSWORD" scp -o StrictHostKeyChecking=no \
        "$LOCAL_PATH/storage/listings_database.db" \
        "$VPS_HOST:$VPS_PATH/storage/" 2>/dev/null && \
        echo -e "   ${GREEN}✓${NC} listings_database.db"

    sshpass -p "$VPS_PASSWORD" scp -o StrictHostKeyChecking=no \
        "$LOCAL_PATH/storage/pipeline_state.db" \
        "$VPS_HOST:$VPS_PATH/storage/" 2>/dev/null && \
        echo -e "   ${GREEN}✓${NC} pipeline_state.db"

    # 2. ASINs
    echo -e "${YELLOW}📝 Subiendo lista de ASINs...${NC}"
    sshpass -p "$VPS_PASSWORD" scp -o StrictHostKeyChecking=no \
        "$LOCAL_PATH/asins.txt" \
        "$VPS_HOST:$VPS_PATH/" 2>/dev/null && \
        echo -e "   ${GREEN}✓${NC} asins.txt"

    # 3. Datos de Amazon
    echo -e "${YELLOW}📦 Sincronizando datos de Amazon...${NC}"
    sshpass -p "$VPS_PASSWORD" rsync -avz --progress \
        -e "sshpass -p $VPS_PASSWORD ssh -o StrictHostKeyChecking=no" \
        "$LOCAL_PATH/storage/asins_json/" \
        "$VPS_HOST:$VPS_PATH/storage/asins_json/" 2>/dev/null | grep -E "\.json$|sent|received" | tail -3

    # 4. Listings listos para publicar
    echo -e "${YELLOW}📋 Sincronizando listings listos...${NC}"
    sshpass -p "$VPS_PASSWORD" rsync -avz --progress \
        -e "sshpass -p $VPS_PASSWORD ssh -o StrictHostKeyChecking=no" \
        "$LOCAL_PATH/storage/logs/publish_ready/" \
        "$VPS_HOST:$VPS_PATH/storage/logs/publish_ready/" 2>/dev/null | grep -E "\.json$|sent|received" | tail -3

    echo ""
    echo -e "${GREEN}✅ Sincronización hacia VPS completada${NC}"
    echo ""
}

# ============================================================
# Función: Backup antes de sincronizar
# ============================================================
backup_local() {
    echo -e "${YELLOW}💾 Creando backup local...${NC}"
    BACKUP_DIR="$LOCAL_PATH/backups/sync_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"

    cp "$LOCAL_PATH/storage/listings_database.db" "$BACKUP_DIR/" 2>/dev/null
    cp "$LOCAL_PATH/storage/pipeline_state.db" "$BACKUP_DIR/" 2>/dev/null
    cp "$LOCAL_PATH/asins.txt" "$BACKUP_DIR/" 2>/dev/null

    echo -e "   ${GREEN}✓${NC} Backup guardado en: $BACKUP_DIR"
    echo ""
}

# ============================================================
# Menú principal
# ============================================================
show_menu() {
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}🔄 SINCRONIZACIÓN MAC ↔ VPS${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "1) 📥 Pull (VPS → Mac)   - Traer datos del VPS"
    echo "2) 📤 Push (Mac → VPS)   - Subir datos al VPS"
    echo "3) 🔄 Sync (Bidireccional) - Pull + Push"
    echo "4) 💾 Backup local antes de sincronizar"
    echo "5) ℹ️  Ver estado de sincronización"
    echo "6) ❌ Salir"
    echo ""
}

# ============================================================
# Ver estado
# ============================================================
show_status() {
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}📊 ESTADO DE SINCRONIZACIÓN${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo ""

    # Mac
    echo -e "${YELLOW}💻 MAC:${NC}"
    if [ -f "$LOCAL_PATH/storage/listings_database.db" ]; then
        LOCAL_DB_SIZE=$(ls -lh "$LOCAL_PATH/storage/listings_database.db" | awk '{print $5}')
        LOCAL_DB_DATE=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$LOCAL_PATH/storage/listings_database.db")
        echo -e "   listings_database.db: ${GREEN}$LOCAL_DB_SIZE${NC} (modificado: $LOCAL_DB_DATE)"
    else
        echo -e "   listings_database.db: ${RED}No existe${NC}"
    fi

    if [ -f "$LOCAL_PATH/asins.txt" ]; then
        LOCAL_ASINS=$(wc -l < "$LOCAL_PATH/asins.txt" | tr -d ' ')
        echo -e "   asins.txt: ${GREEN}$LOCAL_ASINS ASINs${NC}"
    else
        echo -e "   asins.txt: ${RED}No existe${NC}"
    fi

    echo ""

    # VPS
    echo -e "${YELLOW}☁️  VPS:${NC}"
    VPS_DB_INFO=$(sshpass -p "$VPS_PASSWORD" ssh -o StrictHostKeyChecking=no $VPS_HOST \
        "ls -lh $VPS_PATH/storage/listings_database.db 2>/dev/null | awk '{print \$5}' && \
         stat -c '%y' $VPS_PATH/storage/listings_database.db 2>/dev/null | cut -d'.' -f1" 2>/dev/null)

    if [ ! -z "$VPS_DB_INFO" ]; then
        VPS_DB_SIZE=$(echo "$VPS_DB_INFO" | head -1)
        VPS_DB_DATE=$(echo "$VPS_DB_INFO" | tail -1)
        echo -e "   listings_database.db: ${GREEN}$VPS_DB_SIZE${NC} (modificado: $VPS_DB_DATE)"
    else
        echo -e "   listings_database.db: ${RED}No existe${NC}"
    fi

    VPS_ASINS=$(sshpass -p "$VPS_PASSWORD" ssh -o StrictHostKeyChecking=no $VPS_HOST \
        "wc -l < $VPS_PATH/asins.txt 2>/dev/null" 2>/dev/null | tr -d ' ')

    if [ ! -z "$VPS_ASINS" ]; then
        echo -e "   asins.txt: ${GREEN}$VPS_ASINS ASINs${NC}"
    else
        echo -e "   asins.txt: ${RED}No existe${NC}"
    fi

    echo ""
}

# ============================================================
# Main
# ============================================================

# Si se pasa un argumento, ejecutar directamente
if [ "$1" = "pull" ]; then
    sync_pull
    exit 0
elif [ "$1" = "push" ]; then
    sync_push
    exit 0
elif [ "$1" = "sync" ]; then
    backup_local
    sync_pull
    exit 0
fi

# Modo interactivo
while true; do
    show_menu
    read -p "Seleccioná una opción: " option

    case $option in
        1)
            sync_pull
            ;;
        2)
            sync_push
            ;;
        3)
            backup_local
            sync_pull
            echo -e "${BLUE}Esperando 2 segundos antes de push...${NC}"
            sleep 2
            sync_push
            ;;
        4)
            backup_local
            ;;
        5)
            show_status
            ;;
        6)
            echo -e "${GREEN}👋 Chau!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Opción inválida${NC}"
            ;;
    esac

    echo ""
    read -p "Presioná Enter para continuar..."
    clear
done
