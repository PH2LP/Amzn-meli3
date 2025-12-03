#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# CLEANUP LOCAL - Limpieza de Archivos Temporales
# ═══════════════════════════════════════════════════════════════════════
# Limpia archivos que se acumulan en tu Mac y ya no son necesarios
#
# Uso:
#   ./cleanup_local.sh --dry-run    # Ver qué se borraría
#   ./cleanup_local.sh              # Ejecutar limpieza real
#
# Se elimina:
#   - Logs viejos (>30 días)
#   - Mini ML viejos (listings ya publicados, >7 días)
#   - Backups sync viejos (>14 días)
#   - ASINs JSON viejos (>60 días) - SE MANTIENEN los recientes
#
# NO se elimina:
#   - Base de datos
#   - .env
#   - asins.txt
#   - ASINs JSON recientes (<60 días)
#   - Mini ML recientes (<7 días)
# ═══════════════════════════════════════════════════════════════════════

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Modo
DRY_RUN=false
if [ "$1" == "--dry-run" ]; then
    DRY_RUN=true
fi

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}🧹 CLEANUP LOCAL - Limpieza de Archivos Temporales${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Fecha: $(date '+%Y-%m-%d %H:%M:%S')${NC}"

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}Modo: DRY-RUN (simulación)${NC}"
else
    echo -e "${RED}Modo: REAL (eliminará archivos)${NC}"
fi

echo ""

# Contadores
TOTAL_FILES=0
TOTAL_SIZE=0

# Función para borrar o simular
delete_file() {
    if [ "$DRY_RUN" = true ]; then
        echo -e "  ${YELLOW}[DRY-RUN]${NC} Borraría: $1"
    else
        rm -f "$1"
        echo -e "  ${GREEN}✅${NC} Eliminado: $1"
    fi
    TOTAL_FILES=$((TOTAL_FILES + 1))
}

# 1. Limpiar logs viejos (>30 días)
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}1. Limpiando logs viejos (>30 días)${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

OLD_LOGS=$(find logs/ -type f -name "*.log" -mtime +30 2>/dev/null || true)

if [ -z "$OLD_LOGS" ]; then
    echo -e "${BLUE}  ℹ️  No hay logs viejos para eliminar${NC}"
else
    COUNT=$(echo "$OLD_LOGS" | wc -l | tr -d ' ')
    echo -e "${BLUE}  📊 Encontrados: ${COUNT} logs viejos${NC}"
    echo ""

    echo "$OLD_LOGS" | while read -r file; do
        [ -f "$file" ] && delete_file "$file"
    done
fi

echo ""

# 2. Limpiar Mini ML viejos (>7 días)
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}2. Limpiando Mini ML viejos (>7 días)${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ -d "storage/logs/publish_ready" ]; then
    OLD_MINI=$(find storage/logs/publish_ready/ -type f -name "*_mini_ml.json" -mtime +7 2>/dev/null || true)

    if [ -z "$OLD_MINI" ]; then
        echo -e "${BLUE}  ℹ️  No hay Mini ML viejos para eliminar${NC}"
    else
        COUNT=$(echo "$OLD_MINI" | wc -l | tr -d ' ')
        SIZE=$(echo "$OLD_MINI" | xargs du -ch 2>/dev/null | tail -1 | cut -f1)
        echo -e "${BLUE}  📊 Encontrados: ${COUNT} Mini ML viejos (${SIZE})${NC}"
        echo ""

        echo "$OLD_MINI" | while read -r file; do
            [ -f "$file" ] && delete_file "$file"
        done
    fi
else
    echo -e "${BLUE}  ℹ️  Directorio publish_ready no existe${NC}"
fi

echo ""

# 3. Limpiar backups sync viejos (>14 días)
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}3. Limpiando backups sync viejos (>14 días)${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ -d "backups" ]; then
    OLD_BACKUPS=$(find backups/ -type d -name "sync_*" -mtime +14 2>/dev/null || true)

    if [ -z "$OLD_BACKUPS" ]; then
        echo -e "${BLUE}  ℹ️  No hay backups sync viejos para eliminar${NC}"
    else
        COUNT=$(echo "$OLD_BACKUPS" | wc -l | tr -d ' ')
        echo -e "${BLUE}  📊 Encontrados: ${COUNT} backups sync viejos${NC}"
        echo ""

        echo "$OLD_BACKUPS" | while read -r dir; do
            if [ -d "$dir" ]; then
                if [ "$DRY_RUN" = true ]; then
                    echo -e "  ${YELLOW}[DRY-RUN]${NC} Borraría: $dir/"
                else
                    rm -rf "$dir"
                    echo -e "  ${GREEN}✅${NC} Eliminado: $dir/"
                fi
            fi
        done
    fi
