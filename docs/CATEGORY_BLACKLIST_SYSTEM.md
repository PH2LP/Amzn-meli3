# Sistema de Blacklist de Categorías - Documentación

## 📋 Resumen

Después de investigar múltiples enfoques para pre-detectar categorías prohibidas en MercadoLibre, **confirmamos que NO existe forma de escanearlas antes de publicar**. Los endpoints de la API no exponen información de restricciones por país.

**Solución implementada**: Sistema reactivo que detecta automáticamente categorías prohibidas durante la publicación y actualiza una blacklist global para evitar futuras repeticiones del error.

---

## 🔍 Investigación Realizada

### Endpoints Probados (sin éxito)

1. **`/sites/{SITE}/categories/{CAT_ID}`**
   - ❌ Retorna 404 para categorías CBT
   - Categorías CBT son globales, no pertenecen a sites específicos

2. **`/categories/{ID}`**
   - ✅ Retorna info de categoría
   - ❌ NO muestra restricciones por país
   - Retorna `listing_allowed: true` globalmente pero puede estar prohibida en países específicos

3. **`/items/validate`**
   - ❌ Rechaza categorías CBT con `cause_id: 125`
   - No valida restricciones de categorías CBT

4. **`/items` POST con `site_id`**
   - ❌ Rechaza publicaciones cross-site con `cause_id: 179`

5. **`/global/items` POST con CBT format**
   - ✅ Endpoint correcto para CBT
   - ❌ NO permite validación sin datos completos (requiere todas las dimensiones, sale_terms, etc)
   - Imposible de usar para escaneo masivo

6. **`/categories/{ID}/technical_specs`**
   - ✅ Muestra atributos requeridos
   - ❌ NO muestra restricciones de publicación

7. **`/sites/{SITE}/category_predictor/predict`**
   - ❌ No funciona para categorías CBT (404)

8. **`/sites/{SITE}/domain_discovery/search`**
   - ✅ Funciona
   - ❌ Retorna categorías locales, no CBT
   - Ejemplo: Para "monocular" retorna MLM49569 en vez de CBT412529

### Conclusión de la Investigación

**No existe endpoint que permita validar restricciones de categorías CBT sin intentar publicar un producto real.**

Las restricciones son:
- **Por país**: Cada país (MLM, MLA, MLC, MCO, MLB) tiene sus propias reglas
- **Sin exposición en API**: No hay metadata que indique "esta categoría está prohibida en X país"
- **Detectables solo en publicación**: El error `cause_id: 5100` aparece solo al intentar publicar

---

## ✅ Solución Implementada

### Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                    FLUJO DE PUBLICACIÓN                     │
└─────────────────────────────────────────────────────────────┘

1. Category Matcher encuentra categoría
   ├─ Carga blacklist al inicializar
   └─ Excluye automáticamente categorías prohibidas

2. Se intenta publicar producto con mainglobal.py
   └─ POST /global/items con categoria seleccionada

3. ML responde con site_items (resultado por país)
   ├─ Algunos países: OK (item_id retornado)
   └─ Otros países: ERROR con cause_id 5100

4. Detector automático de blacklist (NEW!)
   ├─ Analiza todos los site_items
   ├─ Busca cause_id 5100 en cada país
   ├─ Si detecta prohibición:
   │  ├─ Actualiza storage/category_blacklist_global.json
   │  ├─ Registra países que bloquearon
   │  ├─ Registra ASIN ejemplo
   │  ├─ **PAUSA el item inmediatamente** (si se publicó)
   │  └─ Evita suspensiones futuras en otros países
   └─ Notifica al usuario

5. Futuras publicaciones
   └─ Category Matcher automáticamente evita esa categoría
