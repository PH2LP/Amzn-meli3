# 💰 Sistema de Precios Dinámicos para Catálogo

Sistema automático para ajustar precios de productos de catálogo en MercadoLibre, manteniendo competitividad sin sacrificar rentabilidad.

## 🎯 Objetivo

En productos de catálogo, **ganar con el precio** es clave para aparecer en el buybox. Este sistema:

1. **Detecta productos de catálogo** automáticamente
2. **Compite con el precio más bajo** del mercado
3. **Respeta un margen mínimo del 25%** para no perder dinero
4. **Permite reversión fácil** a precios originales

---

## 📊 Cálculo de Precios

### Fórmulas Base

```
Costo Real = Precio Amazon × 1.07  (tax Florida 7%)
Precio Original = Costo Real × 1.45  (margen 45% del .env)
Precio Mínimo = Costo Real × 1.25  (margen 25% no negociable)
```

### Lógica de Ajuste

```
Si es_catalogo:
    obtener buybox_price de ML

    Si buybox_price < precio_minimo:
        → Mantener precio_original (no compito, perdería plata)

    Si buybox_price >= precio_minimo:
        → Bajar a (buybox_price - 1 USD)
```

---

## 🗄️ Base de Datos

### Nuevas Columnas en `listings`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `costo_amazon` | REAL | Precio base de Amazon |
| `tax_florida` | REAL | Tax aplicado (7%) |
| `precio_original` | REAL | Precio inicial con margen 45% |
| `precio_actual` | REAL | Precio activo en ML |
| `es_catalogo` | INTEGER | 1 si es catálogo, 0 si no |
| `ultima_actualizacion_precio` | TIMESTAMP | Última vez que se ajustó |

---

## 🛠️ Scripts Disponibles

### 1. **Monitor Automático de Catálogo (RECOMENDADO)**

Script todo-en-uno que detecta productos de catálogo y ajusta precios automáticamente.

```bash
# Ejecutar una vez
python3 scripts/tools/catalog_price_monitor.py

# Loop automático cada 6 horas (RECOMENDADO)
python3 scripts/tools/catalog_price_monitor.py --loop
```

**Qué hace:**
- Detecta cuando productos pasan a catálogo automáticamente
- Ajusta precios respetando margen mínimo 25%
- Notifica cambios por Telegram (si está configurado)
- Se ejecuta cada 6 horas sin intervención

**Notificaciones Telegram:**
- 🏷️ Cuando un producto pasa a catálogo
- 💰 Cuando ajusta un precio
- 📊 Resumen de cada ejecución

---

### 2. **Ajustar Precios de Catálogo (Manual)**

Revisa productos de catálogo y ajusta precios competitivamente.

```bash
# Ajustar todos los productos de catálogo
python3 scripts/tools/adjust_catalog_prices.py

# Ajustar solo un ASIN específico
python3 scripts/tools/adjust_catalog_prices.py --asin B0CYM126TT

# Simular sin actualizar (dry-run)
python3 scripts/tools/adjust_catalog_prices.py --dry-run
```

**Qué hace:**
- Obtiene el buybox price de ML
- Calcula si puede competir con margen 20%
- Ajusta precio en ML si es rentable
- Guarda histórico en DB

**Output esperado:**
```
🔍 Procesando 5 producto(s) de catálogo...
   Margen mínimo: 25%
   Margen objetivo: 45%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 ASIN: B0CYM126TT
   Item ID: MLM123456789
   💰 Costo real (+ tax): $53.50
   📊 Precio original (45%): $77.58
   🚨 Precio mínimo (25%): $66.88
   🏆 Buybox actual: $70.00
   💡 Decisión: $69.00
      Razón: Precio competitivo manteniendo margen
   ✅ Precio actualizado en ML y DB
```

---

### 3. **Verificar Productos de Catálogo**

Revisa cuáles de tus productos publicados son de catálogo.

```bash
python3 scripts/tools/check_catalog_items.py
```

**Qué hace:**
- Consulta ML para cada producto publicado
- Verifica si está asociado a catálogo
- Actualiza `es_catalogo` en la DB
- Muestra el catalog_id y precio actual

---

### 4. **Restaurar Precios Originales**

Vuelve todos los precios a su valor inicial.

```bash
# Restaurar todos los productos
python3 scripts/tools/restore_original_prices.py

# Restaurar solo un ASIN
python3 scripts/tools/restore_original_prices.py --asin B0CYM126TT

# Simular (dry-run)
python3 scripts/tools/restore_original_prices.py --dry-run
```

**Qué hace:**
- Lee `precio_original` de la DB
- Actualiza en ML
- Sincroniza `precio_actual` en DB

**Útil para:**
- Revertir experimentos de precios
- Volver a margen estándar después de promociones
- Resetear precios antes de recalcular

---

## 🔄 Flujo de Trabajo Típico

### Escenario 1: Monitoreo Automático (RECOMENDADO)

```bash
# Iniciar monitor en background
nohup python3 scripts/tools/catalog_price_monitor.py --loop > logs/catalog_monitor.log 2>&1 &

# Ver el log en tiempo real
tail -f logs/catalog_monitor.log
```

**Qué hace:**
- Detecta automáticamente cuando productos pasan a catálogo
- Ajusta precios cada 6 horas
- Notifica por Telegram
- Corre en background sin intervención

