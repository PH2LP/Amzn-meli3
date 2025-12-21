# Consulta para Soporte de Amazon SP-API

## PROBLEMA

Estamos desarrollando un sistema de sincronización automática de productos entre Amazon y MercadoLibre para nuestra cuenta de vendedor.

**El problema principal:** Necesitamos saber cuántos días tarda un producto en llegar a nuestros clientes en Miami, FL (zipcode 33172), pero la SP-API no proporciona esta información.

## LO QUE NECESITAMOS

Necesitamos obtener para cada producto (ASIN):
1. **Fecha estimada de entrega** para un zipcode específico (33172 - Miami, FL)
2. **Días hasta la entrega** desde hoy
3. **Desde qué estado/warehouse se enviará** el producto

**¿Por qué lo necesitamos?**
- Solo queremos listar en MercadoLibre productos que lleguen en **3 días o menos**
- Si un producto tarda 6-7 días en llegar, no nos sirve aunque tenga "fast fulfillment"

## LO QUE ESTAMOS USANDO ACTUALMENTE

### Endpoint actual: Product Pricing API v0
```
GET /products/pricing/v0/items/{asin}/offers
```

**Parámetros que enviamos:**
```json
{
  "MarketplaceId": "ATVPDKIKX0DER",
  "ItemCondition": "New",
  "deliveryPostalCode": "33172"
}
```

### Lo que nos devuelve la API:

```json
{
  "ShippingTime": {
    "availabilityType": "NOW",
    "maximumHours": 0,
    "minimumHours": 0
  },
  "ShipsFrom": {
    "State": null,
    "Country": null
  },
  "PrimeInformation": {
    "IsPrime": true,
    "IsNationalPrime": true
  }
}
```

## EL PROBLEMA ESPECÍFICO

### Lo que la API nos dice:
- ✅ `availabilityType: "NOW"` → Producto disponible
- ✅ `maximumHours: 0` → Sale del warehouse inmediatamente
- ✅ `IsPrime: true` → Tiene Prime
- ❌ `ShipsFrom.State: null` → **NO sabemos desde dónde envía**
- ❌ **NO hay fecha de entrega estimada**

### Por qué esto es un problema:

**Ejemplo real con ASIN B0FGJ3G6V8:**

La API nos dice:
```
availabilityType: "NOW"
maximumHours: 0
ShipsFrom.State: null
```

Esto nos haría pensar: "¡Perfecto! Disponible inmediatamente, acepto el producto"

**PERO** cuando revisamos en Amazon.com con zipcode 33172:
- **Fecha de entrega real:** Lunes 22 de diciembre (4 días)
- **Conclusión:** Tarda 4 días, NO cumple nuestro requisito de ≤3 días
- **Debemos RECHAZARLO**, no listarlo en MercadoLibre

### ¿Por qué pasa esto?

`maximumHours: 0` solo indica el tiempo que tarda en **salir del warehouse**.

NO incluye:
- ❌ Tiempo de tránsito desde el warehouse hasta Miami
- ❌ Distancia geográfica (puede enviar desde Washington State, California, etc.)
- ❌ Método de envío (terrestre, aéreo, etc.)

**Resultado:** Un producto puede tener `maximumHours: 0` pero tardar 6-7 días en llegar a Miami si se envía desde la costa oeste.

## EJEMPLO CONCRETO DE PRODUCTOS

### Productos de prueba:

| ASIN | SP-API dice | Realidad (en Amazon.com con 33172) | Problema |
|------|-------------|-------------------------------------|----------|
| B0FGJ3G6V8 | `maximumHours: 0`, `availabilityType: NOW` | Llega **Lunes 22** (4 días) | ❌ Rechazar >3d |
| B0D9H19PBL | `maximumHours: 0`, `availabilityType: NOW` | Llega **Viernes 26** (6 días) | ❌ Rechazar >3d |
| B0DJH46BBL | `maximumHours: 0`, `availabilityType: NOW` | Llega **Miércoles 24** (4 días) | ❌ Rechazar >3d |

Todos los productos reportan `maximumHours: 0` (parecen rápidos) pero en realidad tardan 4-6 días.

