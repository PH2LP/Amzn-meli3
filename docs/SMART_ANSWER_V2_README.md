# Smart Answer Engine v2.0 - Guía de Uso

## 📖 Descripción

Sistema inteligente de respuestas automáticas completamente rediseñado usando:
- **Chain-of-Thought reasoning**: Razonamiento paso a paso
- **Self-consistency**: Validación con múltiples respuestas
- **Confidence scoring**: Puntuación inteligente de confianza
- **Smart notifications**: Notificaciones solo cuando es necesario

## 🎯 Mejoras vs Sistema Anterior

| Aspecto | Sistema Anterior | Sistema v2.0 |
|---------|------------------|--------------|
| Prompt | 172 líneas de reglas | 30 líneas de principios |
| Razonamiento | Básico | Chain-of-Thought estructurado |
| Validación | Manual | Automática (contradicciones, coherencia) |
| Confidence | Básico | Multi-factor scoring |
| Notificaciones | Todo o nada | Inteligentes por contexto |
| Mantenimiento | Agregar reglas constantemente | Cero mantenimiento |
| Coherencia esperada | ~70% | >95% |

## 🚀 Instalación

No requiere instalación adicional. Usa las mismas dependencias que el sistema actual:
- `openai`
- `python-dotenv`

## 📝 Uso Básico

### Opción 1: Usar Directamente

```python
from smart_answer_engine_v2 import answer_question_v2

result = answer_question_v2(
    question="Funciona con pilas AA?",
    asin="B0BFJWCYTL",
    item_title="Producto de ejemplo",
    question_id=123456,
    customer_nickname="cliente123",
    site_id="MLA"
)

# Resultado
print(result["action"])       # "answered" o "no_answer"
print(result["answer"])        # La respuesta generada (si action="answered")
print(result["confidence"])    # 0-100
print(result["should_notify"]) # True/False
```

### Opción 2: Integración con Sistema Actual

El archivo `auto_answer_questions.py` puede usar el nuevo motor:

```python
# En auto_answer_questions.py
from smart_answer_engine_v2 import answer_question_v2

# Reemplazar la función answer_question existente
def answer_question(asin, question, ...):
    result_v2 = answer_question_v2(
        question=question,
        asin=asin,
        ...
    )

    # Adaptar al formato antiguo
    if result_v2["action"] == "answered":
        return {
            "answer": f"{SALUDO} {result_v2['answer']} {DESPEDIDA}",
            "method": "smart_v2",
            "tokens_used": 0,  # Estimar si es necesario
            "cost_usd": 0.0
        }
    else:
        # Notificar y no responder
        return {
            "answer": None,
            "method": "smart_v2_no_answer",
            "tokens_used": 0,
            "cost_usd": 0.0
        }
```

## 🔧 Configuración

Editar `CONFIG` en `smart_answer_engine_v2.py`:

```python
CONFIG = {
    "models": {
        "fast": "gpt-4o-mini",      # Para clasificación/validación (barato)
        "smart": "gpt-4o",           # Para razonamiento (balanceado)
        "genius": "o1-preview"       # Para casos complejos (caro)
    },
    "confidence_thresholds": {
        "no_answer": 70,      # < 70% = No responder
        "review": 85,         # 70-85% = Responder + notificar
        "auto": 100           # > 85% = Responder automático
    },
    "enable_self_consistency": True,    # Self-consistency para críticos
    "enable_validation": True,           # Validar contradicciones
    ...
}
```

## 📊 Estructura de Respuesta

```python
{
    "action": "answered" | "no_answer",
    "answer": "La respuesta generada" | None,
    "confidence": 87.5,  # 0-100
    "reason": "high_confidence" | "low_confidence" | "critical_question" | ...,
    "should_notify": False,
    "notification_type": "review_recommended" | "critical_question" | ...,
    "metadata": {
        "reasoning": "El razonamiento paso a paso...",
        "confidence_factors": [...]
    }
}
```

## 🎭 Casos de Uso

### 1. Pregunta Normal (Alta Confianza)

**Entrada:**
```python
question = "De qué color es?"
asin = "B0BFJWCYTL"
```

**Salida:**
```python
{
    "action": "answered",
    "answer": "Está disponible en color negro. Es un diseño elegante...",
    "confidence": 92.3,
    "should_notify": False
}
```

### 2. Pregunta Técnica Crítica

**Entrada:**
```python
question = "Funciona a 220v o necesita transformador?"
asin = "B0BFJWCYTL"
```

**Salida:**
```python
{
    "action": "no_answer",
    "reason": "critical_question",
    "should_notify": True,
    "notification_type": "critical_question",
    "metadata": {
        "critical_category": "electrical_safety"
    }
}
```

### 3. Búsqueda de Producto

**Entrada:**
```python
question = "Tenés el iPhone 15 Pro?"
asin = "B0BFJWCYTL"
```

**Salida:**
```python
{
    "action": "no_answer",
    "reason": "product_search",
    "should_notify": True,
    "notification_type": "product_search",
    "metadata": {
        "product_searched": "iPhone 15 Pro"
    }
}
```

### 4. Confianza Media (Responde + Notifica)

**Entrada:**
```python
question = "Es sumergible?"
asin = "B0BFJWCYTL"
```

**Salida:**
```python
{
    "action": "answered",
    "answer": "Tiene resistencia al agua IP67...",
    "confidence": 78.5,
    "should_notify": True,
    "notification_type": "review_recommended"
}
```

