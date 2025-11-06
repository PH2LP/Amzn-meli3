# 🎯 Plan de Optimización de Costos de IA

## Análisis de Oportunidades

### 💰 Potencial de Ahorro Total: ~$0.0035 por ASIN (35% de reducción)

---

## 🟢 Nivel 1: Quick Wins (Implementación Inmediata)

### 1️⃣ Agregar Cache a `ai_characteristics`
**Ahorro: $0.0023 por ASIN (22.8%)**

**Problema actual:**
- Se ejecuta SIEMPRE en cada `build_mini_ml()`
- Usa 12,000 tokens input + 800 output
- NO tiene cache implementado

**Solución:**
```python
# En transform_mapper_new.py, línea ~802
CHAR_CACHE_PATH = "storage/logs/ai_characteristics_cache.json"

def ai_characteristics(amazon_json) -> Tuple[List[dict], List[dict]]:
    asin = amazon_json.get("asin") or amazon_json.get("ASIN") or ""

    # Agregar cache
    char_cache = _load_cache(CHAR_CACHE_PATH, {})
    if asin in char_cache:
        return char_cache[asin]["main"], char_cache[asin]["second"]

    # ... código existente ...

    # Guardar en cache antes de return
    char_cache[asin] = {"main": main, "second": second}
    _save_cache(CHAR_CACHE_PATH, char_cache)

    return main, second
```

**Impacto:**
- Primera ejecución: $0.0023
- Ejecuciones posteriores: $0.0000
- Para 1000 ASINs: **$2.30 de ahorro**

---

### 2️⃣ Reducir Input de `ai_desc_es`
**Ahorro: ~$0.0008 por ASIN (8%)**

**Problema actual:**
- Envía hasta 15,000 caracteres del JSON completo
- Mucha información redundante

**Solución:**
```python
# En transform_mapper_new.py, línea ~673
# ANTES:
{json.dumps(amazon_json, ensure_ascii=False)[:15000]}

# DESPUÉS: Enviar solo datos relevantes
relevant_data = {
    "title": amazon_json.get("title"),
    "brand": brand,
    "model": model,
    "bullets": bullets[:5],  # Solo primeros 5
    "main_characteristics": main_ch[:10],  # Solo top 10
    "second_characteristics": second_ch[:10],
    "category": cat_name,
    "dimensions": pkg,
    "attributes": {k: v for k, v in amazon_json.get("attributes", {}).items()
                   if k in ["material", "color", "size", "weight"]}
}

{json.dumps(relevant_data, ensure_ascii=False)[:8000]}  # Reducir a 8000
```

**Impacto:**
- Reduce input de 15,000 a ~8,000 tokens
- Ahorro: ~$0.0008 por ASIN
- Para 1000 ASINs: **$0.80 de ahorro**
- **Mantiene calidad:** Incluye todo lo necesario para descripción

---

### 3️⃣ Cache Inteligente para `ask_gpt_equivalences`
**Ahorro: $0.0005 por ASIN (5%)**

**Problema actual:**
- Cache funciona bien pero pregunta atributos de uno en uno
- Podría reutilizar equivalencias entre categorías similares

**Solución:**
```python
# Guardar equivalencias a nivel de categoría, no solo en cache global
def ask_gpt_equivalences(category_id, missing, amazon_json, cache: dict):
    # Buscar en equivalencias de categoría primero
    cat_equiv_path = f"resources/schemas/{category_id}_equiv.json"
    if os.path.exists(cat_equiv_path):
        cat_equivs = json.load(open(cat_equiv_path))
        # Filtrar missing que ya están en cat_equivs
        missing = [m for m in missing if m not in cat_equivs]

    if not missing:
        return {}  # Ya todo está en equivalencias locales

    # Solo preguntar lo que realmente falta
    # ... resto del código ...
```

**Impacto:**
- Reduce llamadas duplicadas entre productos de misma categoría
- Ahorro estimado: $0.0005 por ASIN (50% de las veces se evita)

---

## 🟡 Nivel 2: Mejoras Medias (Requiere Testing)

### 4️⃣ Hacer `enhance_description_with_ai` Condicional
**Ahorro: $0.0010 por ASIN (10%)**

**Problema actual:**
- Se ejecuta SIEMPRE en `mainglobal.py` (línea 661)
- Enriquece descripción que ya fue generada con IA
- Costo: $0.0020 por llamada

**Solución A (Conservadora):**
```python
# Solo ejecutar si descripción es muy corta o genérica
if len(mini_ml.get("description_ai", "")) < 200:
    description = enhance_description_with_ai(mini_ml)
else:
    description = mini_ml.get("description_ai")
```

**Solución B (Agresiva):**
```python
# Eliminar completamente - la descripción de transform_mapper_new ya es buena
description = mini_ml.get("description_ai")
```

**Impacto:**
- Solución A: Ahorro 50% ($0.0010)
- Solución B: Ahorro 100% ($0.0020)
- **REQUIERE TESTING** para validar calidad

---

### 5️⃣ Optimizar `ai_characteristics` - Reducir Max Tokens
**Ahorro: $0.0005 por ASIN (5%)**

**Problema actual:**
- Pide "AT LEAST 20-30 characteristics"
- A veces genera más de lo necesario

**Solución:**
```python
# Cambiar prompt para ser más específico
prompt = f"""Extract EXACTLY 20 product characteristics (no more, no less).

Divide them:
- "main": 10 most important specs
- "second": 10 additional details

Extract ONLY actual values, NEVER metadata.
Be concise - one line per characteristic.
...
```

**Impacto:**
- Reduce output tokens de ~800 a ~500
- Ahorro: ~$0.0005 por ASIN
- **Mantiene calidad:** 20 características son suficientes

---

