# Sistema de Retención de Datos y Reportes Anuales

## 📋 Resumen

Este sistema mantiene **todos los datos históricos importantes** para generar reportes anuales completos del negocio, mientras limpia automáticamente los archivos temporales y técnicos que no son necesarios.

## 🗂️ Datos que se MANTIENEN (para reportes)

### 1. Logs de Sync (Histórico Completo)
- **Ubicación**: `logs/sync/sync_*.json` y `logs/sync/sync_*.json.gz`
- **Contenido**:
  - Productos publicados/actualizados
  - Cambios de precio (old → new)
  - Productos pausados y razón
  - Productos reactivados
  - Errores y problemas
- **Retención**: ♾️ PERMANENTE (comprimidos después de 30 días)
- **Uso**: Análisis de rendimiento, reportes anuales, auditorías

### 2. Base de Datos de Listings
- **Ubicación**: `storage/listings_database.db`
- **Contenido**:
  - Todos los productos publicados
  - Precios históricos
  - Categorías, marcas, atributos
  - Fechas de publicación y actualización
- **Retención**: ♾️ PERMANENTE
- **Backups**: 7 días (se rotan automáticamente)

### 3. Cache de Tokens
- **Ubicación**: `cache/amazon_token.json`
- **Contenido**: Token de autenticación Amazon (se auto-actualiza)
- **Retención**: Permanente (se sobrescribe)
- **Tamaño**: ~400 bytes

## 🧹 Datos que se LIMPIAN (logs técnicos)

### 1. Logs de Sync Técnicos
- `logs/sync/sync_cron.log`: Rotado cuando >10MB
- Backups comprimidos: Eliminados después de 60 días

### 2. Logs de DB Sync
- `logs/db_sync.log`: Truncado a últimas 500 líneas cuando >5MB

### 3. Backups de BD Antiguos
- `storage/listings_database.db.backup.*`: Eliminados después de 7 días

## ⏰ Programación Automática

### Diario
- **5:00 AM**: Sync de BD (local → VPS)
- **7:00 AM**: Sync Amazon→ML (actualización de precios)

### Semanal
- **Domingo 3:00 AM**: Limpieza automática de logs
  - Comprime logs >30 días
  - Rota logs grandes
  - Elimina backups antiguos
  - Envía notificación Telegram si libera >5MB

## 📊 Generación de Reportes Anuales

### Comando Manual
```bash
# Generar reporte del año actual
./venv/bin/python3 scripts/reports/generate_annual_report.py

# Generar reporte de un año específico
./venv/bin/python3 scripts/reports/generate_annual_report.py 2025
```

### Contenido del Reporte
El reporte anual (`reports/annual_report_YYYY.json`) incluye:

1. **Métricas de Sync**:
   - Total de syncs realizados
   - Total de actualizaciones de precio
   - Total de productos pausados/reactivados
   - Errores por tipo

2. **Estadísticas de Base de Datos**:
   - Total de productos activos
   - Productos por país
   - Top 10 categorías más vendidas
   - Rango de precios (min/max/promedio)

3. **Muestras de Datos**:
   - Primeros 100 cambios de precio
   - Primeros 50 productos pausados
   - Análisis de tendencias

## 💾 Estimación de Almacenamiento

### Con Compresión (logs >30 días)
```
Logs JSON recientes (30 días):    ~11 MB
Logs JSON comprimidos (335 días): ~67 MB (gzip reduce ~80%)
Base de datos:                     ~25 MB
Cache:                             <1 MB
───────────────────────────────────────
TOTAL ANUAL ESTIMADO:              ~104 MB
```

### Sin el Sistema de Limpieza
```
Logs sin comprimir (365 días):    ~135 MB
Logs técnicos acumulados:          ~50 MB
Backups de BD sin limpiar:         ~200 MB
───────────────────────────────────────
TOTAL SIN LIMPIEZA:                ~385 MB
```

**Ahorro de espacio**: ~281 MB/año (73%)

## 📈 Casos de Uso de los Reportes

### 1. Análisis de Fin de Año
```python
# Generar reporte completo 2025
./venv/bin/python3 scripts/reports/generate_annual_report.py 2025

# Analizar:
# - ¿Cuántos productos se publicaron?
# - ¿Cuántas veces cambiaron los precios?
# - ¿Qué categorías fueron más exitosas?
# - ¿Qué problemas fueron más frecuentes?
```

### 2. Auditoría de Precios
Los logs históricos permiten rastrear:
- Precio original de publicación
- Todos los cambios de precio
- Razón de cada cambio
- Impacto en disponibilidad

### 3. Análisis de Errores
Identificar patrones:
- Errores más frecuentes
- Productos problemáticos
- Mejoras necesarias en el sistema

### 4. Reportes para Impuestos
- Historial completo de productos vendidos
- Precios de compra (Amazon) vs venta (ML)
- Fechas exactas de operaciones

## 🔧 Mantenimiento

### Verificar Estado del Sistema
```bash
# Ver tamaño de directorios
du -sh cache/ storage/ logs/

# Ver últimos logs de limpieza
tail -100 logs/cleanup.log

# Ver logs comprimidos
ls -lh logs/sync/*.gz
```

### Generar Reporte Inmediato
```bash
# En local
./scripts/cleanup/cleanup_old_logs.sh

# En VPS (remoto)
ssh root@138.197.32.67 'cd /opt/amz-ml-system && ./scripts/cleanup/cleanup_old_logs.sh'
```

## 🚨 Recuperación de Datos

### Si necesitas datos antiguos
Todos los logs comprimidos se pueden descomprimir:

```bash
# Descomprimir un log específico
gunzip logs/sync/sync_20251015_120000.json.gz

# Descomprimir todos los logs de un mes
gunzip logs/sync/sync_202510*.json.gz

# Ver contenido sin descomprimir
zcat logs/sync/sync_20251015_120000.json.gz | jq '.'
```

## 📝 Notas Importantes

1. **Nunca se eliminan datos de negocio**: Solo logs técnicos temporales
2. **Compresión sin pérdida**: Los archivos .gz mantienen 100% de la información
3. **Reportes generables en cualquier momento**: Todos los años históricos disponibles
4. **Notificaciones Telegram**: Te avisa cuando se libera espacio significativo
5. **Backups automáticos**: La BD se respalda antes de cada sync

## 🎯 Próximos Pasos

Para generar tu primer reporte anual a fin de año:

```bash
# 31 de Diciembre 2025, 11:59 PM
./venv/bin/python3 scripts/reports/generate_annual_report.py 2025

# El reporte estará en:
reports/annual_report_2025.json
```

Luego puedes analizar los datos con Python, Excel, o cualquier herramienta de análisis de datos.
