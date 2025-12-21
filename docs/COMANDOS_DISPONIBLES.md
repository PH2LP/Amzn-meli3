# 📋 COMANDOS DISPONIBLES - REVANCHA SYSTEM

## ✅ Scripts Principales (en orden de uso)

### 1️⃣ BUSCAR PRODUCTOS
```bash
python3 01_search_products.py
```
Busca productos en Amazon según keywords.txt

---

### 2️⃣ PUBLICAR EN MERCADOLIBRE
```bash
python3 02_publish_to_ml.py                    # Publicar todos los ASINs
python3 02_publish_to_ml.py --asin B0BFJWCYTL  # Publicar un ASIN específico
python3 02_publish_to_ml.py --dry-run          # Simular sin publicar
```
Publica productos de Amazon a MercadoLibre

---

### 3️⃣ ACTUALIZAR PRECIOS
```bash
python3 03_update_prices.py                    # Actualizar todos los precios
python3 03_update_prices.py --dry-run          # Ver cambios sin aplicar
python3 03_update_prices.py --asin B0...       # Actualizar un producto
```
Recalcula y actualiza precios en MercadoLibre

---

### 4️⃣ SINCRONIZAR BASE DE DATOS
```bash
python3 04_sync_db.py         # Sincronizar DB + mini_ml al servidor
python3 04_sync_db.py --yes   # Auto-confirmar sin preguntar
```
**IMPORTANTE**: Ejecutar siempre después de publicar o cambiar precios
Sube: Base de datos SQLite + Archivos mini_ml.json

---

### 5️⃣ INICIAR SYNC AUTOMÁTICO AMAZON ↔ ML (SERVIDOR)
```bash
python3 05_start_sync_amzn_meli.py
```
Inicia daemon de sincronización automática cada 3 horas **en el servidor VPS**
- Ejecuta en servidor remoto (138.197.32.67)
- Muestra PID del proceso

---

### 6️⃣ DETENER SYNC AUTOMÁTICO (SERVIDOR)
```bash
python3 06_stop_sync_amzn_meli.py
```
Detiene el daemon de sincronización **en el servidor VPS**

---

### 7️⃣ VER LOGS DE SYNC (SERVIDOR)
```bash
python3 07_view_sync_logs.py              # Ver últimas 50 líneas del servidor
python3 07_view_sync_logs.py -n 100       # Ver últimas 100 líneas
python3 07_view_sync_logs.py --all        # Ver archivo completo
python3 07_view_sync_logs.py --results    # Ver resultados JSON de sincronización
python3 07_view_sync_live.py              # Seguir logs en tiempo real (tail -f)
```
Muestra logs del sync Amazon ↔ MercadoLibre **desde el servidor VPS**
- Lee archivos directamente del servidor
- No requiere descargar archivos

---

### 8️⃣ INICIAR AUTO-RESPUESTA
```bash
python3 08_start_autoanswer.py
```
Inicia respuestas automáticas a preguntas de clientes

---

### 9️⃣ DETENER AUTO-RESPUESTA
```bash
python3 09_stop_autoanswer.py
```
Detiene las respuestas automáticas

---

### 🔟 VER LOGS DE AUTO-RESPUESTA
```bash
python3 10_view_autoanswer_logs.py     # Ver últimas 100 líneas
python3 10_view_autoanswer_logs.py -f  # Seguir en tiempo real
```
Muestra logs del sistema de auto-respuesta

---

### 1️⃣1️⃣ ESTADO DEL SERVIDOR
```bash
python3 11_server_status.py
```
Muestra estado general del servidor (sync, auto-answer, etc.)

---

### 1️⃣2️⃣ LOGS DEL SERVIDOR
```bash
python3 12_server_logs.py
```
Muestra logs generales del servidor

---

