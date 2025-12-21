# 📊 SISTEMA DE SALES TRACKING AUTOMÁTICO CON DROPBOX

## 🎯 ¿Qué se implementó?

Sistema completamente automático que se ejecuta en el servidor y actualiza Dropbox cada 1 hora con:

### ✅ Lo que hace automáticamente:

1. **Tracking de ventas**
   - Obtiene nuevas órdenes de MercadoLibre
   - Calcula ingresos reales (precio - fees - envío)
   - Calcula costos (Amazon + tax + 3PL)
   - Calcula ganancia neta y margen

2. **Genera Excel profesional**
   - Dashboard con gráficos
   - KPIs principales
   - Top productos
   - Distribución de costos
   - Métricas financieras

3. **Sube a Dropbox**
   - `/VENTAS_MERCADOLIBRE.xlsx` - Excel con dashboard
   - `/sales_tracking.db` - Base de datos de ventas
   - `/listings_database.db` - Base de datos de productos

### 📱 Acceso desde cualquier dispositivo

- Abre Dropbox en tu móvil, tablet o PC
- Busca el archivo: `/VENTAS_MERCADOLIBRE.xlsx`
- Excel profesional con todas tus ventas y estadísticas
- Se actualiza automáticamente cada 1 hora

---

## 🚀 Comandos Disponibles

### 18_start_sales_tracking.py
Inicia el daemon en el servidor
```bash
python3 18_start_sales_tracking.py
```

### 19_view_sales_logs.py
Ver logs del daemon
```bash
python3 19_view_sales_logs.py              # Últimas 50 líneas
python3 19_view_sales_logs.py --live       # Tiempo real
python3 19_view_sales_logs.py --full       # Archivo completo
```

### 20_stop_sales_tracking.py
Detener el daemon
```bash
python3 20_stop_sales_tracking.py
```

### 21_deploy_sales_tracking.py
Deploy de archivos al servidor
```bash
python3 21_deploy_sales_tracking.py                # Solo deploy
python3 21_deploy_sales_tracking.py --start        # Deploy + start
```

---

## 📊 Estado Actual

### ✅ Sistema Ejecutándose

```
DAEMON INICIADO - PID: 1193248
Servidor: 138.197.32.67
Path: /opt/amz-ml-system

Última ejecución: 2025-12-14 12:14:28
Próxima ejecución: 2025-12-14 13:00:00
```

### 📈 Última Sincronización

```
✅ Excel de ventas subido a Dropbox (9.9 KB)
✅ DB de ventas subida a Dropbox (52.0 KB)
✅ 4 ventas totales
✅ Ganancia total: $113.64
✅ Margen promedio: 26.9%
```

---

## 🗂️ Estructura de Archivos

### En el servidor (`/opt/amz-ml-system`)

```
scripts/
├── server/
│   └── sales_tracking_daemon.py    # Daemon principal
└── tools/
    ├── track_sales.py               # Tracking de ventas
    └── generate_excel_desktop.py    # Generación de Excel

storage/
├── sales_tracking.db                # DB de ventas
├── listings_database.db             # DB de productos
└── 20251214_VENTAS_MERCADOLIBRE.xlsx # Excel local

logs/
├── sales_daemon.log                 # Logs del daemon
└── sales_daemon.pid                 # PID del proceso
```

### En Dropbox (raíz `/`)

```
/VENTAS_MERCADOLIBRE.xlsx            # Excel con ventas (actualizado cada 1h)
/sales_tracking.db                   # DB de ventas (actualizado cada 1h)
/listings_database.db                # DB de productos (actualizado cada 1h)
```

---

## 📱 Cómo Acceder al Excel desde tu Móvil

### 1. Abre la app de Dropbox
- iOS: App Store → Dropbox
- Android: Google Play → Dropbox

### 2. Busca el archivo
- Archivo: `VENTAS_MERCADOLIBRE.xlsx`
- Ubicación: Raíz de Dropbox (`/`)

### 3. Ver el Dashboard
El Excel incluye 2 hojas:

#### **Dashboard** (primera hoja)
- 💰 Resumen financiero
  - Total ventas
  - Revenue total
  - Ganancia total
  - ROI
  - Ticket promedio
  - Margen promedio

- 📉 Desglose de costos
  - Comisiones ML
  - Costos Amazon
  - 3PL Fulfillment
  - Total costos

- 🏆 Top 5 productos más rentables

- 📊 Gráficos
  - Ganancia por producto
  - Distribución revenue vs costos

#### **Ventas** (segunda hoja)
Tabla completa con todas las ventas:
- Fecha
- Marketplace
- Producto
- Cantidad
- Precio venta
- Fee ML
- Envío
- Neto ML
- Costo Amazon
- 3PL
- Total costo
- **GANANCIA** (resaltada en verde)
- Margen %
- ASIN
- Orden ML
- CBT ID
- Comprador
- País
- Estado

