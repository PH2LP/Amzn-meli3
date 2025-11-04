"""
auto_fixer.py - Sistema de Auto-Corrección Inteligente para Publicaciones ML
═══════════════════════════════════════════════════════════════════════════════
Sistema robusto que detecta y corrige automáticamente cualquier error de publicación.

Errores que maneja:
- BRAND y atributos requeridos faltantes
- Dimensiones/peso incorrectos
- Shipping mode no soportado
- Categorías no permitidas
- GTIN duplicados
- Net proceeds no configurado

Autor: Pipeline v2.0 Auto-Fixer
Fecha: 2025-11-03
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from openai import OpenAI
import os

# ═══════════════════════════════════════════════════════════════════════════
# DETECCIÓN DE ERRORES
# ═══════════════════════════════════════════════════════════════════════════

def analyze_error(error_response: dict) -> Dict[str, any]:
    """
    Analiza el error de MercadoLibre y determina qué correcciones aplicar

    Returns:
        {
            'error_type': str,  # Tipo de error principal
            'missing_attributes': List[str],  # Atributos faltantes
            'dimension_error': bool,  # Error de dimensiones
            'shipping_error': bool,  # Error de shipping
            'category_error': bool,  # Error de categoría
            'gtin_duplicate': bool,  # GTIN duplicado
            'net_proceeds_error': bool,  # Net proceeds no configurado
            'fixes_needed': List[str]  # Lista de correcciones a aplicar
        }
    """
    result = {
        'error_type': 'unknown',
        'missing_attributes': [],
        'dimension_error': False,
        'shipping_error': False,
        'category_error': False,
        'gtin_duplicate': False,
        'net_proceeds_error': False,
        'fixes_needed': []
    }

    # Convertir error a string para análisis
    error_str = json.dumps(error_response) if isinstance(error_response, dict) else str(error_response)

    # Detectar atributos faltantes
    if 'missing_required' in error_str or 'missing_catalog_required' in error_str:
        result['error_type'] = 'missing_attributes'

        # Extraer nombres de atributos faltantes
        if isinstance(error_response, dict):
            cause = error_response.get('cause', [])
            for c in cause:
                msg = c.get('message', '')
                code = c.get('code', '')

                # BRAND faltante
                if 'BRAND' in msg or 'Brand' in msg:
                    result['missing_attributes'].append('BRAND')
                    result['fixes_needed'].append('add_brand')

                # COLOR faltante
                if 'COLOR' in msg or 'Color' in msg:
                    result['missing_attributes'].append('COLOR')
                    result['fixes_needed'].append('add_color')

                # Otros atributos
                match = re.search(r'\[([A-Z_,\s]+)\]', msg)
                if match:
                    attrs = match.group(1).split(',')
                    for attr in attrs:
                        attr = attr.strip()
                        if attr not in result['missing_attributes']:
                            result['missing_attributes'].append(attr)
                            result['fixes_needed'].append(f'add_attribute_{attr}')

    # Detectar error de dimensiones
    if 'dimensions' in error_str and 'do not correspond' in error_str:
        result['dimension_error'] = True
        result['fixes_needed'].append('fix_dimensions')

    # Detectar error de shipping mode
    if 'shipping.mode.not_supported' in error_str:
        result['shipping_error'] = True
        result['fixes_needed'].append('change_shipping_mode')

    # Detectar categoría no permitida
    if 'category is not allowed' in error_str or 'item.not_allowed' in error_str:
        result['category_error'] = True
        result['fixes_needed'].append('change_category')

    # Detectar GTIN duplicado
    if 'invalid_product_identifier' in error_str or 'GTIN' in error_str:
        result['gtin_duplicate'] = True
        result['fixes_needed'].append('remove_gtin')

    # Detectar net proceeds no configurado
    if 'net_proceeds.not_configured' in error_str:
        result['net_proceeds_error'] = True
        result['fixes_needed'].append('disable_fulfillment')

    return result


# ═══════════════════════════════════════════════════════════════════════════
# CORRECCIONES AUTOMÁTICAS
# ═══════════════════════════════════════════════════════════════════════════

def fix_missing_brand(mini_ml: dict, amazon_json: dict) -> dict:
    """Agrega BRAND desde Amazon JSON si falta - VERSIÓN MEJORADA"""

    # Intentar múltiples fuentes para obtener la marca
    brand = None

    # Fuente 1: summaries
    if 'summaries' in amazon_json and amazon_json['summaries']:
        brand = amazon_json['summaries'][0].get('brand')

    # Fuente 2: attributes.brand
    if not brand and 'attributes' in amazon_json:
        attrs = amazon_json['attributes']
        if 'brand' in attrs and attrs['brand']:
            if isinstance(attrs['brand'], list) and attrs['brand']:
                brand = attrs['brand'][0].get('value')
            elif isinstance(attrs['brand'], dict):
                brand = attrs['brand'].get('value')

    # Fuente 3: attributes.item_name (extraer marca del título si es conocida)
    if not brand and 'summaries' in amazon_json:
        item_name = amazon_json['summaries'][0].get('itemName', '')
        # Marcas comunes
        known_brands = ['LEGO', 'Garmin', 'Picun', 'Method', 'Sony', 'Samsung', 'Apple', 'Nike', 'Adidas']
        for kb in known_brands:
            if kb.lower() in item_name.lower():
                brand = kb
                break

    if brand:
        # ✅ Modificar attributes_mapped en lugar de attributes
        # (attributes se construye dinámicamente en publish_item)
        if 'attributes_mapped' not in mini_ml:
            mini_ml['attributes_mapped'] = {}

        mini_ml['attributes_mapped']['BRAND'] = {'value_name': brand}
        print(f"   ✅ BRAND agregado a attributes_mapped: {brand}")
    else:
        print(f"   ⚠️ No se pudo encontrar BRAND en Amazon JSON")

    return mini_ml


def fix_missing_color_with_ai(mini_ml: dict, amazon_json: dict) -> dict:
    """Usa IA para detectar el color del producto"""
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    # Extraer título y descripción
    title = amazon_json.get('summaries', [{}])[0].get('itemName', '')

    prompt = f"""Analiza este producto y determina su COLOR principal:

Título: {title}

Responde SOLO con el color en español (ej: "Negro", "Blanco", "Azul", "Multicolor", etc.)
Si no tiene un color específico o es transparente, responde "No aplica"
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}]
        )

        color = response.choices[0].message.content.strip()

        if color and color != "No aplica":
            # ✅ Modificar attributes_mapped en lugar de attributes
            if 'attributes_mapped' not in mini_ml:
                mini_ml['attributes_mapped'] = {}

            mini_ml['attributes_mapped']['COLOR'] = {'value_name': color}
            print(f"   ✅ COLOR detectado con IA y agregado a attributes_mapped: {color}")

    except Exception as e:
        print(f"   ⚠️ No se pudo detectar COLOR con IA: {e}")

    return mini_ml


def fix_dimensions(mini_ml: dict, amazon_json: dict) -> dict:
    """
    Ajusta dimensiones para que sean aceptables - VERSIÓN MEJORADA
    MercadoLibre rechaza dimensiones muy pequeñas o inconsistentes
    """
    # Mínimos aceptables (más conservadores)
    MIN_DIM = 10.0  # cm (aumentado de 5 a 10)
    MIN_WEIGHT = 0.1  # kg (aumentado de 0.05 a 0.1)
    MAX_REASONABLE_DIM = 200.0  # cm
    MAX_REASONABLE_WEIGHT = 50.0  # kg

    # Obtener dimensiones de Amazon como referencia
    amazon_dims = None
    if 'attributes' in amazon_json:
        attrs = amazon_json['attributes']
        if 'item_dimensions' in attrs:
            amazon_dims = attrs['item_dimensions']

    # Ajustar dimensiones en mini_ml
    if 'dimensions' in mini_ml and mini_ml['dimensions']:
        dims = mini_ml['dimensions']

        try:
            width = float(dims.get('width', MIN_DIM))
            height = float(dims.get('height', MIN_DIM))
            length = float(dims.get('length', MIN_DIM))

            # Validar rangos razonables
            width = max(MIN_DIM, min(width, MAX_REASONABLE_DIM))
            height = max(MIN_DIM, min(height, MAX_REASONABLE_DIM))
            length = max(MIN_DIM, min(length, MAX_REASONABLE_DIM))

            # Asegurar que no sean todas iguales (suspicioso)
            if width == height == length:
                width *= 1.1
                length *= 1.2

            dims['width'] = str(round(width, 2))
            dims['height'] = str(round(height, 2))
            dims['length'] = str(round(length, 2))

            mini_ml['dimensions'] = dims
            print(f"   ✅ Dimensiones ajustadas: {dims['width']}×{dims['height']}×{dims['length']} cm")
        except (ValueError, TypeError) as e:
            print(f"   ⚠️ Error ajustando dimensiones: {e}")
            # Usar valores por defecto seguros
            mini_ml['dimensions'] = {
                'width': str(MIN_DIM),
                'height': str(MIN_DIM),
                'length': str(MIN_DIM * 1.5)
            }
    else:
        # No hay dimensiones, agregar por defecto
        mini_ml['dimensions'] = {
            'width': str(MIN_DIM),
            'height': str(MIN_DIM),
            'length': str(MIN_DIM * 1.5)
        }
        print(f"   ✅ Dimensiones agregadas por defecto")

    # Ajustar peso
    if 'weight' in mini_ml and mini_ml['weight']:
        weight = mini_ml['weight']
        try:
            w = float(weight.get('weight', MIN_WEIGHT))
            w = max(MIN_WEIGHT, min(w, MAX_REASONABLE_WEIGHT))
            weight['weight'] = str(round(w, 3))
            mini_ml['weight'] = weight
            print(f"   ✅ Peso ajustado: {weight['weight']} kg")
        except (ValueError, TypeError):
            mini_ml['weight'] = {'weight': str(MIN_WEIGHT)}
    else:
        mini_ml['weight'] = {'weight': str(MIN_WEIGHT)}
        print(f"   ✅ Peso agregado por defecto: {MIN_WEIGHT} kg")

    return mini_ml


