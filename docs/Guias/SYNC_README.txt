# 🔄 Sistema de Sincronización Amazon → MercadoLibre

Sistema automático que mantiene tus publicaciones de MercadoLibre sincronizadas con el inventario y precios de Amazon.

---

## 📋 ¿Qué hace?

El sistema de sincronización monitorea automáticamente tus productos en Amazon y actualiza MercadoLibre en tiempo real:

### 1. **Actualización de Precios** 💰
- Detecta cambios de precio en Amazon
- Aplica tu markup configurado (ej: 30%)
- Actualiza automáticamente en MercadoLibre
- Solo actualiza si el cambio es > 2% (evita fluctuaciones menores)

### 2. **Gestión de Inventario** 📦
- **Cuando producto se agota en Amazon:**
  - Pone stock en 0 en MercadoLibre
  - Producto aparece como "sin stock" (no se puede comprar)
  - Evita ventas de productos no disponibles

- **Cuando producto vuelve a estar disponible:**
  - Detecta automáticamente el cambio
  - Reactiva el producto (stock: 10)
  - Vuelve a estar disponible para la venta

### 3. **Notificaciones por Telegram** 📱
- Cambios de precio
- Productos sin stock
- Productos reactivados
- Errores de sincronización

---

## 🚀 Uso

### Ejecución Manual

```bash
python3 scripts/tools/sync_amazon_ml.py
```

### Ejecución Automática (Recomendado)

Configurá un cron job para ejecutar cada hora:

```bash
# Editar crontab
crontab -e

# Agregar esta línea (ejecuta cada hora)
0 * * * * cd /Users/felipemelucci/Desktop/revancha && ./venv/bin/python3 scripts/tools/sync_amazon_ml.py >> logs/sync_amazon_ml.log 2>&1
```

---

## ⚙️ Configuración

### 1. Variables de Entorno (.env)

```bash
# Amazon SP-API
LWA_APP_ID=amzn1.application-oa2-client.xxxxx
LWA_CLIENT_SECRET=xxxxx
REFRESH_TOKEN=Atzr|xxxxx
AWS_ACCESS_KEY=xxxxx
AWS_SECRET_KEY=xxxxx
ROLE_ARN=arn:aws:iam::xxxxx

# MercadoLibre
ML_ACCESS_TOKEN=APP_USR-xxxxx

# Configuración de precios
PRICE_MARKUP_PERCENT=30  # Markup del 30% sobre precio Amazon

# Telegram (opcional)
TELEGRAM_BOT_TOKEN=xxxxx
TELEGRAM_CHAT_ID=xxxxx
```

### 2. Base de Datos

El sistema requiere que los productos publicados estén en la base de datos:

```bash
# Guardar productos publicados en BD
python3 scripts/tools/save_listing_data.py

# Vincular item_ids de ML a la BD (una sola vez)
python3 scripts/tools/link_ml_items_to_db.py
```

---

## 📊 Ejemplo de Funcionamiento

### Escenario 1: Cambio de Precio

```
Amazon: $99.99 → $89.99
ML antes: $129.99
ML después: $116.99 (con 30% markup)
Notificación: "💰 Precio actualizado"
```

### Escenario 2: Producto Sin Stock

```
Amazon: Out of Stock
ML antes: Stock 10
ML después: Stock 0 (sin disponibilidad)
Notificación: "⏸️ Publicación Sin Stock"
```

### Escenario 3: Producto Reactivado

```
Amazon: Vuelve a estar disponible
ML antes: Stock 0
ML después: Stock 10
Notificación: "♻️ Publicación Reactivada"
```

---

## 📝 Logs

Los logs se guardan en:

```
logs/sync_amazon_ml.log       # Log principal
logs/sync_changes.json         # Registro de cambios en JSON
```

### Ver últimos cambios:

```bash
tail -100 logs/sync_amazon_ml.log
```

### Ver solo productos actualizados:

```bash
grep "Precio actualizado" logs/sync_amazon_ml.log
```

