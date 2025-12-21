# Cómo Capturar la API de Respuesta Sugerida de MercadoLibre

## Objetivo
Descubrir qué endpoint y parámetros usa MercadoLibre cuando hacés click en "Ver respuesta sugerida"

## Pasos a Seguir

### 1. Preparar el Navegador
1. Abrí Chrome o Firefox
2. Presiona `F12` o `Cmd+Option+I` (Mac) para abrir DevTools
3. Ve a la pestaña **Network** (Red)
4. Activa **Preserve log** (Conservar registro)
5. Filtra por: **XHR** o **Fetch**

### 2. Ir a una Pregunta sin Responder
1. Entrá a https://www.mercadolibre.com.ar/ventas/preguntas
2. Seleccioná una pregunta que tenga el botón "Ver respuesta sugerida"
3. **ANTES de hacer click**, asegurate que la pestaña Network esté abierta

### 3. Capturar la Llamada
1. Hacé click en **"Ver respuesta sugerida"**
2. En la pestaña Network, buscá llamadas a:
   - `api.mercadolibre.com`
   - URLs que contengan: `suggest`, `ai`, `answer`, `recommendation`, etc.
3. Hacé click en cada llamada y revisá:
   - **Request URL**: La URL completa
   - **Request Headers**: Headers importantes (Authorization, etc.)
   - **Request Payload**: Datos enviados (si es POST)
   - **Response**: La respuesta que recibe

### 4. Información a Capturar

**Necesitamos:**
```
✅ URL completa del endpoint
✅ Método HTTP (GET/POST)
✅ Headers importantes (especialmente Authorization)
✅ Query parameters (si tiene)
✅ Body/Payload (si es POST)
✅ Respuesta JSON completa (para ver estructura)
```

### 5. Ejemplo de lo que Buscamos

```http
GET https://api.mercadolibre.com/questions/XXXXX/suggested-answer
Authorization: Bearer APP_USR-...
```

o

```http
POST https://api.mercadolibre.com/ai/answer-suggestion
Content-Type: application/json
Authorization: Bearer APP_USR-...

{
  "question_id": 123456,
  "item_id": "MLAxxxxx"
}
```

### 6. Cómo Compartir la Info

Una vez capturado, copia y pega:

1. **La URL completa** (Request URL)
2. **Los Headers** (clic derecho > Copy > Copy all as HAR o copia manual)
3. **El Response** (pestaña Response)

## Tips Adicionales

- Si la llamada usa websockets, revisá la pestaña **WS**
- Algunos endpoints pueden estar ofuscados o tener nombres raros
- Buscá llamadas que se hagan JUSTO cuando hacés click en el botón
- Ordená por **Time** para ver qué se ejecutó después del click

---

**Cuando tengas esta info, podemos replicar la llamada desde Python**
