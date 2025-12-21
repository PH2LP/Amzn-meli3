# 📊 SISTEMA DE TRACKING DE VENTAS

## 🎯 ¿Qué hace?

Monitorea automáticamente tus ventas de MercadoLibre usando la **Billing API oficial**:
- ✅ **Ingresos REALES**: Obtiene precio de venta, comisiones ML, envío e impuestos desde la API
- ✅ **Neto EXACTO**: Lo que realmente te queda después de TODO
- ✅ **Costos**: Amazon + tax 7% + fulfillment 3PL
- ✅ **Ganancia neta** y **margen de ganancia**
- ✅ **Estadísticas** por país, producto, período

**⚡ NO usa estimaciones - TODO es data real de MercadoLibre API**

---

## 📋 Datos Registrados

Cada venta incluye:

### Identificación
- Número de orden ML
- ML Item ID (CBT...)
- ASIN de Amazon
- SKU (si existe)

### Ubicación
- País del comprador
- Marketplace (MLU, MLM, etc.)
- Nickname del comprador

### Producto
- Título
- Cantidad vendida

### Fechas
- Fecha de venta
- Fecha de registro

### Financiero - MercadoLibre (desde Billing API)
- **Precio de venta**: Lo que pagó el cliente (REAL)
- **Comisión ML**: Fee exacto de ML (NO es % fijo, varía por categoría/reputación)
- **Costo de envío**: Si es Free Shipping (REAL)
- **Impuestos ML**: Taxes e IVA (REAL)
- **Neto ML**: Lo que TE QUEDA después de TODO (paid_amount de la API)

### Costos - Amazon + 3PL
- **Costo Amazon**: Precio que pagaste en Amazon
- **Tax 7%**: Impuesto de Florida
- **Fulfillment**: Fee del 3PL ($4.00)
- **Costo total**: Suma de todo

### Ganancia
- **Profit**: Neto ML - Costo total
- **Margen %**: (Profit / Precio venta) × 100

### Estado
- `pending`: Pendiente de envío
- `shipped`: Enviado
- `delivered`: Entregado
- `cancelled`: Cancelado

---

## 🚀 Uso

### 1️⃣ Inicializar sistema (solo primera vez)
```bash
python3 17_track_sales.py --init
```

### 2️⃣ Revisar nuevas ventas (últimas 24h)
```bash
python3 17_track_sales.py
```

**Output ejemplo:**
```
✅ NUEVA VENTA REGISTRADA
   Orden:         2000012345678
   Producto:      LEGO Technic Lamborghini Sián...
   ASIN:          B0CYM126TT
   Comprador:     juan_perez123
   Cantidad:      1

   💵 INGRESOS ML:
      Precio venta:     $325.39
      - Fee ML:         -$46.23    ← REAL desde API (14.2%)
      - Envío:          -$8.50     ← REAL desde API
      - Impuestos ML:   -$3.25     ← REAL desde API
      = Neto ML:        $267.41    ← LO QUE TE QUEDA

   💸 COSTOS:
      Amazon:           -$193.99
      Tax 7%:           -$13.58
      3PL:              -$4.00
      = Total costo:    -$211.57

   💰 GANANCIA NETA:  $55.84 (17.2%)
```

### 3️⃣ Ver estadísticas
```bash
python3 17_track_sales.py --stats
```

**Output ejemplo:**
```
📊 ESTADÍSTICAS DE VENTAS
════════════════════════════════════════════

   Total ventas:       45
   Total unidades:     52
   Revenue total:      $12,458.90
   Ganancia total:     $2,891.34
   Margen promedio:    23.2%

🏆 TOP 5 PRODUCTOS MÁS VENDIDOS:

   1. LEGO Technic Lamborghini Sián
      ASIN: B0CYM126TT | Ventas: 8 | Ganancia: $510.08

   2. DJI Mini 3 Pro Drone
      ASIN: B09WDC1JJJ | Ventas: 5 | Ganancia: $892.15
   ...
```

### 4️⃣ Exportar a Excel
```bash
python3 17_track_sales.py --export
```

Genera: `storage/sales_report.xlsx`

**Columnas en Excel:**
- order_id
- sale_date
- country
- marketplace
- product_title
- asin
- quantity
- sale_price_usd
- ml_fee
- net_proceeds
- amazon_cost
- amazon_tax
- fulfillment_fee
- total_cost
- **profit**
- **profit_margin**
- status
- buyer_nickname

---

## ⚙️ Configuración Automática

### Opción 1: Ejecutar manualmente cada X horas
```bash
# Agregar a crontab (cada 1 hora)
0 * * * * cd /path/to/revancha && python3 17_track_sales.py >> logs/sales_tracking.log 2>&1
```

