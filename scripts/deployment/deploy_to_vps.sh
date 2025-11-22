#!/bin/bash
# ============================================================
# Script Automático de Deployment a VPS
# ============================================================

VPS_IP="138.197.32.67"
DEPLOY_FILE="/tmp/deploy.tar.gz"

echo "════════════════════════════════════════════════════════"
echo "🚀 DEPLOYMENT AUTOMÁTICO A VPS"
echo "════════════════════════════════════════════════════════"
echo ""

# Verificar que existe el archivo
if [ ! -f "$DEPLOY_FILE" ]; then
    echo "❌ Error: $DEPLOY_FILE no existe"
    echo "   Ejecuta primero: tar --exclude='venv' --exclude='storage/*.db' --exclude='cache' -czf $DEPLOY_FILE ."
    exit 1
fi

echo "📦 Archivo listo: $(ls -lh $DEPLOY_FILE | awk '{print $5}')"
echo ""

# Paso 1: Subir archivo
echo "═══ PASO 1/5: Subiendo código al VPS ═══"
scp $DEPLOY_FILE root@$VPS_IP:/opt/
if [ $? -ne 0 ]; then
    echo "❌ Error subiendo archivo"
    exit 1
fi
echo "✅ Código subido"
echo ""

# Paso 2: Conectar y extraer
echo "═══ PASO 2/5: Extrayendo código en VPS ═══"
ssh root@$VPS_IP << 'ENDSSH'
cd /opt
mkdir -p amz-ml-system
tar -xzf deploy.tar.gz -C amz-ml-system
cd amz-ml-system
echo "✅ Código extraído en /opt/amz-ml-system"
ENDSSH
echo ""

# Paso 3: Ejecutar instalación
echo "═══ PASO 3/5: Instalando dependencias (esto toma ~5 min) ═══"
ssh root@$VPS_IP << 'ENDSSH'
cd /opt/amz-ml-system
chmod +x install_vps.sh
bash install_vps.sh
ENDSSH
echo ""

# Paso 4: Mostrar siguiente paso
echo "════════════════════════════════════════════════════════"
echo "✅ INSTALACIÓN COMPLETADA"
echo "════════════════════════════════════════════════════════"
echo ""
echo "📝 PRÓXIMO PASO: Configurar credenciales"
echo ""
echo "Ejecuta:"
echo "  ssh root@$VPS_IP"
echo "  nano /opt/amz-ml-system/.env"
echo ""
echo "Pega tus credenciales:"
echo "  LWA_CLIENT_ID=..."
echo "  LWA_CLIENT_SECRET=..."
echo "  REFRESH_TOKEN=..."
echo "  ML_ACCESS_TOKEN=..."
echo "  OPENAI_API_KEY=..."
echo ""
echo "Guarda: Ctrl+O → Enter → Ctrl+X"
echo ""
echo "Luego ejecuta: bash /opt/amz-ml-system/start_services.sh"
echo ""
