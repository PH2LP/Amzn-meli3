#!/bin/bash
# ============================================================
# Script para Iniciar Servicios en VPS
# Ejecutar DESPUÉS de configurar .env
# ============================================================

cd /opt/amz-ml-system

echo "════════════════════════════════════════════════════════"
echo "🚀 INICIANDO SERVICIOS"
echo "════════════════════════════════════════════════════════"
echo ""

# Verificar que .env existe
if [ ! -f .env ]; then
    echo "❌ Error: .env no existe"
    echo "   Ejecuta: nano .env"
    echo "   Y pega tus credenciales"
    exit 1
fi

echo "✅ .env encontrado"
echo ""

# Crear servicio de pipeline
echo "📝 [1/4] Creando servicio de pipeline..."
tee /etc/systemd/system/amz-ml-pipeline.service > /dev/null <<'EOF'
[Unit]
Description=AMZ-ML Autonomous Pipeline
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/amz-ml-system
Environment="PATH=/opt/amz-ml-system/venv/bin:/usr/bin:/bin"
ExecStart=/opt/amz-ml-system/venv/bin/python3 /opt/amz-ml-system/pipeline.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Crear servicio de auto-answer
echo "📝 [2/4] Creando servicio de auto-answer..."
tee /etc/systemd/system/amz-ml-auto-answer.service > /dev/null <<'EOF'
[Unit]
Description=AMZ-ML Auto Answer Questions
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/amz-ml-system
Environment="PATH=/opt/amz-ml-system/venv/bin:/usr/bin:/bin"
ExecStart=/opt/amz-ml-system/venv/bin/python3 /opt/amz-ml-system/scripts/tools/auto_answer_questions.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Crear servicio de backups
echo "📝 [3/4] Creando servicio de backups..."
tee /etc/systemd/system/amz-ml-backup.service > /dev/null <<'EOF'
[Unit]
Description=AMZ-ML Backup Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/amz-ml-system
ExecStart=/opt/amz-ml-system/scripts/backup/backup_loop.sh
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Activar e iniciar servicios
echo "🚀 [4/4] Activando e iniciando servicios..."
systemctl daemon-reload
systemctl enable amz-ml-pipeline amz-ml-auto-answer amz-ml-backup
systemctl start amz-ml-pipeline amz-ml-auto-answer amz-ml-backup

echo ""
echo "════════════════════════════════════════════════════════"
echo "✅ SERVICIOS INICIADOS"
echo "════════════════════════════════════════════════════════"
echo ""

# Ver estado
systemctl status amz-ml-pipeline --no-pager -l
echo ""
systemctl status amz-ml-auto-answer --no-pager -l
echo ""
systemctl status amz-ml-backup --no-pager -l

echo ""
echo "════════════════════════════════════════════════════════"
echo "📊 COMANDOS ÚTILES:"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Ver logs en vivo:"
echo "  tail -f /opt/amz-ml-system/storage/autonomous_logs/autonomous_system.log"
echo ""
echo "Ver estado de servicios:"
echo "  systemctl status amz-ml-*"
echo ""
echo "Reiniciar un servicio:"
echo "  systemctl restart amz-ml-pipeline"
echo ""
echo "Ver logs de systemd:"
echo "  journalctl -u amz-ml-pipeline -f"
echo ""
