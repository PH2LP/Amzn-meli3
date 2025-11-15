#!/bin/bash
# ============================================================
# publish_local.sh
# Wrapper para publicar desde Mac con sincronización automática
# ============================================================

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SYNC_SCRIPT="$SCRIPT_DIR/sync_with_vps.sh"

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🚀 PUBLICACIÓN LOCAL CON SINCRONIZACIÓN${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# ============================================================
# Paso 1: Sincronizar DESDE VPS (traer datos actualizados)
# ============================================================
echo -e "${YELLOW}📥 Paso 1/3: Sincronizando datos desde VPS...${NC}"
echo ""
bash "$SYNC_SCRIPT" pull

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Error en sincronización. Abortando.${NC}"
    exit 1
fi

# ============================================================
# Paso 2: Ejecutar publicación
# ============================================================
echo -e "${YELLOW}🚀 Paso 2/3: Ejecutando publicación local...${NC}"
echo ""

# Verificar si se pasaron argumentos
if [ $# -eq 0 ]; then
    # Sin argumentos, usar asins.txt por defecto
    python3 "$SCRIPT_DIR/main2.py"
else
    # Con argumentos, pasarlos a main2.py
    python3 "$SCRIPT_DIR/main2.py" "$@"
fi

PUBLISH_EXIT_CODE=$?

if [ $PUBLISH_EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${RED}⚠️  La publicación terminó con errores (código: $PUBLISH_EXIT_CODE)${NC}"
    echo -e "${YELLOW}¿Querés sincronizar los cambios al VPS de todas formas? [s/n]${NC}"
    read -r response
    if [[ ! "$response" =~ ^[Ss]$ ]]; then
        echo -e "${RED}❌ Sincronización cancelada${NC}"
        exit $PUBLISH_EXIT_CODE
    fi
fi

# ============================================================
# Paso 3: Sincronizar HACIA VPS (subir cambios)
# ============================================================
echo ""
echo -e "${YELLOW}📤 Paso 3/3: Sincronizando cambios hacia VPS...${NC}"
echo ""
bash "$SYNC_SCRIPT" push

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Error en sincronización final${NC}"
    exit 1
fi

# ============================================================
# Resumen final
# ============================================================
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ PROCESO COMPLETADO${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "   📥 Datos sincronizados desde VPS"
echo -e "   🚀 Publicación ejecutada localmente"
echo -e "   📤 Cambios sincronizados hacia VPS"
echo ""
echo -e "${GREEN}Todo está actualizado en Mac y VPS${NC}"
echo ""

exit $PUBLISH_EXIT_CODE
