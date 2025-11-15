#!/bin/bash
# ============================================================
# Backup Automático de Base de Datos + Archivos Críticos
# Se ejecuta cada 6 horas y sube a múltiples destinos
# ============================================================

cd "$(dirname "$0")/../.."

BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="backup_${TIMESTAMP}"

mkdir -p $BACKUP_DIR

echo "🔄 Iniciando backup: $BACKUP_NAME"

# 1. Backup de la base de datos (CRÍTICO)
echo "📦 [1/4] Backup de base de datos..."
cp storage/listings_database.db $BACKUP_DIR/${BACKUP_NAME}_listings.db
cp storage/pipeline_state.db $BACKUP_DIR/${BACKUP_NAME}_pipeline.db 2>/dev/null || true

# 2. Backup de configuraciones (CRÍTICO)
echo "⚙️  [2/4] Backup de configuraciones..."
tar -czf $BACKUP_DIR/${BACKUP_NAME}_config.tar.gz \
    config/ \
    .env \
    docs/questions/ \
    2>/dev/null || true

# 3. Backup de logs importantes (últimos 7 días)
echo "📝 [3/4] Backup de logs recientes..."
find storage/autonomous_logs -name "*.log" -mtime -7 -exec tar -czf $BACKUP_DIR/${BACKUP_NAME}_logs.tar.gz {} + 2>/dev/null || true

# 4. Comprimir todo en un archivo
echo "🗜️  [4/4] Comprimiendo backup completo..."
tar -czf $BACKUP_DIR/${BACKUP_NAME}_FULL.tar.gz \
    $BACKUP_DIR/${BACKUP_NAME}_*.db \
    $BACKUP_DIR/${BACKUP_NAME}_*.tar.gz \
    2>/dev/null

# Limpiar archivos temporales
rm -f $BACKUP_DIR/${BACKUP_NAME}_*.db
rm -f $BACKUP_DIR/${BACKUP_NAME}_config.tar.gz
rm -f $BACKUP_DIR/${BACKUP_NAME}_logs.tar.gz

BACKUP_FILE="$BACKUP_DIR/${BACKUP_NAME}_FULL.tar.gz"
BACKUP_SIZE=$(du -h $BACKUP_FILE | cut -f1)

echo "✅ Backup creado: $BACKUP_FILE ($BACKUP_SIZE)"

# 5. Subir a múltiples destinos
echo ""
echo "☁️  Subiendo a destinos remotos..."

# ══════════════════════════════════════════════════════════
# OPCIÓN A: Dropbox (usando Dropbox-Uploader)
# ══════════════════════════════════════════════════════════
if command -v dropbox_uploader.sh &> /dev/null; then
    echo "  📤 Subiendo a Dropbox..."
    dropbox_uploader.sh upload $BACKUP_FILE /backups/ && echo "  ✅ Dropbox OK"
fi

# ══════════════════════════════════════════════════════════
# OPCIÓN B: Google Drive (usando rclone)
# ══════════════════════════════════════════════════════════
if command -v rclone &> /dev/null; then
    echo "  📤 Subiendo a Google Drive..."
    rclone copy $BACKUP_FILE gdrive:AMZ-ML-Backups/ && echo "  ✅ Google Drive OK"
fi

# ══════════════════════════════════════════════════════════
# OPCIÓN C: AWS S3 (si tienes cuenta)
# ══════════════════════════════════════════════════════════
if command -v aws &> /dev/null; then
    echo "  📤 Subiendo a AWS S3..."
    aws s3 cp $BACKUP_FILE s3://tu-bucket/backups/ && echo "  ✅ AWS S3 OK"
fi

# ══════════════════════════════════════════════════════════
# OPCIÓN D: Tu servidor personal (SCP)
# ══════════════════════════════════════════════════════════
# Descomentar si tienes otro servidor
# echo "  📤 Subiendo a servidor personal..."
# scp $BACKUP_FILE user@tu-otro-servidor.com:/backups/ && echo "  ✅ Servidor personal OK"

# 6. Limpiar backups locales viejos (mantener últimos 7 días)
echo ""
echo "🧹 Limpiando backups locales antiguos..."
find $BACKUP_DIR -name "backup_*_FULL.tar.gz" -mtime +7 -delete
REMAINING=$(ls -1 $BACKUP_DIR/backup_*_FULL.tar.gz 2>/dev/null | wc -l)
echo "   Backups locales restantes: $REMAINING"

echo ""
echo "════════════════════════════════════════════════════════"
echo "✅ Backup completado exitosamente"
echo "════════════════════════════════════════════════════════"
echo "   Archivo: $BACKUP_FILE"
echo "   Tamaño: $BACKUP_SIZE"
echo "   Próximo backup: En 6 horas"
echo "════════════════════════════════════════════════════════"
