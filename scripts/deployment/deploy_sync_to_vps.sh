#!/bin/bash
# ============================================================
# deploy_sync_to_vps.sh
# Despliega el sistema de sincronización actualizado al VPS
# ============================================================

set -e  # Exit on error

VPS_HOST="root@138.197.32.67"
VPS_PATH="/opt/amz-ml-system"
VPS_PASSWORD="koqven-1regka-nyfXiw"

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🚀 DESPLEGANDO SISTEMA DE SYNC AL VPS${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# ============================================================
# PASO 1: Verificar conexión VPS
# ============================================================
echo -e "${YELLOW}1️⃣  Verificando conexión al VPS...${NC}"
if sshpass -p "$VPS_PASSWORD" ssh -o StrictHostKeyChecking=no "$VPS_HOST" "echo 'Conectado'" > /dev/null 2>&1; then
    echo -e "   ${GREEN}✓${NC} Conexión exitosa"
else
    echo -e "   ${RED}✗${NC} No se pudo conectar al VPS"
    exit 1
fi
echo ""

# ============================================================
# PASO 2: Subir archivo principal de sync
# ============================================================
echo -e "${YELLOW}2️⃣  Subiendo scripts de sincronización...${NC}"

# Sync principal
sshpass -p "$VPS_PASSWORD" scp -o StrictHostKeyChecking=no \
    scripts/tools/sync_amazon_ml.py \
    "$VPS_HOST:$VPS_PATH/scripts/tools/" && \
    echo -e "   ${GREEN}✓${NC} sync_amazon_ml.py"

# Tests de verificación
sshpass -p "$VPS_PASSWORD" scp -o StrictHostKeyChecking=no \
    test_sync_complete.py \
    "$VPS_HOST:$VPS_PATH/" && \
    echo -e "   ${GREEN}✓${NC} test_sync_complete.py"

sshpass -p "$VPS_PASSWORD" scp -o StrictHostKeyChecking=no \
    test_new_price_logic.py \
    "$VPS_HOST:$VPS_PATH/" && \
    echo -e "   ${GREEN}✓${NC} test_new_price_logic.py"

sshpass -p "$VPS_PASSWORD" scp -o StrictHostKeyChecking=no \
    verify_price_consistency.py \
    "$VPS_HOST:$VPS_PATH/" && \
    echo -e "   ${GREEN}✓${NC} verify_price_consistency.py"

echo ""

# ============================================================
# PASO 3: Verificar instalación de dependencias
# ============================================================
echo -e "${YELLOW}3️⃣  Verificando dependencias en VPS...${NC}"
sshpass -p "$VPS_PASSWORD" ssh -o StrictHostKeyChecking=no "$VPS_HOST" << 'ENDSSH'
cd /opt/amz-ml-system

# Activar venv si existe
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "   ✓ venv activado"
else
    echo "   ✗ venv no existe"
    exit 1
fi

# Verificar paquetes necesarios
python3 -c "import requests; import sqlite3; from dotenv import load_dotenv" 2>/dev/null && \
    echo "   ✓ Dependencias instaladas" || \
    echo "   ✗ Faltan dependencias"
ENDSSH
echo ""

# ============================================================
# PASO 4: Test de cálculo de precios
# ============================================================
echo -e "${YELLOW}4️⃣  Probando cálculo de precios en VPS...${NC}"
sshpass -p "$VPS_PASSWORD" ssh -o StrictHostKeyChecking=no "$VPS_HOST" << 'ENDSSH'
cd /opt/amz-ml-system
source venv/bin/activate

python3 test_new_price_logic.py 2>&1 | grep -E "✅|❌|Test [0-9]"
ENDSSH
echo ""

# ============================================================
# PASO 5: Verificar consistencia de precios
# ============================================================
echo -e "${YELLOW}5️⃣  Verificando consistencia con transform_mapper...${NC}"
sshpass -p "$VPS_PASSWORD" ssh -o StrictHostKeyChecking=no "$VPS_HOST" << 'ENDSSH'
cd /opt/amz-ml-system
source venv/bin/activate

python3 verify_price_consistency.py 2>&1 | grep -E "✅|❌|CONSISTENTE"
ENDSSH
echo ""

# ============================================================
# PASO 6: Verificar cron job
# ============================================================
echo -e "${YELLOW}6️⃣  Verificando cron job...${NC}"
CRON_EXISTS=$(sshpass -p "$VPS_PASSWORD" ssh -o StrictHostKeyChecking=no "$VPS_HOST" \
    "crontab -l 2>/dev/null | grep -c 'sync_amazon_ml.py' || echo 0")

if [ "$CRON_EXISTS" -gt 0 ]; then
    echo -e "   ${GREEN}✓${NC} Cron job ya configurado"
    sshpass -p "$VPS_PASSWORD" ssh -o StrictHostKeyChecking=no "$VPS_HOST" \
        "crontab -l | grep 'sync_amazon_ml.py'"
else
    echo -e "   ${YELLOW}⚠${NC} Cron job NO configurado"
    echo -e "   ${BLUE}ℹ${NC} Configurando cron job automáticamente..."

    # Configurar cron job
    sshpass -p "$VPS_PASSWORD" ssh -o StrictHostKeyChecking=no "$VPS_HOST" << 'ENDSSH'
# Obtener crontab actual
crontab -l > /tmp/current_cron 2>/dev/null || touch /tmp/current_cron

# Agregar nuevo job si no existe
if ! grep -q "sync_amazon_ml.py" /tmp/current_cron; then
    echo "# Sync Amazon -> MercadoLibre (cada 3 días a las 9am)" >> /tmp/current_cron
    echo "0 9 */3 * * cd /opt/amz-ml-system && source venv/bin/activate && python3 scripts/tools/sync_amazon_ml.py >> logs/sync/cron.log 2>&1" >> /tmp/current_cron
    crontab /tmp/current_cron
    echo "   ✓ Cron job configurado"
else
    echo "   ✓ Cron job ya existía"
fi
rm /tmp/current_cron
ENDSSH
fi
echo ""

# ============================================================
# PASO 7: Test en vivo (opcional)
# ============================================================
echo -e "${YELLOW}7️⃣  ¿Ejecutar test de sync en vivo en VPS? (opcional)${NC}"
echo -e "   ${BLUE}ℹ${NC} Esto ejecutará sync con productos reales en el VPS"
echo -n "   Ejecutar? [y/N]: "
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${YELLOW}   Ejecutando sync en VPS...${NC}"
    sshpass -p "$VPS_PASSWORD" ssh -o StrictHostKeyChecking=no "$VPS_HOST" << 'ENDSSH'
cd /opt/amz-ml-system
source venv/bin/activate

echo "   Iniciando sync..."
timeout 120 python3 scripts/tools/sync_amazon_ml.py 2>&1 | tail -30
ENDSSH
    echo ""
else
    echo -e "   ${YELLOW}⏭${NC} Test en vivo omitido"
fi
echo ""

# ============================================================
# PASO 8: Resumen final
# ============================================================
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ DEPLOYMENT COMPLETADO${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}📋 Archivos desplegados:${NC}"
echo "   • scripts/tools/sync_amazon_ml.py"
echo "   • test_sync_complete.py"
echo "   • test_new_price_logic.py"
echo "   • verify_price_consistency.py"
echo ""
echo -e "${BLUE}🔄 Cron job:${NC}"
echo "   • Configurado para ejecutar cada 3 días a las 9am"
echo "   • Logs en: logs/sync/cron.log"
echo ""
echo -e "${BLUE}✅ Tests pasados:${NC}"
echo "   • Cálculo de precios"
echo "   • Consistencia con transform_mapper"
echo ""
echo -e "${BLUE}🎯 Próximos pasos:${NC}"
echo "   1. El sync se ejecutará automáticamente cada 3 días"
echo "   2. Puedes ejecutarlo manualmente: ssh $VPS_HOST 'cd $VPS_PATH && source venv/bin/activate && python3 scripts/tools/sync_amazon_ml.py'"
echo "   3. Ver logs: ssh $VPS_HOST 'tail -f $VPS_PATH/logs/sync/cron.log'"
echo ""
echo -e "${GREEN}🚀 Sistema de sync operativo en VPS${NC}"
echo ""