### 6️⃣ Agregar Cache a `validate_category_with_ai`
**Ahorro: $0.0001 por retry**

**Problema actual:**
- Se ejecuta en cada intento de publicación
- Valida la misma categoría múltiples veces para mismo ASIN

**Solución:**
```python
# En mainglobal.py
CATEGORY_VALIDATION_CACHE = {}

def validate_category_with_ai(product_data, category_id):
    cache_key = f"{product_data.get('asin')}_{category_id}"
    if cache_key in CATEGORY_VALIDATION_CACHE:
        return CATEGORY_VALIDATION_CACHE[cache_key]

    # ... validación existente ...

    CATEGORY_VALIDATION_CACHE[cache_key] = result
    return result
```

**Impacto:**
- Ahorra en escenarios con múltiples retries
- Pequeño ahorro pero sin riesgo

---

## 🔴 Nivel 3: Optimizaciones Avanzadas (Requiere Refactoring)

### 7️⃣ Batch Processing para Equivalencias
**Ahorro potencial: $0.0003 por ASIN**

Procesar múltiples ASINs de la misma categoría juntos y compartir equivalencias.

### 8️⃣ Modelo más Barato para Validaciones Simples
**Ahorro potencial: $0.0002 por ASIN**

Usar `gpt-3.5-turbo` (más barato) para validaciones binarias como `validate_dimensions_with_ai`.

---

## 📊 Resumen de Ahorros

### Implementando Solo Nivel 1 (Quick Wins)

| Optimización | Ahorro | Dificultad | Riesgo |
|--------------|--------|------------|--------|
| Cache a ai_characteristics | $0.0023 | Muy fácil | Ninguno |
| Reducir input ai_desc_es | $0.0008 | Fácil | Muy bajo |
| Cache inteligente equivalences | $0.0005 | Fácil | Ninguno |
| **TOTAL NIVEL 1** | **$0.0036** | - | - |

**Costo optimizado por ASIN:**
- Primera vez: $0.0101 → $0.0065 (35% reducción)
- Con cache: $0.0056 → $0.0020 (64% reducción)

### Implementando Nivel 1 + 2

| Optimización | Ahorro | Dificultad | Riesgo |
|--------------|--------|------------|--------|
| NIVEL 1 | $0.0036 | - | - |
| enhance_description condicional | $0.0010 | Media | Medio |
| Optimizar ai_characteristics | $0.0005 | Fácil | Bajo |
| Cache validate_category | $0.0001 | Fácil | Ninguno |
| **TOTAL NIVEL 1+2** | **$0.0052** | - | - |

**Costo optimizado por ASIN:**
- Primera vez: $0.0101 → $0.0049 (51% reducción)
- Con cache: $0.0056 → $0.0004 (93% reducción)

---

## 🎯 Proyección de Ahorro Anual

Asumiendo 1000 ASINs procesados por mes:

### Solo Nivel 1 (Sin Riesgo)
```
Mes 1 (primera vez):      $10.10 → $6.50    (-$3.60)
Mes 2-12 (con cache):     $5.60  → $2.00    (-$3.60 × 11 = -$39.60)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AHORRO ANUAL: $43.20
```

### Nivel 1 + 2 (Requiere Testing)
```
Mes 1 (primera vez):      $10.10 → $4.90    (-$5.20)
Mes 2-12 (con cache):     $5.60  → $0.40    (-$5.20 × 11 = -$57.20)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AHORRO ANUAL: $62.40
```

---

## ✅ Recomendación de Implementación

### Fase 1 (Esta semana): Nivel 1 Completo
1. ✅ Cache a `ai_characteristics` - 30 minutos
2. ✅ Reducir input de `ai_desc_es` - 20 minutos
3. ✅ Cache inteligente equivalences - 15 minutos

**Total: ~1 hora de trabajo**
**Ahorro: $43.20/año**
**ROI: Inmediato**

### Fase 2 (Próxima semana): Testing de Nivel 2
1. ⚠️ Test de `enhance_description_with_ai` condicional
2. ✅ Optimizar prompt `ai_characteristics`
3. ✅ Cache `validate_category`

**Total: ~2 horas (incluyendo testing)**
**Ahorro adicional: $19.20/año**

---

## 🔧 Archivos a Modificar

### Nivel 1
1. `src/transform_mapper_new.py`:
   - Agregar cache a `ai_characteristics` (línea ~802)
   - Optimizar input de `ai_desc_es` (línea ~673)
   - Mejorar cache de `ask_gpt_equivalences` (línea ~548)

### Nivel 2
2. `src/mainglobal.py`:
   - Hacer condicional `enhance_description_with_ai` (línea ~661)
   - Agregar cache a `validate_category_with_ai` (línea ~699)

---

## ⚠️ Consideraciones Importantes

1. **NO tocar estos archivos de cache:**
   - Los existentes funcionan bien
   - Solo agregar nuevos para funciones sin cache

2. **Testing crítico para Nivel 2:**
   - Validar 10-20 ASINs con optimizaciones
   - Comparar calidad de descripciones
   - Verificar que publicaciones sean exitosas

3. **Monitoreo post-implementación:**
   - Verificar tasas de éxito de publicación
   - Revisar logs de errores
   - Comparar calidad de listings

---

## 📈 Métricas de Éxito

### KPIs a Monitorear
- ✅ Costo promedio por ASIN (debe bajar 35-50%)
- ✅ Tasa de éxito de publicación (debe mantenerse ≥95%)
- ✅ Tiempo de ejecución (puede aumentar ligeramente por cache I/O)
- ⚠️ Calidad de descripciones (revisar manualmente 10 samples)

---

**Siguiente paso:** ¿Quieres que implemente las optimizaciones de Nivel 1?
