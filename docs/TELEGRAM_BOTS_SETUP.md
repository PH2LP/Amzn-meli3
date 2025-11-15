# Configuración de Bots de Telegram Separados

El sistema usa **4 bots separados** para diferentes tipos de notificaciones, evitando spam y organizando la información:

## 📱 Bots Actuales

### 1️⃣ Bot de Ventas (Ya configurado ✅)
**Propósito**: Notificaciones de nuevas ventas con link directo a Amazon para comprar

**Variables en `.env`**:
```bash
TELEGRAM_BOT_TOKEN=8273559490:AAEAhUm0fPN_aghkzLxVqBmgAvvz3LTzBik
TELEGRAM_CHAT_ID=5915021583
TELEGRAM_NOTIFICATIONS_ENABLED=true
```

**Archivo**: `scripts/tools/telegram_sales_notifier.py`

**Ejemplo de notificación**:
```
🎉 ¡NUEVA VENTA EN MERCADOLIBRE! 🎉
📦 Producto: iPhone 15 Pro Max
💰 Total: $1,299.99
🔗 CLICK AQUÍ PARA COMPRAR EN AMAZON
```

---

### 2️⃣ Bot de Publicaciones (Ya configurado ✅)
**Propósito**: Progreso de publicaciones (pipeline main2)

**Variables en `.env`**:
```bash
TELEGRAM_PUBLISHING_BOT_TOKEN=8373572993:AAGbIiQTjXgUup8PR3ObZ7RGTtQEgduo2AM
TELEGRAM_PUBLISHING_CHAT_ID=5915021583
TELEGRAM_PUBLISHING_ENABLED=true
```

**Archivo**: `scripts/tools/telegram_publishing_notifier.py`

**Ejemplo de notificación**:
```
[40/100] ✅ B0ABC123 → 5/5 MCO, MLM, MLA, MLB, MLC
📦 Samsung Galaxy S24 Ultra 256GB
```

---

### 3️⃣ Bot de Solicitudes de Productos (PENDIENTE ⚠️)
**Propósito**: Notificaciones cuando un cliente pregunta por un producto que no tenemos

**Variables en `.env`**:
```bash
TELEGRAM_PRODUCT_REQUESTS_BOT_TOKEN=PENDIENTE_CREAR_BOT
TELEGRAM_PRODUCT_REQUESTS_CHAT_ID=5915021583
TELEGRAM_PRODUCT_REQUESTS_ENABLED=true
```

**Archivo**: `scripts/tools/telegram_product_notifier.py`

**Ejemplo de notificación**:
```
🔍 PRODUCTO SOLICITADO
━━━━━━━━━━━━━━━━━━━━━
🌎 País: 🇲🇽 México
👤 Cliente: @juanperez
💬 Pregunta: "Tenés el modelo Pro?"
🎯 Producto buscado: iPhone 15 Pro
```

---

### 4️⃣ Bot de Sync Amazon-ML (PENDIENTE ⚠️)
**Propósito**: Sincronización de precios/stock entre Amazon y MercadoLibre

**Variables en `.env`**:
```bash
TELEGRAM_SYNC_BOT_TOKEN=PENDIENTE_CREAR_BOT
TELEGRAM_SYNC_CHAT_ID=5915021583
TELEGRAM_SYNC_ENABLED=true
```

**Archivo**: `scripts/tools/telegram_sync_notifier.py`

**Ejemplo de notificación**:
```
🔄 Iniciando sync: 150 productos
📈 B0ABC123 → $599.99 → $649.99 (+8.3%)
⏸️ B0DEF456 → Pausado: Sin oferta Prime
✅ SYNC COMPLETADO
   • Total procesados: 150
   • Precios actualizados: 12
   • Productos pausados: 3
```

---

## 🚀 Cómo Crear los Bots Pendientes

### Paso 1: Crear el Bot con @BotFather

1. Abre Telegram y busca `@BotFather`
2. Envía `/newbot`
3. Escoge un nombre para el bot:
   - Para Bot 3: `Nexo Trading Product Requests Bot`
   - Para Bot 4: `Nexo Trading Sync Bot`
4. Escoge un username (debe terminar en `bot`):
   - Para Bot 3: `nexo_product_requests_bot`
   - Para Bot 4: `nexo_sync_bot`