else
    echo -e "${BLUE}  ℹ️  Directorio backups no existe${NC}"
fi

echo ""

# 4. Limpiar ASINs JSON MUY viejos (>60 días)
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}4. Limpiando ASINs JSON muy viejos (>60 días)${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ -d "storage/asins_json" ]; then
    OLD_ASINS=$(find storage/asins_json/ -type f -name "*.json" -mtime +60 2>/dev/null || true)

    if [ -z "$OLD_ASINS" ]; then
        echo -e "${BLUE}  ℹ️  No hay ASINs JSON muy viejos para eliminar${NC}"
    else
        COUNT=$(echo "$OLD_ASINS" | wc -l | tr -d ' ')
        SIZE=$(echo "$OLD_ASINS" | xargs du -ch 2>/dev/null | tail -1 | cut -f1)
        echo -e "${BLUE}  📊 Encontrados: ${COUNT} ASINs JSON muy viejos (${SIZE})${NC}"
        echo -e "${YELLOW}  ⚠️  Nota: Se mantienen los ASINs de los últimos 60 días${NC}"
        echo ""

        # Mostrar solo los primeros 5
        SHOWN=0
        echo "$OLD_ASINS" | while read -r file; do
            if [ -f "$file" ]; then
                if [ $SHOWN -lt 5 ]; then
                    delete_file "$file"
                    SHOWN=$((SHOWN + 1))
                else
                    [ "$DRY_RUN" = true ] && delete_file "$file"
                    [ "$DRY_RUN" = false ] && rm -f "$file" && TOTAL_FILES=$((TOTAL_FILES + 1))
                fi
            fi
        done

        if [ $COUNT -gt 5 ] && [ "$DRY_RUN" = false ]; then
            echo -e "  ${GREEN}✅${NC} ... y $((COUNT - 5)) más"
        fi
    fi
else
    echo -e "${BLUE}  ℹ️  Directorio asins_json no existe${NC}"
fi

echo ""

# 5. Limpiar archivos temporales
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}5. Limpiando archivos temporales${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

TEMP_FILES=$(find . -type f -name ".DS_Store" -o -name "*.pyc" -o -name "__pycache__" 2>/dev/null || true)

if [ -z "$TEMP_FILES" ]; then
    echo -e "${BLUE}  ℹ️  No hay archivos temporales para eliminar${NC}"
else
    COUNT=$(echo "$TEMP_FILES" | wc -l | tr -d ' ')
    echo -e "${BLUE}  📊 Encontrados: ${COUNT} archivos temporales${NC}"
    echo ""

    echo "$TEMP_FILES" | while read -r file; do
        [ -f "$file" ] || [ -d "$file" ] && delete_file "$file"
    done
fi

echo ""

# Resumen
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}📊 RESUMEN DE LIMPIEZA${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Total de archivos procesados: ${TOTAL_FILES}${NC}"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}⚠️  Esto fue una simulación (--dry-run)${NC}"
    echo -e "${BLUE}ℹ️  Ejecutá sin --dry-run para hacer la limpieza real${NC}"
else
    echo -e "${GREEN}✅ Limpieza completada exitosamente${NC}"
    echo ""
    echo -e "${BLUE}💾 Espacio liberado:${NC}"
    echo -e "   Logs viejos eliminados"
    echo -e "   Mini ML viejos eliminados"
    echo -e "   Backups sync viejos eliminados"
    echo -e "   ASINs JSON muy viejos eliminados (>60 días)"
    echo ""
    echo -e "${GREEN}🎉 Tu Mac está más limpia!${NC}"
fi

echo ""

# Mostrar uso actual de disco
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📊 USO DE DISCO ACTUAL${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${BLUE}Tamaño por directorio:${NC}"
[ -d "storage/asins_json" ] && echo -e "  ASINs JSON: $(du -sh storage/asins_json/ | cut -f1)"
[ -d "storage/logs/publish_ready" ] && echo -e "  Mini ML: $(du -sh storage/logs/publish_ready/ | cut -f1)"
[ -d "logs" ] && echo -e "  Logs: $(du -sh logs/ | cut -f1)"
[ -d "backups" ] && echo -e "  Backups: $(du -sh backups/ | cut -f1)"
[ -f "storage/listings_database.db" ] && echo -e "  Base de datos: $(du -sh storage/listings_database.db | cut -f1)"

echo ""
