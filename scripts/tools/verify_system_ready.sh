#!/bin/bash

# Script de verificación del sistema autónomo

echo "════════════════════════════════════════════════════════════"
echo "🔍 VERIFICACIÓN DEL SISTEMA AUTÓNOMO"
echo "════════════════════════════════════════════════════════════"
echo ""

ERRORS=0

# 1. Verificar master_keywords.json
echo "1️⃣  Verificando keywords..."
if [ -f "config/master_keywords.json" ]; then
    TOTAL_KW=$(python3 -c "import json; data=json.load(open('config/master_keywords.json')); print(data.get('total_keywords', 0))")
    echo "   ✅ config/master_keywords.json existe"
    echo "   📊 Total keywords: $TOTAL_KW"

    if [ "$TOTAL_KW" -lt 100 ]; then
        echo "   ⚠️  ADVERTENCIA: Menos de 100 keywords"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "   ❌ config/master_keywords.json NO existe"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 2. Verificar scripts autónomos
echo "2️⃣  Verificando scripts..."
if [ -f "scripts/autonomous/autonomous_search_and_publish.py" ]; then
    echo "   ✅ autonomous_search_and_publish.py existe"
else
    echo "   ❌ autonomous_search_and_publish.py NO existe"
    ERRORS=$((ERRORS + 1))
fi

if [ -f "scripts/autonomous/keyword_manager.py" ]; then
    echo "   ✅ keyword_manager.py existe"
else
    echo "   ❌ keyword_manager.py NO existe"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 3. Verificar configuración
echo "3️⃣  Verificando configuración..."
if [ -f "config/quality_config.json" ]; then
    echo "   ✅ quality_config.json existe"
else
    echo "   ❌ quality_config.json NO existe"
    ERRORS=$((ERRORS + 1))
fi

if [ -f "config/autonomous_config.json" ]; then
    echo "   ✅ autonomous_config.json existe"
else
    echo "   ❌ autonomous_config.json NO existe"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 4. Verificar credenciales
echo "4️⃣  Verificando credenciales..."
if grep -q "ML_ACCESS_TOKEN=" .env 2>/dev/null; then
    echo "   ✅ ML_ACCESS_TOKEN configurado"
else
    echo "   ❌ ML_ACCESS_TOKEN NO configurado"
    ERRORS=$((ERRORS + 1))
fi

if grep -q "AMZ_CLIENT_ID=" .env 2>/dev/null; then
    echo "   ✅ Amazon credentials configurados"
else
    echo "   ❌ Amazon credentials NO configurados"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 5. Verificar base de datos
echo "5️⃣  Verificando base de datos..."
if [ -f "storage/listings_database.db" ]; then
    LISTINGS_COUNT=$(sqlite3 storage/listings_database.db "SELECT COUNT(*) FROM listings;" 2>/dev/null || echo "0")
    echo "   ✅ Database existe"
    echo "   📊 Publicaciones actuales: $LISTINGS_COUNT"
else
    echo "   ⚠️  Database no existe (se creará al publicar)"
fi
echo ""

# 6. Verificar pipeline
echo "6️⃣  Verificando pipeline de publicación..."
if [ -f "src/integrations/mainglobal.py" ]; then
    echo "   ✅ mainglobal.py existe"
else
    echo "   ❌ mainglobal.py NO existe"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 7. Verificar venv
echo "7️⃣  Verificando virtual environment..."
if [ -f "venv/bin/python3" ]; then
    PYTHON_VERSION=$(venv/bin/python3 --version 2>&1)
    echo "   ✅ venv existe ($PYTHON_VERSION)"
else
    echo "   ❌ venv NO existe"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Resultado final
echo "════════════════════════════════════════════════════════════"
if [ $ERRORS -eq 0 ]; then
    echo "✅ SISTEMA LISTO PARA PRODUCCIÓN"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    echo "🚀 Para iniciar el sistema:"
    echo ""
    echo "   # Test (1 keyword sin publicar):"
    echo "   ./venv/bin/python3 scripts/autonomous/autonomous_search_and_publish.py --dry-run --max-cycles 1"
    echo ""
    echo "   # Test real (1 keyword con publicación):"
    echo "   ./venv/bin/python3 scripts/autonomous/autonomous_search_and_publish.py --max-cycles 1"
    echo ""
    echo "   # Producción (loop infinito):"
    echo "   nohup ./venv/bin/python3 scripts/autonomous/autonomous_search_and_publish.py > logs/autonomous_system.log 2>&1 &"
    echo ""
else
    echo "❌ ERRORES ENCONTRADOS: $ERRORS"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    echo "Por favor corrige los errores antes de iniciar el sistema."
    echo ""
    exit 1
fi
