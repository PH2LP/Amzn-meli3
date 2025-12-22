# Amazon Videos API - Extracción de Videos de Productos

## ✅ SOLUCIÓN ENCONTRADA

Se creó una función que extrae **TODOS los videos de un ASIN** (listing + customer videos) parseando el HTML de la página de producto.

## 📁 Archivos Creados

1. **`src/integrations/amazon_videos_api.py`** - Función principal
2. **`scripts/research/test_get_videos.py`** - Script de prueba/ejemplo

## 🚀 Uso Rápido

```python
from src.integrations.amazon_videos_api import get_product_videos

# Obtener videos de un ASIN
result = get_product_videos("B09X7MPX8L")

print(f"Total videos: {result['total_videos']}")
print(f"Listing videos: {len(result['listing_videos'])}")
print(f"Customer videos: {len(result['customer_videos'])}")

# Acceder a los videos
for video in result['all_videos']:
    print(f"- {video['title']}")
    print(f"  URL: {video['url']}")
    print(f"  Duración: {video['duration_seconds']}s")
```

## 📊 Respuesta de la Función

```python
{
    "asin": "B0C683F516",
    "total_videos": 9,
    "listing_videos": [...],  // Todos los listing videos
    "customer_videos": [...],  // Todos los customer videos
    "listing_horizontal": [  // Listing videos horizontales
        {
            "title": "Arlo Video Doorbell (2nd Generation)",
            "url": "https://m.media-amazon.com/images/S/vse-vms-transcoding-artifact-us-east-1-prod/.../default.jobtemplate.hls.m3u8",
            "duration_seconds": 30,
            "thumbnail": "https://m.media-amazon.com/images/I/61FmwyBZ-HL.SS40_BG85,85,85_BR-120_PKdp-play-icon-overlay__.jpg",
            "content_id": "amzn1.vse.video.xxx",
            "group_type": "IB_G1",
            "orientation": "horizontal",
            "creator_profile": {}
        }
    ],
    "listing_vertical": [],  // Listing videos verticales (si hay)
    "customer_horizontal": [  // Customer videos horizontales
        {
            "title": "My Front Door Camera Review",
            "url": "https://m.media-amazon.com/images/S/vse-vms-transcoding-artifact-us-east-1-prod/.../default.jobtemplate.hls.m3u8",
            "duration_seconds": 80,
            "thumbnail": "https://m.media-amazon.com/images/I/A1V0rBvqdCL.SS40_BG85,85,85_BR-120_PKdp-play-icon-overlay__.png",
            "content_id": "amzn1.vse.video.xxx",
            "group_type": "IB_G2",
            "orientation": "horizontal",
            "creator_profile": {}
        }
    ],
    "customer_vertical": [  // Customer videos verticales
        {
            "title": "Watch me catch a thief on my Arlo doorbell camera",
            "url": "https://m.media-amazon.com/images/S/vse-vms-transcoding-artifact-us-east-1-prod/.../default.vertical.jobtemplate.hls.m3u8",
            "duration_seconds": 55,
            "thumbnail": "https://m.media-amazon.com/images/I/81NSZWAGIUL.SS40_BG85,85,85_BR-120_PKdp-play-icon-overlay__.jpg",
            "content_id": "amzn1.vse.video.xxx",
            "group_type": "IB_G2",
            "orientation": "vertical",
            "creator_profile": {}
        }
    ],
    "all_videos": [...],  // Todos combinados
    "error": null
}
```

## 🎬 Tipos de Videos

### Por Origen:
1. **Listing Videos (IB_G1)**: Videos del seller/brand en el listing principal
2. **Customer Videos (IB_G2)**: Videos subidos por customers en reviews

### Por Orientación:
1. **Horizontal (🖥️)**: Videos en formato landscape (tradicional, YouTube)
2. **Vertical (📱)**: Videos en formato portrait (móvil, TikTok, Reels, Stories)

### Categorías Combinadas:
- `listing_horizontal`: Videos del seller en formato horizontal
- `listing_vertical`: Videos del seller en formato vertical
- `customer_horizontal`: Reviews en formato horizontal
- `customer_vertical`: Reviews en formato vertical

## 🔍 Cómo Funciona

1. **Evita CAPTCHA**: Primero visita la homepage para obtener cookies
2. **Descarga el HTML**: GET de la página de producto
3. **Parsea JSON embebido**: Amazon incluye un array JSON con todos los videos en el HTML
4. **Extrae metadata**: Título, URL, duración, thumbnail, creator info, etc.

## ⚡ Performance

