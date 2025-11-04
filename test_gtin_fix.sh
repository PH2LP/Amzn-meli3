#!/bin/bash
# Test alternative category finder fix

for asin in B092RCLKHN B0BXSLRQH7 B0CLC6NBBX B081SRSNWW; do
  echo "======================================================================"
  echo "🧪 Testing ASIN: $asin"
  echo "======================================================================"
  python3 main2.py --asin $asin --skip-validation 2>&1 | grep -A 3 -E "(Evaluando|categoría alternativa|Publicado exitosamente|Error publicación|Error buscando)"
  echo ""
done
