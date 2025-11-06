# 💰 Reporte de Costos de IA por ASIN

## Resumen Ejecutivo

**Costo por ASIN (primera ejecución):** `$0.0101 USD` (~53,000 tokens)
**Costo por ASIN (con cache):** `$0.0056 USD` (~29,000 tokens)
**Ahorro por cache:** `$0.0045 USD` (44.6%)

---

## 📊 Proyección de Costos

| ASINs | Primera Vez | Con Cache | Ahorro Total |
|-------|-------------|-----------|--------------|
| 10    | $0.10       | $0.06     | $0.04        |
| 50    | $0.51       | $0.28     | $0.23        |
| 100   | $1.01       | $0.56     | $0.45        |
| 500   | $5.05       | $2.80     | $2.25        |
| 1000  | $10.10      | $5.60     | $4.50        |

---

## 🔍 Desglose Detallado por Llamada

### Fase TRANSFORM (build_mini_ml)

| Función | Tokens | Costo | Cache | Condición |
|---------|--------|-------|-------|-----------|
| `ai_desc_es` | 16,500 | $0.0032 | ✅ | Siempre |
| `ai_characteristics` | 12,800 | $0.0023 | ❌ | Siempre |
| `detect_gtin_with_ai` | 8,050 | $0.0012 | ❌ | Solo si no encuentra GTIN |
| `ask_gpt_equivalences` | 6,300 | $0.0011 | ✅ | Solo si hay attrs faltantes |
| `CategoryMatcherV2.validate_with_ai` | 830 | $0.0001 | ✅ | Siempre (use_ai=True) |
| `ai_title_es` | 480 | $0.0001 | ✅ | Siempre |

**Subtotal TRANSFORM (primera vez):** $0.0080
**Subtotal TRANSFORM (con cache):** $0.0036

---

### Fase PUBLISH (mainglobal.py)

| Función | Tokens | Costo | Cache | Condición |
|---------|--------|-------|-------|-----------|
| `fix_publishing_error_with_ai` | 4,000 | $0.0010 | ❌ | Solo si hay error |
| `enhance_description_with_ai` | 2,800 | $0.0020 | ❌ | Siempre |
| `validate_category_with_ai` | 600 | $0.0001 | ❌ | Siempre |
| `validate_dimensions_with_ai` | 400 | $0.0001 | ❌ | Si dimensiones sospechosas |
| `improve_title_with_ai` | 260 | $0.0000 | ❌ | Si título > 60 chars |

**Subtotal PUBLISH:** $0.0021
**Nota:** Estas llamadas NO usan cache y se ejecutan en cada intento de publicación

---

## 💡 Llamadas con Cache (Ahorro Garantizado)

Estas 4 llamadas **solo se ejecutan la primera vez** por ASIN:

1. ✅ **ai_desc_es** - Genera descripción HTML optimizada
   Cache: `storage/logs/ai_desc_cache.json`

2. ✅ **ai_title_es** - Genera título en español
   Cache: `storage/logs/ai_title_cache.json`

3. ✅ **ask_gpt_equivalences** - Aprende mapeo de atributos
   Cache: `storage/logs/ai_equivalences_cache.json`

4. ✅ **CategoryMatcherV2** - Valida categoría con IA
   Cache: `storage/logs/category_cache.json`

**Total ahorro por cache:** $0.0045 por ASIN (después de primera ejecución)

---

## ⚠️ Llamadas SIN Cache (Costo Recurrente)

Estas llamadas se ejecutan **SIEMPRE** y no usan cache:

1. ❌ **ai_characteristics** ($0.0023) - Extrae 20+ características del producto
   → Se ejecuta en cada `build_mini_ml()`

2. ❌ **enhance_description_with_ai** ($0.0020) - Enriquece descripción en publish
   → Se ejecuta en cada intento de publicación

3. ❌ **detect_gtin_with_ai** ($0.0012) - Solo si no encuentra GTIN en JSON
   → Fallback cuando `extract_gtins()` falla

4. ❌ **validate_category_with_ai** ($0.0001) - Valida categoría en publish
   → Se ejecuta en cada publicación

5. ❌ **fix_publishing_error_with_ai** ($0.0010) - Solo si hay errores
   → Solo en publicaciones fallidas

---

## 🎯 Análisis de Optimización

### 1️⃣ Llamadas más costosas (Top 3)

| Ranking | Función | % del Total | Optimización |
|---------|---------|-------------|--------------|
| 1º | `ai_desc_es` | 31.2% | ✅ Ya tiene cache |
| 2º | `ai_characteristics` | 22.8% | 🔴 No tiene cache → Oportunidad |
| 3º | `enhance_description_with_ai` | 19.8% | 🔴 Se ejecuta en publish (sin cache) |