## 🧪 Testing

```bash
# Ejecutar suite de tests
python3 test_smart_answer_v2.py
```

Los tests verifican:
- ✅ Detección de búsquedas de productos
- ✅ Detección de preguntas críticas
- ✅ Generación de respuestas coherentes
- ✅ Niveles de confidence apropiados
- ✅ Decisiones de notificación correctas

## 📈 Monitoreo

El sistema genera logs detallados:

```
[2024-12-18 20:35:10] [INFO] Procesando pregunta: Funciona con pilas AA?...
[2024-12-18 20:35:10] [INFO] ASIN: B0BFJWCYTL
[2024-12-18 20:35:11] [INFO] Detectando búsqueda de producto...
[2024-12-18 20:35:11] [INFO] Búsqueda detectada: False (confidence: 95%)
[2024-12-18 20:35:12] [INFO] Detectando pregunta crítica...
[2024-12-18 20:35:12] [INFO] Extrayendo contexto inteligente para ASIN B0BFJWCYTL...
[2024-12-18 20:35:13] [INFO] mini_ml cargado: storage/logs/publish_ready/B0BFJWCYTL_mini_ml.json
[2024-12-18 20:35:15] [INFO] Contexto extraído (completeness: 0.92)
[2024-12-18 20:35:15] [INFO] Generando respuesta con razonamiento estructurado...
[2024-12-18 20:35:18] [INFO] Respuesta generada (confidence: 88%)
[2024-12-18 20:35:18] [INFO] Calculando confidence final...
[2024-12-18 20:35:18] [INFO] Confidence final: 89.2%
[2024-12-18 20:35:18] [INFO]   - Model: 88%
[2024-12-18 20:35:18] [INFO]   - Info completeness: 92.0%
[2024-12-18 20:35:18] [INFO]   - Answer length: 95.0%
[2024-12-18 20:35:18] [INFO]   - No suspicious: 100%
[2024-12-18 20:35:19] [INFO] Validando coherencia...
[2024-12-18 20:35:20] [INFO] ✅ Confidence alto (89.2%) - Responder automático
```

## 💰 Costos Estimados

```
Por pregunta respondida:
  - Clasificación: ~$0.00002 (GPT-4o-mini)
  - Extracción: ~$0.00015 (GPT-4o-mini)
  - Razonamiento: ~$0.006 (GPT-4o)
  - Validación: ~$0.00003 (GPT-4o-mini)
  ─────────────────────────────
  Total: ~$0.0064 USD/pregunta

Con 100 preguntas/día:
  - Diario: $0.64
  - Mensual: ~$19

Casos complejos con o1-preview (5%):
  - +$5/mes adicional

TOTAL MENSUAL: ~$24 USD
```

## 🔄 Migración desde Sistema Anterior

### Paso 1: Testing Paralelo (Semana 1)
```python
# Comparar respuestas de ambos sistemas
result_old = answer_question_old(...)
result_new = answer_question_v2(...)

# Usar resultado antiguo pero loggear el nuevo
log_comparison(result_old, result_new)
```

### Paso 2: Rollout Gradual (Semana 2-3)
```python
import random

if random.random() < 0.5:  # 50% de preguntas
    result = answer_question_v2(...)
else:
    result = answer_question_old(...)
```

### Paso 3: Migración Completa (Semana 4)
```python
# Usar solo sistema nuevo
result = answer_question_v2(...)
```

## ⚙️ Personalización

### Agregar Nuevas Categorías Críticas

```python
# En smart_answer_engine_v2.py
CRITICAL_TOPICS = {
    "electrical_safety": [...],
    "health_safety": [...],
    "mi_categoria_nueva": [
        "keyword1",
        "keyword2",
        ...
    ]
}
```

### Ajustar Thresholds de Confidence

```python
CONFIG = {
    "confidence_thresholds": {
        "no_answer": 60,    # Más permisivo (responde más)
        "review": 80,
        "auto": 100
    }
}
```

### Deshabilitar Self-Consistency (más rápido, menos preciso)

```python
CONFIG = {
    "enable_self_consistency": False
}
```

## 🐛 Troubleshooting

### Problema: Muchas notificaciones de "low_confidence"

**Solución:** Reducir threshold o verificar que los productos tengan información completa.

```python
CONFIG["confidence_thresholds"]["no_answer"] = 60  # en vez de 70
```

### Problema: Respuestas muy largas o muy cortas

**Solución:** Ajustar en el prompt o aumentar/reducir max_tokens.

```python
CONFIG["max_tokens_reasoning"] = 800  # Reducir si muy largo
```

### Problema: No detecta búsquedas de productos

**Solución:** Revisar el prompt de detección o agregar ejemplos específicos.

## 📞 Soporte

- Archivo de backup: `backups/auto_answer_backup_20251218/`
- Logs: Habilitados por defecto en stdout
- Tests: `python3 test_smart_answer_v2.py`

## 🎯 Roadmap Futuro

- [ ] Dashboard de métricas en tiempo real
- [ ] A/B testing automático
- [ ] Fine-tuning de GPT-4o con respuestas aprobadas
- [ ] Integración con sistema de tickets
- [ ] API REST para otros servicios
- [ ] Análisis de sentimiento en preguntas
- [ ] Detección de urgencia/prioridad

---

**Versión:** 2.0
**Fecha:** Diciembre 2024
**Autor:** Sistema mejorado con ingeniería de prompts avanzada
