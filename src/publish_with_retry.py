#!/usr/bin/env python3
"""
Sistema de publicación con retry automático.
Maneja GTINs duplicados, errores de BRAND, y otros errores comunes.
"""

import sys
import os
import json
from pathlib import Path
from typing import Optional, Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mainglobal import publish_item
from src.category_validator import validate_and_fix_category


def publish_with_smart_retry(
    mini_ml: dict,
    ml_token: str,
    max_retries: int = 3
) -> Optional[Dict]:
    """
    Publica un item con retry inteligente según el error.

    Estrategia de retry:
    1. GTIN duplicado (3701) → Retry sin GTIN
    2. BRAND no válido (147, 3250) → Cambiar a categoría flexible y retry
    3. Categoría inválida (126) → Usar predictor ML y retry
    4. Otros errores → Reportar sin retry

    Args:
        mini_ml: Datos del producto a publicar
        ml_token: Token de ML
        max_retries: Número máximo de intentos

    Returns:
        Resultado de la publicación o None si falla
    """
    asin = mini_ml.get('asin', 'UNKNOWN')
    original_gtins = mini_ml.get('gtins', []).copy()
    original_category = mini_ml.get('category_id', '')

    print(f"\n🚀 Publicando {asin}...")
    print(f"   Categoría: {original_category}")
    print(f"   GTINs: {len(original_gtins)}")

    for attempt in range(max_retries):
        try:
            # Intento de publicación
            result = publish_item(mini_ml)

            if result:
                # Éxito
                print(f"✅ {asin}: Publicado exitosamente")
                if attempt > 0:
                    print(f"   (Después de {attempt} reintentos)")
                return result

            # Si publish_item retorna None, no hay resultado
            print(f"⚠️ {asin}: Sin resultado en intento {attempt + 1}")

        except Exception as e:
            error_msg = str(e)
            print(f"❌ {asin}: Error en intento {attempt + 1}: {error_msg[:100]}")

            # Analizar error y decidir retry
            should_retry, modified_mini = analyze_error_and_fix(
                error_msg,
                mini_ml,
                ml_token,
                attempt
            )

            if should_retry and modified_mini:
                mini_ml = modified_mini
                print(f"🔄 Reintentando con modificaciones...")
                continue
            else:
                # Error no recuperable
                print(f"❌ {asin}: Error no recuperable")
                break

    # Si llegamos aquí, fallaron todos los intentos
    print(f"❌ {asin}: Falló después de {max_retries} intentos")
    return None


