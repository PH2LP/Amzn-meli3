# 🤖 SISTEMA DE RESPUESTAS AUTOMÁTICAS PARA MERCADOLIBRE

Sistema inteligente diseñado para **minimizar el uso de tokens** mientras responde preguntas de clientes automáticamente.

---

## 🎯 FILOSOFÍA: MÍNIMO USO DE TOKENS

El sistema sigue una estrategia de **"cascada"** desde lo más barato a lo más caro:

```
1. Caché de respuestas (GRATIS) ✅
   ↓ (si no encuentra)
2. Clasificación con regex (GRATIS) ✅
   ↓ (si no clasifica)
3. Respuestas template (GRATIS) ✅
   ↓ (solo si es necesario)
4. IA con contexto mínimo (CARO) 💰
```

---

## 📊 AHORRO DE TOKENS ESPERADO

| Método | % Preguntas | Tokens Usados | Costo |
|--------|-------------|---------------|-------|
| **Caché** | ~40% | 0 | $0.00 |
| **Template** | ~50% | 0 | $0.00 |
| **IA** | ~10% | 150 | $0.0001 |

**Estimación:** De 1000 preguntas, solo ~100 usarán IA = **15,000 tokens** (~$0.01 USD)

---

## 🏗️ ARQUITECTURA

### 1. Base de Datos (`storage/listings_database.db`)

**Tabla `listings`:**
- Guarda datos completos de cada producto publicado
- Optimizada para consultas rápidas por `item_id` o `asin`
- Incluye: dimensiones, precio, atributos, imágenes, etc.

**Tabla `faq_templates`:**
- Respuestas predefinidas para preguntas comunes
- Patrones regex para clasificación automática

**Tabla `answer_cache`:**
- Caché de respuestas generadas
- Reduce llamadas a IA para preguntas similares

### 2. Módulo de Clasificación (Sin IA)

**`classify_question()`** - Clasifica preguntas con **regex**:

```python
CATEGORIES:
- shipping: "envío", "demora", "llega", etc.
- stock: "disponible", "hay", "queda", etc.
- warranty: "garantía", "defecto", "devolución", etc.
- dimensions: "medidas", "tamaño", "peso", etc.
- authenticity: "original", "falso", etc.
- price: "precio", "descuento", etc.
- invoice: "factura", "recibo", etc.
- specs: "características", "incluye", etc.
```

**Gratis** - 0 tokens usados ✅

### 3. Sistema de Templates

Respuestas predefinidas personalizables:

```python
# Ejemplo: Pregunta sobre envío
Template: "¡Hola! Este producto se envía desde Estados Unidos..."

# Ejemplo: Pregunta sobre dimensiones
Template personalizado con datos del listing:
"¡Hola! Las dimensiones del producto son: 6.5×26×38cm, pesa 0.66kg 📦"
```

**Gratis** - 0 tokens usados ✅

### 4. IA con Contexto Mínimo

Solo se usa cuando NO hay template disponible:

**Optimizaciones:**
- Solo contexto relevante (no todo el producto)
- Máximo 300 caracteres de descripción
- Máximo 5 características principales
- Modelo: `gpt-4o-mini` (más barato)
- Límite: 150 tokens por respuesta

**Costo:** ~$0.0001 USD por pregunta 💰

---

## 🚀 USO

### Inicializar Sistema

```bash
# 1. Crear base de datos y templates
./venv/bin/python3 save_listing_data.py

# 2. Guardar listings cuando se publican
# (Esto se hace automáticamente en el pipeline)
```

### Responder Preguntas Automáticamente

```bash
# Modo DRY RUN (solo muestra, no postea)
./venv/bin/python3 auto_answer_questions.py

# Modo LIVE (postea respuestas reales)
# Editar script y cambiar: auto_answer_loop(dry_run=False)
```

### Uso Programático

```python
from auto_answer_questions import answer_question

# Generar respuesta para una pregunta
result = answer_question(
    item_id="CBT123456",
    question="¿Cuánto demora el envío?"
)

print(result['answer'])       # Texto de la respuesta
print(result['method'])        # cache/template/ai
print(result['tokens_used'])   # Tokens consumidos
print(result['cost_usd'])      # Costo en USD
```

---

## 📝 INTEGRACIÓN CON PIPELINE DE PUBLICACIÓN

### En `src/mainglobal.py`, después de publicar:

```python
from save_listing_data import save_listing

# Al publicar exitosamente
if result and result.get('id'):
    item_id = result['id']

    # Guardar en base de datos para respuestas automáticas
    save_listing(
        item_id=item_id,
        mini_ml=mini_ml,
        marketplaces=["MLM", "MLB", "MLC", "MCO", "MLA"]
    )
```

---

## 🤖 AUTOMATIZACIÓN CON CRON

Para responder preguntas automáticamente cada hora:

```bash
# Editar crontab
crontab -e

# Agregar línea:
0 * * * * cd /Users/felipemelucci/Desktop/revancha && ./venv/bin/python3 auto_answer_questions.py >> logs/auto_answer.log 2>&1
```

---

## 📊 EJEMPLOS DE RESPUESTAS

### Ejemplo 1: Pregunta sobre envío (Template - 0 tokens)

