#!/bin/bash
# Monitor del mega stress test de 300 productos

echo "═══════════════════════════════════════════════════════════════════════"
echo "         🚀 MONITOR - MEGA TEST 300 PRODUCTOS"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

# Check si está corriendo
if pgrep -f "mega_stress_test.py" > /dev/null; then
    PID=$(pgrep -f "mega_stress_test.py" | head -1)
    echo "✅ Test corriendo (PID: $PID)"
    echo ""

    # Tiempo corriendo
    ps -p $PID -o etime= | xargs echo "⏱️  Tiempo corriendo:"

    # Uso de memoria
    ps -p $PID -o rss= | awk '{print "💾 Memoria: " $1/1024 " MB"}'

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 PROGRESO ACTUAL:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Contar preguntas procesadas
    if [ -f "/tmp/mega_test_300.log" ]; then
        TOTAL=$(grep -c "^\[" /tmp/mega_test_300.log || echo "0")
        ANSWERED=$(grep -c "answered (conf:" /tmp/mega_test_300.log || echo "0")
        NO_ANSWER=$(grep -c "no_answer (conf:" /tmp/mega_test_300.log || echo "0")

        echo "  Total procesadas: $TOTAL / 300"
        echo "  Respondidas:      $ANSWERED"
        echo "  No respondidas:   $NO_ANSWER"

        if [ "$TOTAL" -gt 0 ]; then
            PERCENT=$((TOTAL * 100 / 300))
            echo "  Progreso:         $PERCENT%"
        fi

        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "📝 ÚLTIMAS 5 PREGUNTAS:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        tail -50 /tmp/mega_test_300.log | grep -A 1 "^\[" | tail -10
    else
        echo "  ⏳ Log aún no disponible..."
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Check si ya hay archivo de resultados
    LATEST_RESULT=$(ls -t test_results_stress/mega*.json 2>/dev/null | head -1)
    if [ -n "$LATEST_RESULT" ]; then
        echo "🎯 Archivo de resultado: $LATEST_RESULT"
        echo "   Tamaño: $(ls -lh "$LATEST_RESULT" | awk '{print $5}')"

        # Intentar leer stats del JSON
        if command -v jq &> /dev/null; then
            echo ""
            echo "📊 Estadísticas parciales:"
            jq -r '.summary | "  Aceptables: \(.acceptable) / \(.total_questions)\n  Rate: \(.acceptance_rate)%"' "$LATEST_RESULT" 2>/dev/null || echo "  Aún no hay stats finales"
        fi
    else
        echo "⏳ Archivo de resultados no creado aún"
    fi

else
    echo "❌ Test no está corriendo"
    echo ""
    echo "Último resultado:"
    ls -lth test_results_stress/mega*.json 2>/dev/null | head -1 || echo "  No hay resultados de mega test"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "TIP: Ejecuta './monitor_mega_test_300.sh' cada 30 seg para actualizar"
echo "═══════════════════════════════════════════════════════════════════════"