### Escenario 2: Ajuste Puntual

```bash
# Ver qué pasaría (dry-run)
python3 scripts/tools/adjust_catalog_prices.py --dry-run

# Si te gusta el resultado, ejecutar de verdad
python3 scripts/tools/adjust_catalog_prices.py
```

### Escenario 3: Promoción Temporal

```bash
# Día 1: Bajar precios para competir
python3 scripts/tools/adjust_catalog_prices.py

# Día 7: Volver a precios normales
python3 scripts/tools/restore_original_prices.py
```

### Escenario 4: Revisar Estado Actual

```bash
# Ver productos de catálogo
python3 scripts/tools/check_catalog_items.py

# Ejecutar monitor una vez
python3 scripts/tools/catalog_price_monitor.py
```

---

## ⚙️ Configuración

### Variables de Entorno (.env)

```bash
PRICE_MARKUP=45          # Margen inicial (45%)
ML_ACCESS_TOKEN=...      # Token de MercadoLibre
```

### Constantes en Scripts

En `adjust_catalog_prices.py`:

```python
TAX_FLORIDA = 0.07       # 7% tax
MARGEN_MINIMO = 0.25     # 25% margen mínimo
```

---

## 🚨 Consideraciones Importantes

### Limitaciones de MercadoLibre

- **Límite de actualizaciones**: ML restringe cambios frecuentes de precio
- **Penalizaciones**: Cambiar precios cada 5 minutos puede penalizar tu listing
- **Recomendación**: Ajustar máximo cada 6-12 horas

### Cálculo de Costos

- **Envío**: Ya incluido (usas Amazon Prime)
- **Tax Florida**: 7% fijo
- **Comisiones ML**: No incluidas en el cálculo (ajustar `MARGEN_MINIMO` si es necesario)

### Casos Especiales

**Si no hay buybox:**
- El script usa el precio actual del item como referencia

**Si buybox < precio_minimo:**
- No compite (mantiene precio_original)
- Evita pérdidas

**Si el producto no es catálogo:**
- El script lo ignora
- Solo procesa productos con `es_catalogo = 1`

---

## 📈 Ejemplos de Uso

### Ejemplo 1: Producto Rentable

```
Costo Amazon: $50
Tax (7%): $3.50
Costo Real: $53.50

Precio Original (45%): $77.58
Precio Mínimo (25%): $66.88
Buybox ML: $70.00

→ Nuevo Precio: $69.00 ✅
   (Compito y mantengo 28.9% de margen)
```

### Ejemplo 2: Producto No Rentable

```
Costo Amazon: $50
Tax (7%): $3.50
Costo Real: $53.50

Precio Original (45%): $77.58
Precio Mínimo (25%): $66.88
Buybox ML: $60.00

→ Nuevo Precio: $77.58 ❌
   (No compito, perdería plata)
```

---

## 🔧 Troubleshooting

### Error: "No se pudo obtener buybox"

**Causa**: Token ML expirado o item no existe

**Solución**:
```bash
# Verificar token
echo $ML_ACCESS_TOKEN

# Regenerar token si es necesario
```

### Error: "Sin datos de costo"

**Causa**: Producto no tiene `costo_amazon` en DB

**Solución**:
El script calcula automáticamente desde `precio_original`:
```python
costo_amazon = precio_original / 1.45 / 1.07
```

### Precios no se actualizan

**Causa**: ML puede rechazar cambios muy frecuentes

**Solución**:
- Esperar al menos 1 hora entre ajustes
- Verificar logs de ML para errores

---

## 📝 Logs y Monitoreo

### Ver Productos de Catálogo

```bash
sqlite3 storage/listings_database.db "
SELECT asin, precio_original, precio_actual, es_catalogo, ultima_actualizacion_precio
FROM listings
WHERE es_catalogo = 1;
"
```

### Ver Histórico de Cambios

```bash
sqlite3 storage/listings_database.db "
SELECT asin, precio_original, precio_actual,
       ROUND((precio_actual - precio_original) / precio_original * 100, 2) as descuento_pct
FROM listings
WHERE es_catalogo = 1 AND precio_actual < precio_original;
"
```

---

## 🚀 Integración con main2.py (Opcional)

**IMPORTANTE**: `main2.py` funciona perfecto, es muy frágil. NO lo toques a menos que sea necesario.

Si querés integrar el sistema de precios dinámicos:

1. **Opción Segura**: Ejecutar scripts por separado después de publicar
2. **Opción Integrada**: Importar funciones en `main2.py` solo si es crítico

### Opción Segura (Recomendada)

```bash
# Después de correr main2.py
python3 main2.py  # Publica productos
python3 scripts/tools/adjust_catalog_prices.py  # Ajusta precios después
```

---

## 📌 Resumen

✅ **DB actualizada** con columnas para precios dinámicos
✅ **Script de ajuste** automático con margen mínimo 20%
✅ **Script de reversión** a precios originales
✅ **Documentación completa** con ejemplos

**Próximos pasos sugeridos:**
1. Probar con `--dry-run` primero
2. Ejecutar en 2-3 productos de prueba
3. Monitorear resultados
4. Configurar cron job si funciona bien

---

**ONE WORLD**
Hecho con Claude Code 🤖
