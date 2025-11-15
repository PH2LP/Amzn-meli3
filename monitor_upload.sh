#!/bin/bash
# Monitor del progreso de upload en tiempo real

clear
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 MONITOR DE PROGRESO - PIPELINE DE PUBLICACIÓN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

while true; do
    clear
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 MONITOR DE PROGRESO - PIPELINE DE PUBLICACIÓN"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⏰ $(date '+%H:%M:%S')"
    echo ""

    # Total de ASINs
    if [ -f asins.txt ]; then
        total=$(wc -l < asins.txt | tr -d ' ')
        echo "📦 Total ASINs a procesar: $total"
    else
        total=0
        echo "📦 Total ASINs: ⏳ Esperando..."
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📈 PROGRESO:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Buscar en todos los logs posibles
    if [ -f /tmp/autonomous_test_run.log ]; then
        procesados=$(grep -c "Processing\|🔍.*ASIN" /tmp/autonomous_test_run.log 2>/dev/null || echo "0")
        publicados=$(grep -c "✅.*Publicado\|Published successfully\|item_id.*CB" /tmp/autonomous_test_run.log 2>/dev/null || echo "0")
        errores=$(grep -c "❌.*Error\|ERROR\|Failed" /tmp/autonomous_test_run.log 2>/dev/null || echo "0")

        echo "✅ Publicados:  $publicados"
        echo "⏳ Procesando:  $procesados"
        echo "❌ Errores:     $errores"

        if [ "$total" -gt 0 ]; then
            porcentaje=$((publicados * 100 / total))
            echo "📊 Completado:  ${porcentaje}%"
        fi
    else
        echo "⏳ Pipeline iniciando..."
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📝 ÚLTIMAS 10 LÍNEAS DEL LOG:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if [ -f /tmp/autonomous_test_run.log ]; then
        tail -10 /tmp/autonomous_test_run.log | grep -E "✅|❌|🔍|Processing|ASIN|Publicado|Error" || echo "⏳ Sin actividad reciente..."
    else
        echo "⏳ Esperando que inicie el pipeline..."
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Actualizando cada 10 segundos... (Ctrl+C para salir)"

    sleep 10
done
