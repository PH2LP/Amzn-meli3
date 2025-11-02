#!/bin/bash
# Auto-monitor script - Supervisa pipeline y toma decisiones automáticas

LOG_FILE="/tmp/pipeline_FINAL_100PCT.log"
CYCLE=0

while true; do
    CYCLE=$((CYCLE + 1))
    echo "═══════════════════════════════════════════════════════"
    echo "🔍 Ciclo de monitoreo #$CYCLE - $(date)"
    echo "═══════════════════════════════════════════════════════"

    # Esperar 120 segundos para que el pipeline avance
    sleep 120

    # Verificar si el log existe
    if [ ! -f "$LOG_FILE" ]; then
        echo "⚠️ Log no encontrado, esperando..."
        continue
    fi

    # Extraer resumen del pipeline
    LINES=$(wc -l < "$LOG_FILE" 2>/dev/null || echo 0)
    PUBLICADOS=$(grep -c "✅ Publicado exitosamente" "$LOG_FILE" 2>/dev/null || echo 0)
    ERRORES=$(grep -c "❌ Error publicando" "$LOG_FILE" 2>/dev/null || echo 0)
    GTIN_ERRORS=$(grep -c "3701\|invalid_product_identifier" "$LOG_FILE" 2>/dev/null || echo 0)
    CAT_ERRORS=$(grep -c "category.*incorrect\|Title and photos did not match" "$LOG_FILE" 2>/dev/null || echo 0)

    echo "📊 Estado actual:"
    echo "   • Total líneas: $LINES"
    echo "   • Publicados: $PUBLICADOS"
    echo "   • Errores: $ERRORES"
    echo "   • Errores GTIN: $GTIN_ERRORS"
    echo "   • Errores categoría: $CAT_ERRORS"

    # Verificar si terminó (buscar "REPORTE FINAL")
    if grep -q "REPORTE FINAL" "$LOG_FILE"; then
        echo ""
        echo "✅ Pipeline completado!"
        echo ""
        grep -A10 "REPORTE FINAL" "$LOG_FILE" | tail -15

        # Si hay fallidos, mostrarlos
        FALLIDOS=$(grep "ASINs fallidos:" "$LOG_FILE" | tail -1)
        if [ ! -z "$FALLIDOS" ]; then
            echo ""
            echo "⚠️ $FALLIDOS"
            echo ""
            echo "🔄 Reintentando ASINs fallidos automáticamente..."
            # TODO: Aquí se podría agregar lógica para reintentar solo los fallidos
        fi

        break
    fi

    # Si llevamos más de 10 minutos (5 ciclos) sin avance, algo está mal
    if [ $CYCLE -ge 5 ] && [ $LINES -lt 100 ]; then
        echo ""
        echo "⚠️ Pipeline parece estar bloqueado (pocas líneas después de 10 minutos)"
        echo "Últimas 30 líneas del log:"
        tail -30 "$LOG_FILE"
        break
    fi

done

echo ""
echo "═══════════════════════════════════════════════════════"
echo "🏁 Monitoreo finalizado - $(date)"
echo "═══════════════════════════════════════════════════════"