```

### Componentes Implementados

#### 1. `src/utils/category_blacklist_manager.py`

**Clase Principal**: `CategoryBlacklistManager`

**Métodos clave**:
- `detect_and_update_from_publishing_errors()`: Analiza errores de publicación
- `add_to_blacklist()`: Agrega categoría a blacklist
- `is_blacklisted()`: Verifica si categoría está prohibida
- `get_blacklist()`: Obtiene lista completa

**Función Helper**:
```python
check_and_update_blacklist_from_publishing(
    site_items=res.get("site_items", []),
    category_id="CBT412529",
    category_name="Monoculars",
    asin="B0FKPK5D8F"
)
```

#### 2. Integración en `CategoryMatcherV2`

```python
# Carga automática de blacklist al inicializar
self.blacklist_manager = CategoryBlacklistManager()
self.excluded_categories = self.blacklist_manager.get_blacklist()

# Uso automático en find_category()
if excluded_categories is None:
    excluded_categories = self.excluded_categories
```

#### 3. Detección en `mainglobal.py`

```python
# Después de publicar, detectar errores
blacklist_result = check_and_update_blacklist_from_publishing(
    site_items=site_items,
    category_id=asin_json.get("category_id"),
    category_name=asin_json.get("category_name"),
    asin=asin
)

if blacklist_result["newly_blacklisted"]:
    print("🚫 NUEVA CATEGORÍA PROHIBIDA DETECTADA")
```

---

## 📊 Formato de Blacklist

**Archivo**: `storage/category_blacklist_global.json`

```json
{
  "blacklist": ["CBT412529"],
  "details": {
    "CBT412529": {
      "name": "Monoculars",
      "reason": "Not allowed in MLM, MLA - Suspended in MLC, MCO, MLB",
      "first_detected": "2025-12-08",
      "blocked_in": ["MLM", "MLA"],
      "suspended_in": ["MLC", "MCO", "MLB"],
      "asin_examples": ["B0FKPK5D8F"],
      "note": "Prohibited globally - if blocked in 1 country, avoid in all countries"
    }
  },
  "total": 1,
  "last_updated": "2025-12-08T06:30:00Z",
  "version": "1.0",
  "description": "Global category blacklist - categories that failed publishing in at least one country"
}
```

### Criterio de Blacklist Global

**Regla**: Si una categoría está prohibida en AL MENOS 1 país → blacklist global

**Razón**:
- Algunos países detectan en publicación (MLM, MLA)
- Otros suspenden días después (MLC, MCO, MLB)
- Mejor prevenir en todos los países para evitar suspensiones futuras

---

## 🚀 Cómo Funciona en Producción

### Primer Producto con Categoría Prohibida

1. **Blink Monocular (B0FKPK5D8F)** intenta publicarse
2. Category Matcher asigna CBT412529 (Monoculars)
3. Publicación:
   - ✅ Éxito en MLC, MCO, MLB (item_id generado)
   - ❌ Falla en MLM y MLA con cause_id 5100
4. Sistema detecta automáticamente:
   - Actualiza blacklist
   - **PAUSA el item inmediatamente** via PUT /items/{item_id}
   - Evita que ML lo suspenda días después
5. Usuario ve notificación:
   ```
   🚫 CATEGORÍA PROHIBIDA DETECTADA - PAUSANDO PUBLICACIÓN:
      Categoría: CBT412529 (Monoculars)
      Bloqueada en: MLM, MLA
      → Agregada a blacklist global
      ⏸️  Item MLB123456789 PAUSADO exitosamente
      → Evitando suspensiones futuras en otros países
      → Futuros productos evitarán esta categoría automáticamente
   ```

### Segundo Producto Similar

1. **Otro Monocular** llega al pipeline
2. Category Matcher carga blacklist al iniciar
3. CBT412529 está excluido automáticamente
4. AI elige categoría alternativa (ej: CBT8888 - Binoculars & Monoculars - Tools)
5. Publicación exitosa en todos los países

---

## 🔧 Mantenimiento

### Ver Blacklist Actual

```bash
cat storage/category_blacklist_global.json | jq '.blacklist'
```

### Ver Detalles de Categoría Específica

```bash
cat storage/category_blacklist_global.json | jq '.details.CBT412529'
```

### Ver Items Pausados por Categoría Prohibida

```bash
# Buscar en base de datos items con categorías prohibidas
sqlite3 storage/listings_database.db "
  SELECT asin, item_id, status
  FROM listings
  WHERE status = 'paused'
  AND category_id IN (
    SELECT json_each.value
    FROM json_each((SELECT json(blacklist) FROM category_blacklist))
  )
