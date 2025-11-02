#!/bin/bash
# Loop autónomo - Ejecuta pipeline, analiza errores, corrige, repite hasta 100% éxito

MAX_ITERATIONS=10
ITERATION=0

while [ $ITERATION -lt $MAX_ITERATIONS ]; do
    ITERATION=$((ITERATION + 1))
    echo ""
    echo "═══════════════════════════════════════════════════════"
    echo "🔄 ITERACIÓN #$ITERATION - $(date)"
    echo "═══════════════════════════════════════════════════════"

    # 1. Ejecutar pipeline
    echo "🚀 Ejecutando pipeline..."
    python3 main.py 2>&1 | tee "/tmp/pipeline_iteration_${ITERATION}.log"

    # 2. Verificar resultados
    echo ""
    echo "📊 Verificando resultados..."
    PUBLICADOS=$(grep -c "✅ Publicado exitosamente" "/tmp/pipeline_iteration_${ITERATION}.log" || echo 0)
    FALLIDOS=$(grep "ASINs fallidos:" "/tmp/pipeline_iteration_${ITERATION}.log" | tail -1 | grep -oP '\d+(?=/)')
    TOTAL=14

    echo "   • Publicados: $PUBLICADOS/$TOTAL"
    echo "   • Fallidos: ${FALLIDOS:-0}"

    # 3. Si todos publicados → ÉXITO
    if [ "$PUBLICADOS" -eq "$TOTAL" ]; then
        echo ""
        echo "🎉 ¡ÉXITO! Todos los ASINs publicados correctamente"
        echo ""
        python3 verificar_publicaciones.py
        break
    fi

    # 4. Analizar y corregir errores
    echo ""
    echo "🔧 Analizando y corrigiendo errores..."
    python3 fix_all_errors.py

    # 5. Eliminar mini_ml de productos fallidos para regenerarlos
    echo ""
    echo "🗑️  Eliminando mini_ml de productos fallidos para regeneración..."
    if [ ! -z "$FALLIDOS" ]; then
        # Extraer ASINs fallidos
        FAILED_ASINS=$(grep "ASINs fallidos:" "/tmp/pipeline_iteration_${ITERATION}.log" | tail -1 | sed 's/.*: //' | tr ',' '\n' | tr -d ' ')
        for asin in $FAILED_ASINS; do
            if [ -f "logs/publish_ready/${asin}_mini_ml.json" ]; then
                echo "   • Eliminando logs/publish_ready/${asin}_mini_ml.json"
                rm -f "logs/publish_ready/${asin}_mini_ml.json"
            fi
        done
    fi

    echo ""
    echo "⏳ Esperando 5 segundos antes del próximo intento..."
    sleep 5

done

if [ $ITERATION -ge $MAX_ITERATIONS ]; then
    echo ""
    echo "⚠️ Máximo de iteraciones alcanzado ($MAX_ITERATIONS)"
    echo "Ver logs en: /tmp/pipeline_iteration_*.log"
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "🏁 Loop autónomo finalizado - $(date)"
echo "═══════════════════════════════════════════════════════"