def analyze_error_and_fix(
    error_msg: str,
    mini_ml: dict,
    ml_token: str,
    attempt: int
) -> tuple[bool, Optional[Dict]]:
    """
    Analiza un error de publicación y decide cómo corregirlo.

    Parsea el JSON del error de ML para detectar cause_id específicos.

    Returns:
        tuple: (should_retry, modified_mini_ml)
    """
    asin = mini_ml.get('asin', 'UNKNOWN')

    # Parsear JSON del error si está presente
    error_data = {}
    cause_ids = set()

    try:
        # El error viene como "POST url → 400 {json}"
        # Extraer el JSON
        if '{' in error_msg and '}' in error_msg:
            json_start = error_msg.index('{')
            json_str = error_msg[json_start:]
            error_data = json.loads(json_str)

            # Extraer cause_ids
            for cause in error_data.get('cause', []):
                cid = cause.get('cause_id')
                if cid:
                    cause_ids.add(cid)

            # Debug
            if cause_ids:
                print(f"   📋 Error codes detectados: {cause_ids}")

    except json.JSONDecodeError:
        # Si no puede parsear, usar string matching
        pass

    # 1. GTIN duplicado (Error 3701)
    if 3701 in cause_ids or 'invalid_product_identifier' in error_msg:
        print(f"   → GTIN duplicado detectado (3701)")

        if mini_ml.get('gtins'):
            # Primera vez: eliminar GTINs
            print(f"   → Eliminando GTINs y reintentando...")
            mini_ml['gtins'] = []
            return True, mini_ml
        else:
            # Ya intentamos sin GTIN
            return False, None

    # 2. BRAND requerido pero no válido (Error 147, 3250)
    if 147 in cause_ids or 3250 in cause_ids or 'BRAND' in error_msg:
        print(f"   → BRAND no válido en categoría actual (147/3250)")

        if attempt == 0:
            # Primera vez: validar y cambiar categoría
            print(f"   → Validando categoría y cambiando si es necesario...")
            fixed_mini, warnings = validate_and_fix_category(mini_ml, ml_token)

            for w in warnings:
                print(f"      {w}")

            return True, fixed_mini
        else:
            # Ya intentamos con validación
            return False, None

    # 3. Categoría inválida (Error 126)
    if 126 in cause_ids or 'category' in error_msg.lower():
        print(f"   → Categoría inválida (126)")

        if attempt == 0:
            # Validar categoría con fallback a ML predictor
            print(f"   → Validando categoría con predictor ML...")
            fixed_mini, warnings = validate_and_fix_category(mini_ml, ml_token)

            for w in warnings:
                print(f"      {w}")

            return True, fixed_mini
        else:
            return False, None

    # 4. COLOR u otro atributo catalog_required (Error 3704)
    if 3704 in cause_ids or 'missing_catalog_required' in error_msg:
        print(f"   → Atributo catalog_required faltante (3704)")

        # Detectar qué atributo falta
        missing_attr = None
        for cause in error_data.get('cause', []):
            if cause.get('cause_id') == 3704:
                msg = cause.get('message', '')
                if 'Color' in msg:
                    missing_attr = 'COLOR'
                elif 'Brand' in msg:
                    missing_attr = 'BRAND'

        if missing_attr and missing_attr in mini_ml.get('attributes_mapped', {}):
            # Eliminar el atributo problemático
            del mini_ml['attributes_mapped'][missing_attr]
            print(f"   → {missing_attr} eliminado, reintentando...")
            return True, mini_ml

    # 5. Atributo con formato inválido (Error 3708)
    if 3708 in cause_ids or 'invalid_format' in error_msg:
        print(f"   → Formato de atributo inválido (3708)")

        # Buscar atributo problemático en el mensaje
        if 'UNIT_VOLUME' in error_msg:
            # Arreglar formato UNIT_VOLUME
            attrs = mini_ml.get('attributes_mapped', {})
            if 'UNIT_VOLUME' in attrs:
                # Cambiar formato a "X fl oz" o "X L"
                current = attrs['UNIT_VOLUME'].get('value_name', '')
                # Normalizar formato
                import re
                match = re.search(r'(\d+\.?\d*)\s*(fl\s*oz|L|ml|mL)', current, re.IGNORECASE)
                if match:
                    number = match.group(1)
                    unit = match.group(2).lower()
                    if 'fl' in unit:
                        attrs['UNIT_VOLUME']['value_name'] = f"{number} fl oz"
                    elif unit == 'l':
                        attrs['UNIT_VOLUME']['value_name'] = f"{number} L"
                    elif 'ml' in unit:
                        attrs['UNIT_VOLUME']['value_name'] = f"{number} mL"

                    print(f"   → UNIT_VOLUME corregido a: {attrs['UNIT_VOLUME']['value_name']}")
                    return True, mini_ml

    # 6. Otros errores no recuperables
    if cause_ids:
        print(f"   → Error no recuperable: {cause_ids}")
    else:
        print(f"   → Error no recuperable o desconocido")
    return False, None


def batch_publish_with_retry(
    asins: List[str],
    ml_token: str
) -> Dict[str, List[str]]:
    """
    Publica un lote de ASINs con retry inteligente.

    Returns:
        Dict con 'success', 'failed', 'warnings'
    """
    results = {
        'success': [],
        'failed': [],
        'warnings': []
    }

    for i, asin in enumerate(asins, 1):
        print(f"\n{'=' * 70}")
        print(f"{i}/{len(asins)}. {asin}")
        print(f"{'=' * 70}")

        # Cargar mini_ml
        mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")

        if not mini_path.exists():
            print(f"❌ Mini ML no existe para {asin}")
            results['failed'].append(asin)
            continue

        with open(mini_path) as f:
            mini_ml = json.load(f)

        # Publicar con retry
        result = publish_with_smart_retry(mini_ml, ml_token)

        if result:
            results['success'].append(asin)
        else:
            results['failed'].append(asin)

        # Delay entre publicaciones
        import time
        time.sleep(3)

    return results


def main():
    """Test del sistema de retry"""
    import os

    # Cargar tokens
    ml_token = os.getenv('ML_TOKEN')
    if not ml_token:
        print("❌ ML_TOKEN no encontrado")
        return

    # Test con un ASIN problemático
    test_asin = 'B092RCLKHN'  # Garmin con GTIN duplicado

    mini_path = Path(f"storage/logs/publish_ready/{test_asin}_mini_ml.json")
    if not mini_path.exists():
        print(f"❌ {test_asin} no existe")
        return

    with open(mini_path) as f:
        mini_ml = json.load(f)

    print("🧪 TESTING PUBLISH WITH RETRY")
    print("=" * 70)

    result = publish_with_smart_retry(mini_ml, ml_token)

    if result:
        print(f"\n✅ Test exitoso!")
    else:
        print(f"\n❌ Test falló")


if __name__ == "__main__":
    main()
