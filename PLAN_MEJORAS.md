# Plan de Mejoras para main3.py

## Problemas a Resolver

### 1. Validación de Categorías Demasiado Estricta
- **Productos afectados:** B092RCLKHN, B0BGQLZ921, B0D3H3NKBN, B0D1Z99167, B0BRNY9HZB
- **Solución:**
  - Desactivar validación IA de categorías (solo usar embeddings + fallback)
  - Permitir confianza >= 0.70 en lugar de exigir 0.90

### 2. Atributo BRAND Faltante
- **Productos afectados:** B0BXSLRQH7, B081SRSNWW, B0CLC6NBBX
- **Solución:**
  - Extraer brand de: `attributes[0].brand` o `summaries[0].brand`
  - Si no existe, usar "Generic" como fallback
  - Asegurar que BRAND siempre se incluya en attributes

### 3. GTIN Inválido
- **Productos afectados:** B0CLC6NBBX
- **Solución:**
  - Extraer UPC de: `attributes[0].itemClassificationMarketplace[0].classificationValues[0].value`
  - Si no hay UPC válido, **NO incluir GTIN** (es opcional en muchas categorías)
  - NUNCA usar el ASIN como GTIN

### 4. Shipping Mode No Soportado
- **Productos afectados:** B0DRW69H11 y otros
- **Solución:**
  - Usar solo países que soporten el shipping actual
  - Filtrar países que retornen error 5101
  - Si todos fallan con un logistic_type, intentar otro

### 5. Net Proceeds No Configurado
- **Productos afectados:** B0DRW69H11 (México)
- **Solución:**
  - Detectar error 5246
  - Excluir ese país de la publicación
  - Continuar con los demás países

## Cambios en el Código

### src/ai_validators.py
```python
# Línea ~100: Relajar validación de categoría
- if category_match < 0.90:
+ if category_match < 0.70:  # Más permisivo
```

### src/transform_mapper_new.py o src/unified_transformer.py
```python
# Extraer brand correctamente
def extract_brand(amazon_json):
    # Intentar múltiples fuentes
    brand = None

    # Opción 1: attributes[0].brand
    if 'attributes' in amazon_json and amazon_json['attributes']:
        brand = amazon_json['attributes'][0].get('brand')

    # Opción 2: summaries[0].brand
    if not brand and 'summaries' in amazon_json and amazon_json['summaries']:
        brand = amazon_json['summaries'][0].get('brand')

    # Fallback
    return brand or "Generic"

# Extraer UPC/GTIN correctamente
def extract_gtin(amazon_json):
    try:
        classifications = amazon_json['attributes'][0]['itemClassificationMarketplace']
        for classification in classifications:
            if classification.get('classificationType') == 'UPC':
                upc = classification['classificationValues'][0]['value']
                if len(upc) >= 12:  # UPC válido
                    return upc
    except:
        pass

    return None  # No incluir GTIN si no hay válido
```

### src/mainglobal.py
```python
# Línea ~200: Manejar errores de shipping y net proceeds
def publish_item(payload):
    response = requests.post(url, json=payload)

    if response.status_code == 200:
        result = response.json()

        # Filtrar solo países exitosos
        successful_countries = []
        for site_item in result.get('site_items', []):
            if 'error' not in site_item:
                successful_countries.append(site_item)

        if successful_countries:
            # Éxito parcial o total
            return {
                'status': 'success',
                'countries': successful_countries,
                'item_id': result.get('id')
            }

    # ... resto del código
```

## Resultado Esperado

Con estos cambios, **100% (14/14)** de los productos deberían publicarse exitosamente.