**Pregunta:** "Hola, cuánto demora el envío?"

**Proceso:**
1. Clasificación → `shipping`
2. Template → Respuesta predefinida
3. Tokens: **0**

**Respuesta:**
> ¡Hola! Este producto se envía desde Estados Unidos a través de MercadoLibre Global. El tiempo de entrega estimado es de 15-25 días hábiles. El envío está incluido en el precio y puedes hacer seguimiento desde tu cuenta.

---

### Ejemplo 2: Pregunta sobre dimensiones (Template Personalizado - 0 tokens)

**Pregunta:** "Qué medidas tiene?"

**Proceso:**
1. Clasificación → `dimensions`
2. Template personalizado con datos del listing
3. Tokens: **0**

**Respuesta:**
> ¡Hola! Las dimensiones del producto son: 6.5cm × 26.01cm × 38.0cm, y pesa 0.662kg. 📦

---

### Ejemplo 3: Pregunta específica (IA - 150 tokens)

**Pregunta:** "Es compatible con mi iPhone 13 Pro?"

**Proceso:**
1. Clasificación → `specs`
2. No hay template específico
3. IA genera respuesta con contexto mínimo
4. Tokens: **150** (~$0.0001 USD)

**Respuesta:**
> ¡Hola! Según las especificaciones, este accesorio es compatible con modelos iPhone 12 y posteriores, incluyendo el iPhone 13 Pro. ✅ Si tienes dudas adicionales, no dudes en consultarme.

---

## 💰 ANÁLISIS DE COSTOS

### Escenario Real: 1000 preguntas/mes

| Método | Preguntas | Tokens | Costo |
|--------|-----------|--------|-------|
| Caché | 400 | 0 | $0.00 |
| Template | 500 | 0 | $0.00 |
| IA | 100 | 15,000 | ~$0.01 |
| **TOTAL** | **1000** | **15,000** | **$0.01/mes** |

### Comparación: Sin sistema inteligente

Si todas las preguntas usaran IA:
- 1000 preguntas × 300 tokens = 300,000 tokens
- Costo: ~$0.20 USD/mes

**Ahorro: 95% de tokens** ✅

---

## 🔧 CONFIGURACIÓN AVANZADA

### Agregar Nuevos Templates

Editar `save_listing_data.py`:

```python
templates = [
    # Nuevo template
    ("pregunta|pattern|regex",
     "Respuesta template aquí",
     "categoria", prioridad),
]
```

### Ajustar Modelo de IA

Editar `auto_answer_questions.py`:

```python
# Cambiar modelo
model="gpt-4o-mini"  # Más barato
# o
model="gpt-4o"       # Más inteligente
```

### Aumentar Contexto

```python
# Aumentar límite de descripción
desc[:300]  # Cambiar a 500, 1000, etc.

# Aumentar límite de tokens
max_tokens=150  # Cambiar a 200, 300, etc.
```

---

## 📈 MÉTRICAS Y MONITOREO

### Ver estadísticas de uso:

```sql
-- Respuestas más comunes (caché)
SELECT question, used_count
FROM answer_cache
ORDER BY used_count DESC
LIMIT 10;

-- Templates más usados
SELECT question_pattern, category, uses_count
FROM faq_templates
ORDER BY uses_count DESC;

-- Listings más consultados
SELECT item_id, asin, COUNT(*) as questions_count
FROM answer_cache
GROUP BY item_id
ORDER BY questions_count DESC;
```

---

## 🎯 RECOMENDACIONES

### Para Maximizar Ahorro:

1. **Actualizar templates regularmente**
   - Analizar preguntas frecuentes
   - Agregar nuevos patterns

2. **Revisar respuestas de IA**
   - Convertir respuestas comunes en templates
   - Mejorar clasificación

3. **Monitorear costos**
   - Revisar logs mensualmente
   - Ajustar límites de tokens

4. **Mejorar clasificación**
   - Agregar patterns específicos de tus productos
   - Reducir uso de IA

---

## 📁 ESTRUCTURA DE ARCHIVOS

```
.
├── save_listing_data.py          # Módulo de base de datos
├── auto_answer_questions.py      # Sistema de respuestas
├── storage/
│   └── listings_database.db      # Base de datos SQLite
└── logs/
    └── auto_answer.log           # Logs de respuestas
```

---

## ✅ CHECKLIST DE IMPLEMENTACIÓN

- [x] Base de datos creada
- [x] Templates inicializados
- [x] Sistema de clasificación funcionando
- [x] Caché de respuestas implementado
- [x] Integración con OpenAI
- [ ] Integrar con pipeline de publicación (agregar save_listing en mainglobal.py)
- [ ] Configurar cron job para automatización
- [ ] Monitorear costos y ajustar

---

## 🆘 SOPORTE

Si necesitas ayuda o quieres agregar funcionalidades:

1. Revisar logs en `logs/auto_answer.log`
2. Verificar base de datos: `sqlite3 storage/listings_database.db`
3. Probar en modo dry_run primero

---

**Creado:** 2025-11-02
**Sistema:** Completamente modular e independiente del pipeline principal
**Estado:** ✅ Listo para uso
