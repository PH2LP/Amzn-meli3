#!/usr/bin/env python3
"""
Encuentra el rate limit óptimo para Glow API sin bloqueo de Amazon

Este script prueba diferentes velocidades de request para encontrar el máximo
rate limit que Amazon permite sin bloquear tu IP.

Estrategia:
1. Empieza con rate conservador (1 req/segundo)
2. Incrementa gradualmente la velocidad
3. Detecta cuando Amazon empieza a dar CAPTCHAs o errores
4. Te dice el rate limit óptimo para 31_glow_parallel_optimized.py

Uso:
    python3 32_find_optimal_rate_limit.py
"""

import os
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# ASINs de prueba (productos reales que sabemos que existen)
TEST_ASINS = [
    "B0D9PK465N",
    "B0FGJ3G6V8",
    "B09P53JX4R",
    "B0CX23V2ZK",
    "B0D1XD1ZV3",
]

print("=" * 80)
print("🔍 BUSCANDO RATE LIMIT ÓPTIMO - Glow API")
print("=" * 80)
print()
print("Este test va a probar diferentes velocidades de request para encontrar")
print("el máximo rate limit que Amazon permite sin bloquearte.")
print()
print("IMPORTANTE: Esto puede tomar 10-15 minutos")
print()

def is_blocked_response(html_content):
    """
    Detecta si Amazon está bloqueando requests

    Señales de bloqueo:
    - CAPTCHA page
    - "Robot Check" page
    - Error 503
    - Respuesta muy pequeña (< 10KB)
    """
    if len(html_content) < 10000:
        return True, "Response muy pequeña"

    # Buscar CAPTCHA
    if "captcha" in html_content.lower():
        return True, "CAPTCHA detectado"

    if "robot check" in html_content.lower():
        return True, "Robot Check detectado"

    # Buscar delivery block (señal de que la página cargó bien)
    soup = BeautifulSoup(html_content, 'html.parser')
    delivery_block = soup.find(id='mir-layout-DELIVERY_BLOCK')

    if not delivery_block:
        return True, "No delivery block (página incompleta)"

    return False, "OK"


def test_rate_limit(requests_per_second, num_requests=20):
    """
    Prueba un rate limit específico

    Args:
        requests_per_second: Requests por segundo a probar
        num_requests: Número de requests a hacer en el test

    Returns:
        (success_rate, blocked, error_message)
    """
    delay = 1.0 / requests_per_second
    successful = 0
    blocked = 0
    errors = 0

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    print(f"\n📊 Testing {requests_per_second:.2f} req/sec (delay={delay:.2f}s)...")

    for i in range(num_requests):
        asin = TEST_ASINS[i % len(TEST_ASINS)]
        url = f"https://www.amazon.com/dp/{asin}"

        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                errors += 1
                print(f"   ❌ Request {i+1}: HTTP {response.status_code}")
            else:
                is_blocked, reason = is_blocked_response(response.text)

                if is_blocked:
                    blocked += 1
                    print(f"   ⚠️  Request {i+1}: BLOCKED - {reason}")
                else:
                    successful += 1
                    print(f"   ✅ Request {i+1}: OK")

        except Exception as e:
            errors += 1
            print(f"   ❌ Request {i+1}: {str(e)[:50]}")

        time.sleep(delay)

    success_rate = successful / num_requests
    blocked_rate = blocked / num_requests

    print(f"\n   Resultados: {successful}/{num_requests} exitosos ({success_rate*100:.1f}%)")
    print(f"   Blocked: {blocked} ({blocked_rate*100:.1f}%)")
    print(f"   Errors: {errors}")

    # Consideramos que el rate limit es seguro si >90% exitosos y <5% blocked
    is_safe = success_rate > 0.9 and blocked_rate < 0.05

    return success_rate, blocked_rate, is_safe


def main():
    """Main execution"""

    # Test diferentes rate limits
    test_configs = [
        (0.5, "Muy conservador"),    # 0.5 req/sec = 30 req/min
        (1.0, "Conservador"),         # 1 req/sec = 60 req/min
        (2.0, "Moderado"),            # 2 req/sec = 120 req/min
        (3.0, "Agresivo"),            # 3 req/sec = 180 req/min
        (5.0, "Muy agresivo"),        # 5 req/sec = 300 req/min
    ]

    results = []

    for rate, description in test_configs:
        print("=" * 80)
        print(f"TEST: {description} - {rate} requests/segundo")
        print("=" * 80)

        success_rate, blocked_rate, is_safe = test_rate_limit(rate)

        results.append({
            'rate': rate,
            'description': description,
            'success_rate': success_rate,
            'blocked_rate': blocked_rate,
            'is_safe': is_safe
        })

        if not is_safe:
            print("\n⚠️  RATE LIMIT ALCANZADO - Este rate es muy alto")
            break

        # Wait entre tests para que Amazon "olvide" los requests anteriores
        print("\n⏳ Esperando 30 segundos antes del siguiente test...")
        time.sleep(30)

    # Encontrar el rate limit óptimo
    print("\n")
    print("=" * 80)
    print("📊 RESUMEN DE RESULTADOS")
    print("=" * 80)
    print()

    for result in results:
        status = "✅ SAFE" if result['is_safe'] else "❌ UNSAFE"
        print(f"{status} | {result['rate']:.1f} req/sec | "
              f"Success: {result['success_rate']*100:.1f}% | "
              f"Blocked: {result['blocked_rate']*100:.1f}% | "
              f"{result['description']}")

    print()
    print("=" * 80)
    print("🎯 RECOMENDACIÓN FINAL")
    print("=" * 80)
    print()

    # Encontrar el rate limit más alto que sea seguro
    safe_rates = [r for r in results if r['is_safe']]

    if safe_rates:
        optimal = max(safe_rates, key=lambda x: x['rate'])
        optimal_rate = optimal['rate']

        print(f"✅ Rate limit óptimo: {optimal_rate:.1f} requests/segundo")
        print()
        print("CONFIGURACIÓN RECOMENDADA para 31_glow_parallel_optimized.py:")
        print()

        # Calcular configuración óptima de workers
        for num_workers in [2, 4, 6, 8, 10]:
            delay = num_workers / optimal_rate
            total_rate = num_workers / delay

            print(f"  • {num_workers} workers + {delay:.2f}s delay = {total_rate:.2f} req/sec total")

        print()
        print("Ejemplo para actualizar 31_glow_parallel_optimized.py:")
        print()

        # Sugerir configuración conservadora (75% del rate óptimo)
        safe_rate = optimal_rate * 0.75
        recommended_workers = 4
        recommended_delay = recommended_workers / safe_rate

        print(f"NUM_WORKERS = {recommended_workers}")
        print(f"DELAY_BETWEEN_REQUESTS = {recommended_delay:.2f}")
        print()
        print(f"→ Esto procesará ~{safe_rate:.1f} ASINs/segundo")
        print(f"→ 50,000 productos en {50000/safe_rate/60:.1f} minutos ({50000/safe_rate/3600:.1f} horas)")

    else:
        print("❌ No se encontró un rate limit seguro")
        print()
        print("RECOMENDACIÓN: Usar configuración muy conservadora")
        print()
        print("NUM_WORKERS = 2")
        print("DELAY_BETWEEN_REQUESTS = 4.0  # 0.5 req/sec total")

    print()
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Test interrumpido por usuario")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
