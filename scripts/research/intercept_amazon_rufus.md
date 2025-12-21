# INTERCEPTAR ENDPOINTS DE AMAZON RUFUS

## Objetivo
Descubrir los endpoints no documentados que usa Amazon Rufus para hacer preguntas sobre productos.

## Método 1: mitmproxy (Recomendado)

### Requisitos
- mitmproxy instalado
- iPhone/Android con app de Amazon
- Misma red WiFi

### Pasos

1. **Instalar mitmproxy**
```bash
brew install mitmproxy
# o
pip install mitmproxy
```

2. **Iniciar proxy**
```bash
mitmweb --set block_global=false
```

Esto abrirá un servidor web en http://localhost:8081

3. **Configurar certificado en el móvil**

En tu iPhone/Android:
- Ve a WiFi → Configurar proxy manual
- Servidor: [IP de tu Mac]
- Puerto: 8080
- Visita http://mitm.it e instala el certificado

4. **Abrir Amazon app y usar Rufus**

- Abre la app de Amazon
- Ve a cualquier producto
- Abre Rufus (icono del chat)
- Haz una pregunta como "¿Este producto es resistente al agua?"

5. **Filtrar tráfico relevante**

En mitmweb, busca requests que contengan:
- `rufus`
- `chat`
- `assistant`
- `conversation`
- `genai`
- `ai`

### Qué buscar en las requests

```
🔍 Headers importantes:
- x-api-key
- x-amz-access-token
- x-requested-with
- user-agent

🔍 URL patterns:
- /rufus/*
- /assistant/*
- /chat/*
- /genai/*
- /conversation/*

🔍 Body payload:
{
  "asin": "B00XXXXX",
  "question": "...",
  "conversationId": "...",
  "sessionId": "..."
}
```

## Método 2: Charles Proxy (Más visual)

1. Descargar Charles Proxy (trial 30 días)
2. Configurar proxy en móvil
3. Instalar certificado SSL
4. Usar Rufus en la app
5. Buscar requests con filtro "rufus" o "ai"

## Método 3: Android Studio (Solo Android)

Si tienes un Android:

```bash
# Conectar dispositivo
adb devices

# Iniciar Network Profiler
# Android Studio → View → Tool Windows → App Inspection → Network Inspector
```

## Próximos pasos una vez descubierto el endpoint

Una vez que identifiquemos el endpoint, podemos:

1. **Replicar la request en Python**
```python
import requests

def ask_rufus(asin, question):
    url = "https://ENDPOINT_DESCUBIERTO"
    headers = {
        "x-api-key": "...",
        # otros headers
    }
    payload = {
        "asin": asin,
        "question": question
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()
```

2. **Integrar con tu sistema**
```python
# En telegram_sales_notifier.py
def get_product_qa(asin):
    """Obtiene respuestas inteligentes sobre el producto"""
    questions = [
        "¿Cuáles son las principales características?",
        "¿Es de buena calidad?",
        "¿Hay quejas comunes?"
    ]

    answers = []
    for q in questions:
        answer = ask_rufus(asin, q)
        answers.append(answer)

    return answers
```

## Limitaciones y consideraciones

⚠️ **Importante:**
- Esto puede violar los términos de servicio de Amazon
- Los endpoints pueden cambiar sin aviso
- Puede haber rate limiting
- Amazon podría bloquear el acceso si detecta uso automatizado

## Alternativa legal: Contactar Amazon

Si esto es para un producto/servicio comercial, considera:
- Contactar Amazon Developer Relations
- Solicitar acceso a beta de APIs de IA
- Unirte al Amazon Affiliate Program (pueden tener más acceso)
