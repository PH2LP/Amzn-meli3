#!/usr/bin/env python3
import requests
import re
import time

def scrape_amazon_prime_status(asin):
    url = f'https://www.amazon.com/dp/{asin}'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    try:
        r = requests.get(url, headers=headers, timeout=15)

        if r.status_code != 200:
            return (False, {'error': f'HTTP {r.status_code}'})

        html = r.text

        # 1. Verificar badge Prime
        has_prime_badge = any([
            'amazon-prime-logo' in html,
            'i-sprime-medium' in html,
            'a-icon-prime' in html,
            'prime-logo' in html,
        ])

        # 2. Buscar PRIMERO patrones FBM (sold and shipped by seller)
        # Patrón: "Sold and shipped by [SomeSeller]" o "Ships from and sold by [SomeSeller]"
        fbm_pattern_1 = re.search(r'sold and shipped by (?!Amazon)', html, re.IGNORECASE)
        fbm_pattern_2 = re.search(r'ships from and sold by (?!Amazon)', html, re.IGNORECASE)

        has_fbm = fbm_pattern_1 is not None or fbm_pattern_2 is not None

        # 3. Verificar FBA SOLO si NO es FBM
        is_amazon_seller = 'Ships from and sold by Amazon.com' in html
        is_fulfilled_by_amazon = 'Fulfilled by Amazon' in html

        # Solo considerar FBA si NO tiene patrón FBM
        if has_fbm:
            is_fba = False
        else:
            is_fba = is_amazon_seller or is_fulfilled_by_amazon

        # 4. Delivery
        delivery_match = re.search(r'(FREE|Get it).*?delivery.*?(\w+day, \w+ \d+)', html, re.IGNORECASE)
        delivery_date = delivery_match.group(2) if delivery_match else None

        # 5. Stock
        in_stock = 'In Stock' in html or 'Add to Cart' in html

        # Extraer nombre del seller si es FBM
        fbm_seller = None
        if fbm_pattern_1:
            seller_match = re.search(r'sold and shipped by ([^<\.]+)', html, re.IGNORECASE)
            if seller_match:
                fbm_seller = seller_match.group(1).strip()
        elif fbm_pattern_2:
            seller_match = re.search(r'ships from and sold by ([^<\.]+)', html, re.IGNORECASE)
            if seller_match:
                fbm_seller = seller_match.group(1).strip()

        details = {
            'has_prime_badge': has_prime_badge,
            'is_amazon_seller': is_amazon_seller,
            'is_fulfilled_by_amazon': is_fulfilled_by_amazon,
            'is_fba': is_fba,
            'has_fbm': has_fbm,
            'fbm_seller': fbm_seller,
            'delivery_date': delivery_date,
            'in_stock': in_stock,
        }

        # Decisión: Aceptar si Prime + FBA + Stock + NO FBM
        is_valid = has_prime_badge and is_fba and not has_fbm and in_stock

        return (is_valid, details)

    except Exception as e:
        return (False, {'error': str(e)})


if __name__ == '__main__':
    test_asins = {
        'B0D2F4T9RJ': 'API dice FBA - usuario dice FBM',
        'B08X6LYPHK': 'API dice FBA - debería ser correcto',
        'B0FGND9HR1': 'Venta original',
        'B0D9H19PBL': 'Sin badge Prime según usuario',
    }

    print('='*70)
    print('SCRAPER TEST - Verificando productos REALES en Amazon.com')
    print('='*70)

    results = {}

    for asin, desc in test_asins.items():
        print(f'\n{asin}: {desc}')
        print('-'*70)

        is_valid, details = scrape_amazon_prime_status(asin)
        results[asin] = (is_valid, details)

        print(f'Resultado: {"✅ VÁLIDO (ACEPTAR)" if is_valid else "❌ INVÁLIDO (RECHAZAR)"}')
        print('Detalles:')
        for key, val in details.items():
            if isinstance(val, bool):
                symbol = '✅' if val else '❌'
                print(f'  {symbol} {key}')
            else:
                print(f'  → {key}: {val}')

        time.sleep(2)  # Evitar rate limit

    print('\n' + '='*70)
    print('RESUMEN COMPARACIÓN API vs SCRAPER:')
    print('='*70)
    print(f'\nB0D2F4T9RJ (API mintió - dice FBA):')
    print(f'  Scraper: {"✅ ACEPTÓ" if results["B0D2F4T9RJ"][0] else "❌ RECHAZÓ"}')
    print(f'  Esperado: ❌ RECHAZAR (es FBM según usuario)')
    print(f'\nB08X6LYPHK (API correcto - es FBA):')
    print(f'  Scraper: {"✅ ACEPTÓ" if results["B08X6LYPHK"][0] else "❌ RECHAZÓ"}')
    print(f'  Esperado: ✅ ACEPTAR (es FBA real)')
