# 📱 Sistema Completo de Notificaciones Telegram

## 🤖 Sistema de Doble Bot

Este sistema usa **2 bots separados** para diferentes tipos de notificaciones:

### 🤖 Bot 1 - Monitor de Ventas y Operaciones
**Notifica sobre**:
- 🎉 Nuevas ventas
- ❓ Preguntas respondidas automáticamente
- ❓ Preguntas sin responder (requieren atención manual)
- 💬 Mensajes de compradores
- ⏸️ Publicaciones pausadas por MercadoLibre
- 💰 Cambios de precio (Amazon → ML)
- 📦 Stock agotado en Amazon
- 🚨 Errores críticos del sistema

### 🤖 Bot 2 - Monitor de Publicaciones (main2)
**Notifica sobre**:
- 🚀 Inicio de batch de publicaciones
- 📦 Cada producto procesándose
- ✅ Descarga de Amazon completada
- 🔄 Transformación y categorización completada
- ✅ Publicación exitosa (con países)
- ❌ Errores en publicación
- 🏁 Resumen final del batch

---

## 🚀 Configuración Rápida (5 minutos)

### Método Simple: Setup Automático de Ambos Bots

```bash
./setup_telegram_dual.sh
```

Este script interactivo te guiará paso a paso para:
1. ✅ Crear **Bot 1** (Ventas y Operaciones) con @BotFather
2. ✅ Obtener token y chat_id automáticamente
3. ✅ Crear **Bot 2** (Publicaciones) con @BotFather
4. ✅ Obtener token y chat_id automáticamente
5. ✅ Guardar todo en `.env`
6. ✅ Enviar mensajes de prueba a ambos bots

**Tiempo estimado**: 5 minutos

---

### Método Manual (si preferís configurar paso a paso)

<details>
<summary>Click para expandir instrucciones manuales</summary>

#### Paso 1: Crear Bot 1 en Telegram

1. Abrí Telegram
2. Buscá: `@BotFather`
3. Enviá: `/newbot`
4. Seguí las instrucciones:
   - Nombre: `ML Monitor Ventas` (o el que quieras)
   - Username: `mi_ml_ventas_bot` (debe terminar en \_bot)
5. **Copiá el token** que te da Bot Father
6. Buscá tu bot y enviále: `Hola`

#### Paso 2: Crear Bot 2 en Telegram

1. En @BotFather, enviá: `/newbot` de nuevo
2. Seguí las instrucciones:
   - Nombre: `ML Monitor Publicaciones`
   - Username: `mi_ml_publishing_bot` (diferente al anterior)
3. **Copiá el token** que te da Bot Father
4. Buscá tu bot y enviále: `Hola`

#### Paso 3: Configurar en .env

Agregá a tu archivo `.env`:

```bash
# Bot 1 - Ventas y Operaciones
TELEGRAM_BOT_TOKEN=tu_token_bot1
TELEGRAM_CHAT_ID=tu_chat_id_bot1
TELEGRAM_NOTIFICATIONS_ENABLED=true

# Bot 2 - Publicaciones
TELEGRAM_PUBLISHING_BOT_TOKEN=tu_token_bot2
TELEGRAM_PUBLISHING_CHAT_ID=tu_chat_id_bot2
TELEGRAM_PUBLISHING_ENABLED=true
```

#### Paso 4: Verificar

Test Bot 1:
```bash
python3 scripts/tools/telegram_notifier.py
```

Test Bot 2:
```bash
python3 scripts/tools/telegram_publishing_notifier.py
```

</details>

---

## 📂 Estructura de Archivos

```
revancha/
├── setup_telegram_dual.sh             # Setup automático de AMBOS bots 🆕
├── monitor_loop.sh                    # Loop de monitoreo (Bot 1)
├── sync_loop.sh                       # Loop de sincronización (Bot 1)
├── main2.py                           # Publicación normal (sin notifs)
├── main2_with_notifications.py        # Publicación con notifs (Bot 2) 🆕
├── scripts/tools/
│   ├── telegram_notifier.py           # Bot 1 - Ventas/Ops
│   ├── telegram_publishing_notifier.py # Bot 2 - Publicaciones 🆕
│   ├── ml_monitor.py                  # Monitoreo de ML
│   ├── sync_amazon_ml.py              # Sync de precios (con notifs Bot 1)
│   └── auto_answer_questions.py       # Auto-respuestas (con notifs Bot 1)
└── storage/
    ├── ml_monitor_state.json          # Estado del monitoreo
    └── listings_database.db           # BD de productos publicados
```

---

## 🎯 Uso Diario

### Opción 1: Ejecutar Todo en Paralelo

Abrí **3 terminales** y ejecutá:

**Terminal 1 - Monitoreo (Bot 1: ventas, preguntas, mensajes)**
```bash
./monitor_loop.sh
```

**Terminal 2 - Sincronización de precios (Bot 1)**
```bash
./sync_loop.sh
```

**Terminal 3 - Publicación de productos**

**CON notificaciones (Bot 2):**
```bash
python3 main2_with_notifications.py
```

**SIN notificaciones (como siempre):**
```bash
python3 main2.py
```

### Opción 2: Ejecutar en Background

```bash
# Monitoreo
nohup ./monitor_loop.sh > logs/monitor.log 2>&1 &

# Sync
nohup ./sync_loop.sh > logs/sync.log 2>&1 &
```

