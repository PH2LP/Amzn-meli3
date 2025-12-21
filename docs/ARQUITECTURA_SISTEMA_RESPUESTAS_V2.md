# Arquitectura del Sistema de Respuestas Inteligente v2.0

## 🎯 Objetivos del Sistema

1. **Coherencia 95%+**: Respuestas siempre coherentes con el producto
2. **Información Completa**: Usar toda la info disponible del producto
3. **Notificación Inteligente**: Avisar cuando realmente no puede responder
4. **Detección de Búsquedas**: Identificar cuando piden productos específicos
5. **Cero Mantenimiento**: No requiere agregar reglas nuevas

## 🏗️ Arquitectura General

```
┌─────────────────────────────────────────────────────────────┐
│                    PREGUNTA ENTRANTE                         │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  FASE 0: CLASIFICACIÓN INICIAL (GPT-4o-mini - rápido/barato)│
│  ¿Es búsqueda de producto? ¿Es pregunta técnica crítica?    │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
        ┌──────────────┴──────────────┐
        ↓                              ↓
   ES BÚSQUEDA                    ES PREGUNTA NORMAL
        │                              ↓
        │              ┌───────────────────────────────────────┐
        │              │ FASE 1: EXTRACCIÓN DE INFORMACIÓN     │
        │              │ - Preparar contexto del producto      │
        │              │ - Identificar info relevante          │
        │              │ - Calcular "confidence score"         │
        │              └─────────────┬─────────────────────────┘
        │                            ↓
        │              ┌───────────────────────────────────────┐
        │              │ FASE 2: RAZONAMIENTO (GPT-4o/o1)     │
        │              │ - Chain-of-Thought paso a paso        │
        │              │ - Generar respuesta con razonamiento  │
        │              │ - Auto-validación                     │
        │              └─────────────┬─────────────────────────┘
        │                            ↓
        │              ┌───────────────────────────────────────┐
        │              │ FASE 3: VALIDACIÓN Y REFINAMIENTO    │
        │              │ - Verificar coherencia                │
        │              │ - Detectar contradicciones            │
        │              │ - Self-consistency (críticos)         │
        │              └─────────────┬─────────────────────────┘
        │                            ↓
        │                     ¿Confidence > 80%?
        │                            │
        │                ┌───────────┴───────────┐
        │                ↓                       ↓
        │              SÍ                       NO
        │                │                       │
        ↓                ↓                       ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐
│ NOTIFICAR    │  │ RESPONDER    │  │ NOTIFICAR + NO       │
│ TELEGRAM     │  │ AL CLIENTE   │  │ RESPONDER            │
│ (búsqueda)   │  │              │  │ (info insuficiente)  │
└──────────────┘  └──────────────┘  └──────────────────────┘
```

## 📦 FASE 1: Extracción de Información del Producto

### Objetivo
Preparar un contexto rico, relevante y estructurado del producto.

### Fuentes de Datos (en orden de prioridad)

```python
Prioridad 1: mini_ml.json
  ✅ Más compacto
  ✅ Ya procesado/limpio
  ✅ Información específica para ML

Prioridad 2: amazon_json (SP-API)
  ✅ Información completa de Amazon
  ✅ Bullet points, specs, etc
  ⚠️  Más verboso

Prioridad 3: Descargar de Amazon
  ⚠️  Solo si no existe
  ⚠️  Más lento
```

### Estructura del Contexto Preparado

```json
{
  "product_identity": {
    "title": "...",
    "brand": "...",
    "category": "...",
    "product_type": "smartwatch|doorbell|microphone|etc"
  },

  "specifications": {
    // Top 15 specs más relevantes
    "battery": "rechargeable lithium-ion",
    "connectivity": "Bluetooth 5.0, WiFi",
    "water_resistance": "IP67",
    ...
  },

  "features": [
    // Top 10 features más importantes
    "Heart rate monitoring",
    "Sleep tracking",
    ...
  ],

  "what_it_does": "...", // Explicación simple del propósito
  "key_highlights": [...], // 3-5 puntos clave

  "dimensions_and_package": {
    "weight": "...",
    "dimensions": "...",
    "whats_included": [...]
  },

  "info_completeness": {
    "has_full_specs": true,
    "has_description": true,
    "has_features": true,
    "confidence_level": 0.95
  }
}
```

### Algoritmo de Extracción Inteligente