## LO QUE HEMOS INTENTADO

### 1. Parámetro `deliveryPostalCode`
```
GET /products/pricing/v0/items/{asin}/offers?deliveryPostalCode=33172
```
**Resultado:** El parámetro es ignorado, la respuesta es idéntica con o sin él.

### 2. Product Pricing API v2022
```
POST /products/pricing/2022-05-01/offer/competitiveSummary
```
**Resultado:** Tampoco proporciona fecha de entrega estimada.

### 3. Filtro por `ShipsFrom.State`
**Problema:** El campo `ShipsFrom.State` siempre viene `null` para productos FBA.

### 4. Configurar `ALLOWED_SHIP_FROM_STATES`
**Problema:** No podemos filtrar si el campo está vacío.

## NUESTRA SOLUCIÓN TEMPORAL (NO IDEAL)

Como la SP-API no provee esta información, tuvimos que implementar **web scraping** usando la API interna "Glow" de Amazon:

```python
# 1. GET página del producto
GET https://www.amazon.com/dp/{asin}

# 2. POST a API interna para cambiar zipcode
POST https://www.amazon.com/portal-migration/hz/glow/address-change
Body: {"zipCode": "33172", "locationType": "LOCATION_INPUT"}

# 3. GET página nuevamente y parsear HTML para extraer fecha
# Ejemplo: "Prime members get FREE delivery Monday, December 22"
```

**Problemas de esta solución:**
- ❌ No es oficial, puede romperse en cualquier momento
- ❌ Más lento (~4 segundos vs <1 segundo de SP-API)
- ❌ Requiere parsear HTML con regex (frágil)
- ❌ No está documentado, podría violar términos de servicio
- ⚠️  Dependemos de que el HTML tenga el formato esperado

## PREGUNTA PARA SOPORTE

**¿Existe alguna forma oficial de obtener la fecha de entrega estimada para un zipcode específico usando la SP-API?**

Específicamente necesitamos:

1. **Fecha de entrega estimada** (ej: "December 22, 2024")
2. **Desde qué estado/warehouse** se enviará el producto
3. Que el parámetro **`deliveryPostalCode`** sea respetado
4. Que funcione para productos **FBA** (Fulfillment by Amazon)

### Endpoints que hemos revisado:

- ✅ `/products/pricing/v0/items/{asin}/offers` - No tiene fecha de entrega
- ✅ `/products/pricing/2022-05-01/offer/competitiveSummary` - No tiene fecha de entrega
- ✅ `/fba/inbound/v0/shipments` - Solo para inbound, no para customer delivery
- ✅ `/orders/v0/orders` - Solo para órdenes ya realizadas

### Alternativas consideradas:

1. **¿Hay un endpoint de "Delivery Estimation" que no conozcamos?**
2. **¿El parámetro `deliveryPostalCode` funciona en algún otro endpoint?**
3. **¿Hay forma de obtener `ShipsFrom.State` para productos FBA?**
4. **¿Existe algún campo adicional en la respuesta que estemos ignorando?**

## POR QUÉ ES CRÍTICO PARA NUESTRO NEGOCIO

Sincronizamos **miles de ASINs** automáticamente.

**Sin esta información:**
- ❌ Listamos productos que tardan 7 días en llegar
- ❌ Clientes se quejan en MercadoLibre por entregas lentas
- ❌ Recibimos penalizaciones por mal servicio
- ❌ Perdemos ventas y reputación

**Con esta información:**
- ✅ Solo listamos productos que llegan en ≤3 días
- ✅ Mejor experiencia del cliente
- ✅ Mejor reputación del vendedor
- ✅ Proceso 100% automatizado y confiable

## INFORMACIÓN ADICIONAL

**Cuenta:** Seller account en marketplace US (ATVPDKIKX0DER)
**Región:** Miami, FL - Zipcode 33172
**Volumen:** ~5000-10000 productos sincronizados
**SP-API App:** Credenciales LWA configuradas correctamente
**Permisos actuales:** Product Pricing API habilitado

---

**Resumen en 1 línea:**
¿Cómo obtener la fecha de entrega estimada de un producto FBA para un zipcode específico usando SP-API oficial?