- **Tiempo**: ~3-4 segundos por ASIN
- **No requiere**: Selenium, ChromeDriver, ni navegador headless
- **Solo usa**: requests + HTML parsing

## 📝 Ejemplo de Ejecución

```bash
# Test con el script de ejemplo
python3 scripts/research/test_get_videos.py B09X7MPX8L

# O importar directamente
python3 -c "
from src.integrations.amazon_videos_api import get_product_videos
result = get_product_videos('B09X7MPX8L')
print(f'Videos: {result[\"total_videos\"]}')
"
```

## 🎯 Casos de Uso

### 1. Verificar si un producto tiene videos

```python
result = get_product_videos(asin)
if result['total_videos'] > 0:
    print(f"✅ Tiene {result['total_videos']} videos")
else:
    print("❌ No tiene videos")
```

### 2. Obtener solo listing videos

```python
result = get_product_videos(asin)
for video in result['listing_videos']:
    print(f"Listing video: {video['title']}")
```

### 3. Obtener solo customer videos

```python
result = get_product_videos(asin)
for video in result['customer_videos']:
    print(f"Customer video: {video['title']}")
```

### 4. Obtener solo videos verticales (para TikTok/Reels)

```python
result = get_product_videos(asin)

# Todos los verticales (listing + customer)
all_vertical = result['listing_vertical'] + result['customer_vertical']

for video in all_vertical:
    print(f"📱 {video['title']} ({video['duration_seconds']}s)")
```

### 5. Obtener solo videos horizontales (para YouTube)

```python
result = get_product_videos(asin)

# Todos los horizontales (listing + customer)
all_horizontal = result['listing_horizontal'] + result['customer_horizontal']

for video in all_horizontal:
    print(f"🖥️  {video['title']} ({video['duration_seconds']}s)")
```

### 6. Filtrar por tipo Y orientación

```python
result = get_product_videos(asin)

# Solo customer reviews en formato vertical
for video in result['customer_vertical']:
    print(f"Customer review vertical: {video['title']}")

# Solo listing videos en formato horizontal
for video in result['listing_horizontal']:
    print(f"Listing video horizontal: {video['title']}")
```

### 7. Descargar videos

```python
import requests

result = get_product_videos(asin)
for i, video in enumerate(result['all_videos']):
    # Los videos están en formato HLS (.m3u8)
    # Se pueden descargar con ffmpeg o reproductores HLS
    print(f"Video URL: {video['url']}")

    # Para descargar con ffmpeg:
    # ffmpeg -i "{video['url']}" -c copy "video_{i}.mp4"
```

## ⚠️ Limitaciones

1. **CAPTCHA**: Si Amazon detecta muchas requests, puede mostrar CAPTCHA
   - Solución: Agregar delays entre requests o usar proxies/rotating IPs
2. **Formato HLS**: Los videos están en formato .m3u8 (HLS streaming)
   - Se pueden reproducir directamente en navegador o descargar con ffmpeg
3. **Productos sin videos**: Algunos productos no tienen videos
   - La función retorna `total_videos: 0` sin error

## 🔧 Troubleshooting

### Error: CAPTCHA detected

```python
result = get_product_videos(asin)
if result['error'] == "CAPTCHA detected":
    # Esperar más tiempo entre requests
    time.sleep(5)
    result = get_product_videos(asin)
```

### Error: HTTP 404

El ASIN no existe o no está disponible en Amazon.com

### No videos encontrados

```python
result = get_product_videos(asin)
if result['total_videos'] == 0:
    print("Este producto no tiene videos")
```

## 🎓 Metadata de Videos

Cada video incluye:

- **title**: Título del video
- **url**: URL del video (formato HLS .m3u8)
- **duration_seconds**: Duración en segundos
- **thumbnail**: URL de la imagen de preview
- **content_id**: ID único de Amazon (amzn1.vse.video.xxx)
- **group_type**: IB_G1 (listing) o IB_G2 (customer)
- **creator_profile**: Información del creator (si es customer video)

## 📞 API Interna de Amazon

La función NO usa ninguna API pública de Amazon, sino que parsea el HTML que Amazon genera para la página de producto.

Amazon incluye un array JSON embebido en el HTML con toda la metadata de videos:

```javascript
"videos": [
    {
        "title": "...",
        "url": "...",
        "durationSeconds": 37,
        "groupType": "IB_G1",
        // ... más campos
    }
]
```

Este JSON es usado por el frontend de Amazon para renderizar la galería de videos.

## ✅ Conclusión

**SÍ es posible obtener videos de productos Amazon** (listing + customers) sin usar Selenium ni APIs oficiales, parseando el HTML de la página de producto.

La función `get_product_videos()` está lista para usarse en producción.