```python
def extract_smart_context(asin):
    """
    Extrae información del producto de forma inteligente.
    """

    # 1. Cargar datos disponibles
    mini_ml = load_mini_ml(asin)
    amazon_json = load_amazon_json(asin)

    if not mini_ml and not amazon_json:
        # Último recurso: descargar de Amazon
        amazon_json = download_from_amazon(asin)

    # 2. Usar GPT-4o-mini para ANALIZAR y EXTRAER
    # (No solo copiar, sino ENTENDER qué es el producto)

    extraction_prompt = f"""
    Analiza este producto y extrae información estructurada.

    Datos disponibles:
    {json.dumps(mini_ml or amazon_json, ensure_ascii=False)[:3000]}

    Tu trabajo:
    1. Identifica QUÉ tipo de producto es (categoría real de uso)
    2. Extrae las 10 características MÁS IMPORTANTES
    3. Extrae especificaciones técnicas clave
    4. Resume en 1 línea: "Para qué sirve este producto"

    Responde en JSON:
    {{
      "product_type": "tipo específico",
      "purpose": "para qué sirve",
      "top_features": [...],
      "key_specs": {{...}},
      "completeness_score": 0.0-1.0
    }}
    """

    # Llamada a GPT-4o-mini (barato, ~$0.0001)
    extracted = call_gpt_mini(extraction_prompt)

    return extracted
```

### Ventajas de Este Enfoque

1. **Inteligente**: No solo copia datos, ENTIENDE el producto
2. **Relevante**: Filtra lo importante vs ruido
3. **Estructurado**: Formato consistente para razonamiento
4. **Con Confidence**: Sabe cuánta info tiene

## 🧠 FASE 2: Sistema de Razonamiento Chain-of-Thought

### Modelo Recomendado: GPT-4o (o o1-preview para casos complejos)

**Por qué GPT-4o:**
- Excelente razonamiento
- Buen balance costo/calidad
- ~$0.005 por 1K tokens (aceptable)

**Cuándo usar o1-preview:**
- Preguntas muy técnicas
- Múltiples sub-preguntas
- Cuando confidence < 60%
- ~$15 por 1M tokens (10x más caro pero más inteligente)

### Prompt Principal con Chain-of-Thought

```python
REASONING_PROMPT = """
Eres un asistente de ventas experto respondiendo preguntas de clientes.

INFORMACIÓN DEL PRODUCTO:
{product_context}

PREGUNTA DEL CLIENTE:
{question}

───────────────────────────────────────────────────────────────

PIENSA PASO A PASO (usa <thinking> tags):

<thinking>
PASO 1 - ENTENDER EL PRODUCTO:
- ¿Qué tipo de producto es?
- ¿Para qué se usa normalmente?
- ¿Cuáles son sus características principales?

PASO 2 - ENTENDER LA PREGUNTA:
- ¿Qué quiere saber realmente el cliente?
- ¿Por qué pregunta esto? (motivación)
- ¿Qué info necesita para decidir comprar?

PASO 3 - BUSCAR LA INFORMACIÓN:
- ¿Tengo la información que necesita?
- ¿Dónde está esa info en el contexto?
- ¿Hay info adicional relevante?

PASO 4 - EVALUAR CONFIANZA:
- ¿Puedo responder con certeza?
- ¿O necesito que el vendedor verifique?
- Nivel de confianza: [0-100]%

PASO 5 - PLANEAR LA RESPUESTA:
- ¿Cómo presentar la info de forma útil?
- ¿Qué tono usar? (informativo/persuasivo/técnico)
- ¿Algo positivo para destacar?
</thinking>

AHORA GENERA LA RESPUESTA:

<response>
[Tu respuesta aquí: 2-4 líneas, tono amigable y profesional]
</response>

<confidence>
[Tu nivel de confianza: 0-100]
</confidence>

<reasoning_summary>
[Breve resumen de por qué respondiste así]
</reasoning_summary>

REGLAS CRÍTICAS:
- NUNCA inventes información que no está en el contexto
- Si no tienes la info, di confidence=0 para que se notifique
- Sé positivo pero honesto
- No uses lenguaje robótico o templates
- Contextualiza según el tipo de producto
"""
```

### Procesamiento de la Respuesta

```python
def generate_smart_answer(question, product_context):
    """
    Genera respuesta con razonamiento estructurado.
    """

    # 1. Preparar prompt con contexto
    prompt = REASONING_PROMPT.format(
        product_context=json.dumps(product_context, ensure_ascii=False, indent=2),
        question=question
    )

    # 2. Llamar a GPT-4o con razonamiento
    response = openai.chat.completions.create(
        model="gpt-4o",  # o "o1-preview" para casos complejos
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=800,
        temperature=0.3  # Más determinístico
    )

    full_output = response.choices[0].message.content

    # 3. Parsear respuesta estructurada
    parsed = parse_structured_response(full_output)

    return {
        "answer": parsed["response"],
        "confidence": parsed["confidence"],
        "reasoning": parsed["reasoning_summary"],
        "thinking": parsed["thinking"]  # Para debugging
    }
```

