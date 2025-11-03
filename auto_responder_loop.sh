#!/bin/bash

echo "🤖 Sistema de Respuestas Automáticas Iniciado"
echo "================================================"
echo "Revisando preguntas cada 60 segundos..."
echo "Presiona Ctrl+C para detener"
echo ""

while true; do
    echo "⏰ $(date '+%Y-%m-%d %H:%M:%S') - Revisando preguntas..."

    cd /Users/felipemelucci/Desktop/revancha
    ./venv/bin/python3 auto_answer_questions.py

    echo "✅ Revisión completada. Esperando 60 segundos..."
    echo ""

    sleep 60
done