5. @BotFather te dará un **TOKEN**. Guárdalo.

### Paso 2: Obtener el Chat ID

Ya tenés el chat ID: `5915021583` (es el mismo para todos los bots).

Si necesitás verificarlo:
1. Envía un mensaje al bot
2. Abre: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Busca `"chat":{"id":XXXXXXX}`

### Paso 3: Actualizar el .env

Reemplaza `PENDIENTE_CREAR_BOT` en `.env` con los tokens que obtuviste:

```bash
# === BOT 3: SOLICITUDES DE PRODUCTOS (Preguntas) ===
TELEGRAM_PRODUCT_REQUESTS_BOT_TOKEN=1234567890:ABC-DEF_GHI... # <- Pegar aquí
TELEGRAM_PRODUCT_REQUESTS_CHAT_ID=5915021583
TELEGRAM_PRODUCT_REQUESTS_ENABLED=true

# === BOT 4: SYNC AMAZON-ML (Precio/Stock) ===
TELEGRAM_SYNC_BOT_TOKEN=9876543210:XYZ-UVW_RST... # <- Pegar aquí
TELEGRAM_SYNC_CHAT_ID=5915021583
TELEGRAM_SYNC_ENABLED=true
```

### Paso 4: Probar los Bots

#### Probar Bot 3 (Solicitudes):
```bash
cd /Users/felipemelucci/Desktop/revancha
./venv/bin/python3 scripts/tools/telegram_product_notifier.py
```

Deberías recibir un mensaje de prueba en Telegram.

#### Probar Bot 4 (Sync):
```bash
cd /Users/felipemelucci/Desktop/revancha
./venv/bin/python3 scripts/tools/telegram_sync_notifier.py
```

Deberías recibir un mensaje de prueba en Telegram.

### Paso 5: Desplegar al VPS

Una vez probado localmente:

```bash
cd /Users/felipemelucci/Desktop/revancha
./sync_with_vps.sh
```

Esto subirá automáticamente los nuevos archivos y el `.env` actualizado al VPS.

---

## 📊 Resumen de Archivos

| Bot | Archivo Notificador | Estado |
|-----|-------------------|--------|
| Ventas | `telegram_sales_notifier.py` | ✅ Funcionando |
| Publicaciones | `telegram_publishing_notifier.py` | ✅ Funcionando |
| Solicitudes | `telegram_product_notifier.py` | ⚠️ Pendiente configurar token |
| Sync | `telegram_sync_notifier.py` | ⚠️ Pendiente configurar token |

---

## 🔧 Servicios que Usan Cada Bot

### Bot de Ventas
- `scripts/tools/telegram_sales_notifier.py` (loop 24/7)

### Bot de Publicaciones
- `main2.py` (pipeline de publicación)
- `pipeline.py` (wrapper principal)

### Bot de Solicitudes
- `scripts/tools/auto_answer_questions.py` (loop 24/7)
- Sistema de búsqueda inteligente de productos

### Bot de Sync
- `scripts/tools/sync_amazon_ml.py` (cron cada 3 días)

---

## ❓ FAQ

**P: ¿Por qué usar bots separados?**
R: Para poder silenciar notificaciones específicas sin perder las importantes. Por ejemplo, el sync puede enviar 100+ mensajes, pero las ventas son críticas.

**P: ¿Puedo usar el mismo token para todos?**
R: Sí, técnicamente funciona, pero NO es recomendado porque no podrás separar las notificaciones.

**P: ¿Qué pasa si no configuro los bots pendientes?**
R: El sistema seguirá funcionando, simplemente no recibirás esas notificaciones. Los logs locales seguirán disponibles.

**P: ¿Cómo desactivo un bot temporalmente?**
R: Cambia `TELEGRAM_XXX_ENABLED=false` en el `.env` para ese bot específico.

---

## 📝 Próximos Pasos

1. ✅ Bot de ventas - Funcionando
2. ✅ Bot de publicaciones - Funcionando
3. ⚠️ **Bot de solicitudes - Crear en @BotFather y configurar**
4. ⚠️ **Bot de sync - Crear en @BotFather y configurar**
5. 🔄 Desplegar al VPS con `./sync_with_vps.sh`