## ✅ FASE 3: Validación y Control de Calidad

### Sistema de Confidence Scoring

```python
def calculate_final_confidence(result, product_context):
    """
    Calcula confianza final considerando múltiples factores.
    """

    confidence_factors = []

    # Factor 1: Confidence del modelo
    model_confidence = result["confidence"]
    confidence_factors.append(("model", model_confidence, 0.5))

    # Factor 2: Completitud de la información del producto
    info_completeness = product_context["info_completeness"]["confidence_level"]
    confidence_factors.append(("info", info_completeness * 100, 0.2))

    # Factor 3: Longitud de respuesta (muy corta = sospechoso)
    answer_length = len(result["answer"].split())
    length_score = min(100, (answer_length / 20) * 100)  # 20 palabras = 100%
    confidence_factors.append(("length", length_score, 0.1))

    # Factor 4: No hay palabras sospechosas
    suspicious_words = ["no tengo", "consulta", "verificar", "no especifica"]
    has_suspicious = any(word in result["answer"].lower() for word in suspicious_words)
    suspicious_score = 0 if has_suspicious else 100
    confidence_factors.append(("no_suspicious", suspicious_score, 0.2))

    # Calcular weighted average
    final_confidence = sum(score * weight for _, score, weight in confidence_factors)

    return {
        "final_confidence": final_confidence,
        "breakdown": confidence_factors
    }
```

### Self-Consistency (para preguntas críticas)

```python
def apply_self_consistency(question, product_context, n=3):
    """
    Genera N respuestas y selecciona la más consistente.
    Usar solo para preguntas críticas (voltaje, compatibilidad, etc).
    """

    responses = []

    # Generar N respuestas con temperatura ligeramente diferente
    for i in range(n):
        response = generate_smart_answer(
            question,
            product_context,
            temperature=0.2 + (i * 0.1)  # 0.2, 0.3, 0.4
        )
        responses.append(response)

    # Usar GPT-4o para seleccionar la más consistente y precisa
    consistency_prompt = f"""
    Analiza estas {n} respuestas a la misma pregunta:

    Pregunta: {question}

    Respuestas:
    {json.dumps([r["answer"] for r in responses], indent=2)}

    ¿Cuál es la MÁS PRECISA y CONSISTENTE?
    Responde con el número (0, 1, 2) y por qué.
    """

    selection = call_gpt_mini(consistency_prompt)
    best_index = extract_number(selection)

    return responses[best_index]
```

### Detección de Contradicciones

```python
def check_contradictions(answer, product_context):
    """
    Verifica que la respuesta no se contradiga.
    """

    validation_prompt = f"""
    Producto: {product_context["product_identity"]["title"]}
    Respuesta generada: "{answer}"

    Verifica:
    1. ¿Hay contradicciones internas? (ej: "Sí... pero no")
    2. ¿Es coherente con el tipo de producto?
    3. ¿El tono es apropiado para ventas?

    Responde JSON:
    {{
      "has_contradictions": true/false,
      "issues": ["lista de problemas"],
      "is_coherent": true/false,
      "score": 0-100
    }}
    """

    validation = call_gpt_mini(validation_prompt)
    return validation
```

## 🔍 FASE 0: Clasificación y Detección

### Detectar Búsquedas de Productos

```python
def detect_product_search(question, item_context=None):
    """
    Detecta si el cliente está buscando un producto específico.
    Mejorado con razonamiento.
    """

    detection_prompt = f"""
    Analiza esta pregunta y determina si el cliente está BUSCANDO un producto específico
    que NO es el producto actual en la publicación.

    Pregunta: "{question}"
    Producto actual: {item_context.get("title") if item_context else "N/A"}

    Ejemplos de BÚSQUEDA:
    - "Tenés el modelo XYZ?"
    - "Vendés auriculares Sony?"
    - "Cuánto sale el iPhone 15?"

    Ejemplos de NO BÚSQUEDA:
    - "De qué color es?"
    - "Funciona con pilas?"
    - "Cuánto cuesta?" (pregunta sobre el producto actual)

    Responde JSON:
    {{
      "is_product_search": true/false,
      "product_mentioned": "nombre del producto buscado o null",
      "confidence": 0-100,
      "reasoning": "breve explicación"
    }}
    """

    result = call_gpt_mini(detection_prompt)
    return result
```

