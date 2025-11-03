# ✅ Sistema de Sincronización Automática - COMPLETO

## 🎯 ¿Qué hace?

Este sistema mantiene automáticamente sincronizados tus productos de MercadoLibre con Amazon:

- 🔄 **Sincroniza precios**: Si Amazon cambia el precio, ML se actualiza automáticamente (con tu markup)
- ⏸️ **Pausa productos descontinuados**: Si Amazon ya no tiene stock, se pausa en ML
- 🤖 **100% automático**: Una vez configurado, no necesitas hacer nada

## ✅ Estado Actual: LISTO PARA USAR

```
✅ Sistema de sincronización creado
✅ Base de datos configurada
✅ Integración con pipeline de publicación completada
✅ Scripts de prueba y configuración listos
✅ Documentación completa
```

## 🚀 Cómo Funciona (Automático)

### Cuando publiques un nuevo producto:

```bash
python3 src/mainglobal.py
```

**El sistema automáticamente:**
1. Publica el producto en MercadoLibre ✅
2. Obtiene el Item ID de ML ✅
3. Guarda en la base de datos: ASIN → Item ID + precio ✅
4. Ya está listo para sincronización ✅

### Cada 3 días (automático con cron):

```
El sistema sincronizará automáticamente:
├── Consulta Amazon por cada ASIN
├── Detecta cambios de precio
├── Detecta productos descontinuados
└── Actualiza MercadoLibre automáticamente
```

## 📋 Configuración Inicial (Una Sola Vez)

### 1. Instala el cron job

```bash
./setup_sync_cron.sh
```

Esto configura el sistema para que se ejecute cada 3 días a las 9 AM.

### 2. (Opcional) Si ya tienes productos publicados

Si ya publicaste productos ANTES de instalar este sistema, agrega los item_ids manualmente:

```bash
# Modo interactivo (recomendado)
python3 add_item_id_manually.py --interactive

# O uno por uno
python3 add_item_id_manually.py MLM123456 B0ABC123XYZ
```

## 🎮 Comandos Útiles

### Ver estado del sistema

```bash
python3 test_auto_sync.py
```

### Sincronizar manualmente (sin esperar 3 días)

```bash
python3 sync_amazon_ml.py
```

### Ver logs

```bash
# Último log
tail -100 logs/sync/sync_cron.log

# Ver estadísticas
cat logs/sync/sync_*.json | jq .statistics
```

### Verificar productos en la BD

```bash
sqlite3 storage/listings_database.db "SELECT asin, item_id, price_usd FROM listings;"
```

### Desinstalar cron job

```bash
crontab -l | grep -v sync_amazon_ml | crontab -
```

## 📊 Ejemplo Real

### Publicas un producto

```bash
$ python3 src/mainglobal.py

🚀 Publicando item desde mini_ml ...
✅ Publicado → MLM1234567890
💾 Guardado en BD para sincronización: B0ABC123XYZ → MLM1234567890
```

### 3 días después (automático)

```
🔄 SINCRONIZACIÓN AMAZON → MERCADOLIBRE
📅 Fecha: 2025-01-05 09:00:00

[1/10] 🔄 Sincronizando: B0ABC123XYZ
   📡 Consultando Amazon...
   ✅ Producto disponible en Amazon
   💰 Precio Amazon: $30.00 USD (antes: $25.00)
   💰 Precio ML calculado: $42.00 USD
   📊 Cambio de precio: 20.0%
   🔄 ACCIÓN: Actualizar precio en ML
   ✅ Precio actualizado exitosamente

📊 RESUMEN
Precios actualizados: 3
Publicaciones pausadas: 1
Sin cambios: 6
```

## ⚙️ Configuración Avanzada

### Cambiar markup de precio

Edita `.env`:

```bash
PRICE_MARKUP_PERCENT=50  # 50% de ganancia sobre Amazon
```

### Cambiar frecuencia de sincronización

Edita el cron job:

```bash
crontab -e

# Cada día a las 9 AM
0 9 * * * cd /ruta/proyecto && ./venv/bin/python3 sync_amazon_ml.py

# Cada 2 días a las 9 AM
0 9 */2 * * cd /ruta/proyecto && ./venv/bin/python3 sync_amazon_ml.py
```

### Cambiar umbral de cambio de precio

Por defecto, solo actualiza si el cambio es > 2%. Para cambiar esto, edita `sync_amazon_ml.py` línea 423:

```python
PRICE_CHANGE_THRESHOLD = 1.0  # Más sensible (1%)
```

## 📁 Archivos del Sistema

```
revancha/
├── sync_amazon_ml.py              # Script principal de sincronización
├── test_auto_sync.py              # Test de integración
├── test_sync.py                   # Test de componentes
├── add_item_id_manually.py        # Agregar item_ids manualmente
├── setup_sync_cron.sh             # Instalador de cron job
├── src/
│   └── mainglobal.py              # 🆕 Modificado: guarda item_ids automáticamente
├── storage/
│   └── listings_database.db       # Base de datos SQLite
└── logs/
    └── sync/
        ├── sync_cron.log          # Logs en texto
        └── sync_*.json            # Logs detallados JSON
```

## 🎯 Resumen Ejecutivo

### ¿Qué tienes que hacer?

**NADA (después de la configuración inicial)**

### Configuración inicial (5 minutos):

1. ✅ Ya está todo instalado
2. Ejecuta: `./setup_sync_cron.sh` (una sola vez)
3. Publica productos normalmente: `python3 src/mainglobal.py`

### A partir de ahí:

- 🤖 Cada producto nuevo se guarda automáticamente
- 🔄 Cada 3 días se sincroniza con Amazon
- 💰 Los precios se actualizan solos
- ⏸️ Los productos descontinuados se pausan solos

## 📚 Documentación

- **Guía rápida**: `QUICKSTART_SYNC.md`
- **Documentación completa**: `docs/SYNC_AMAZON_ML_README.md`
- **Tests**: `python3 test_auto_sync.py`

## ✅ Checklist Final

- [x] Sistema de sincronización creado
- [x] Integración con pipeline de publicación
- [x] Base de datos configurada
- [x] Scripts de prueba funcionando
- [x] Documentación completa
- [ ] **Instalar cron job** (ejecuta `./setup_sync_cron.sh`)
- [ ] Publicar primer producto y verificar que se guarda en BD

## 🎉 Resultado Final

Una vez instalado el cron job:

```
TÚ PUBLICAS → Sistema guarda automáticamente → Cada 3 días sincroniza → ✅ LISTO
```

**¡Todo automático, cero intervención manual!**
