#!/bin/bash
# Monitor del mega stress test

echo "=== MONITOR DEL MEGA STRESS TEST ==="
echo ""

# Check si está corriendo
if pgrep -f "mega_stress_test.py" > /dev/null; then
    echo "✅ Test corriendo (PID: $(pgrep -f mega_stress_test.py | head -1))"
    echo ""

    # Tiempo corriendo
    ps -p $(pgrep -f mega_stress_test.py | head -1) -o etime= | xargs echo "⏱️  Tiempo corriendo:"

    # Uso de memoria
    ps -p $(pgrep -f mega_stress_test.py | head -1) -o rss= | awk '{print "💾 Memoria: " $1/1024 " MB"}'

    echo ""
    echo "📊 Esperando resultados..."
    echo ""

    # Check si ya hay archivo de resultados
    LATEST_RESULT=$(ls -t test_results_stress/mega*.json 2>/dev/null | head -1)
    if [ -n "$LATEST_RESULT" ]; then
        echo "🎯 Archivo de resultado encontrado: $LATEST_RESULT"
        echo "   Tamaño: $(ls -lh "$LATEST_RESULT" | awk '{print $5}')"
    else
        echo "⏳ Aún no hay archivo de resultados"
    fi
else
    echo "❌ Test no está corriendo"
    echo ""
    echo "Último resultado:"
    ls -lth test_results_stress/mega*.json 2>/dev/null | head -1 || echo "  No hay resultados de mega test"
fi

echo ""
echo "=== FIN MONITOR ==="