### 1️⃣3️⃣ CONFIGURAR SERVIDOR
```bash
python3 13_update_server_config.py --show              # Ver config actual
python3 13_update_server_config.py --markup 40         # Cambiar markup
python3 13_update_server_config.py --use-tax false     # Desactivar tax
python3 13_update_server_config.py --fulfillment-fee 4.5  # Cambiar costo envío
```
Actualiza configuración de pricing en el servidor

---

### 1️⃣4️⃣ PUBLICACIÓN PARALELA (RÁPIDA)
```bash
python3 14_parallel_publish.py                         # Publicar con 4 workers
python3 14_parallel_publish.py --workers 8             # Usar 8 workers
python3 14_parallel_publish.py --dry-run               # Simular sin publicar
```
Publica productos en paralelo (4x más rápido que publicación normal)

---

### 1️⃣5️⃣ SINCRONIZAR MINI_ML
```bash
python3 15_sync_mini_ml.py
```
Sincroniza archivos mini_ml.json al servidor (solo archivos, sin DB)

---

### 1️⃣6️⃣ REFRESCAR TOKEN DE MERCADOLIBRE
```bash
python3 16_refresh_ml_token.py
```
Refresca el access token de MercadoLibre cuando expire

---

### 1️⃣7️⃣ TRACKING DE VENTAS (LOCAL)
```bash
python3 17_track_sales.py                              # Revisar nuevas ventas (últimas 24h)
python3 17_track_sales.py --stats                      # Ver estadísticas
python3 17_track_sales.py --export                     # Exportar a Excel
```
**Sistema automático de tracking de ventas**:
- Registra cada venta automáticamente
- Calcula ingresos (venta ML - fees)
- Calcula costos (Amazon + tax + 3PL)
- Calcula ganancia neta y margen
- Exporta a Excel para análisis

**Base de datos:** `storage/sales_tracking.db`
**Excel:** `storage/sales_report.xlsx`

---

### 1️⃣8️⃣ INICIAR SALES TRACKING EN SERVIDOR
```bash
python3 18_start_sales_tracking.py
```
Inicia daemon automático en el servidor que cada 1 hora:
- Trackea nuevas ventas de MercadoLibre
- Genera Excel profesional con Dashboard
- Sube a Dropbox:
  - `/VENTAS_MERCADOLIBRE.xlsx` (Excel con todas las ventas)
  - `/sales_tracking.db` (Base de datos de ventas)
  - `/listings_database.db` (Base de datos de productos)

**Acceso desde cualquier dispositivo**: Abre Dropbox en tu móvil/tablet/PC

---

### 1️⃣9️⃣ VER LOGS DE SALES TRACKING (SERVIDOR)
```bash
python3 19_view_sales_logs.py              # Ver últimas 50 líneas
python3 19_view_sales_logs.py --live       # Ver en tiempo real (tail -f)
python3 19_view_sales_logs.py --full       # Ver archivo completo
```
Muestra logs del daemon de sales tracking ejecutándose en el servidor

---

### 2️⃣0️⃣ DETENER SALES TRACKING (SERVIDOR)
```bash
python3 20_stop_sales_tracking.py
```
Detiene el daemon de sales tracking en el servidor

---

### 2️⃣1️⃣ DEPLOY SALES TRACKING AL SERVIDOR
```bash
python3 21_deploy_sales_tracking.py                    # Solo deploy
python3 21_deploy_sales_tracking.py --start            # Deploy + iniciar
```
Sube todos los archivos necesarios al servidor e instala dependencias.
**Ejecutar solo la primera vez o después de actualizar código**

---

## 📌 Flujo de Trabajo Típico

### ▶️ WORKFLOW 1: Buscar y Publicar Productos Nuevos
```bash
# 1. Editar keywords
nano keywords.txt

# 2. Buscar productos
python3 01_search_products.py

# 3. Publicar (probar primero con dry-run)
python3 02_publish_to_ml.py --asin B0BFJWCYTL --dry-run
python3 02_publish_to_ml.py

# 4. Sincronizar al servidor
python3 04_sync_db.py --yes
```