### Opción 2: Daemon automático (RECOMENDADO)
```bash
# Local
python3 scripts/tools/auto_track_sales_loop.py

# En servidor (background)
nohup python3 scripts/tools/auto_track_sales_loop.py > logs/sales_tracking.log 2>&1 &
```

**Configuración** (en `.env`):
```bash
# Intervalo de revisión (en horas)
SALES_TRACKING_INTERVAL_HOURS=1  # Revisar cada 1 hora
```

---

## 📊 Análisis de Datos

### Python/Pandas
```python
import sqlite3
import pandas as pd

# Conectar a DB
conn = sqlite3.connect("storage/sales_tracking.db")

# Leer todas las ventas
df = pd.read_sql_query("SELECT * FROM sales", conn)

# Análisis por país
by_country = df.groupby('country').agg({
    'profit': 'sum',
    'quantity': 'sum'
}).reset_index()

print(by_country)

# Top productos por ganancia
top_products = df.groupby('asin').agg({
    'product_title': 'first',
    'profit': 'sum',
    'quantity': 'sum'
}).sort_values('profit', ascending=False).head(10)

print(top_products)
```

### SQL Directo
```sql
-- Ventas del mes actual
SELECT
    COUNT(*) as ventas,
    SUM(profit) as ganancia_total,
    AVG(profit_margin) as margen_promedio
FROM sales
WHERE strftime('%Y-%m', sale_date) = strftime('%Y-%m', 'now');

-- Top 10 productos
SELECT
    product_title,
    asin,
    COUNT(*) as ventas,
    SUM(profit) as ganancia
FROM sales
GROUP BY asin
ORDER BY ganancia DESC
LIMIT 10;

-- Ventas por país
SELECT
    country,
    COUNT(*) as ventas,
    SUM(sale_price_usd) as revenue,
    SUM(profit) as ganancia,
    AVG(profit_margin) as margen_avg
FROM sales
GROUP BY country
ORDER BY ganancia DESC;
```

---

## 🔄 Integración con ML API

### Webhooks (Opcional - Tiempo Real)

Puedes configurar un webhook en MercadoLibre para recibir notificaciones instantáneas:

1. **Crear endpoint en tu servidor**:
```python
from flask import Flask, request
import json

app = Flask(__name__)

@app.route('/ml-webhook', methods=['POST'])
def ml_webhook():
    data = request.json

    # Si es una nueva orden
    if data.get('topic') == 'orders_v2':
        order_id = data['resource'].split('/')[-1]

        # Procesar orden
        # ... (usar track_sales.py)

    return '', 200
```

2. **Registrar webhook en ML**:
```bash
curl -X POST \
  'https://api.mercadolibre.com/applications/YOUR_APP_ID/webhooks' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '{
    "url": "https://tu-servidor.com/ml-webhook",
    "topic": "orders_v2"
  }'
```

---

## 📈 Métricas Clave

### KPIs Importantes
- **Ganancia total**: Suma de profit
- **Margen promedio**: AVG(profit_margin)
- **Ticket promedio**: AVG(sale_price_usd)
- **Unidades vendidas**: SUM(quantity)
- **ROI**: (Ganancia / Costo total) × 100

### Dashboards Sugeridos
- Ventas por día/mes
- Ganancia por producto
- Margen por categoría
- Productos más vendidos
- Tendencias de precios

---

## 🐛 Troubleshooting

### Error: "ML_ACCESS_TOKEN requerido"
```bash
# Verificar .env
grep ML_ACCESS_TOKEN .env

# Si expiró, refrescar token
python3 16_refresh_ml_token.py
```

### Error: "No se pueden obtener órdenes"
- Verificar que ML_USER_ID sea correcto
- Verificar que access token tenga permisos de "read_orders"
- Verificar conectividad con ML API

### Ventas duplicadas
El sistema usa `order_id` como UNIQUE key, por lo que no puede haber duplicados.

Si ves duplicados en Excel, probablemente sean ventas diferentes con IDs distintos.

---

## 💡 Tips

1. **Ejecutar al menos 1 vez al día** para no perder ventas
2. **Exportar a Excel mensualmente** para análisis histórico
3. **Revisar margen promedio** - si es <15%, aumentar markup
4. **Identificar productos top** y buscar más similares
5. **Pausar productos con margen negativo**

---

## 🔮 Mejoras Futuras

- [ ] Integración con Google Sheets
- [ ] Dashboard web (Streamlit/Dash)
- [ ] Alertas por email/Telegram
- [ ] Tracking de costos de devoluciones
- [ ] Análisis de tendencias con ML
- [ ] Proyecciones de ganancias
- [ ] Comparativa mes a mes
- [ ] Cálculo automático de impuestos

---

## 📞 Soporte

Si encontrás bugs o tenés sugerencias, abrí un issue en GitHub o contactame.

**Happy selling! 💰**
