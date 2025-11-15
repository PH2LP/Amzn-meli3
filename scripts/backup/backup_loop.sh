#!/bin/bash
# ============================================================
# Loop de Backup Automático - Cada 6 horas
# ============================================================

cd "$(dirname "$0")/../.."

echo "🔄 Sistema de backup automático iniciado"
echo "   Frecuencia: Cada 6 horas"
echo "   Presiona Ctrl+C para detener"
echo ""

# Ejecutar backup inmediato
./scripts/backup/auto_backup_db.sh

while true; do
    echo ""
    echo "⏰ Próximo backup en 6 horas..."
    echo "   $(date)"

    sleep 21600  # 6 horas = 21600 segundos

    echo ""
    echo "════════════════════════════════════════════════════════"
    echo "🕐 $(date '+%Y-%m-%d %H:%M:%S') - Ejecutando backup..."
    echo "════════════════════════════════════════════════════════"

    ./scripts/backup/auto_backup_db.sh
done