### ▶️ WORKFLOW 2: Actualizar Precios Globalmente
```bash
# 1. Editar markup local
nano .env  # Cambiar PRICE_MARKUP=35 a 40

# 2. Ver impacto
python3 03_update_prices.py --dry-run

# 3. Aplicar cambios
python3 03_update_prices.py

# 4. Sincronizar DB
python3 04_sync_db.py --yes

# 5. Actualizar config del servidor
python3 13_update_server_config.py --markup 40
```

### ▶️ WORKFLOW 3: Activar Sistema Completo en Servidor
```bash
# 1. Sincronizar DB y mini_ml
python3 04_sync_db.py --yes

# 2. Iniciar sync automático (cada 3h)
python3 05_start_sync_amzn_meli.py

# 3. Iniciar auto-respuesta
python3 08_start_autoanswer.py

# 4. Verificar estado
python3 11_server_status.py
```

### ▶️ WORKFLOW 4: Activar Sales Tracking Automático
```bash
# 1. Primera vez: Deploy al servidor
python3 21_deploy_sales_tracking.py --start

# 2. Ver logs en tiempo real
python3 19_view_sales_logs.py --live

# 3. Acceder al Excel desde Dropbox
# Abre Dropbox en tu móvil/tablet/PC
# Archivo: /VENTAS_MERCADOLIBRE.xlsx
```

### ▶️ WORKFLOW 5: Monitorear el Sistema
```bash
# Ver estado general
python3 11_server_status.py

# Ver logs de sync en tiempo real
python3 07_view_sync_logs.py -f

# Ver logs de auto-respuesta
python3 10_view_autoanswer_logs.py -f

# Ver logs de sales tracking
python3 19_view_sales_logs.py --live
```

## ⚠️ Notas Importantes

✅ **Siempre sincronizar después de**:
   - Publicar productos nuevos
   - Actualizar precios
   - Modificar productos

✅ **El sync automático (05)**:
   - Corre cada 3 horas
   - Actualiza precios si Amazon cambió
   - Pausa productos sin stock

✅ **Auto-respuesta (08)**:
   - Necesita archivos mini_ml.json
   - Se sincronizan con `04_sync_db.py`
   - Responde cada 60 segundos

✅ **Para cambios de configuración**:
   - Local: editar `.env`
   - Servidor: `13_update_server_config.py`

## 🔧 Solución de Problemas

### Error: "ModuleNotFoundError: No module named 'dotenv'"
```bash
pip3 install python-dotenv --break-system-packages
```

### Error: "no such table: listings" en servidor
```bash
python3 04_sync_db.py --yes
```

### Sync no está corriendo
```bash
python3 05_start_sync_amzn_meli.py
```

### Ver qué está pasando
```bash
python3 11_server_status.py
python3 07_view_sync_logs.py
python3 10_view_autoanswer_logs.py
```

## 📊 Orden de los Scripts

Los scripts están numerados en orden lógico de uso:

1. **01-04**: Operaciones locales (buscar, publicar, precios, sync)
2. **05-07**: Sync Amazon ↔ ML (servidor)
3. **08-10**: Auto-respuesta (servidor)
4. **11-13**: Monitoreo y configuración
5. **14-17**: Herramientas avanzadas (publicación paralela, tokens, tracking local)
6. **18-21**: Sales Tracking Automático (servidor + Dropbox)

Simplemente escribí `ls` para ver todos los scripts en orden.

---

## 📱 ACCESO MÓVIL A VENTAS

Una vez iniciado el sales tracking daemon (script 18), puedes:

1. **Ver Excel de ventas desde cualquier dispositivo**:
   - Abre la app de Dropbox en tu móvil/tablet
   - Busca el archivo: `/VENTAS_MERCADOLIBRE.xlsx`
   - Dashboard profesional con gráficos y estadísticas

2. **Consultar bases de datos**:
   - `/sales_tracking.db` (ventas)
   - `/listings_database.db` (productos publicados)

El daemon actualiza los archivos automáticamente cada 1 hora.
