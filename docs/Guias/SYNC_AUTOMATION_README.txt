# 🔄 Sistema de Sincronización Automática Amazon → MercadoLibre

Sistema que monitorea continuamente tus productos en Amazon y sincroniza automáticamente con MercadoLibre.

## 🎯 ¿Qué hace?

### Monitoreo Automático
- ✅ **Detecta cambios de precio en Amazon** → Actualiza precio en MercadoLibre proporcionalmente
- ✅ **Detecta productos sin stock en Amazon** → Pausa en ML (pone stock en 0)
- ✅ **Detecta productos disponibles de nuevo** → Reactiva en ML (pone stock en 10)
- ✅ **Actualiza la base de datos** automáticamente con cada cambio

### Beneficios
- 🤖 **100% Automático** - no requiere intervención manual
- 💰 **Mantiene precios sincronizados** - si Amazon sube/baja precio, ML se actualiza
- 📦 **Evita ventas de productos sin stock** - pausa automáticamente productos no disponibles
- ♻️ **Reactiva productos automáticamente** - cuando vuelven a estar disponibles en Amazon
- 📊 **Base de datos siempre actualizada** - refleja el estado real de ML

---

## 🚀 Inicio Rápido

### Opción 1: Loop Continuo (Cada 6 horas)
```bash
# Iniciar sincronización continua en background
cd /Users/felipemelucci/Desktop/revancha
nohup ./scripts/tools/sync_amazon_ml_loop.sh > /dev/null 2>&1 &

# Ver el log en tiempo real
tail -f logs/sync_amazon_ml_loop.log
```

### Opción 2: Ejecución Manual (On-demand)
```bash
# Ejecutar sincronización una sola vez
./venv/bin/python3 scripts/tools/sync_amazon_ml.py
```

### Opción 3: Cron Job (Ejecutar automáticamente)
```bash
# Editar crontab
crontab -e

# Agregar esta línea para ejecutar cada 6 horas:
0 */6 * * * cd /Users/felipemelucci/Desktop/revancha && ./venv/bin/python3 scripts/tools/sync_amazon_ml.py >> logs/sync_amazon_ml.log 2>&1

# O cada 12 horas:
0 */12 * * * cd /Users/felipemelucci/Desktop/revancha && ./venv/bin/python3 scripts/tools/sync_amazon_ml.py >> logs/sync_amazon_ml.log 2>&1

# O una vez al día (9am):
0 9 * * * cd /Users/felipemelucci/Desktop/revancha && ./venv/bin/python3 scripts/tools/sync_amazon_ml.py >> logs/sync_amazon_ml.log 2>&1
```

---

## 📋 Gestión del Loop

### Ver si está corriendo
```bash
ps aux | grep sync_amazon_ml_loop.sh
```

### Detener el loop
```bash
# Encontrar el PID
ps aux | grep sync_amazon_ml_loop.sh

# Matar el proceso (reemplaza PID con el número)
kill <PID>

# O detener todos los loops de sync
pkill -f sync_amazon_ml_loop.sh
```

### Ver logs en tiempo real
```bash
# Log del loop
tail -f logs/sync_amazon_ml_loop.log

# Log del script de sync
tail -f logs/sync_amazon_ml.log

# Ver últimas 100 líneas
tail -100 logs/sync_amazon_ml_loop.log
```

---

## 🔍 Monitoreo

### Verificar última ejecución
```bash
# Ver últimas líneas del log
tail -50 logs/sync_amazon_ml_loop.log
```

### Ver cambios realizados
```bash
# Cambios de precio
grep "💰.*Actualizado" logs/sync_amazon_ml.log

# Productos pausados
grep "⏸️.*pausado" logs/sync_amazon_ml.log

# Productos reactivados
grep "♻️.*reactivado" logs/sync_amazon_ml.log
```

### Verificar estado en BD
```bash
# Ver productos con stock = 0 (pausados)
sqlite3 storage/listings_database.db "SELECT asin, item_id, stock FROM listings WHERE stock = 0;"

# Ver productos activos
sqlite3 storage/listings_database.db "SELECT asin, item_id, price_usd, stock FROM listings WHERE stock > 0;"
```

---

## ⚙️ Configuración

