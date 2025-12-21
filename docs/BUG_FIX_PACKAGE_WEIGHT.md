# Bug Fix: Conversión Incorrecta de Pesos de Paquete

**Fecha**: 2025-12-11
**Archivo**: `src/pipeline/transform_mapper_new.py`
**Función afectada**: `get_pkg_dim()` y `_find_in_flat()`

## Resumen

Se encontraron 12 publicaciones (1% del total) con pesos de paquete incorrectos en la base de datos. El problema se debía a dos bugs en el código de extracción de dimensiones de paquete.

## Problema 1: Unidades no se extraían correctamente

### Causa
La función `_find_in_flat()` tenía dos problemas:

1. **Filtro de arrays demasiado estricto** (línea 243-245):
   ```python
   # ANTES
   if "[" in fk and not fk.endswith("value"):
       continue
   ```
   Esto bloqueaba las claves como `attributes.item_package_weight[0].unit`

2. **Lista de valores inválidos incluía unidades** (línea 229):
   ```python
   # ANTES
   invalid_values = {
       ...,
       "kilograms", "grams", "pounds", "ounces", "kg", "g", "lb", "oz",
       ...
   }
   ```
   Las unidades se descartaban como valores inválidos.

### Efecto
Cuando Amazon enviaba `1.168 pounds`, el sistema:
- ✅ Extraía el valor: `1.168`
- ❌ NO extraía la unidad: `None`
- ❌ Asumía `kg` por defecto
- ❌ Guardaba: `1.168 kg` (debería ser `0.53 kg`)

### Solución
```python
# DESPUÉS
# 1. Permitir claves que terminan en "unit"
if "[" in fk and not (fk.endswith("value") or fk.endswith("unit")):
    continue

# 2. Quitar unidades de la lista de valores inválidos
invalid_values = {
    "en_us", "en-us", "es_mx", "pt_br", "language_tag",
    "atvpdkikx0der", "a1am78c64um0y8", "marketplace_id",
    "default", "none", "null", "n/a", "na", "not specified", "unknown",
    "true", "false", "yes", "no"
}
```

## Problema 2: Búsqueda genérica capturaba peso incorrecto

### Causa
La función `get_pkg_dim()` buscaba con claves genéricas (líneas 260-264):
```python
# ANTES
for val_key in [
    f"attributes.item_package_dimensions[0].{kind}.value",
    f"item_package_dimensions.{kind}.value",
    f"package_dimensions.{kind}.value",
    f"{kind}.value"  # <-- Demasiado genérico!
] + PACKAGE_DIMENSION_KEYS.get(kind, []):
```

La clave `weight.value` coincidía con:
- `attributes.compatible_vesa_mount_specifications[0].screen_weight.value: 19.8`
- `attributes.item_weight[0].value: 11.0` (peso del producto)

En lugar del correcto:
- `attributes.item_package_weight[0].value: 5.062` (peso del paquete)

### Efecto
Para algunos productos con campos de peso adicionales:
- ❌ Extraía peso de pantalla: `19.8 kg` (ASIN B07T5SY43L)
- ❌ Extraía peso del producto: `11.0 kg`
- En lugar del peso del paquete: `5.062 kg`

### Solución
```python
# DESPUÉS
# Buscar SOLO en las claves específicas de PAQUETE
for val_key in PACKAGE_DIMENSION_KEYS.get(kind, []):
    v = _find_in_flat(flat, [val_key])
    if v is not None:
        val = extract_number(v)
        if val is not None: break
```

Y también se limpiaron las `unit_keys`:
```python
# ANTES
if kind == "weight":
    unit_keys = [
        "attributes.item_package_weight[0].unit",
        "item_package_weight.unit",
        "attributes.item_weight[0].unit",  # Peso del PRODUCTO
        "item_weight.unit",
        f"{kind}.unit"  # Demasiado genérico
    ]

# DESPUÉS
if kind == "weight":
    unit_keys = [
        "attributes.item_package_weight[0].unit",
        "item_package_weight.unit"
    ]
```

## ASINs Afectados

| ASIN | Peso Incorrecto | Peso Correcto |
|------|----------------|---------------|
| B09SVHP9X8 | 1.168 kg | 0.53 kg |
| B0BLJ3RRHD | 3.0 kg | 1.36 kg |
| B07T5SY43L | 19.8 kg | 5.06 kg |
| B0CTMHHJJC | 19.8 kg | 5.02 kg |
| B0F1XHP6JL | 19.8 kg | 5.47 kg |
| B009S750LA | 9.98 kg | 4.28 kg |
| B0BNWDV6R7 | 10.0 kg | 3.78 kg |
| B0F9FH8RYG | 1.37 kg | 0.62 kg |
| B0D91CCYPX | 3.1 kg | 1.41 kg |
| B07HC9RM8N | 1.0 kg | 0.041 kg |
| B084NY52HF | 10.0 kg | 4.54 kg |
| B002FXS4BM | 0.15 kg | 0.068 kg |

## Impacto

- **Total de publicaciones**: 1,199
- **Publicaciones afectadas**: 12 (1%)
- **Tipo de error**: Solo pesos incorrectos (dimensiones L/W/H estaban correctas)

## Acciones Tomadas

1. ✅ Bugs corregidos en `transform_mapper_new.py`
2. ✅ Pesos actualizados en `storage/listings_database.db`
3. ⚠️ **Publicaciones en ML NO pueden actualizarse** (son items CBT de catálogo)

## Prevención

- Todas las nuevas publicaciones usarán el código corregido
- Los pesos se extraerán correctamente de Amazon
- Las conversiones de libras a kilogramos funcionarán correctamente

## Scripts Creados

- `scripts/tools/verify_package_dimensions.py` - Verifica dimensiones ML vs Amazon
- `scripts/tools/fix_package_weights.py` - Corrige pesos en base de datos local
- `scripts/tools/update_ml_package_weights.py` - Intenta actualizar en ML (limitado por API)
