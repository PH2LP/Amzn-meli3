#!/usr/bin/env python3
"""
Amazon Product Pricing API
Obtiene precios y ofertas Prime de productos en Amazon
"""

import os
import requests
import time
from datetime import datetime, timezone
from typing import Optional, Dict, List
from .amazon_api import get_amazon_access_token

# Configuración
SPAPI_BASE = "https://sellingpartnerapi-na.amazon.com"
MARKETPLACE_ID = "ATVPDKIKX0DER"  # US

# Configuración de filtros de fast fulfillment
MAX_WAREHOUSE_HOURS = 24  # Máximo 24 horas para salir del almacén (Prime 1-day)
MAX_BACKORDER_DAYS = 0    # Máximo días de espera si tiene fecha futura

# Import opcional del scraper para validación adicional
try:
    from .amazon_availability_scraper import validate_fast_fulfillment_scraper
    SCRAPER_AVAILABLE = True
except ImportError:
    SCRAPER_AVAILABLE = False


def validate_fast_fulfillment(offer: Dict, asin: str = "") -> tuple[bool, str]:
    """
    Valida que una oferta cumpla con requisitos de fast fulfillment.

    Filtros aplicados:
    1. ✅ Debe ser Prime + FBA + precio válido
    2. ✅ availabilityType debe ser "NOW" (no backorder)
    3. ✅ Si es "NOW", maximumHours debe ser <= 24h
    4. ❌ Rechaza "FUTURE_WITH_DATE" si faltan >7 días
    5. ❌ Rechaza "FUTURE_WITHOUT_DATE"
    6. ✅ Validar ShipsFrom state (rechaza estados lejanos a tu ubicación)
    7. 🔍 (OPCIONAL) Validación adicional con web scraping para verificar disponibilidad REAL

    Args:
        offer: Dict con datos de la oferta de Amazon SP-API
        asin: ASIN del producto (para logging y scraping)

    Returns:
        Tuple (is_valid: bool, reason: str)
        - (True, "OK") si cumple todos los requisitos
        - (False, "razón del rechazo") si no cumple
    """

    # Obtener ShippingTime
    shipping_time = offer.get('ShippingTime', {})

    if not shipping_time:
        # RECHAZAR: Sin ShippingTime no podemos validar availabilityType ni maximumHours
        return (False, "Sin datos de ShippingTime - No se puede validar fast fulfillment")

    availability_type = shipping_time.get('availabilityType', 'NOW')
    maximum_hours = shipping_time.get('maximumHours', 0)
    available_date = shipping_time.get('availableDate')

    # REGLA 1: Rechazar productos sin fecha de disponibilidad
    if availability_type == "FUTURE_WITHOUT_DATE":
        return (False, f"Sin fecha de disponibilidad (FUTURE_WITHOUT_DATE)")

    # REGLA 2: RECHAZAR todos los productos en backorder (FUTURE_WITH_DATE)
    # No aceptamos productos sin inventario inmediato
    if availability_type == "FUTURE_WITH_DATE":
        if not available_date:
            return (False, "FUTURE_WITH_DATE pero sin availableDate")

        try:
            # Calcular días hasta disponibilidad para el mensaje
            avail_dt = datetime.fromisoformat(available_date.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            days_until = (avail_dt - now).days

            # RECHAZAR - No aceptamos productos en backorder
            return (False, f"Producto en backorder - Disponible en {days_until} días")

        except Exception as e:
            return (False, f"Error parseando availableDate: {e}")

    # REGLA 3: Validar productos disponibles NOW
    if availability_type == "NOW":
        # Si maximumHours > MAX_WAREHOUSE_HOURS, tarda mucho en salir del almacén
        if maximum_hours > MAX_WAREHOUSE_HOURS:
            hours = maximum_hours
            days = hours / 24
            return (False, f"MaxHours={hours}h ({days:.1f}d) >{MAX_WAREHOUSE_HOURS}h")

        # REGLA 3.1: Validar desde qué estado envía el producto
        # IMPORTANTE: maximumHours solo mide tiempo en warehouse, NO tiempo de tránsito
        # Un producto puede salir en 0h de Seattle pero tardar 7 días en llegar a Miami
        ships_from = offer.get('ShipsFrom', {})
        ships_from_state = ships_from.get('State', '').upper()

        # Obtener lista de estados permitidos desde .env
        allowed_states_str = os.getenv('ALLOWED_SHIP_FROM_STATES', '')

        if allowed_states_str and ships_from_state:
            allowed_states = [s.strip().upper() for s in allowed_states_str.split(',')]

            if ships_from_state not in allowed_states:
                return (False, f"Envía desde {ships_from_state} (muy lejos, tarda días en llegar)")

        # Validación básica de SP-API pasó
        location_info = f" desde {ships_from_state}" if ships_from_state else ""
        sp_api_reason = f"OK - Envío inmediato{location_info}" if maximum_hours == 0 else f"OK - Sale en {maximum_hours}h{location_info}"

        # VALIDACIÓN ADICIONAL CON SCRAPER (si está habilitado)
        # NOTA: La SP-API NO respeta el parámetro zipcode, por lo que puede dar
        # disponibilidad inmediata cuando en realidad tarda días en tu ubicación
        use_scraper = os.getenv("USE_SCRAPER_VALIDATION", "false").lower() == "true"

        if use_scraper and SCRAPER_AVAILABLE and asin:
            # Hacer validación adicional con scraping (más lento pero preciso)
            max_delivery_days = int(os.getenv("MAX_DELIVERY_DAYS", "3"))

            # Obtener precio del SP-API para validación cruzada
            listing_price = offer.get('ListingPrice', {})
            sp_api_price = listing_price.get('Amount')
            if sp_api_price:
                sp_api_price = float(sp_api_price)  # Ya viene en dólares, no en centavos

            try:
                is_valid_scraper, scraper_reason = validate_fast_fulfillment_scraper(
                    asin,
                    max_delivery_days=max_delivery_days,
                    sp_api_price=sp_api_price  # Pasar precio para validación cruzada
                )

                if not is_valid_scraper:
                    # El scraper detectó que NO cumple fast fulfillment real
                    return (False, f"Scraper validation: {scraper_reason}")

                # Ambas validaciones pasaron
                return (True, f"{sp_api_reason} + Scraper: {scraper_reason}")

            except Exception as e:
                # Si el scraper falla, usar solo validación de SP-API
                return (True, f"{sp_api_reason} (scraper error: {str(e)[:50]})")

        # Sin scraper, confiar en SP-API
        return (True, sp_api_reason)

    # Tipo de disponibilidad desconocido
    return (False, f"Tipo de disponibilidad desconocido: {availability_type}")


def get_prime_offer(asin: str, retry_count: int = 3) -> Optional[Dict]:
    """
    Obtiene la oferta Prime de un ASIN desde Product Pricing API.

    SOLO retorna la oferta si:
    - Es Prime (IsPrime = true)
    - Es FBA (IsFulfilledByAmazon = true)
    - Tiene precio válido

    Args:
        asin: ASIN del producto
        retry_count: Intentos si hay error (default: 3)

    Returns:
        Dict con datos de la oferta Prime:
        {
            "price": 199.95,
            "currency": "USD",
            "is_prime": True,
            "is_fba": True,
            "in_stock": True,
            "is_buybox_winner": True
        }

        None si no hay oferta Prime disponible
    """

    url = f"{SPAPI_BASE}/products/pricing/v0/items/{asin}/offers"

    for attempt in range(retry_count):
        try:
            # 1. Obtener token
            token = get_amazon_access_token()

            # 2. Headers
            headers = {
                "Authorization": f"Bearer {token}",
                "x-amz-access-token": token,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            # 3. Params
            params = {
                "MarketplaceId": MARKETPLACE_ID,
                "ItemCondition": "New",  # Solo productos nuevos
                "CustomerType": "Consumer"  # Consumer (Prime personal) vs Business (Business Prime)
            }

            # Agregar zipcode si está configurado (para obtener disponibilidad precisa)
            buyer_zipcode = os.getenv("BUYER_ZIPCODE")
            if buyer_zipcode:
                params["deliveryPostalCode"] = buyer_zipcode

            # 4. Request
            response = requests.get(url, headers=headers, params=params, timeout=15)

            # 5. Manejar errores
            if response.status_code == 429:
                # Rate limit - esperar y reintentar
                wait_time = 2 ** attempt  # Backoff exponencial: 1s, 2s, 4s
                print(f"⏱️  Rate limit alcanzado, esperando {wait_time}s...")
                time.sleep(wait_time)
                continue

            if response.status_code == 403:
                print(f"❌ Error 403: Sin permisos para Product Pricing API")
                print(f"   Verificar en Seller Central que la app tenga el rol 'Pricing'")
                return None

            if response.status_code != 200:
                print(f"⚠️  Error {response.status_code} para {asin}: {response.text[:200]}")
                return None

            # 6. Parsear respuesta
            data = response.json()

            if 'payload' not in data:
                print(f"⚠️  Respuesta sin payload para {asin}")
                return None

            payload = data['payload']

            if 'Offers' not in payload or len(payload['Offers']) == 0:
                # No hay ofertas disponibles
                return None

            # 7. Recolectar TODAS las ofertas Prime + FBA válidas y elegir la más barata
            valid_offers = []

            for offer in payload['Offers']:
                # Verificar que sea FBA
                is_fba = offer.get('IsFulfilledByAmazon', False)
                if not is_fba:
                    continue

                # Verificar que sea Prime
                prime_info = offer.get('PrimeInformation', {})
                is_prime = prime_info.get('IsPrime', False)
                if not is_prime:
                    continue

                # Verificar que tenga precio
                listing_price = offer.get('ListingPrice', {})
                price = listing_price.get('Amount')
                currency = listing_price.get('CurrencyCode', 'USD')

                if price is None or price <= 0:
                    continue

                # ✅ Validar fast fulfillment (nuevo filtro)
                is_valid, reason = validate_fast_fulfillment(offer, asin)
                if not is_valid:
                    # No retornar None, solo skip esta oferta y continuar
                    continue

                # ✅ Oferta válida - agregarla a la lista
                # Obtener ShipsFrom para logging
                ships_from = offer.get('ShipsFrom', {})

                valid_offers.append({
                    "price": float(price),
                    "currency": currency,
                    "is_prime": True,
                    "is_fba": True,
                    "in_stock": True,
                    "is_buybox_winner": offer.get('IsBuyBoxWinner', False),
                    "fulfillment_validation": reason,  # Razón de aceptación
                    "ships_from_state": ships_from.get("State"),
                    "ships_from_country": ships_from.get("Country")
                })

            # Si no hay ofertas válidas, retornar None
            if not valid_offers:
                return None

            # Elegir la oferta MÁS BARATA de las válidas
            cheapest_offer = min(valid_offers, key=lambda x: x['price'])
            return cheapest_offer

        except requests.exceptions.Timeout:
            print(f"⏱️  Timeout en intento {attempt + 1}/{retry_count} para {asin}")
            if attempt < retry_count - 1:
                time.sleep(1)
                continue
            return None

        except Exception as e:
            print(f"❌ Error obteniendo precio de {asin}: {e}")
            if attempt < retry_count - 1:
                time.sleep(1)
                continue
            return None

    # Agotados los reintentos
    return None


def get_prime_offers_batch(asins: list, delay: float = 1.5) -> Dict[str, Optional[Dict]]:
    """
    Obtiene ofertas Prime para múltiples ASINs.

    DEPRECATED: Esta función hace requests individuales.
    Usar get_prime_offers_batch_optimized() para batch real (4x más rápido).

    Args:
        asins: Lista de ASINs
        delay: Delay entre requests en segundos (para respetar rate limits)

    Returns:
        Dict: {asin: offer_data} o {asin: None} si no tiene oferta Prime
    """

    results = {}

    for i, asin in enumerate(asins):
        print(f"📊 [{i+1}/{len(asins)}] Obteniendo precio Prime de {asin}...")

        offer = get_prime_offer(asin)
        results[asin] = offer

        if offer:
            print(f"   ✅ Prime: ${offer['price']} {offer['currency']}")
        else:
            print(f"   ⏭️  No tiene oferta Prime")

        # Delay para respetar rate limits (10 req/s = 0.1s mínimo)
        if i < len(asins) - 1:
            time.sleep(delay)

    return results


def get_prime_offers_batch_optimized(asins: List[str], batch_size: int = 20, show_progress: bool = True) -> Dict[str, Optional[Dict]]:
    """
    Obtiene ofertas Prime para múltiples ASINs usando el endpoint BATCH de Amazon SP-API.

    OPTIMIZACIÓN: Procesa hasta 20 ASINs por request (vs 1 ASIN individual).
    Resultado: 4x más rápido que get_prime_offers_batch().

    Args:
        asins: Lista de ASINs
        batch_size: ASINs por batch (máx 20 según Amazon SP-API)
        show_progress: Mostrar progreso en consola

    Returns:
        Dict: {asin: offer_data} o {asin: None} si no tiene oferta Prime

    Ejemplo:
        results = get_prime_offers_batch_optimized(asins)
        # results = {
        #     "B0CYM126TT": {"price": 199.95, "currency": "USD", "is_prime": True, ...},
        #     "B0DRW8G3WK": {"price": 57.34, "currency": "USD", "is_prime": True, ...},
        #     "B0XXXXXX": None  # Sin oferta Prime
        # }
    """

    if not asins:
        return {}

    # 🔥 DEDUPLICAR ASINs para evitar error "Duplicate requests submitted"
    original_count = len(asins)
    asins = list(dict.fromkeys(asins))  # Mantiene orden, elimina duplicados
    if len(asins) < original_count and show_progress:
        print(f"ℹ️  Eliminados {original_count - len(asins)} ASINs duplicados", flush=True)

    if batch_size > 20:
        print(f"⚠️ batch_size limitado a 20 (máximo de Amazon SP-API)")
        batch_size = 20

    results = {}
    total_batches = (len(asins) + batch_size - 1) // batch_size

    if show_progress:
        print(f"📊 Obteniendo precios Prime de {len(asins)} ASINs usando BATCH (batches de {batch_size})", flush=True)

    # Procesar en batches
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(asins))
        batch_asins = asins[start_idx:end_idx]

        if show_progress:
            print(f"   Batch {batch_num + 1}/{total_batches}: Procesando {len(batch_asins)} ASINs...", flush=True)

        # Preparar batch request
        url = f"{SPAPI_BASE}/batches/products/pricing/v0/itemOffers"
        token = get_amazon_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "x-amz-access-token": token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Crear array de requests
        requests_array = []
        buyer_zipcode = os.getenv("BUYER_ZIPCODE")

        for asin in batch_asins:
            request_params = {
                "uri": f"/products/pricing/v0/items/{asin}/offers",
                "method": "GET",
                "MarketplaceId": MARKETPLACE_ID,
                "ItemCondition": "New",
                "CustomerType": "Consumer"  # Consumer (Prime personal) vs Business (Business Prime)
            }

            # Agregar zipcode si está configurado (para obtener disponibilidad precisa)
            if buyer_zipcode:
                request_params["deliveryPostalCode"] = buyer_zipcode

            requests_array.append(request_params)

        body = {"requests": requests_array}

        # Hacer batch request con retry en caso de rate limit
        max_retries = 3
        retry_delay = 15  # Esperar 15s antes de reintentar

        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=body, timeout=30)

                # Si es rate limit, esperar y reintentar
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1)  # 15s, 30s, 45s
                        print(f"   ⏱️ Rate limit (429) en batch {batch_num + 1}, esperando {wait_time}s antes de reintentar...", flush=True)
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"   ❌ Rate limit persistente después de {max_retries} intentos", flush=True)
                        for asin in batch_asins:
                            results[asin] = None
                        break

                if response.status_code != 200:
                    print(f"   ❌ Error batch {batch_num + 1}: Status {response.status_code}", flush=True)
                    try:
                        error_msg = response.json()
                        print(f"      Error: {error_msg}", flush=True)
                    except:
                        print(f"      Response: {response.text[:200]}", flush=True)
                    # Marcar todos los ASINs del batch como None
                    for asin in batch_asins:
                        results[asin] = None
                    break

                # ✅ Request exitoso
                data = response.json()

                if "responses" not in data:
                    print(f"   ⚠️ Respuesta sin 'responses' en batch {batch_num + 1}", flush=True)
                    for asin in batch_asins:
                        results[asin] = None
                    break

                # Procesar cada respuesta
                for i, resp in enumerate(data["responses"]):
                    asin = batch_asins[i]

                    # Verificar status
                    status = resp.get("status", {}).get("statusCode")
                    if status != 200:
                        results[asin] = None
                        continue

                    # Parsear body
                    body_data = resp.get("body", {})
                    payload = body_data.get("payload", {})
                    offers = payload.get("Offers", [])

                    if not offers:
                        results[asin] = None
                        continue

                    # Recolectar TODAS las ofertas Prime + FBA válidas y elegir la más barata
                    valid_offers = []

                    for offer in offers:
                        is_fba = offer.get("IsFulfilledByAmazon", False)
                        prime_info = offer.get("PrimeInformation", {})
                        is_prime = prime_info.get("IsPrime", False)

                        if is_fba and is_prime:
                            listing_price = offer.get("ListingPrice", {})
                            price = listing_price.get("Amount")
                            currency = listing_price.get("CurrencyCode", "USD")

                            if price and price > 0:
                                # Validar fast fulfillment
                                is_valid, reason = validate_fast_fulfillment(offer, asin)
                                if not is_valid:
                                    # No rechazar, solo skip esta oferta y continuar
                                    continue

                                # Obtener datos de ShippingTime y ShipsFrom para logging
                                shipping_time = offer.get("ShippingTime", {})
                                ships_from = offer.get("ShipsFrom", {})

                                # Oferta válida - agregarla
                                valid_offers.append({
                                    "price": float(price),
                                    "currency": currency,
                                    "is_prime": True,
                                    "is_fba": True,
                                    "in_stock": True,
                                    "is_buybox_winner": offer.get("IsBuyBoxWinner", False),
                                    "fulfillment_validation": reason,
                                    "availability_type": shipping_time.get("availabilityType"),
                                    "maximum_hours": shipping_time.get("maximumHours"),
                                    "available_date": shipping_time.get("availableDate"),
                                    "ships_from_state": ships_from.get("State"),
                                    "ships_from_country": ships_from.get("Country")
                                })

                    # Elegir la MÁS BARATA de las ofertas válidas
                    if valid_offers:
                        results[asin] = min(valid_offers, key=lambda x: x['price'])
                    else:
                        results[asin] = None

                # Salir del retry loop si todo fue exitoso
                break

            except requests.exceptions.Timeout:
                print(f"   ⏱️ Timeout en batch {batch_num + 1}, intento {attempt + 1}/{max_retries}", flush=True)
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    for asin in batch_asins:
                        results[asin] = None

            except Exception as e:
                print(f"   ❌ Error en batch {batch_num + 1}: {e}", flush=True)
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    for asin in batch_asins:
                        results[asin] = None

        # Rate limit: Amazon recomienda 0.1 req/s = 10s entre batches
        # Aumentamos a 15s para tener margen y evitar 429
        if batch_num < total_batches - 1:
            time.sleep(15)  # 15s entre batches para evitar rate limits

    # Resumen
    if show_progress:
        prime_count = sum(1 for v in results.values() if v is not None)
        print(f"   ✅ {prime_count}/{len(asins)} ASINs con Prime", flush=True)

    return results


if __name__ == "__main__":
    # Test
    test_asins = [
        "B0CYM126TT",  # LEGO (sabemos que tiene Prime)
        "B0DRW8G3WK",  # Otro producto
    ]

    print("🧪 TEST: Obteniendo ofertas Prime...\n")
    results = get_prime_offers_batch(test_asins)

    print(f"\n📊 RESULTADOS:")
    for asin, offer in results.items():
        if offer:
            print(f"✅ {asin}: ${offer['price']} (Prime: {offer['is_prime']})")
        else:
            print(f"❌ {asin}: Sin oferta Prime")