---

## 🔧 Funciones Principales

### `sync_amazon_ml.py`

| Función | Descripción |
|---------|-------------|
| `check_amazon_product_status()` | Consulta estado y precio en Amazon |
| `pause_ml_listing()` | Pone stock en 0 cuando no hay disponibilidad |
| `reactivate_ml_listing()` | Reactiva producto poniendo stock en 10 |
| `update_ml_price()` | Actualiza precio en ML con markup |
| `sync_one_listing()` | Sincroniza un producto completo |

---

## 📱 Notificaciones por Telegram

### Tipos de Notificaciones

1. **Cambio de Precio**
   ```
   💰 Precio Actualizado
   📦 ASIN: B001234567
   💵 Antes: $129.99
   💵 Ahora: $116.99
   🌍 Países: MCO, MLC, MLA, MLB
   ```

2. **Producto Sin Stock**
   ```
   ⏸️ Publicación Sin Stock
   📦 ASIN: B001234567
   📦 Stock: 0 (sin disponibilidad)
   ⚠️ Razón: Sin ofertas disponibles
   ```

3. **Producto Reactivado**
   ```
   ♻️ Publicación Reactivada
   📦 ASIN: B001234567
   📦 Stock: 10 (disponible nuevamente)
   ✅ Producto disponible en Amazon
   ```

### Configurar Telegram

Ver `docs/telegram/TELEGRAM_SETUP.md` para instrucciones detalladas.

---

## 🎯 Casos de Uso

### 1. Dropshipping desde Amazon
- Mantener precios competitivos automáticamente
- Evitar ventas cuando Amazon no tiene stock
- Reactivar productos cuando vuelven a estar disponibles

### 2. Sincronización Multi-País (CBT)
- Un solo comando sincroniza todos los países
- México, Colombia, Chile, Argentina, Brasil

### 3. Monitoreo 24/7
- Cron job ejecuta cada hora
- No necesitás estar pendiente
- Notificaciones instantáneas por Telegram

---

## ⚠️ Consideraciones Importantes

### Gestión de Stock para Productos CBT

**Importante:** Para productos CBT (Cross-Border Trading), MercadoLibre NO permite pausar/ocultar productos mediante API. La única forma de gestionar disponibilidad es:

- ✅ **Stock = 0**: Producto visible pero no se puede comprar
- ❌ **Status "paused"**: No oculta el producto del sitio web

Por eso el sistema usa `available_quantity: 0` en lugar de cambiar el status.

### Límites de Rate

- Amazon SP-API: Respeta los rate limits automáticamente
- MercadoLibre: Máximo 1000 requests/hora

### Precio Mínimo

El sistema solo actualiza si hay un cambio > 2% para evitar fluctuaciones menores y ahorrar API calls.

---

## 🐛 Troubleshooting

### Error: "Token expired"
```bash
# Refrescar token de ML
# Ver SETUP.md para regenerar access_token
```

### Error: "Item not found in database"
```bash
# Ejecutar primero
python3 scripts/tools/link_ml_items_to_db.py
```

### Productos no se sincronizan
```bash
# Verificar logs
tail -50 logs/sync_amazon_ml.log

# Verificar BD
sqlite3 storage/listings_database.db "SELECT COUNT(*) FROM listings WHERE item_id IS NOT NULL;"
```

---

## 📚 Documentación Relacionada

- `README.md` - Configuración general del proyecto
- `docs/telegram/TELEGRAM_SETUP.md` - Setup de notificaciones
- `MIGRATION_VPS.md` - Migración a servidor

---

## 🎉 ¡Listo!

Tu sistema de sincronización está configurado. Los productos se mantendrán actualizados automáticamente con Amazon, sin intervención manual.

**Próximos pasos recomendados:**
1. ✅ Configurar cron job para ejecución automática
2. ✅ Configurar Telegram para notificaciones
3. ✅ Monitorear logs la primera semana
4. ✅ Migrar a VPS para 24/7 uptime
