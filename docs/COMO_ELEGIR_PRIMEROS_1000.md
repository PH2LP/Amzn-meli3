# 🎯 Cómo Elegir los Primeros 1,000 ASINs para Publicar

## 📊 Sistema de Scoring

El sistema evalúa cada ASIN con un score de 0-100 basado en 5 factores:

| Factor | Peso | Descripción |
|--------|------|-------------|
| **BSR** | 35% | Best Seller Rank (mientras más bajo, mejor) |
| **Reviews** | 25% | Cantidad y rating de reviews |
| **Precio** | 20% | Precio ideal: $20-$70 |
| **Competencia** | 15% | Saturación en MercadoLibre |
| **Categoría** | 5% | Categorías populares |

### 🎯 Scoring Detallado

#### 1. BSR Score (35 puntos)
```
BSR 1-100        → 35 pts ⭐⭐⭐⭐⭐
BSR 100-1,000    → 30 pts ⭐⭐⭐⭐
BSR 1K-10K       → 25 pts ⭐⭐⭐
BSR 10K-50K      → 20 pts ⭐⭐
BSR 50K-100K     → 15 pts ⭐
BSR 100K+        → 10 pts
Sin BSR          → 5 pts
```

#### 2. Reviews Score (25 puntos)

**Cantidad (15 pts):**
```
1,000+ reviews   → 15 pts
500+ reviews     → 12 pts
100+ reviews     → 10 pts
50+ reviews      → 8 pts
10+ reviews      → 5 pts
< 10 reviews     → 2 pts
```

**Rating (10 pts):**
```
4.5+ estrellas   → 10 pts
4.0+ estrellas   → 8 pts
3.5+ estrellas   → 5 pts
3.0+ estrellas   → 3 pts
< 3.0 estrellas  → 1 pt
```

#### 3. Price Score (20 puntos)
```
$20-$70          → 20 pts (ideal)
$15-$20 o $70-$100  → 15 pts
$10-$15 o $100-$150 → 10 pts
Otros rangos     → 5 pts
Sin precio       → 0 pts
```

#### 4. Competition Score (15 puntos)
*Por ahora: 10 pts por defecto (se puede integrar con ML API después)*

#### 5. Category Score (5 puntos)
```
Categorías populares → 5 pts
Otras categorías     → 3 pts
```

---

## 🚀 Cómo Usar el Sistema

### Paso 1: Tener ASINs para Evaluar

Primero necesitas un archivo con ASINs (puede tener miles):

```bash
# Opción A: Usar asins.txt existente
cat asins.txt
# B0ABC123
# B0DEF456
# B0GHI789
# ...

# Opción B: Ejecutar búsqueda autónoma primero
python3 scripts/autonomous/autonomous_search_and_publish.py --search-only
```

### Paso 2: Rankear ASINs

Ejecuta el script de ranking:

```bash
# Rankear ASINs y seleccionar top 1000
python3 scripts/tools/rank_asins_for_publication.py --limit 1000

# O personalizar input/output
python3 scripts/tools/rank_asins_for_publication.py \
  --input asins.txt \
  --limit 1000 \
  --output-json storage/ranked_asins.json \
  --output-txt asins_top1000.txt
```

### Paso 3: Ver Resultados

El script genera:

1. **`storage/ranked_asins.json`** - Detalles completos con scores
2. **`asins_top1000.txt`** - Solo ASINs (listo para publicar)

Ejemplo de salida:

```
📊 Evaluando 5000 ASINs...
============================================================

[1-20/5000] Obteniendo datos de Amazon...
   ✅ B0ABC123: Score 87.5/100
   ✅ B0DEF456: Score 72.0/100
   ...

============================================================
📊 RANKING COMPLETADO
============================================================
  Total evaluados: 4,847
  Top seleccionados: 1,000
  Score promedio top 1000: 68.5
  Score más alto: 92.0
  Score más bajo (top 1000): 52.0
============================================================

🏆 TOP 10 ASINs:
============================================================

#1. B0ABC123 - Score: 92.0/100
   📦 Wireless Bluetooth Headphones with Noise Cancelling
   💰 $79.99
   📊 BSR: #145
   ⭐ 4.8 (2,345 reviews)
   📈 Breakdown:
      BSR: 30/35
      Reviews: 25/25
      Price: 20/20
      Competition: 12/15
      Category: 5/5

#2. B0DEF456 - Score: 88.5/100
   ...
```

### Paso 4: Publicar Top 1000

Usa el archivo generado para publicar:

```bash
# Opción A: Renombrar y usar con main2.py
mv asins_top1000.txt asins.txt
python3 main2.py

# Opción B: Especificar archivo directamente
python3 main2.py --input asins_top1000.txt
```

---

## 💡 Estrategias de Selección

### Estrategia 1: Máxima Calidad (Recomendada para primeros 1K)

