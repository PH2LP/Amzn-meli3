#!/bin/bash
# ============================================================
# 💬 SISTEMA DE RESPUESTAS AUTOMÁTICAS MERCADOLIBRE
# ============================================================
# Responde preguntas de clientes automáticamente cada 60 segundos
# ============================================================

cd "$(dirname "$0")" || exit 1

# Activar venv
if [ -d "venv" ]; then
    source venv/bin/activate
fi

LOG_FILE="logs/auto_answer.log"
mkdir -p logs

echo "💬 Iniciando sistema de respuestas automáticas MercadoLibre"
echo "📝 Log: $LOG_FILE"
echo "⏳ Revisa preguntas cada 60 segundos"
echo ""
echo "Sistema INTELIGENTE:"
echo "  1. Preguntas genéricas → Respuesta instantánea (0 tokens)"
echo "  2. Preguntas específicas → IA con datos del producto (~150 tokens)"
echo "  3. Saludo y despedida personalizados"
echo ""
echo "Para detener:"
echo "  pkill -f auto_answer_questions.py"
echo ""

# Loop infinito
iteration=1
while true; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔄 Iteración #$iteration - $(date '+%H:%M:%S')"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    python3 scripts/tools/auto_answer_questions.py 2>&1 | tee -a "$LOG_FILE"

    echo ""
    echo "⏳ Esperando 60 segundos hasta próxima revisión..."
    echo ""

    sleep 60
    iteration=$((iteration + 1))
done
