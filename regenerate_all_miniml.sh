#!/bin/bash

echo "🚀 Regenerando mini_ml para todos los ASINs con correcciones..."
echo ""

SUCCESS=0
FAILED=0

for asin_file in storage/asins_json/*.json; do
  asin=$(basename "$asin_file" .json)
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "🔄 Procesando $asin..."
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  if python3 src/transform_mapper_new.py "$asin_file" 2>&1; then
    SUCCESS=$((SUCCESS + 1))
    echo "✅ $asin completado"
  else
    FAILED=$((FAILED + 1))
    echo "❌ $asin falló"
  fi
  echo ""
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 RESUMEN:"
echo "   ✅ Exitosos: $SUCCESS"
echo "   ❌ Fallidos: $FAILED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