"
```

### Eliminar Items Pausados (cleanup manual)

```python
# Script para eliminar items pausados automáticamente
import requests
import sqlite3

db = sqlite3.connect('storage/listings_database.db')
cursor = db.cursor()

# Obtener items pausados por categoría prohibida
cursor.execute("""
    SELECT item_id FROM listings
    WHERE status = 'paused'
    AND category_id = 'CBT412529'
""")

for (item_id,) in cursor.fetchall():
    # Eliminar de ML
    response = requests.delete(
        f'https://api.mercadolibre.com/items/{item_id}',
        headers={'Authorization': f'Bearer {ML_ACCESS_TOKEN}'}
    )
    if response.status_code == 200:
        print(f"✅ Item {item_id} eliminado")
        # Actualizar en DB
        cursor.execute("UPDATE listings SET status='deleted' WHERE item_id=?", (item_id,))

db.commit()
db.close()
```

### Eliminar Categoría de Blacklist (si fue error)

```python
from src.utils.category_blacklist_manager import CategoryBlacklistManager

manager = CategoryBlacklistManager()
manager.blacklist_data["blacklist"].remove("CBT412529")
del manager.blacklist_data["details"]["CBT412529"]
manager._save_blacklist()
```

### Limpiar Blacklist Completa

```bash
rm storage/category_blacklist_global.json
# Se recreará automáticamente en la próxima detección
```

---

## 📈 Métricas y Monitoreo

### Estadísticas de Blacklist

```python
from src.utils.category_blacklist_manager import CategoryBlacklistManager

manager = CategoryBlacklistManager()
print(f"Total categorías prohibidas: {len(manager.get_blacklist())}")

for cat_id in manager.get_blacklist():
    details = manager.get_category_details(cat_id)
    print(f"{cat_id}: {details['name']}")
    print(f"  Bloqueada en: {', '.join(details['blocked_in'])}")
    print(f"  Suspendida en: {', '.join(details['suspended_in'])}")
    print(f"  Ejemplos: {', '.join(details['asin_examples'])}")
```

---

## ⚠️ Limitaciones Conocidas

1. **No hay pre-escaneo**: No podemos detectar categorías prohibidas sin intentar publicar
2. **Suspensiones tardías**: Algunos países aceptan la publicación y suspenden días después
   - **Mitigación**: Sistema pausa automáticamente items cuando detecta categoría prohibida
3. **Cobertura progresiva**: La blacklist se construye incrementalmente con productos reales
4. **False negatives iniciales**: Primera vez que se usa una categoría prohibida, fallará
   - **Mitigación**: Item se pausa inmediatamente para evitar suspensiones en otros países
5. **Items pausados persisten**: Items pausados siguen existiendo en ML, solo están inactivos
   - No se eliminan automáticamente
   - Usuario debe revisar y eliminar manualmente si lo desea

---

## 🎯 Mejoras Futuras

1. **ML Model**: Entrenar modelo para predecir categorías riesgosas basado en patrones
2. **Categorías hermanas**: Cuando una está prohibida, sugerir hermanas permitidas
3. **Dashboard**: UI para visualizar blacklist y estadísticas
4. **Alertas proactivas**: Notificar cuando se detectan patrones sospechosos

---

## 📚 Referencias

- [MercadoLibre API - Categories](https://developers.mercadolibre.com/en_us/categories)
- [CBT (Cross Border Trade) Documentation](https://developers.mercadolibre.com/en_us/cbt)
- Error cause_id 5100: "Category not allowed" (undocumented)

---

**Fecha de implementación**: 2025-12-08
**Autor**: Pipeline de automatización
**Versión**: 1.0