### Detectar Preguntas Técnicas Críticas

```python
CRITICAL_TOPICS = {
    "electrical_safety": [
        "voltaje", "voltage", "110v", "220v", "transformador",
        "transformer", "se quema", "burn", "electricidad"
    ],
    "health_safety": [
        "alergias", "allergic", "tóxico", "toxic", "seguro para niños",
        "safe for children", "fda approved"
    ],
    "legal_compliance": [
        "certificación", "certification", "garantía", "warranty",
        "anatel", "homologado", "approved"
    ]
}

def is_critical_question(question):
    """
    Detecta preguntas que requieren información precisa del fabricante.
    """

    question_lower = question.lower()

    for category, keywords in CRITICAL_TOPICS.items():
        for keyword in keywords:
            if keyword in question_lower:
                return {
                    "is_critical": True,
                    "category": category,
                    "reason": f"Pregunta sobre {category}"
                }

    return {"is_critical": False}
```

## 📢 Sistema de Notificaciones Inteligente

### Cuándo Notificar

```python
NOTIFICATION_RULES = {
    "product_search": {
        "notify": True,
        "respond": False,
        "reason": "Cliente busca producto específico"
    },
    "critical_question": {
        "notify": True,
        "respond": False,
        "reason": "Pregunta técnica crítica (seguridad/legal)"
    },
    "low_confidence": {
        "notify": True,
        "respond": False,
        "threshold": 70,
        "reason": "Información insuficiente para responder con seguridad"
    },
    "medium_confidence": {
        "notify": True,
        "respond": True,
        "threshold": 85,
        "reason": "Respuesta generada pero requiere revisión"
    },
    "high_confidence": {
        "notify": False,
        "respond": True,
        "threshold": 100,
        "reason": "Respuesta confiable"
    }
}
```

### Mejorar Notificaciones Telegram

```python
def send_smart_notification(
    question_id,
    question_text,
    notification_type,
    context
):
    """
    Notificación inteligente con contexto completo.
    """

    if notification_type == "product_search":
        message = f"""
🔍 <b>BÚSQUEDA DE PRODUCTO</b>

👤 Cliente: {context['customer']}
💬 Pregunta: "{question_text}"

🎯 Producto buscado: {context['product_searched']}
📊 Confidence: {context['confidence']}%

📱 <a href="{context['question_url']}">Responder manualmente</a>
        """

    elif notification_type == "low_confidence":
        message = f"""
⚠️ <b>PREGUNTA COMPLEJA - Respuesta Manual Requerida</b>

👤 Cliente: {context['customer']}
💬 Pregunta: "{question_text}"

❓ Razón: {context['reason']}
📊 Confidence: {context['confidence']}%

💡 Razonamiento del sistema:
{context['reasoning'][:200]}...

🔗 ASIN: {context['asin']}
📱 <a href="{context['question_url']}">Responder manualmente</a>
        """

    elif notification_type == "medium_confidence":
        message = f"""
✅ <b>RESPUESTA GENERADA - Revisión Recomendada</b>

👤 Cliente: {context['customer']}
💬 Pregunta: "{question_text}"

🤖 Respuesta generada:
"{context['generated_answer']}"

📊 Confidence: {context['confidence']}%
⚠️ Revisa antes de 24h para ajustar si es necesario

📱 <a href="{context['question_url']}">Ver en ML</a>
        """

    send_telegram_message(message)
```

## 🎯 Flujo Completo - Ejemplo

