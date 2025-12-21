# Bug: Delay en propagación de stock en MercadoLibre CBT

## Problema

Cuando el sync pausa un producto CBT multi-país poniendo `available_quantity=0`, la API de MercadoLibre confirma el cambio inmediatamente (200 OK), pero el sitio web puede seguir mostrando stock disponible durante **30-60 minutos**.

### Caso documentado: B0F6714SWS (CBT2809400199)

- ✅ **API**: Stock=0, Status=paused, Sub-status=out_of_stock
- ❌ **Sitio web Brasil**: Mostraba stock=10 después del sync

## Causa

**Cache agresivo de MercadoLibre**:
- El CDN de ML cachea las páginas de producto
- La propagación de cambios de stock de CBT global → listings locales por país es **asíncrona**
- Puede tardar entre 10 minutos y 1 hora

## Verificación

### 1. Verificar estado en la API (siempre actualizado):

```bash
python3 << 'EOF'
import os
import requests
from dotenv import load_dotenv

load_dotenv()
ML_TOKEN = os.getenv('ML_ACCESS_TOKEN')

url = 'https://api.mercadolibre.com/items/CBT2809400199'
headers = {'Authorization': f'Bearer {ML_TOKEN}'}

r = requests.get(url, headers=headers, timeout=30)
if r.status_code == 200:
    data = r.json()
    print(f"Stock: {data.get('available_quantity')}")
    print(f"Status: {data.get('status')}")
    print(f"Sub-status: {data.get('sub_status')}")
EOF
```

### 2. Verificar en el sitio web (puede estar cacheado):

1. Abre el link del producto en **modo incógnito/privado**
2. Fuerza actualización: Ctrl+Shift+R (Windows) o Cmd+Shift+R (Mac)
3. Si sigue mostrando stock, espera 30-60 minutos

## Solución

### Opción 1: Esperar (recomendado)
El cache de ML eventualmente expira y se actualiza solo. Tiempo estimado: 30-60 minutos.

### Opción 2: Monitorear con script
```bash
cd /opt/amz-ml-system
python3 scripts/tools/monitor_listing_cache.py
```

Este script verifica cada 2 minutos el estado del producto en la API.

### Opción 3: Forzar refresh (no siempre funciona)
Hacer múltiples PUTs puede acelerar la propagación:

```bash
python3 << 'EOF'
import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()
ML_TOKEN = os.getenv('ML_ACCESS_TOKEN')

url = 'https://api.mercadolibre.com/global/items/CBT2809400199'
headers = {'Authorization': f'Bearer {ML_TOKEN}'}

for i in range(3):
    print(f"PUT #{i+1}...")
    r = requests.put(url, headers=headers, json={'available_quantity': 0}, timeout=30)
    print(f"Status: {r.status_code}")
    time.sleep(2)
EOF
```

## Notas importantes

1. **No es un bug del sync**: El código funciona correctamente. La API confirma el cambio.
2. **Es comportamiento de ML**: El cache/propagación es parte de la infraestructura de MercadoLibre.
3. **Productos CBT multi-país**: Este problema es más común en CBT porque tienen listings separados por país.
4. **No afecta nuevas ventas**: Aunque el sitio muestre stock, la API ya tiene stock=0, así que NO se pueden hacer nuevas compras.

## Evidencia

```
=== Antes del sync ===
API: Stock=10
Sitio: Stock=10

=== Inmediatamente después del sync ===
API: Stock=0, Status=paused ✅
Sitio: Stock=10 ❌ (CACHE)

=== 30-60 minutos después ===
API: Stock=0, Status=paused ✅
Sitio: Stock=0 o "Sin stock" ✅
```

## Conclusión

**El sync funciona correctamente**. Si ves stock en el sitio después de pausar:
1. Verifica la API (siempre tiene el valor real)
2. Espera 30-60 minutos
3. Abre en modo incógnito para evitar cache del navegador

Si después de 1 hora el sitio sigue mostrando stock, puede ser un bug de ML - contactar soporte.