### 2️⃣ Recomendaciones Críticas

#### 🟢 Fácil (Quick Wins)

1. **Agregar cache a `ai_characteristics`**
   → Ahorro: $0.0023 por ASIN en ejecuciones posteriores
   → Impacto: 500 ASINs = $1.15 de ahorro

2. **Optimizar prompt de `ai_desc_es`**
   → Reducir input de 15,000 a 10,000 tokens
   → Ahorro: $0.0008 por ASIN

3. **Validar que `extract_gtins()` funcione bien**
   → Evitar fallback de `detect_gtin_with_ai`
   → Ahorro: $0.0012 cuando se evita

#### 🟡 Medio (Mejoras Importantes)

4. **Revisar llamadas en `mainglobal.py`**
   → `enhance_description_with_ai` se ejecuta SIEMPRE
   → Considerar hacer condicional o agregar cache
   → Potencial ahorro: $0.0020 por retry

5. **Optimizar `ai_characteristics`**
   → Reducir max_tokens o usar prompt más eficiente
   → Ahorro: $0.0005-0.0010 por ASIN

#### 🔴 Difícil (Mejoras Estructurales)

6. **Sistema de cache global para mainglobal.py**
   → Implementar cache para validaciones en publish
   → Requiere refactoring pero ahorra $0.0021 por retry

---

## 📈 Escenarios Reales de Uso

### Escenario A: Primera Publicación Exitosa
- TRANSFORM (primera vez): $0.0080
- PUBLISH (1 intento): $0.0021
- **Total: $0.0101 por ASIN**

### Escenario B: Re-publicación (mismo ASIN con cache)
- TRANSFORM (con cache): $0.0036
- PUBLISH (1 intento): $0.0021
- **Total: $0.0057 por ASIN**

### Escenario C: Publicación con Retry (error de categoría)
- TRANSFORM (primera vez): $0.0080
- PUBLISH intento 1 (falla): $0.0021
- TRANSFORM (regenerar con nueva cat): $0.0036 (usa cache parcial)
- PUBLISH intento 2 (éxito): $0.0021
- **Total: $0.0158 por ASIN**

### Escenario D: Pipeline con Múltiples Retries
- TRANSFORM (primera vez): $0.0080
- PUBLISH intentos 1-3 (fallan): $0.0063 (3 × $0.0021)
- TRANSFORM (regenerar 2 veces): $0.0072 (2 × $0.0036)
- PUBLISH intento 4 (éxito): $0.0021
- **Total: $0.0236 por ASIN** (con 4 intentos de publish)

---

## 💾 Archivos de Cache Críticos

**NO BORRAR ESTOS ARCHIVOS:**

```
storage/logs/ai_desc_cache.json          # Descripciones (ahorro: $0.0032/ASIN)
storage/logs/ai_title_cache.json         # Títulos (ahorro: $0.0001/ASIN)
storage/logs/ai_equivalences_cache.json  # Mapeo atributos (ahorro: $0.0011/ASIN)
storage/logs/category_cache.json         # Categorías (ahorro: $0.0001/ASIN)
```

**Ahorro total si se borran:** $0.0045 por ASIN × cantidad de ASINs procesados

---

## 🔢 Cálculo Manual del Costo

### Precio GPT-4o-mini (2025)
- Input: $0.150 / 1M tokens
- Output: $0.600 / 1M tokens

### Fórmula
```
Costo = (Input_Tokens × $0.150 / 1,000,000) + (Output_Tokens × $0.600 / 1,000,000)
```

### Ejemplo: ai_desc_es
```
Input:  15,000 tokens × $0.150 / 1M = $0.00225
Output:  1,500 tokens × $0.600 / 1M = $0.00090
Total: $0.00315 por llamada
```

---

## 📝 Conclusiones

### ✅ Puntos Positivos
1. **Cache funciona bien**: Ahorra 44.6% del costo
2. **Costo bajo por ASIN**: ~$0.01 es muy razonable
3. **Llamadas caras tienen cache**: Las 2 más costosas usan cache

### ⚠️ Áreas de Mejora
1. **ai_characteristics sin cache**: Oportunidad de ahorro
2. **Llamadas en publish sin cache**: Se ejecutan en cada retry
3. **detect_gtin_with_ai**: Ejecutar menos veces (mejorar extracción)

### 💰 Impacto Financiero
- **100 ASINs (primera vez):** $1.01
- **100 ASINs (con cache):** $0.56
- **1000 ASINs (primera vez):** $10.10
- **1000 ASINs (con cache):** $5.60

**Ahorro potencial con optimizaciones:** ~$2-3 por cada 1000 ASINs

---

**Generado:** $(date)
**Script:** `calculate_ia_cost.py`
**Reporte JSON:** `storage/logs/ia_cost_report.json`
