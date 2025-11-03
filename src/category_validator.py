#!/usr/bin/env python3
"""
Validador de categorías y atributos con fallback automático.
Valida que la categoría existe y que BRAND/COLOR están en el schema antes de publicar.
"""

import requests
import json
from typing import Optional, Dict, List, Tuple
from pathlib import Path


def validate_category_and_attributes(
    category_id: str,
    brand: str,
    attributes: list,
    ml_token: str
) -> Tuple[str, List[dict], List[str]]:
    """
    Valida una categoría y sus atributos contra el schema de ML.

    Returns:
        tuple: (category_id_validado, attributes_validos, warnings)
    """
    warnings = []

    # 1. Validar que la categoría existe
    try:
        cat_response = requests.get(
            f"https://api.mercadolibre.com/categories/{category_id}",
            headers={"Authorization": f"Bearer {ml_token}"},
            timeout=10
        )

        if cat_response.status_code == 404:
            warnings.append(f"❌ Categoría {category_id} no existe")
            return None, [], warnings

        cat_data = cat_response.json()

        # Verificar que permite publicar
        if not cat_data.get('settings', {}).get('listing_allowed', True):
            warnings.append(f"⚠️ Categoría {category_id} no permite publicar")
            return None, [], warnings

    except Exception as e:
        warnings.append(f"⚠️ Error validando categoría: {e}")
        return category_id, attributes, warnings

    # 2. Obtener schema de atributos
    try:
        schema_response = requests.get(
            f"https://api.mercadolibre.com/categories/{category_id}/attributes",
            headers={"Authorization": f"Bearer {ml_token}"},
            timeout=10
        )

        if schema_response.status_code != 200:
            warnings.append(f"⚠️ No se pudo obtener schema de {category_id}")
            return category_id, attributes, warnings

        schema = schema_response.json()

    except Exception as e:
        warnings.append(f"⚠️ Error obteniendo schema: {e}")
        return category_id, attributes, warnings

    # 3. Crear mapa de atributos válidos
    schema_map = {}
    required_attrs = set()

    for field in schema:
        attr_id = field.get('id')
        if not attr_id:
            continue

        schema_map[attr_id] = {
            'values': {},
            'value_type': field.get('value_type'),
            'required': False
        }

        # Verificar si es requerido
        tags = field.get('tags', {})
        if isinstance(tags, dict):
            if tags.get('required') or tags.get('catalog_required'):
                required_attrs.add(attr_id)

        # Mapear valores permitidos
        values = field.get('values', [])
        for v in values:
            val_id = v.get('id')
            val_name = v.get('name', '').lower().strip()
            if val_id and val_name:
                schema_map[attr_id]['values'][val_name] = str(val_id)

    # 4. Validar BRAND específicamente
    brand_valid = True
    if brand and 'BRAND' in schema_map:
        brand_lower = brand.lower().strip()
        if schema_map['BRAND']['values']:  # Si tiene valores predefinidos
            if brand_lower not in schema_map['BRAND']['values']:
                warnings.append(f"⚠️ BRAND '{brand}' no está en schema de {category_id}")
                brand_valid = False

    # 5. Validar otros atributos críticos (COLOR, etc)
    validated_attributes = []
    for attr in attributes:
        attr_id = attr.get('id')
        value_name = attr.get('value_name', '').lower().strip()

        if attr_id not in schema_map:
            # Atributo no existe en schema, descartar
            continue

        attr_schema = schema_map[attr_id]

        # Si tiene valores predefinidos, validar
        if attr_schema['values']:
            if value_name in attr_schema['values']:
                # Usar value_id del schema
                validated_attributes.append({
                    'id': attr_id,
                    'value_id': attr_schema['values'][value_name],
                    'value_name': attr.get('value_name')
                })
            else:
                # Valor no válido, descartar
                warnings.append(f"⚠️ {attr_id}='{attr.get('value_name')}' no válido")
        else:
            # Atributo libre, mantener
            validated_attributes.append(attr)

    # 6. Decidir si necesitamos cambiar categoría
    if not brand_valid and 'BRAND' in required_attrs:
        # BRAND es requerido pero no está en schema → usar categoría flexible
        warnings.append(f"→ Cambiando a categoría flexible (BRAND requerido pero no disponible)")
        return None, [], warnings

    return category_id, validated_attributes, warnings


def get_flexible_category_for_product(product_type: str) -> str:
    """
    Retorna categoría flexible según tipo de producto.
    Estas categorías tienen menos restricciones en BRAND.
    """
    flexible_categories = {
        'electronics': 'CBT1157',      # Categoría flexible para electrónicos
        'beauty': 'CBT29890',           # Beauty and Personal Care
        'toys': 'CBT1157',              # Juguetes
        'sports': 'CBT388015',          # Sports & Fitness
        'home': 'CBT1157',              # Home & Garden
        'jewelry': 'CBT29890',          # Jewelry
        'default': 'CBT1157'            # Categoría más flexible
    }

    # Intentar detectar tipo de producto
    product_type_lower = product_type.lower()

    for ptype, category in flexible_categories.items():
        if ptype in product_type_lower:
            return category

    return flexible_categories['default']


