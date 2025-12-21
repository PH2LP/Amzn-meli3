# Cómo Capturar la Respuesta Sugerida de MercadoLibre (Versión 2)

## El Problema
El endpoint `/api/suggestion/{question_id}` no devuelve la respuesta directamente.
Necesitamos capturar TODAS las llamadas HTTP cuando hacés click.

## Pasos Detallados

### 1. Buscar una Pregunta con Respuesta Sugerida Disponible

1. Anda a: https://global-selling.mercadolibre.com/questions
2. Busca una pregunta que tenga el botón **"Ver respuesta sugerida"** ACTIVO
   - Si el botón está gris o dice "No hay respuesta sugerida" → NO sirve
   - Necesitamos una donde el botón esté clickeable

### 2. Preparar DevTools

1. Abrí DevTools (F12)
2. Pestaña **Network**
3. ✅ Activa **Preserve log** (para no perder las llamadas)
4. Filtra por **All** o **Fetch/XHR**
5. Click en 🚫 (Clear) para limpiar todo

### 3. Capturar TODAS las Llamadas

1. Hacé click en **"Ver respuesta sugerida"**
2. Esperá a que aparezca la respuesta (puede tardar unos segundos)
3. Cuando veas la respuesta en pantalla, revisá la pestaña Network

### 4. Buscar la Llamada Correcta

Buscá llamadas que:
- Se hayan ejecutado DESPUÉS del click
- Contengan en la URL: `suggestion`, `ai`, `answer`, `generate`, etc.
- Tengan Status 200 (exitoso)
- Tengan un Response grande (no un GIF de 1 pixel)

### 5. Revisar TODAS las Llamadas Sospechosas

Para cada llamada que parezca relevante:

**A. Request URL**
```
https://...lo que sea...
```

**B. Request Headers**
- Busca `x-csrf-token`, `Authorization`, etc.

**C. Response (IMPORTANTE)**
- Click en la pestaña **Response** o **Preview**
- ¿Ves texto/JSON?
- ¿Tiene la respuesta sugerida?

**D. Si es POST, ver el Payload**
- Click en **Payload** o **Request Payload**
- ¿Qué datos envía?

## Posibles Escenarios

### Escenario 1: Polling (múltiples requests)
La UI puede hacer:
1. POST para PEDIR la respuesta → devuelve un `request_id`
2. GET cada X segundos para VERIFICAR si está lista → devuelve la respuesta

**Si ves esto:** Busca un POST y varios GETs subsecuentes.

### Escenario 2: WebSocket
La respuesta viene por WebSocket (tiempo real).

**Si ves esto:**
- Pestaña **WS** en DevTools
- Busca mensajes que contengan la respuesta

### Escenario 3: Server-Sent Events (SSE)
Similar a WebSocket pero más simple.

**Si ves esto:**
- Busca requests de tipo `text/event-stream`

## Qué Copiar y Pegar Aquí

Una vez que encuentres la llamada correcta:

```
=== LLAMADA ENCONTRADA ===

REQUEST URL:
[pegar URL completa]

METHOD:
[GET/POST/etc]

REQUEST HEADERS:
[copiar headers importantes]

REQUEST PAYLOAD (si es POST):
[copiar body/payload]

RESPONSE:
[copiar JSON/texto completo de la respuesta]

STATUS:
[200, 206, etc]
```

## Tips Adicionales

- Si hay muchas llamadas, ordena por **Time** (más recientes arriba)
- Usa el filtro de búsqueda en Network (Ctrl+F) para buscar "suggestion"
- Si el botón dispara un modal/popup, la respuesta puede cargarse en ese momento
- Presta atención a requests a dominios diferentes (no solo api.mercadolibre.com)

---

**IMPORTANTE:** Necesitamos una pregunta donde el botón "Ver respuesta sugerida"
funcione y muestre texto. Si todas tus preguntas dicen "No hay respuesta sugerida",
entonces ML no tiene sugerencias para esos productos y necesitamos seguir
usando tu sistema actual.
