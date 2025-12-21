#!/usr/bin/env python3
"""
analyze_amazon_traffic.py
═══════════════════════════════════════════════════════════════════════════════
ANALIZADOR DE TRÁFICO DE AMAZON - DESCUBRIR ENDPOINTS DE RUFUS
═══════════════════════════════════════════════════════════════════════════════

Este script analiza el tráfico capturado de la app de Amazon para descubrir
los endpoints no documentados que usa Rufus (el asistente de IA).

USO:
    1. Capturar tráfico con mitmproxy:
       mitmproxy -w amazon_traffic.flow

    2. Analizar la captura:
       python3 analyze_amazon_traffic.py amazon_traffic.flow

    3. Ver endpoints descubiertos y ejemplos de requests
"""

import sys
import json
from pathlib import Path
from collections import defaultdict

# Palabras clave que indican endpoints de IA/Rufus
AI_KEYWORDS = [
    'rufus', 'chat', 'assistant', 'conversation', 'genai', 'ai',
    'question', 'answer', 'ask', 'llm', 'ml-model', 'inference'
]

# Dominios de Amazon a analizar
AMAZON_DOMAINS = [
    'amazon.com', 'amazon.co', 'amazonservices.com',
    'amazonaws.com', 'api.amazon', 'completion.amazon'
]


def analyze_flow_file(flow_file):
    """
    Analiza un archivo .flow de mitmproxy.

    Si mitmproxy no está instalado, este script mostrará cómo instalar
    y usar la librería de Python.
    """
    try:
        from mitmproxy import io
        from mitmproxy.exceptions import FlowReadException
    except ImportError:
        print("❌ Error: mitmproxy no está instalado")
        print("\nInstalar con:")
        print("  pip install mitmproxy")
        print("\nO capturar manualmente y analizar con:")
        print("  python3 analyze_amazon_traffic.py --json traffic.json")
        return

    print(f"📂 Analizando: {flow_file}\n")
    print("=" * 80)

    endpoints = defaultdict(list)
    rufus_requests = []

    try:
        with open(flow_file, "rb") as f:
            flow_reader = io.FlowReader(f)

            for flow in flow_reader.stream():
                if not hasattr(flow, 'request'):
                    continue

                request = flow.request
                response = flow.response if hasattr(flow, 'response') else None

                # Filtrar solo tráfico de Amazon
                if not any(domain in request.pretty_host for domain in AMAZON_DOMAINS):
                    continue

                url = request.pretty_url
                method = request.method
                path = request.path

                # Buscar keywords de IA en la URL o path
                is_ai_related = any(keyword in url.lower() or keyword in path.lower()
                                   for keyword in AI_KEYWORDS)

                if is_ai_related:
                    # Guardar información del request
                    request_info = {
                        'method': method,
                        'url': url,
                        'path': path,
                        'host': request.pretty_host,
                        'headers': dict(request.headers),
                        'body': None,
                        'response_body': None
                    }

                    # Intentar parsear body si es JSON
                    if request.content:
                        try:
                            request_info['body'] = json.loads(request.content.decode('utf-8'))
                        except:
                            request_info['body'] = request.content.decode('utf-8', errors='ignore')[:500]

                    # Intentar parsear response
                    if response and response.content:
                        try:
                            request_info['response_body'] = json.loads(response.content.decode('utf-8'))
                        except:
                            request_info['response_body'] = response.content.decode('utf-8', errors='ignore')[:500]

                    rufus_requests.append(request_info)
                    endpoints[path].append(request_info)

        # Mostrar resultados
        print(f"\n🎯 ENDPOINTS DESCUBIERTOS: {len(endpoints)}\n")

        for path, requests in endpoints.items():
            print(f"📍 {path}")
            print(f"   Requests: {len(requests)}")
            if requests:
                first = requests[0]
                print(f"   Host: {first['host']}")
                print(f"   Method: {first['method']}")
                print()

        # Mostrar detalles de requests de Rufus
        if rufus_requests:
            print("\n" + "=" * 80)
            print(f"🤖 REQUESTS DE RUFUS/IA ENCONTRADOS: {len(rufus_requests)}\n")

            for idx, req in enumerate(rufus_requests[:5], 1):  # Mostrar primeros 5
                print(f"REQUEST #{idx}")
                print(f"  URL: {req['url']}")
                print(f"  Method: {req['method']}")

                # Headers importantes
                important_headers = ['x-api-key', 'x-amz-access-token', 'authorization',
                                   'x-requested-with', 'user-agent', 'x-amzn-requestid']

                print("  Headers importantes:")
                for header in important_headers:
                    if header in req['headers']:
                        value = req['headers'][header]
                        # Ocultar tokens largos
                        if len(value) > 50:
                            value = value[:20] + "..." + value[-10:]
                        print(f"    {header}: {value}")

                # Body
                if req['body']:
                    print("  Body:")
                    if isinstance(req['body'], dict):
                        print(json.dumps(req['body'], indent=4)[:500])
                    else:
                        print(f"    {req['body'][:200]}")

                print()

            # Guardar a archivo
            output_file = Path("rufus_endpoints_discovered.json")
            with open(output_file, 'w') as f:
                json.dump(rufus_requests, f, indent=2)

            print(f"\n💾 Detalles completos guardados en: {output_file}")

        else:
            print("\n⚠️  No se encontraron requests relacionados con Rufus/IA")
            print("\nAsegúrate de:")
            print("  1. Usar Rufus en la app mientras capturabas el tráfico")
            print("  2. Haber instalado el certificado de mitmproxy en el móvil")
            print("  3. Que la app no tenga SSL pinning (puede requerir jailbreak/root)")

    except FlowReadException as e:
        print(f"❌ Error leyendo archivo: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def analyze_json_file(json_file):
    """Analiza un archivo JSON exportado manualmente desde mitmproxy o Charles"""
    print(f"📂 Analizando JSON: {json_file}\n")

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)

        # Buscar requests relacionados con IA
        rufus_requests = []

        for item in data:
            url = item.get('url', '')
            if any(keyword in url.lower() for keyword in AI_KEYWORDS):
                rufus_requests.append(item)

        if rufus_requests:
            print(f"🤖 Encontrados {len(rufus_requests)} requests de Rufus/IA\n")

            for idx, req in enumerate(rufus_requests[:5], 1):
                print(f"REQUEST #{idx}")
                print(json.dumps(req, indent=2)[:1000])
                print()
        else:
            print("⚠️  No se encontraron requests de Rufus/IA")

    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUso:")
        print("  python3 analyze_amazon_traffic.py capture.flow")
        print("  python3 analyze_amazon_traffic.py --json capture.json")
        sys.exit(1)

    file_path = sys.argv[1]

    if not Path(file_path).exists():
        print(f"❌ Archivo no encontrado: {file_path}")
        sys.exit(1)

    # Analizar según el formato
    if '--json' in sys.argv or file_path.endswith('.json'):
        analyze_json_file(file_path)
    else:
        analyze_flow_file(file_path)


if __name__ == "__main__":
    main()
