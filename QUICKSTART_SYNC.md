# 🚀 Guía Rápida - Sistema de Sincronización Amazon → MercadoLibre

## ¿Qué hace este sistema?

Monitorea automáticamente tus productos de Amazon cada 3 días y:

- ⏸️ **Pausa en ML** si el producto se descontinuó en Amazon
- 💰 **Actualiza precios** si el precio de Amazon cambió (proporcional con tu markup)
- 📊 **Registra todo** en logs detallados

## 🏃 Inicio Rápido (5 minutos)

### 1. Verifica que todo funcione

```bash
python3 test_sync.py
```

✅ Debe mostrar "TODOS LOS TESTS PASARON"

### 2. Agrega los Item IDs a la base de datos

**Opción A: Si ya publicaste en MercadoLibre**

```bash
# Modo interactivo (recomendado)
python3 add_item_id_manually.py --interactive

# O desde un archivo
python3 add_item_id_manually.py --file mis_items.txt
```

**Opción B: Si aún no publicaste**

Los item_ids se agregarán automáticamente cuando publiques usando tu pipeline normal.

### 3. Ejecuta la primera sincronización (manual)

```bash
python3 sync_amazon_ml.py
```

Verás algo como:

```
🔄 SINCRONIZACIÓN AMAZON → MERCADOLIBRE
📅 Fecha: 2025-01-02 09:00:00
💰 Markup configurado: 40%

✅ Encontrados 10 listings para sincronizar

[1/10] 🔄 Sincronizando: B0ABC123XYZ
   📡 Consultando Amazon...
   ✅ Producto disponible en Amazon
   💰 Precio Amazon: $25.00 USD
   💰 Precio ML calculado: $35.00 USD
   📊 Cambio de precio: 5.2%
   🔄 ACCIÓN: Actualizar precio en ML
   ✅ Precio actualizado exitosamente

...

📊 RESUMEN DE SINCRONIZACIÓN
Total procesados:     10
Publicaciones pausadas: 2
Precios actualizados:   3
Sin cambios:            4
Errores:                1
```

### 4. Instala el cron job (automático cada 3 días)

```bash
./setup_sync_cron.sh
```

## 📁 Archivos Importantes

| Archivo | Para qué sirve |
|---------|----------------|
| `sync_amazon_ml.py` | Script principal de sincronización |
| `test_sync.py` | Verifica que todo funcione |
| `add_item_id_manually.py` | Agrega item_ids a la BD |
| `setup_sync_cron.sh` | Instala el cron job |
| `logs/sync/` | Logs de cada sincronización |
| `storage/listings_database.db` | Base de datos local |

## 🔧 Configuración

### Cambiar el markup de precio

Edita `.env`:

```bash
PRICE_MARKUP_PERCENT=50  # 50% de ganancia sobre Amazon
```

### Cambiar frecuencia de sincronización

Edita el cron job:

```bash
crontab -e

# Cada día a las 9 AM
0 9 * * * cd /ruta/al/proyecto && ./venv/bin/python3 sync_amazon_ml.py

# Cada semana (lunes 9 AM)
0 9 * * 1 cd /ruta/al/proyecto && ./venv/bin/python3 sync_amazon_ml.py
```

## 📊 Ver Resultados

### Logs de texto

```bash
# Último log
tail -100 logs/sync/sync_cron.log

# Buscar errores
grep "❌" logs/sync/sync_cron.log
```

### Logs JSON (detallados)

```bash
# Listar todos los logs
ls -lht logs/sync/*.json

# Ver el más reciente
cat logs/sync/sync_$(date +%Y%m%d)*.json | jq .
```

## ❓ Preguntas Frecuentes

### ¿Cómo agrego nuevos productos al sistema?

1. Publica el producto en ML usando tu pipeline normal
2. Agrega el item_id a la BD:
   ```bash
   python3 add_item_id_manually.py MLM123456 B0ABC123XYZ
   ```

### ¿Qué pasa si Amazon baja el precio?

El sistema detectará el cambio y **bajará automáticamente** el precio en ML (manteniendo tu markup).

### ¿Qué pasa si Amazon sube el precio?

El sistema **subirá automáticamente** el precio en ML (manteniendo tu markup).

### ¿Puedo ejecutar la sincronización manualmente?

Sí, siempre:

```bash
python3 sync_amazon_ml.py
```

### ¿Cómo desinstalo el cron job?

```bash
crontab -l | grep -v sync_amazon_ml | crontab -
```

### ¿El sistema usa tokens de OpenAI?

**NO**. Este sistema solo usa las APIs de Amazon y MercadoLibre. No consume tokens de AI.

## 🚨 Solución de Problemas

### Error: "Faltan credenciales de Amazon"

```bash
# Verifica que .env tenga:
cat .env | grep -E "(LWA_CLIENT_ID|REFRESH_TOKEN)"
```

### Error: "Base de datos no encontrada"

```bash
# Inicializa la BD
python3 save_listing_data.py
```

### Token de ML expirado (401 Unauthorized)

```bash
# Renueva el token
python3 utils/auto_refresh_token.py
```

### Los precios no se actualizan

Verifica el umbral de cambio. Por defecto, solo actualiza si cambia más del 2%.

Edita `sync_amazon_ml.py` línea 423:

```python
PRICE_CHANGE_THRESHOLD = 2.0  # Cambia a 1.0 para ser más sensible
```

## 📚 Documentación Completa

Para más detalles, consulta:

- `docs/SYNC_AMAZON_ML_README.md` - Documentación completa
- `sync_amazon_ml.py` - Código fuente comentado

## 🆘 Soporte

1. Ejecuta `python3 test_sync.py` para diagnosticar
2. Revisa los logs en `logs/sync/`
3. Verifica las credenciales en `.env`

---

✅ **Sistema listo para usar**

El sistema ahora monitoreará tus productos automáticamente cada 3 días y mantendrá ML sincronizado con Amazon.
