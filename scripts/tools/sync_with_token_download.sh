#!/bin/bash
# Script wrapper para sincronizar Amazon -> MercadoLibre
# 1. Descarga token actualizado desde servidor
# 2. Ejecuta sync local

cd /Users/felipemelucci/Desktop/revancha

# Descargar .env actualizado desde servidor
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Descargando token desde servidor..."
sshpass -p 'koqven-1regka-nyfXiw' scp -o StrictHostKeyChecking=no root@138.197.32.67:/opt/amz-ml-system/.env .env

if [ $? -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Token descargado exitosamente"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Error descargando token, usando token local"
fi

# Ejecutar sync
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando sync..."
/opt/homebrew/bin/python3 -B scripts/tools/sync_amazon_ml_GLOW.py
