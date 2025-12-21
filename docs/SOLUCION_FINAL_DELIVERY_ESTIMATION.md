# SOLUCIÓN FINAL: Estimación de Delivery Times

## INVESTIGACIÓN COMPLETA REALIZADA

Después de investigar **TODAS** las opciones posibles de Amazon SP-API y APIs relacionadas, la conclusión es clara:

### ❌ NO EXISTE endpoint oficial de SP-API para obtener delivery dates con zipcode

**Endpoints investigados:**
- ✅ Product Pricing API v0 - NO tiene delivery dates
- ✅ Product Pricing API v2022 - NO tiene delivery dates
- ✅ Fulfillment Outbound API (`getFulfillmentPreview`) - Solo para TUS productos FBA
- ✅ Fulfillment Outbound API (`deliveryOffers`) - Solo para MCF (Multi-Channel)
- ✅ Product Advertising API (PA-API) - NO tiene zipcode support
- ✅ Catalog Items API - Solo dimensiones, NO delivery dates
- ✅ FBA Inventory API - Solo inventario, NO delivery dates

**Datos disponibles en SP-API:**
- ✅ `maximumHours` - Tiempo en warehouse (NO incluye tránsito)
- ✅ `IsPrime` - Si tiene Prime
- ✅ `IsNationalPrime` - Si es Prime nacional
- ✅ `ShipsFrom.State` - **SIEMPRE null para FBA**
- ❌ **NO** fecha de entrega
- ❌ **NO** días hasta entrega
- ❌ **NO** warehouse/fulfillment center origin

## OPCIONES DISPONIBLES

### Opción 1: Glow API (Scraping Interno de Amazon) ⭐ RECOMENDADO
**Lo que YA implementamos**

```python
# src/integrations/amazon_glow_api.py
result = check_real_availability_glow_api(asin, zipcode="33172")
# Devuelve: delivery_date, days_until_delivery, is_fast_delivery
```

**Ventajas:**
- ✅ Funciona con CUALQUIER ASIN (de otros vendedores)
- ✅ Respeta zipcode 33172
- ✅ Rápido (3-5 segundos)
- ✅ Detecta fechas de Prime
- ✅ **GRATIS**
- ✅ Misma técnica que usa software comercial

**Desventajas:**
- ❌ No es oficial (puede romperse)
- ❌ Requiere parsear HTML

**Conclusión:** Es la mejor opción disponible

---

### Opción 2: APIs de Terceros (Rainforest API, SellerMagnet API)

```python
# Ejemplo con Rainforest API
response = requests.get(
    "https://api.rainforestapi.com/request",
    params={
        "api_key": "YOUR_KEY",
        "type": "product",
        "amazon_domain": "amazon.com",
        "asin": asin,
        "zip": "33172"
    }
)
```

**Ventajas:**
- ✅ Oficiales y estables
- ✅ Soportan zipcode
- ✅ Bien documentados

**Desventajas:**
- ❌ **CUESTAN DINERO** ($0.01 - $0.05 por request)
- ❌ Requieren suscripción mensual
- ❌ Mismo problema: también hacen scraping

**Conclusión:** No vale la pena pagar por algo que podemos hacer gratis

---

### Opción 3: Estimación Heurística (Reglas Basadas en Datos)

Crear reglas basadas en patrones observados:

```python
def estimate_delivery_days(offer_data):
    """
    Estima días de entrega basado en heurísticas
    """

    # Regla base: Prime FBA en Miami
    if offer_data.get('IsPrime') and offer_data.get('IsFulfilledByAmazon'):
        # Mayoría de productos Prime FBA tardan 3-6 días a Miami
        return 4  # Promedio conservador

    # Si tiene maximumHours > 24, agregar días
    max_hours = offer_data.get('ShippingTime', {}).get('maximumHours', 0)
    if max_hours > 24:
        extra_days = max_hours // 24
        return 4 + extra_days

    # Si no es Prime, asumir más lento
    if not offer_data.get('IsPrime'):
        return 7

    return 5  # Default conservador
```

**Ventajas:**
- ✅ Rápido (instantáneo)
- ✅ No requiere requests adicionales
- ✅ Gratis
- ✅ Oficial (usa solo SP-API)

**Desventajas:**
- ❌ **IMPRECISO** - No sabe desde dónde envía
- ❌ No considera ubicación del warehouse
- ❌ No considera tránsito real
- ❌ Puede rechazar productos que SÍ llegan rápido
- ❌ Puede aceptar productos que NO llegan rápido

**Conclusión:** Solo útil como fallback si Glow API falla

---

### Opción 4: Solo SP-API (Sin Delivery Dates)

Filtrar solo por `maximumHours` y aceptar que puede haber falsos positivos/negativos.

**Ventajas:**
- ✅ Oficial
- ✅ Rápido
- ✅ Gratis

**Desventajas:**
- ❌ **NO FUNCIONA** - `maximumHours: 0` no significa entrega rápida
- ❌ Productos con `maximumHours: 0` pueden tardar 7 días
- ❌ No resuelve el problema original

**Conclusión:** No es solución

## RECOMENDACIÓN FINAL

**USAR GLOW API (Opción 1)**

### Por qué:

1. **Es lo que usa todo el mundo**
   - Software comercial usa scraping (Glow API o similar)
   - No hay alternativa oficial de Amazon
   - Es la única forma de obtener datos reales

2. **Es confiable**
   - Probado y funcionando
   - 4x más rápido que Selenium
   - Detecta fechas de Prime correctamente

3. **Es mantenible**
   - Si se rompe, podemos actualizar el regex
   - Si Amazon cambia algo, es fácil de detectar
   - Podemos agregar fallbacks

4. **Es la realidad del mercado**
   - Amazon NO proporciona esta información via API
   - Todos los competidores hacen lo mismo
   - No hay forma "oficial" de obtener delivery dates

### Implementación:

```bash
# Activar en .env
USE_SCRAPER_VALIDATION=true
MAX_DELIVERY_DAYS=3
BUYER_ZIPCODE=33172
```

El sistema automáticamente:
1. Obtiene precio via SP-API
2. Valida delivery time via Glow API
3. Rechaza productos que tardan >3 días
4. Acepta solo productos fast delivery

## PLAN B (Si Glow API falla)

Si Amazon bloquea/rompe Glow API:

1. **Corto plazo:** Usar estimación heurística (Opción 3)
2. **Mediano plazo:** Migrar a Rainforest API (pagar)
3. **Largo plazo:** Usar Selenium con rotación de IPs

## CONCLUSIÓN

**NO existe "la manera correcta oficial" de hacer esto.**

La gente que lo hace (software comercial) usa:
- Scraping (Glow API, Selenium, etc.)
- APIs de terceros (que también hacen scraping)
- Estimaciones heurísticas (imprecisas)

Nosotros ya implementamos la mejor solución disponible: **Glow API**.

Es hora de activarla y seguir adelante con el proyecto.