```python
def answer_question_v2(question, asin, question_id, customer, site_id):
    """
    Sistema completo de respuestas v2.0
    """

    # PASO 0: Clasificación inicial
    search_detection = detect_product_search(question)

    if search_detection["is_product_search"] and search_detection["confidence"] > 80:
        send_smart_notification(
            question_id, question, "product_search",
            context={"product_searched": search_detection["product_mentioned"], ...}
        )
        return {"action": "no_answer", "reason": "product_search"}

    critical = is_critical_question(question)
    if critical["is_critical"]:
        send_smart_notification(
            question_id, question, "critical_question",
            context={"category": critical["category"], ...}
        )
        return {"action": "no_answer", "reason": "critical"}

    # PASO 1: Extracción de información
    product_context = extract_smart_context(asin)

    # PASO 2: Generar respuesta con razonamiento
    result = generate_smart_answer(question, product_context)

    # PASO 3: Calcular confidence final
    confidence_analysis = calculate_final_confidence(result, product_context)
    final_confidence = confidence_analysis["final_confidence"]

    # PASO 4: Validar (solo si confidence > 50%)
    if final_confidence > 50:
        validation = check_contradictions(result["answer"], product_context)
        if not validation["is_coherent"]:
            final_confidence = final_confidence * 0.7  # Penalizar

    # PASO 5: Self-consistency para preguntas importantes
    if critical["category"] in ["electrical_safety"] and final_confidence < 90:
        result = apply_self_consistency(question, product_context, n=3)
        final_confidence = min(95, final_confidence + 10)  # Boost por self-consistency

    # PASO 6: Decidir acción
    if final_confidence < 70:
        # NO responder, notificar
        send_smart_notification(
            question_id, question, "low_confidence",
            context={
                "confidence": final_confidence,
                "reasoning": result["reasoning"],
                ...
            }
        )
        return {"action": "no_answer", "reason": "low_confidence"}

    elif final_confidence < 85:
        # Responder PERO notificar para revisión
        send_smart_notification(
            question_id, question, "medium_confidence",
            context={
                "generated_answer": result["answer"],
                "confidence": final_confidence,
                ...
            }
        )
        post_answer_to_ml(question_id, result["answer"])
        return {"action": "answered", "confidence": "medium"}

    else:
        # Responder con confianza, NO notificar
        post_answer_to_ml(question_id, result["answer"])
        return {"action": "answered", "confidence": "high"}
```

## 💰 Análisis de Costos

### Estimación por Pregunta

```
FASE 0: Clasificación (GPT-4o-mini)
  - Input: ~200 tokens
  - Output: ~100 tokens
  - Costo: ~$0.00002

FASE 1: Extracción (GPT-4o-mini)
  - Input: ~1500 tokens
  - Output: ~300 tokens
  - Costo: ~$0.00015

FASE 2: Razonamiento (GPT-4o)
  - Input: ~800 tokens
  - Output: ~400 tokens
  - Costo: ~$0.006

FASE 3: Validación (GPT-4o-mini)
  - Input: ~300 tokens
  - Output: ~100 tokens
  - Costo: ~$0.00003

──────────────────────────────
TOTAL POR PREGUNTA: ~$0.0064 USD
──────────────────────────────

Con 100 preguntas/día:
  - Costo diario: $0.64
  - Costo mensual: ~$19

Casos con o1-preview (5% de casos):
  - Costo por pregunta: ~$0.03
  - Impact mensual: +$5

COSTO TOTAL MENSUAL: ~$24 USD
```

### ROI
- Costo actual: ~$5/mes (pero respuestas malas)
- Costo nuevo: ~$24/mes (respuestas excelentes)
- **Inversión adicional: $19/mes**
- **Beneficio: Ventas no perdidas por respuestas malas = invaluable**

## 📊 Métricas de Éxito

### Tracking Automático

```python
METRICS = {
    "total_questions": 0,
    "answered_automatically": 0,
    "notified_product_search": 0,
    "notified_critical": 0,
    "notified_low_confidence": 0,
    "average_confidence": 0.0,
    "contradictions_detected": 0,
    "self_consistency_applied": 0
}
```

### Objetivos

```
Mes 1 (implementación):
  - Answered automatically: >70%
  - Average confidence: >80%
  - Contradictions: <2%

Mes 2 (optimización):
  - Answered automatically: >85%
  - Average confidence: >85%
  - Contradictions: <1%

Mes 3 (madurez):
  - Answered automatically: >90%
  - Average confidence: >90%
  - Contradictions: <0.5%
```

## 🚀 Plan de Implementación

### Semana 1: Core
- [ ] Sistema de extracción de información
- [ ] Prompt Chain-of-Thought básico
- [ ] Confidence scoring
- [ ] Tests unitarios

### Semana 2: Validación
- [ ] Detección de contradicciones
- [ ] Self-consistency
- [ ] Mejora de clasificación inicial
- [ ] Tests de integración

### Semana 3: Notificaciones
- [ ] Sistema de notificaciones mejorado
- [ ] Dashboard de métricas
- [ ] Logging detallado
- [ ] Documentación

### Semana 4: Producción
- [ ] Deploy gradual (10% tráfico)
- [ ] Monitoreo activo
- [ ] Ajustes basados en datos reales
- [ ] Rollout completo

---

**Próximo paso:** Implementar el código completo.