```bash
# Top 1000 con mejor score
python3 scripts/tools/rank_asins_for_publication.py --limit 1000
```

**Ventajas:**
- Productos con mejor reputación
- Mayor probabilidad de ventas
- Menos devoluciones
- Construye autoridad en ML

### Estrategia 2: Diversificación por Categoría

```bash
# Top 200 por categoría (5 categorías = 1000)
python3 scripts/tools/rank_asins_for_publication.py --limit 200 --category Electronics
python3 scripts/tools/rank_asins_for_publication.py --limit 200 --category Home
python3 scripts/tools/rank_asins_for_publication.py --limit 200 --category Kitchen
python3 scripts/tools/rank_asins_for_publication.py --limit 200 --category Sports
python3 scripts/tools/rank_asins_for_publication.py --limit 200 --category Tools
```

**Ventajas:**
- Mayor cobertura de mercado
- Menos dependencia de una categoría
- Mejor posicionamiento en búsquedas

### Estrategia 3: Balanceada (100 keywords × 12 productos = 1,200 ASINs)

```bash
# Ejecutar búsqueda con diversificación
python3 scripts/autonomous/autonomous_search_and_publish.py \
  --keywords 100 \
  --asins-per-keyword 12

# Esto genera ~1,200 ASINs
# Luego rankear y seleccionar top 1000 (compensando errores)
python3 scripts/tools/rank_asins_for_publication.py --limit 1000
```

**Ventajas:**
- Mejor diversificación (100 keywords diferentes)
- 1,200 ASINs iniciales → 1,000 finales (margen para errores)
- Menor riesgo por keyword
- Más oportunidades de encontrar nichos

---

## 📈 Ejemplos de Scores Reales

### Producto Excelente (Score: 90+)
```
ASIN: B08L5VN96K
Score: 92/100

BSR: #50 (35 pts)
Reviews: 3,500 reviews @ 4.7⭐ (24 pts)
Price: $49.99 (20 pts)
Competition: Baja (13 pts)
Category: Electronics (5 pts)

→ PUBLICAR DEFINITIVAMENTE
```

### Producto Bueno (Score: 70-89)
```
ASIN: B09WXYZ123
Score: 78/100

BSR: #5,000 (25 pts)
Reviews: 250 reviews @ 4.3⭐ (18 pts)
Price: $89.99 (20 pts)
Competition: Media (10 pts)
Category: Home (5 pts)

→ BUEN CANDIDATO
```

### Producto Marginal (Score: 50-69)
```
ASIN: B0AAABBB99
Score: 58/100

BSR: #80,000 (15 pts)
Reviews: 45 reviews @ 3.8⭐ (13 pts)
Price: $220 (10 pts)
Competition: Alta (10 pts)
Category: Other (3 pts)

→ CONSIDERAR SOLO SI SOBRA ESPACIO
```

### Producto Malo (Score: <50)
```
ASIN: B0BADITEM1
Score: 35/100

BSR: Sin ranking (5 pts)
Reviews: 5 reviews @ 2.8⭐ (6 pts)
Price: $8 (5 pts)
Competition: Alta (10 pts)
Category: Other (3 pts)

→ NO PUBLICAR
```

---

## 🎯 Recomendaciones Finales

### Para tus primeros 1,000 ASINs:

1. **Ejecuta búsqueda con 100 keywords × 12 ASINs = 1,200 ASINs:**
   ```bash
   python3 scripts/autonomous/autonomous_search_and_publish.py \
     --keywords 100 \
     --asins-per-keyword 12
   ```

2. **Rankea y selecciona los mejores 1,000 (compensando errores):**
   ```bash
   python3 scripts/tools/rank_asins_for_publication.py --limit 1000
   ```

3. **Revisa el top 10 manualmente:**
   - Verifica que sean productos reales
   - Confirma que no tengan restricciones de marca
   - Valida que las categorías tengan sentido

4. **Publica los top 1,000:**
   ```bash
   mv asins_top1000.txt asins.txt
   python3 main2.py
   ```

5. **Monitorea resultados:**
   - Primeras ventas en 7-14 días
   - Ajusta estrategia según performance
   - Cuando ML suba límite, repite desde paso 1

---

## 🔄 Cuando ML te Suba el Límite a 10K

1. **Vuelve a ejecutar las mismas keywords (buscará ASINs nuevos):**
   ```bash
   python3 scripts/autonomous/autonomous_search_and_publish.py \
     --keywords 100 \
     --asins-per-keyword 12
   ```

2. **El sistema automáticamente filtrará los 1,000 ya publicados**

3. **Rankea los nuevos ASINs y selecciona 9,000 más:**
   ```bash
   python3 scripts/tools/rank_asins_for_publication.py --limit 9000
   ```

4. **Publica los siguientes 9,000 mejores**

¡Y así sucesivamente hasta llegar a tu límite máximo!