---

## ⚙️ Configuración

### Intervalo de ejecución

Por defecto: **1 hora**

Para cambiar el intervalo, editar `.env`:
```bash
SALES_TRACKING_INTERVAL_HOURS=2  # Cambiar a 2 horas
```

Y reiniciar el daemon:
```bash
python3 20_stop_sales_tracking.py
python3 18_start_sales_tracking.py
```

### Token de Dropbox

El token ya está configurado en `.env`:
```bash
DROPBOX_ACCESS_TOKEN=sl.u.AGIHYIcB2QyxoL76C1g6nMwnVCF6u7...
```

**IMPORTANTE**: Este token nunca expira mientras no lo revokes.

Si necesitas generar un nuevo token:
1. Ve a: https://www.dropbox.com/developers/apps
2. Crea una app (o usa la existente)
3. Genera un Access Token
4. Copia el token a `.env`
5. Ejecuta: `python3 21_deploy_sales_tracking.py` (para subir .env al servidor)

---

## 🔍 Monitoreo

### Ver logs en tiempo real
```bash
python3 19_view_sales_logs.py --live
```

Output:
```
════════════════════════════════════════════════════════════════
ITERACIÓN #1 - 2025-12-14 12:14:28
════════════════════════════════════════════════════════════════

📊 PASO 1: Tracking de ventas...
   ✅ Tracking completado

📈 PASO 2: Generando Excel profesional...
   ✅ Excel generado

☁️  PASO 3: Sincronizando a Dropbox...
   ✅ Subido: /VENTAS_MERCADOLIBRE.xlsx (9.9 KB)
   ✅ Subido: /sales_tracking.db (52.0 KB)
   ✅ Subido: /listings_database.db (1.2 MB)

📊 ESTADÍSTICAS:
   Total ventas:      4
   Ganancia total:    $113.64
   Margen promedio:   26.9%

✅ Ciclo completado exitosamente
⏰ Próxima ejecución: 2025-12-14 13:00
💤 Durmiendo por 1.0 hora(s)...
```

### Verificar que el daemon está corriendo
```bash
python3 11_server_status.py
```

### Ver estadísticas de ventas
```bash
python3 17_track_sales.py --stats
```

---

## 🐛 Solución de Problemas

### El daemon no está corriendo
```bash
python3 18_start_sales_tracking.py
```

### El Excel no se actualiza en Dropbox
1. Verificar logs: `python3 19_view_sales_logs.py`
2. Verificar token de Dropbox en `.env`
3. Reiniciar daemon:
   ```bash
   python3 20_stop_sales_tracking.py
   python3 18_start_sales_tracking.py
   ```

### Error de conexión SSL con Dropbox
Es un error temporal de la API de Dropbox. El daemon reintentará en el próximo ciclo (1 hora).

### No hay ventas en el Excel
- El tracking solo registra ventas de las últimas 24 horas
- Para importar ventas históricas: `python3 17_track_sales.py --backfill`

### Cambios en el código no se reflejan
Después de modificar cualquier archivo:
```bash
python3 21_deploy_sales_tracking.py    # Subir archivos
python3 20_stop_sales_tracking.py      # Detener daemon
python3 18_start_sales_tracking.py     # Reiniciar daemon
```

---

## 📈 Mejoras Futuras

Posibles mejoras al sistema:

- [ ] Webhook de MercadoLibre para tracking en tiempo real
- [ ] Notificaciones por Telegram cuando hay nueva venta
- [ ] Dashboard web (Streamlit)
- [ ] Sincronización bidireccional (download DBs desde Dropbox)
- [ ] Múltiples usuarios/cuentas
- [ ] Tracking de devoluciones
- [ ] Gráficos de tendencias
- [ ] Proyecciones de ventas con ML
- [ ] Integración con Google Sheets
- [ ] Alertas de margen bajo

---

## 🎉 Resumen

**Sistema 100% automático que:**

✅ Trackea ventas de MercadoLibre cada hora
✅ Calcula ganancias reales (con todos los costos)
✅ Genera Excel profesional con dashboard
✅ Sube todo a Dropbox automáticamente
✅ Acceso desde cualquier dispositivo
✅ Se ejecuta en el servidor 24/7
✅ No requiere intervención manual

**Todo lo que necesitas hacer:**

1. Abrir Dropbox en tu móvil
2. Ver el Excel `VENTAS_MERCADOLIBRE.xlsx`
3. Revisar tus ventas y ganancias

**Eso es todo.** El resto es automático. 🚀
