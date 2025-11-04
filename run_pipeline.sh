#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Pipeline Automático Amazon → MercadoLibre
# ═══════════════════════════════════════════════════════════════════════════
#
# Uso:
#   ./run_pipeline.sh              # Procesa ASINs de new_asins.txt
#   ./run_pipeline.sh --dry-run    # Simula sin publicar
#
# ═══════════════════════════════════════════════════════════════════════════

set -e  # Exit on error

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Banner
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo "🚀 Pipeline Automático Amazon → MercadoLibre"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

# Verificar que existe new_asins.txt
if [ ! -f "new_asins.txt" ]; then
    echo -e "${RED}❌ Error: No se encuentra el archivo new_asins.txt${NC}"
    echo ""
    echo "Crea el archivo con tus ASINs (uno por línea):"
    echo ""
    echo "  echo 'B092RCLKHN' > new_asins.txt"
    echo "  echo 'B0BGQLZ921' >> new_asins.txt"
    echo ""
    exit 1
fi

# Contar ASINs
ASIN_COUNT=$(grep -v '^#' new_asins.txt | grep -v '^$' | wc -l | tr -d ' ')

echo -e "${BLUE}📦 ASINs a procesar: ${ASIN_COUNT}${NC}"
echo ""
echo "ASINs:"
grep -v '^#' new_asins.txt | grep -v '^$' | head -10 | while read asin; do
    echo "  • $asin"
done

if [ "$ASIN_COUNT" -gt 10 ]; then
    echo "  ... y $((ASIN_COUNT - 10)) más"
fi

echo ""
echo -e "${YELLOW}⚙️  El pipeline ejecutará las siguientes fases:${NC}"
echo "  1. ⬇️  Download: Descarga datos de Amazon SP-API"
echo "  2. 🔄 Transform: Transforma y mapea a formato MercadoLibre"
echo "  3. ✅ Validate: Validación con IA (imágenes + categorías)"
echo "  4. 📤 Publish: Publicación en MercadoLibre CBT"
echo ""

# Preguntar confirmación (excepto en dry-run)
if [[ "$*" != *"--dry-run"* ]]; then
    read -p "¿Continuar con la publicación real? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}❌ Pipeline cancelado${NC}"
        exit 1
    fi
    echo ""
fi

# Crear directorio de logs si no existe
mkdir -p logs

# Timestamp para el log
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/pipeline_run_${TIMESTAMP}.log"

echo -e "${GREEN}🚀 Iniciando pipeline...${NC}"
echo ""
echo "📝 Log guardándose en: $LOG_FILE"
echo ""

# Ejecutar pipeline
python3 main2.py --asins-file new_asins.txt "$@" 2>&1 | tee "$LOG_FILE"

# Capturar exit code
EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Pipeline completado exitosamente - Todos los ASINs publicados${NC}"
elif [ $EXIT_CODE -eq 2 ]; then
    echo -e "${YELLOW}⚠️  Pipeline completado con errores parciales${NC}"
    echo -e "${YELLOW}   Revisa el reporte y el log de GTIN: storage/logs/gtin_issues.json${NC}"
else
    echo -e "${RED}❌ Pipeline falló - Revisa el log: $LOG_FILE${NC}"
fi

echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

exit $EXIT_CODE