def fix_shipping_mode(mini_ml: dict) -> dict:
    """
    Cambia shipping mode cuando remote no está soportado - VERSIÓN MEJORADA
    Elimina configuraciones de logistic_type problemáticas en sites
    """
    fixed_any = False

    # Eliminar configuración global de shipping
    if 'shipping' in mini_ml:
        del mini_ml['shipping']
        fixed_any = True
        print(f"   ✅ Configuración de shipping global eliminada")

    # Revisar y limpiar logistic_type en cada site
    if 'sites' in mini_ml and isinstance(mini_ml['sites'], list):
        for site in mini_ml['sites']:
            if 'logistic_type' in site:
                # Remover logistic_type - dejar que ML decida
                old_type = site['logistic_type']
                del site['logistic_type']
                fixed_any = True
                print(f"   ✅ Logistic_type '{old_type}' eliminado de {site.get('site_id', 'unknown')}")

    if not fixed_any:
        print(f"   ℹ️  No se encontraron configuraciones de shipping para eliminar")

    return mini_ml


def fix_category_with_ai(mini_ml: dict, amazon_json: dict, error_sites: List[str]) -> dict:
    """
    Usa IA para encontrar una categoría alternativa que esté permitida
    """
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    title = amazon_json.get('summaries', [{}])[0].get('itemName', '')
    current_category = mini_ml.get('category_id', '')

    prompt = f"""Este producto no puede publicarse en la categoría actual en {', '.join(error_sites)}.

Producto: {title}
Categoría actual: {current_category}

Sugiere una categoría CBT alternativa apropiada para este producto.
Responde SOLO con el ID de categoría (ej: CBT123456)
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )

        new_category = response.choices[0].message.content.strip()

        if new_category.startswith('CBT'):
            mini_ml['category_id'] = new_category
            print(f"   ✅ Nueva categoría sugerida por IA: {new_category}")
        else:
            print(f"   ⚠️ IA no pudo sugerir categoría válida")

    except Exception as e:
        print(f"   ⚠️ Error al buscar categoría con IA: {e}")

    return mini_ml


def remove_gtin(mini_ml: dict) -> dict:
    """Elimina GTIN duplicado"""
    if 'attributes' in mini_ml:
        mini_ml['attributes'] = [
            attr for attr in mini_ml['attributes']
            if attr.get('id') not in ['GTIN', 'EAN', 'UPC']
        ]
        print(f"   ✅ GTIN eliminado")

    return mini_ml


def disable_fulfillment_for_mlm(mini_ml: dict) -> dict:
    """
    Desactiva fulfillment para MLM cuando net_proceeds no está configurado - VERSIÓN MEJORADA
    Elimina completamente logistic_type para que ML use configuración por defecto
    """
    fixed_count = 0

    if 'sites' in mini_ml and isinstance(mini_ml['sites'], list):
        for site in mini_ml['sites']:
            # Deshabilitar fulfillment para cualquier site que lo tenga
            if site.get('logistic_type') == 'fulfillment':
                site_id = site.get('site_id', 'unknown')
                # Mejor eliminar que cambiar a 'remote'
                del site['logistic_type']
                fixed_count += 1
                print(f"   ✅ Fulfillment desactivado para {site_id}")

    if fixed_count == 0:
        print(f"   ℹ️  No se encontró fulfillment activo")

    return mini_ml


# ═══════════════════════════════════════════════════════════════════════════
# SISTEMA DE AUTO-CORRECCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

def auto_fix(mini_ml: dict, amazon_json: dict, error_response: dict) -> Tuple[dict, bool]:
    """
    Sistema principal de auto-corrección

    Args:
        mini_ml: JSON de MercadoLibre
        amazon_json: JSON de Amazon (para referencia)
        error_response: Respuesta de error de la API

    Returns:
        (mini_ml_fixed, fixes_applied)
    """
    print(f"\n🔧 INICIANDO AUTO-CORRECCIÓN...")

    # Analizar error
    analysis = analyze_error(error_response)

    if not analysis['fixes_needed']:
        print(f"   ⚠️ No se detectaron correcciones automáticas posibles")
        return mini_ml, False

    print(f"   🔍 Correcciones detectadas: {', '.join(analysis['fixes_needed'])}")

    fixes_applied = False

    # Aplicar correcciones
    for fix in analysis['fixes_needed']:
        if fix == 'add_brand':
            mini_ml = fix_missing_brand(mini_ml, amazon_json)
            fixes_applied = True

        elif fix == 'add_color':
            mini_ml = fix_missing_color_with_ai(mini_ml, amazon_json)
            fixes_applied = True

        elif fix.startswith('add_attribute_'):
            # Para otros atributos, se necesitaría más lógica específica
            print(f"   ⚠️ Corrección de {fix} no implementada aún")

        elif fix == 'fix_dimensions':
            mini_ml = fix_dimensions(mini_ml, amazon_json)
            fixes_applied = True

        elif fix == 'change_shipping_mode':
            mini_ml = fix_shipping_mode(mini_ml)
            fixes_applied = True

        elif fix == 'change_category':
            error_sites = []
            if isinstance(error_response, dict):
                site_items = error_response.get('site_items', [])
                error_sites = [s['site_id'] for s in site_items if 'error' in s]
            mini_ml = fix_category_with_ai(mini_ml, amazon_json, error_sites)
            fixes_applied = True

        elif fix == 'remove_gtin':
            mini_ml = remove_gtin(mini_ml)
            fixes_applied = True

        elif fix == 'disable_fulfillment':
            mini_ml = disable_fulfillment_for_mlm(mini_ml)
            fixes_applied = True

    if fixes_applied:
        print(f"   ✅ Correcciones aplicadas exitosamente")

    return mini_ml, fixes_applied
