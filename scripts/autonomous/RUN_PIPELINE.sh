#!/bin/bash
# Script para ejecutar el pipeline de publicación
# Procesa ASINs desde asins.txt y publica en MercadoLibre

echo "🚀 Iniciando pipeline de publicación..."
echo "📋 ASINs a procesar: $(wc -l < asins.txt)"
echo ""

python3 -u main2.py 2>&1 | tee logs/main2_$(date +%Y%m%d_%H%M%S).log