### Frecuencia de ejecución
Edita el script `sync_amazon_ml_loop.sh` línea 12:
```bash
# Cada 6 horas (recomendado)
SYNC_INTERVAL=$((6 * 60 * 60))

# Cada 12 horas
SYNC_INTERVAL=$((12 * 60 * 60))

# Cada 24 horas
SYNC_INTERVAL=$((24 * 60 * 60))

# Cada 3 días
SYNC_INTERVAL=$((72 * 60 * 60))
```

### Markup de precios
Edita `.env`:
```bash
PRICE_MARKUP_PERCENT=40   # 40% de ganancia sobre precio Amazon
```

### Notificaciones Telegram
El sistema ya está configurado para enviar notificaciones automáticas cuando:
- 💰 Se actualiza un precio
- ⏸️ Se pausa un producto (sin stock)
- ♻️ Se reactiva un producto (vuelve a tener stock)

---

## 📊 Ejemplos de Uso

### Escenario 1: Precio de Amazon sube $5
```
Amazon: $50 → $55
MercadoLibre: Se actualiza automáticamente a $77 (55 × 1.40)
BD: precio_usd actualizado a 77
```

### Escenario 2: Producto se queda sin stock en Amazon
```
Estado en Amazon: "Currently unavailable"
MercadoLibre: Stock → 0 (sin disponibilidad)
BD: stock actualizado a 0
Telegram: Notificación enviada
```

### Escenario 3: Producto vuelve a estar disponible
```
Estado en Amazon: "In Stock"
MercadoLibre: Stock → 10 (disponible)
BD: stock actualizado a 10
Telegram: Notificación de reactivación
```

---

## 🛠️ Troubleshooting

### El loop no inicia
```bash
# Verificar permisos
chmod +x scripts/tools/sync_amazon_ml_loop.sh

# Verificar que existe venv
ls -la venv/bin/python3
```

### Token expirado (401 Unauthorized)
```bash
# Renovar token de ML
./venv/bin/python3 /tmp/refresh_ml_token.py

# Copiar los nuevos tokens al .env
```

### No se actualizan precios
```bash
# Verificar credenciales de Amazon en .env
grep "LWA_CLIENT_ID" .env
grep "REFRESH_TOKEN" .env

# Verificar que sync_amazon_ml.py funciona manualmente
./venv/bin/python3 scripts/tools/sync_amazon_ml.py
```

### BD no se actualiza
```bash
# Verificar que existe la columna 'stock'
sqlite3 storage/listings_database.db "PRAGMA table_info(listings);"

# Si no existe, se creará automáticamente en la próxima ejecución
```

---

## 📁 Archivos Importantes

| Archivo | Descripción |
|---------|-------------|
| `scripts/tools/sync_amazon_ml.py` | Script principal de sincronización |
| `scripts/tools/sync_amazon_ml_loop.sh` | Loop automático (cada 6 horas) |
| `logs/sync_amazon_ml_loop.log` | Log del loop |
| `logs/sync_amazon_ml.log` | Log detallado de cada sync |
| `storage/listings_database.db` | Base de datos con todos los productos |
| `.env` | Credenciales y configuración |

---

## 🎯 Recomendaciones

### Frecuencia ideal
- **Cada 6 horas**: Balance ideal entre actualización frecuente y ahorro de API calls
- **Cada 12 horas**: Buena opción si tienes pocos cambios de precio
- **Cada 24 horas**: Mínimo recomendado para mantener sincronización

### Monitoreo
- Revisa los logs una vez al día para verificar que todo funciona
- Configura notificaciones Telegram para recibir alertas automáticas
- Verifica la BD semanalmente para confirmar consistencia

### Mantenimiento
- Renueva el token de ML cada 6 meses (el sistema te avisará si expira)
- Verifica que el cron job/loop esté corriendo después de reiniciar el servidor
- Mantén backups de la BD (`storage/listings_database.db`)

---

## ✅ Sistema Listo Para Producción

El sistema está completamente funcional y probado:

✅ Actualización automática de precios
✅ Gestión automática de stock (pause/reactivate)
✅ Base de datos auto-sincronizada
✅ Notificaciones Telegram configuradas
✅ Logs detallados para debugging
✅ Manejo de errores y reintentos

**¡Solo necesitas iniciar el loop y dejar que funcione automáticamente!**