Para detener:
```bash
# Ver procesos
ps aux | grep loop

# Matar procesos
pkill -f monitor_loop
pkill -f sync_loop
```

---

---

## 🔔 Tipos de Mensajes que Recibirás

### 🤖 Bot 1 - Ventas y Operaciones

#### 🎉 Venta Nueva
```
🎉 ¡NUEVA VENTA!

💰 Total: $125.99
👤 Comprador: juan_perez
🆔 Orden: 1234567890

📦 Productos:
  • Nike Backpack (x1)

🕐 2025-01-08 15:30:45
```

#### ❓ Pregunta Respondida
```
💬 Pregunta Respondida

❓ Pregunta: ¿Cuándo llega?
✅ Respuesta: El envío demora 3-5 días...
🆔 Item: MLM2550401031

🕐 2025-01-08 15:32:12
```

#### ❓ Pregunta Sin Responder
```
❓ Nueva Pregunta Sin Responder

💬 Pregunta: ¿Acepta efectivo?
🆔 Item: MLM2550401031
🆔 Pregunta ID: 12345

⚠️ Requiere respuesta manual
🕐 2025-01-08 15:35:20
```

#### 📈 Precio Actualizado
```
📈 Precio Actualizado

📦 ASIN: B0CGX3KN95
💵 Precio anterior: $40.49
💵 Precio nuevo: $45.00
📊 Cambio: +11.1%
🌍 Países: MLM, MLB, MLC, MCO, MLA
🕐 2025-01-08 16:00:00
```

#### ⏸️ Publicación Pausada
```
⏸️ Publicaciones Pausadas

⚠️ 3 publicaciones están pausadas

Verifica en MercadoLibre la razón.
🕐 2025-01-08 16:05:00
```

#### 🚨 Error Crítico
```
🚨 ERROR CRÍTICO

⚠️ Tipo: Sincronización
❌ Error: Token expirado

🕐 2025-01-08 16:10:00

Requiere atención inmediata
```

---

### 🤖 Bot 2 - Publicaciones (Ultra Breve)

#### 🚀 Inicio de Batch
```
🚀 Iniciando batch: 15 productos
```

#### 📦 Procesando Producto (silencioso)
```
📦 [1/15] B0CGX3KN95
📦 [2/15] B013TGEJEE
📦 [3/15] B0DRW8G3WK
```

#### ✅ Publicación Exitosa
```
✅ B0CGX3KN95 → 5/5 países
```

#### ⚠️ Publicación Parcial
```
⚠️ B0DRW8G3WK → 4/5 países
```

#### ❌ Error en Publicación
```
❌ B0INVALID → Category validation failed
```

#### 🏁 Resumen Final
```
🏁 Completado: 13/15 OK (87%) en 45min
```

---

## ⚙️ Personalización

### Cambiar Intervalo de Monitoreo

Edita `monitor_loop.sh` línea 13:
```bash
CHECK_INTERVAL_MINUTES=5  # Cambiar a 10, 15, etc.
```

### Cambiar Intervalo de Sync

Edita `sync_loop.sh` línea 12:
```bash
SYNC_INTERVAL_HOURS=24  # Cambiar a 12, 48, etc.
```

### Desactivar Notificaciones Temporalmente

En `.env`:
```bash
TELEGRAM_NOTIFICATIONS_ENABLED=false
```

### Activar de Nuevo

En `.env`:
```bash
TELEGRAM_NOTIFICATIONS_ENABLED=true
```

---

## 🧪 Pruebas

### Test Bot 1 (Ventas y Operaciones)
```bash
python3 scripts/tools/telegram_notifier.py
```

### Test Bot 2 (Publicaciones)
```bash
python3 scripts/tools/telegram_publishing_notifier.py
```

### Test de Monitoreo (sin loop)
```bash
./venv/bin/python3 scripts/tools/ml_monitor.py 0
```

### Ver Estado del Monitoreo
```bash
cat storage/ml_monitor_state.json
```

---

## ❓ Troubleshooting

### No recibo notificaciones

1. Verificá que tenés `TELEGRAM_NOTIFICATIONS_ENABLED=true` en `.env`
2. Ejecutá el test: `python3 scripts/tools/telegram_notifier.py`
3. Verificá que el bot no esté bloqueado en Telegram
4. Verificá que enviaste un mensaje al bot primero

### "Bot not found"

→ Asegurate de haber usado el username correcto (debe terminar en `_bot`)

### "Unauthorized"

→ El token es incorrecto. Ejecutá `./setup_telegram.sh` de nuevo con el token correcto.

### "Chat not found"

→ No enviaste un mensaje al bot primero. Enviá un mensaje y ejecutá `./setup_telegram.sh` de nuevo.

---

## 🎯 Resumen

**Bot 1 - Ventas y Operaciones:**
- ✅ Ventas
- ✅ Preguntas (respondidas y sin responder)
- ✅ Mensajes de compradores
- ✅ Publicaciones pausadas
- ✅ Cambios de precio
- ✅ Stock agotado
- ✅ Errores del sistema

**Bot 2 - Publicaciones (main2):**
- 🚀 Inicio de batch
- 📦 Progress por producto
- ✅ Publicaciones exitosas
- ❌ Errores
- 🏁 Resumen final

**Todo automático, sin intervención manual.**

---

**🚀 ¡Tu sistema de notificaciones está listo!**

Para configurar AMBOS bots, ejecutá:
```bash
./setup_telegram_dual.sh
```