def use_ml_category_predictor(title: str, ml_token: str) -> Optional[Dict]:
    """
    Usa el predictor de categorías oficial de ML como fallback.

    Args:
        title: Título del producto EN INGLÉS
        ml_token: Token de acceso de ML

    Returns:
        Dict con category_id y attributes sugeridos, o None si falla
    """
    try:
        # Asegurarse que el título está en inglés (ya debería estarlo)
        response = requests.get(
            "https://api.mercadolibre.com/marketplace/domain_discovery/search",
            params={'q': title},
            headers={"Authorization": f"Bearer {ml_token}"},
            timeout=10
        )

        if response.status_code != 200:
            return None

        predictions = response.json()

        if not predictions or len(predictions) == 0:
            return None

        # Tomar primera predicción (mayor confianza)
        best_prediction = predictions[0]

        return {
            'category_id': best_prediction.get('category_id'),
            'domain_id': best_prediction.get('domain_id'),
            'attributes': best_prediction.get('attributes', [])
        }

    except Exception as e:
        print(f"⚠️ Error usando predictor ML: {e}")
        return None


def validate_and_fix_category(
    mini_ml: dict,
    ml_token: str
) -> Tuple[Dict, List[str]]:
    """
    Valida y corrige la categoría y atributos de un mini_ml.

    Proceso:
    1. Valida categoría actual
    2. Si BRAND falla → cambia a categoría flexible
    3. Si categoría no existe → usa predictor ML
    4. Valida atributos contra schema

    Returns:
        tuple: (mini_ml_corregido, warnings)
    """
    warnings = []
    category_id = mini_ml.get('category_id')
    brand = mini_ml.get('brand', '')
    attributes = mini_ml.get('attributes_mapped', {})
    title = mini_ml.get('title_ai', '')

    # Convertir attributes_mapped a lista
    attrs_list = []
    for attr_id, attr_data in attributes.items():
        attrs_list.append({
            'id': attr_id,
            'value_name': attr_data.get('value_name', ''),
            'value_id': attr_data.get('value_id')
        })

    # 1. Validar categoría actual
    validated_cat, validated_attrs, val_warnings = validate_category_and_attributes(
        category_id,
        brand,
        attrs_list,
        ml_token
    )

    warnings.extend(val_warnings)

    # 2. Si validación falló, buscar alternativa
    if not validated_cat:
        print(f"⚠️ Categoría {category_id} falló validación")

        # Opción A: Usar predictor ML
        print(f"🔍 Intentando predictor ML con título: {title[:60]}...")
        ml_prediction = use_ml_category_predictor(title, ml_token)

        if ml_prediction:
            validated_cat = ml_prediction['category_id']
            warnings.append(f"✅ Predictor ML sugiere: {validated_cat}")

            # Re-validar con nueva categoría
            validated_cat, validated_attrs, val_warnings2 = validate_category_and_attributes(
                validated_cat,
                brand,
                attrs_list,
                ml_token
            )
            warnings.extend(val_warnings2)

        # Opción B: Si ML falla, usar categoría flexible
        if not validated_cat:
            print(f"⚠️ Predictor ML falló, usando categoría flexible")
            product_type = mini_ml.get('category_name', 'default')
            validated_cat = get_flexible_category_for_product(product_type)
            warnings.append(f"→ Usando categoría flexible: {validated_cat}")

            # Re-validar con categoría flexible
            validated_cat, validated_attrs, val_warnings3 = validate_category_and_attributes(
                validated_cat,
                brand,
                attrs_list,
                ml_token
            )
            warnings.extend(val_warnings3)

    # 3. Actualizar mini_ml con datos validados
    mini_ml['category_id'] = validated_cat

    # Convertir validated_attrs de vuelta a dict
    new_attrs = {}
    for attr in validated_attrs:
        attr_id = attr['id']
        new_attrs[attr_id] = {
            'value_name': attr.get('value_name', ''),
            'value_id': attr.get('value_id')
        }

    mini_ml['attributes_mapped'] = new_attrs

    return mini_ml, warnings


def main():
    """Test de validación"""
    import os

    # Cargar token
    ml_token = os.getenv('ML_TOKEN')
    if not ml_token:
        print("❌ ML_TOKEN no encontrado")
        return

    # Test con categoría problemática
    test_mini = {
        'asin': 'B092RCLKHN',
        'category_id': 'CBT455414',
        'category_name': 'Sports Watch',
        'brand': 'Garmin',
        'title_ai': 'Garmin GPS Sports Watch Bluetooth',
        'attributes_mapped': {
            'BRAND': {'value_name': 'Garmin'},
            'COLOR': {'value_name': 'Black'},
            'MODEL': {'value_name': 'Forerunner 55'}
        }
    }

    print("🔍 TESTING CATEGORY VALIDATOR")
    print("=" * 70)

    fixed_mini, warnings = validate_and_fix_category(test_mini, ml_token)

    print(f"\n📊 Resultados:")
    print(f"Categoría original: {test_mini['category_id']}")
    print(f"Categoría validada: {fixed_mini['category_id']}")
    print(f"Atributos validados: {len(fixed_mini['attributes_mapped'])}")

    if warnings:
        print(f"\n⚠️ Advertencias:")
        for w in warnings:
            print(f"  • {w}")


if __name__ == "__main__":
    main()
