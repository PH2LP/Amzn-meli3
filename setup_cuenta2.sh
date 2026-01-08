#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# setup_cuenta2.sh - CREAR SEGUNDA INSTANCIA PARA CUENTA ML 2
# ═══════════════════════════════════════════════════════════════════════════════
#
# Este script crea una segunda instancia COMPLETAMENTE AISLADA del sistema
# en ~/Desktop/revancha-cuenta2/
#
# Uso:
#   chmod +x setup_cuenta2.sh
#   ./setup_cuenta2.sh
#
# ═══════════════════════════════════════════════════════════════════════════════

set -e  # Exit on error

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "🚀 SETUP SEGUNDA INSTANCIA - CUENTA ML 2"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

# Directorio destino
DEST_DIR="$HOME/Desktop/revancha-cuenta2"

# Verificar si ya existe
if [ -d "$DEST_DIR" ]; then
    echo "⚠️  ERROR: El directorio $DEST_DIR ya existe"
    echo ""
    read -p "¿Quieres eliminarlo y crear uno nuevo? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  Eliminando directorio existente..."
        rm -rf "$DEST_DIR"
    else
        echo "❌ Setup cancelado"
        exit 1
    fi
fi

# Clonar repositorio
echo "📦 Clonando repositorio desde GitHub..."
cd "$HOME/Desktop"
git clone https://github.com/PH2LP/Amzn-meli3.git revancha-cuenta2

cd "$DEST_DIR"

# Crear virtual environment
echo ""
echo "🐍 Creando virtual environment..."
python3 -m venv venv

# Activar venv
source venv/bin/activate

# Instalar dependencias
echo ""
echo "📚 Instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt

# Crear .env para CUENTA 2
echo ""
echo "📝 Creando archivo .env para CUENTA 2..."

cat > .env << 'EOF'
# ═══════════════════════════════════════════════════════════════════════════════
# .ENV - CUENTA MERCADOLIBRE 2
# ═══════════════════════════════════════════════════════════════════════════════

# === MERCADOLIBRE (CUENTA 2) ===
ML_CLIENT_ID=
ML_CLIENT_SECRET=
ML_ACCESS_TOKEN=
ML_REFRESH_TOKEN=
ML_USER_ID=

# === AMAZON (COMPARTIDO CON CUENTA 1) ===
LWA_CLIENT_ID=
LWA_CLIENT_SECRET=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
SELLER_ID=
REFRESH_TOKEN=

# === SP-API CONFIG ===
SPAPI_REGION=us-east-1
MARKETPLACE_ID=ATVPDKIKX0DER

# === CONFIGURACIÓN DE SYNC ===
MAX_DELIVERY_DAYS=7
BUYER_ZIPCODE=33172
PROFIT_MARGIN_MULTIPLIER=1.50

# === TELEGRAM NOTIFICATIONS (CUENTA 2 - OPCIONAL) ===
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# === HORARIOS DE SYNC (4 veces al día) ===
SYNC_SCHEDULED_TIMES=00:10,06:10,12:10,18:10

# === OPENAI (OPCIONAL - Para descripciones automáticas) ===
OPENAI_API_KEY=

EOF

# Crear directorios necesarios
echo ""
echo "📁 Creando directorios..."
mkdir -p storage cache logs/sync data/schemas temp

# Copiar amazon_session_cookies.json si existe (puede compartirse entre cuentas)
if [ -f "$HOME/Desktop/revancha/cache/amazon_session_cookies.json" ]; then
    echo ""
    echo "🔐 Copiando sesión Prime de Cuenta 1..."
    cp "$HOME/Desktop/revancha/cache/amazon_session_cookies.json" cache/
fi

# Crear README para la cuenta 2
cat > README_CUENTA2.md << 'EOF'
# Instancia para Cuenta MercadoLibre 2

Esta es una instancia COMPLETAMENTE INDEPENDIENTE del sistema Amazon-ML.

## Configuración Inicial

1. **Editar .env con credenciales de la CUENTA 2:**
   ```bash
   nano .env
   ```

2. **Obtener tokens de MercadoLibre Cuenta 2:**
   - Ve a: https://developers.mercadolibre.com.ar/
   - Crea una nueva app o usa una existente para Cuenta 2
   - Copia: CLIENT_ID, CLIENT_SECRET
   - Genera ACCESS_TOKEN y REFRESH_TOKEN

3. **Capturar sesión Prime (opcional, ya está copiada):**
   ```bash
   python3 19_capture_amazon_session.py
   ```

## Uso

### Ejecutar sync manual (una vez):
```bash
source venv/bin/activate
python3 scripts/tools/sync_amazon_ml_GLOW.py
```

### Ejecutar sync automático (loop cada 6 horas):
```bash
source venv/bin/activate
python3 06_sync_loop.py
```

### Publicar productos:
```bash
source venv/bin/activate
python3 01_search.py          # Buscar productos
python3 03_publish_parallel.py  # Publicar
```

## Aislamiento

Esta instancia tiene sus propias bases de datos:
- `storage/listings_database.db` - Listings de CUENTA 2 únicamente
- `storage/pipeline_state.db` - Estado de CUENTA 2
- `cache/` - Cache independiente
- `logs/` - Logs separados

**NO interfiere con la Cuenta 1 en `~/Desktop/revancha/`**

EOF

# Crear script de activación rápida
cat > activate.sh << 'EOF'
#!/bin/bash
# Activar venv rápidamente
source venv/bin/activate
echo "✅ Virtual environment activado (Cuenta 2)"
echo "Ejecuta: python3 06_sync_loop.py"
EOF

chmod +x activate.sh

# Crear .gitignore local para evitar subir datos sensibles
cat > .gitignore << 'EOF'
.env
.env.local*
.env.bak*
cache/
storage/
logs/
temp_parallel_*/
venv/
__pycache__/
*.pyc
*.db
EOF

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "✅ SEGUNDA INSTANCIA CREADA EXITOSAMENTE"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""
echo "📍 Ubicación: $DEST_DIR"
echo ""
echo "📋 PRÓXIMOS PASOS:"
echo ""
echo "1️⃣  Editar .env con credenciales de CUENTA 2:"
echo "   cd $DEST_DIR"
echo "   nano .env"
echo ""
echo "2️⃣  Activar virtual environment:"
echo "   source venv/bin/activate"
echo "   # O simplemente: ./activate.sh"
echo ""
echo "3️⃣  Ejecutar sync:"
echo "   python3 06_sync_loop.py"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "⚠️  IMPORTANTE: Esta instancia es COMPLETAMENTE INDEPENDIENTE"
echo "   - Tiene su propia base de datos (storage/)"
echo "   - Tiene sus propios logs (logs/)"
echo "   - NO interfiere con Cuenta 1 en ~/Desktop/revancha/"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""
