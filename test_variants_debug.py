#!/usr/bin/env python3
"""
Script de prueba con DEBUG para analizar variantes de un ASIN específico
"""
import sys
import requests
import re
from pathlib import Path
from dotenv import load_dotenv
import os
from bs4 import BeautifulSoup

# Agregar path del proyecto
sys.path.insert(0, str(Path(__file__).parent))
from src.integrations.amazon_glow_search import get_random_user_agent

load_dotenv(override=True)

def test_asin_variants_debug(asin: str):
    """Testea la función de variantes con DEBUG detallado"""

    print(f"🔍 Analizando variantes del ASIN: {asin}")
    print("=" * 70)
    print()

    # Configuración desde .env
    BUYER_ZIPCODE = os.getenv("BUYER_ZIPCODE", "33172")
    MIN_PRICE = float(os.getenv("GLOW_MIN_PRICE", "28"))
    MAX_PRICE = float(os.getenv("GLOW_MAX_PRICE", "450"))
    MAX_DELIVERY_DAYS = int(os.getenv("GLOW_MAX_DELIVERY_DAYS", "4"))

    print(f"📋 Configuración:")
    print(f"   Zipcode: {BUYER_ZIPCODE}")
    print(f"   Rango de precio: ${MIN_PRICE} - ${MAX_PRICE}")
    print(f"   Max días envío: {MAX_DELIVERY_DAYS}")
    print()

    # Crear sesión
    session = requests.Session()
    user_agent = get_random_user_agent()

    print(f"🤖 User-Agent: {user_agent[:60]}...")
    print()

    session.headers.update({
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })

    # Configurar zipcode con Glow API
    try:
        print("🌐 Paso 1: Accediendo a Amazon homepage...")
        homepage_url = "https://www.amazon.com"
        resp = session.get(homepage_url, timeout=15)
        print(f"   Status: {resp.status_code}")
        print(f"   Cookies recibidas: {len(session.cookies)}")
        print()

        print("📍 Paso 2: Configurando zipcode con Glow API...")
        glow_url = "https://www.amazon.com/portal-migration/hz/glow/address-change"
        params = {
            'actionSource': 'glow',
            'deviceType': 'desktop',
            'pageType': 'Search',
            'storeContext': 'pc'
        }
        payload = {
            'locationType': 'LOCATION_INPUT',
            'zipCode': BUYER_ZIPCODE,
            'deviceType': 'web',
            'storeContext': 'generic',
            'pageType': 'Search'
        }
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': homepage_url
        }
        resp = session.post(glow_url, params=params, json=payload, headers=headers, timeout=10)
        print(f"   Status: {resp.status_code}")
        print(f"   Zipcode configurado: {BUYER_ZIPCODE}")
        print()
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
        print()

    print("🔎 Paso 3: Accediendo a página del producto...")
    product_url = f"https://www.amazon.com/dp/{asin}"
    print(f"   URL: {product_url}")

    try:
        response = session.get(product_url, timeout=15)
        print(f"   Status code: {response.status_code}")
        print(f"   Tamaño respuesta: {len(response.text):,} bytes")

        if response.status_code != 200:
            print(f"   ❌ Error: Amazon retornó status {response.status_code}")
            print(f"   Headers de respuesta: {dict(response.headers)}")
            return

        print(f"   ✅ Página cargada correctamente")
        print()

        # Parsear HTML
        print("🔍 Paso 4: Buscando variantes en el HTML...")
        soup = BeautifulSoup(response.text, 'html.parser')

        variant_asins = set()

        # Método 1: Selectores de variantes
        print("   Método 1: Buscando selectores de variantes...")
        variant_selects = soup.find_all('select', {'id': re.compile(r'native_dropdown_selected_')})
        print(f"   - Encontrados {len(variant_selects)} selectores")
        for select in variant_selects:
            options = select.find_all('option', {'value': True})
            for option in options:
                value = option.get('value', '')
                if len(value) == 10 and value.isalnum():
                    variant_asins.add(value)
                    print(f"     → {value} (desde selector)")

        # Método 2: Links de variantes
        print("   Método 2: Buscando links a variantes...")
        variant_links = soup.find_all('a', {'href': re.compile(r'/dp/[A-Z0-9]{10}')})
        print(f"   - Encontrados {len(variant_links)} links")
        count = 0
        for link in variant_links:
            href = link.get('href', '')
            match = re.search(r'/dp/([A-Z0-9]{10})', href)
            if match:
                asin_found = match.group(1)
                if asin_found not in variant_asins:
                    variant_asins.add(asin_found)
                    count += 1
                    if count <= 5:  # Mostrar solo primeros 5
                        print(f"     → {asin_found} (desde link)")
        if count > 5:
            print(f"     ... y {count - 5} más")

        # Método 3: JSON embebido
        print("   Método 3: Buscando ASINs en scripts JSON...")
        scripts = soup.find_all('script', {'type': 'text/javascript'})
        print(f"   - Encontrados {len(scripts)} scripts")
        json_asins = 0
        for script in scripts:
            script_text = script.string if script.string else ''
            asin_matches = re.findall(r'"asin"\s*:\s*"([A-Z0-9]{10})"', script_text)
            for asin_match in asin_matches:
                if asin_match not in variant_asins:
                    variant_asins.add(asin_match)
                    json_asins += 1
        print(f"     → {json_asins} ASINs nuevos desde JSON")

        # Remover el ASIN original
        variant_asins.discard(asin)

        print()
        print(f"📊 Total de variantes encontradas: {len(variant_asins)}")

        if not variant_asins:
            print("   ℹ️  No se encontraron variantes")
            print()
            print("💡 Guardando HTML para inspección...")
            debug_file = Path(__file__).parent / f"debug_product_{asin}.html"
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"   → {debug_file}")
            return

        print()
        print(f"🔎 Paso 5: Validando variantes (precio + envío)...")
        print()

        valid_variants = []
        for i, variant_asin in enumerate(list(variant_asins)[:10], 1):  # Limitar a 10 para test
            print(f"   [{i}/{min(10, len(variant_asins))}] Verificando {variant_asin}...")

            variant_url = f"https://www.amazon.com/dp/{variant_asin}"
            try:
                variant_response = session.get(variant_url, timeout=10)
                print(f"      Status: {variant_response.status_code}")

                if variant_response.status_code != 200:
                    print(f"      ❌ Error al cargar")
                    continue

                variant_soup = BeautifulSoup(variant_response.text, 'html.parser')

                # Buscar precio - múltiples métodos
                price = None
                variant_html = variant_response.text

                # Método 1: a-price con a-offscreen (más común actualmente)
                price_span = variant_soup.find('span', class_='a-price')
                if price_span:
                    offscreen = price_span.find('span', class_='a-offscreen')
                    if offscreen:
                        price_text = offscreen.get_text(strip=True).replace('$', '').replace(',', '')
                        match = re.search(r'(\d+(?:\.\d{1,2})?)', price_text)
                        if match:
                            try:
                                price = float(match.group(1))
                                print(f"      💡 Precio encontrado (método 1: a-offscreen)")
                            except ValueError:
                                pass

                # Método 2: priceblock IDs (legacy)
                if not price:
                    for price_id in ['priceblock_ourprice', 'priceblock_dealprice', 'priceblock_saleprice']:
                        price_elem = variant_soup.find('span', {'id': price_id})
                        if price_elem:
                            price_text = price_elem.get_text(strip=True).replace('$', '').replace(',', '')
                            match = re.search(r'(\d+(?:\.\d{1,2})?)', price_text)
                            if match:
                                try:
                                    price = float(match.group(1))
                                    print(f"      💡 Precio encontrado (método 2: {price_id})")
                                    break
                                except ValueError:
                                    continue

                # Método 3: Buscar en cualquier span con patrón $XX.XX
                if not price:
                    # Buscar patrones como $99.99 o $99
                    price_matches = re.findall(r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', variant_html)
                    if price_matches:
                        # Tomar el primer precio que parezca razonable
                        for pm in price_matches:
                            try:
                                potential_price = float(pm.replace(',', ''))
                                if 1 <= potential_price <= 10000:  # Rango razonable
                                    price = potential_price
                                    print(f"      💡 Precio encontrado (método 3: regex en HTML)")
                                    break
                            except:
                                continue

                if price:
                    print(f"      💰 Precio: ${price}")
                    if MIN_PRICE <= price <= MAX_PRICE:
                        print(f"      ✅ Precio en rango")
                    else:
                        print(f"      ❌ Precio fuera de rango (${MIN_PRICE}-${MAX_PRICE})")
                        continue
                else:
                    print(f"      ❌ No se encontró precio")
                    continue

                # Verificar envío
                has_fast_delivery = False
                delivery_patterns = [
                    r'FREE\s+delivery',
                    r'Get\s+it\s+by',
                    r'Get\s+it\s+(today|tomorrow)',
                    r'Arrives\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)',
                ]

                for pattern in delivery_patterns:
                    if re.search(pattern, variant_html, re.IGNORECASE):
                        has_fast_delivery = True
                        break

                if has_fast_delivery:
                    print(f"      ✅ Envío rápido disponible")
                    valid_variants.append(variant_asin)
                else:
                    print(f"      ❌ Sin envío rápido")

                import time
                time.sleep(0.5)

            except Exception as e:
                print(f"      ❌ Error: {e}")
                continue

        print()
        print("=" * 70)
        print("📊 RESULTADOS FINALES:")
        print("=" * 70)
        print()
        print(f"Total variantes detectadas: {len(variant_asins)}")
        print(f"Variantes validadas: {len(valid_variants)}")
        print()

        if valid_variants:
            print("✅ Variantes que cumplen criterios:")
            for i, v in enumerate(valid_variants, 1):
                print(f"   {i}. {v} → https://www.amazon.com/dp/{v}")
        else:
            print("❌ Ninguna variante cumple los criterios")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_asin = sys.argv[1]
    else:
        test_asin = "B0FKT28PP7"

    try:
        test_asin_variants_debug(test_asin)
    except KeyboardInterrupt:
        print("\n\n🛑 Prueba detenida por usuario (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
