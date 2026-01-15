#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# 01_search_glow.py - BUSCAR PRODUCTOS EN AMAZON CON GLOW API
# ═══════════════════════════════════════════════════════════════════════════════
#
# ¿Qué hace?
#   Busca productos en Amazon usando keywords con Glow API y guarda los ASINs encontrados.
#   Los resultados se guardan en data/asins.txt para luego publicarlos.
#
#   VENTAJAS sobre 01_search.py (API oficial):
#   - No requiere credenciales de Amazon SP-API
#   - Más rápido (búsqueda directa sin throttling de API)
#   - Simula búsqueda real de usuario
#   - Usa sesiones con zipcode para relevancia local
#   - Filtra automáticamente productos sponsoreados
#   - Filtra por envío rápido (criterio consistente con sync: ≤4 días)
#   - Filtra por rango de precio (min $28 - max $450) para garantizar rentabilidad
#   - Analiza variantes de productos y las agrega si cumplen criterios (precio/envío)
#
# Comando:
#   python3 01_search_glow.py
#
# ═══════════════════════════════════════════════════════════════════════════════
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Importar la nueva integración de Glow Search
sys.path.insert(0, str(Path(__file__).parent))
from src.integrations.amazon_glow_search import search_multiple_keywords, get_product_variants
import requests

# Cargar .env (override=True para sobreescribir variables del sistema)
load_dotenv(override=True)

# Colores para consola
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color

def log(message, color=Colors.NC):
    """Print con color"""
    print(f"{color}{message}{Colors.NC}")

def is_asin(text: str) -> bool:
    """Verifica si un texto es un ASIN válido (10 caracteres alfanuméricos)"""
    text = text.strip().upper()
    return len(text) == 10 and text.isalnum()

def process_asins_directly(asins: list, zipcode: str, min_price: float, max_price: float, max_delivery_days: int) -> dict:
    """
    Procesa ASINs directamente para obtener sus variantes sin buscar por keywords

    Returns:
        Dict con ASINs encontrados y métricas
    """
    from src.integrations.amazon_glow_search import get_random_user_agent

    all_asins = set()
    total_variants = 0
    failed_asins = []

    # Crear sesión
    session = requests.Session()
    user_agent = get_random_user_agent()

    session.headers.update({
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })

    # Configurar zipcode con Glow
    try:
        homepage_url = "https://www.amazon.com"
        session.get(homepage_url, timeout=15)

        glow_url = "https://www.amazon.com/portal-migration/hz/glow/address-change"
        params = {
            'actionSource': 'glow',
            'deviceType': 'desktop',
            'pageType': 'Search',
            'storeContext': 'pc'
        }
        payload = {
            'locationType': 'LOCATION_INPUT',
            'zipCode': zipcode,
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
        session.post(glow_url, params=params, json=payload, headers=headers, timeout=10)
    except:
        pass

    log("🔍 Procesando ASINs directamente...", Colors.BLUE)
    print()

    for i, asin in enumerate(asins, 1):
        log(f"  [{i}/{len(asins)}] ASIN: {asin}", Colors.CYAN)

        # Agregar el ASIN principal
        all_asins.add(asin)

        # Buscar variantes
        try:
            variants = get_product_variants(
                asin=asin,
                session=session,
                zipcode=zipcode,
                min_price=min_price,
                max_price=max_price,
                max_delivery_days=max_delivery_days
            )

            if variants:
                log(f"    ✅ {len(variants)} variantes encontradas", Colors.GREEN)
                for variant in variants:
                    if variant not in all_asins:
                        all_asins.add(variant)
                        total_variants += 1
            else:
                log(f"    ℹ️  Sin variantes válidas", Colors.YELLOW)

        except Exception as e:
            log(f"    ❌ Error: {str(e)}", Colors.RED)
            failed_asins.append(asin)

        # Pequeño delay entre ASINs
        if i < len(asins):
            import time
            time.sleep(1.5)

    return {
        "all_asins": all_asins,
        "total_variants": total_variants,
        "failed_asins": failed_asins,
        "total_processed": len(asins)
    }

def main():
    # Leer configuración desde .env
    MAX_RESULTS = int(os.getenv("GLOW_MAX_RESULTS", "10"))
    MAX_DELIVERY_DAYS = int(os.getenv("GLOW_MAX_DELIVERY_DAYS", "4"))
    MIN_PRICE = float(os.getenv("GLOW_MIN_PRICE", "28"))
    MAX_PRICE = float(os.getenv("GLOW_MAX_PRICE", "450"))
    KEYWORDS_FILE = os.getenv("KEYWORDS_FILE", "keywords.txt")
    BUYER_ZIPCODE = os.getenv("BUYER_ZIPCODE", "33172")
    CHECK_VARIANTS = os.getenv("GLOW_CHECK_VARIANTS", "true").lower() == "true"
    PROJECT_ROOT = Path(__file__).parent.absolute()

    # Configuración fija (no necesita cambiar)
    DELAY_BETWEEN_REQUESTS = 2.0
    FILTER_FAST_DELIVERY = True
    USE_BLACKLIST = True

    log("╔════════════════════════════════════════════════════════════════╗", Colors.BLUE)
    log("║      BÚSQUEDA DE ASINs POR KEYWORDS CON GLOW API              ║", Colors.BLUE)
    log("╚════════════════════════════════════════════════════════════════╝", Colors.BLUE)
    print()
    # Verificar si hay cookies Prime
    cookies_file = "cache/amazon_session_cookies.json"
    has_prime_cookies = os.path.exists(cookies_file)

    log("📋 Configuración:", Colors.GREEN)
    log(f"   ASINs por keyword:           {Colors.YELLOW}{MAX_RESULTS}{Colors.NC}")
    log(f"   Máx días de envío:           {Colors.YELLOW}{MAX_DELIVERY_DAYS} días{Colors.NC}")
    log(f"   Rango de precio:             {Colors.YELLOW}${MIN_PRICE} - ${MAX_PRICE}{Colors.NC}")
    log(f"   Archivo de keywords:         {Colors.YELLOW}{KEYWORDS_FILE}{Colors.NC}")
    log(f"   Sesión Prime:                {Colors.YELLOW}{'🔐 ACTIVA' if has_prime_cookies else '❌ NO (anónima)'}{Colors.NC}")
    log(f"   Buyer zipcode:               {Colors.YELLOW}{BUYER_ZIPCODE}{Colors.NC}")
    log(f"   Analizar variantes:          {Colors.YELLOW}{'✅ SÍ' if CHECK_VARIANTS else '❌ NO'}{Colors.NC}")
    print()

    # Verificar que existe el archivo de keywords
    keywords_path = PROJECT_ROOT / KEYWORDS_FILE
    if not keywords_path.exists():
        log(f"❌ Error: No se encontró el archivo de keywords: {KEYWORDS_FILE}", Colors.RED)
        log(f"   Creá el archivo en: {keywords_path}", Colors.YELLOW)
        sys.exit(1)

    # Leer keywords/ASINs (soporta .txt y .json)
    log(f"📖 Leyendo desde {KEYWORDS_FILE}...", Colors.CYAN)
    if keywords_path.suffix.lower() == '.json':
        # Formato JSON
        with open(keywords_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        keywords_raw = data.get("keywords", [])
        # Si es lista de dicts, extraer campo "keyword"
        if keywords_raw and isinstance(keywords_raw[0], dict):
            keywords = [kw.get("keyword", "") for kw in keywords_raw if kw.get("keyword")]
        else:
            keywords = keywords_raw
    else:
        # Formato TXT simple (una keyword/ASIN por línea)
        with open(keywords_path, "r", encoding="utf-8") as f:
            keywords = [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith("#")
            ]

    total_items = len(keywords)

    # Detectar si son ASINs o keywords
    asins = [kw for kw in keywords if is_asin(kw)]
    keywords_only = [kw for kw in keywords if not is_asin(kw)]

    mode = None
    if asins and not keywords_only:
        mode = "asins"
        log(f"   ✅ {len(asins)} ASINs cargados", Colors.GREEN)
    elif keywords_only and not asins:
        mode = "keywords"
        log(f"   ✅ {len(keywords_only)} keywords cargadas", Colors.GREEN)
    elif asins and keywords_only:
        log(f"   ✅ {len(keywords_only)} keywords y {len(asins)} ASINs cargados", Colors.GREEN)
        log(f"   ℹ️  Modo mixto: se procesarán keywords y ASINs", Colors.YELLOW)
        mode = "mixed"
    else:
        log("❌ Error: No hay keywords ni ASINs para procesar", Colors.RED)
        sys.exit(1)

    print()

    if total_items == 0:
        log("❌ Error: No hay items para procesar", Colors.RED)
        sys.exit(1)

    # Mostrar preview
    if mode == "asins":
        log("🔍 ASINs a procesar:", Colors.CYAN)
        preview_count = min(5, len(asins))
        for i, asin in enumerate(asins[:preview_count], 1):
            log(f"   {i}. {asin}", Colors.YELLOW)
        if len(asins) > preview_count:
            log(f"   ... y {len(asins) - preview_count} más", Colors.YELLOW)
    elif mode == "keywords":
        log("🔍 Keywords a buscar:", Colors.CYAN)
        preview_count = min(5, len(keywords_only))
        for i, kw in enumerate(keywords_only[:preview_count], 1):
            log(f"   {i}. {kw}", Colors.YELLOW)
        if len(keywords_only) > preview_count:
            log(f"   ... y {len(keywords_only) - preview_count} más", Colors.YELLOW)
    else:  # mixed
        if keywords_only:
            log("🔍 Keywords a buscar:", Colors.CYAN)
            preview_count = min(3, len(keywords_only))
            for i, kw in enumerate(keywords_only[:preview_count], 1):
                log(f"   {i}. {kw}", Colors.YELLOW)
            if len(keywords_only) > preview_count:
                log(f"   ... y {len(keywords_only) - preview_count} más", Colors.YELLOW)
        if asins:
            log("🔍 ASINs a procesar:", Colors.CYAN)
            preview_count = min(3, len(asins))
            for i, asin in enumerate(asins[:preview_count], 1):
                log(f"   {i}. {asin}", Colors.YELLOW)
            if len(asins) > preview_count:
                log(f"   ... y {len(asins) - preview_count} más", Colors.YELLOW)
    print()

    # Confirmar
    if mode == "asins":
        log(f"⏱️  Tiempo estimado: ~{len(asins) * 2 / 60:.1f} minutos", Colors.CYAN)
    else:
        total_time = len(keywords_only) * DELAY_BETWEEN_REQUESTS + len(asins) * 2
        log(f"⏱️  Tiempo estimado: ~{total_time / 60:.1f} minutos", Colors.CYAN)
    print()
    confirm = input("¿Iniciar búsqueda? (s/N): ")
    if confirm.lower() != 's':
        log("❌ Búsqueda cancelada", Colors.YELLOW)
        return
    print()

    # Iniciar búsqueda
    log("🚀 Iniciando búsqueda en Amazon...", Colors.BLUE)
    print()

    start_time = datetime.now()
    all_asins = set()
    results = []
    total_variants_found = 0

    # Procesar keywords
    if keywords_only:
        log("═" * 70, Colors.BLUE)
        log("📝 PROCESANDO KEYWORDS", Colors.BLUE)
        log("═" * 70, Colors.BLUE)
        print()

        keyword_results = search_multiple_keywords(
            keywords=keywords_only,
            max_results_per_keyword=MAX_RESULTS,
            delay_between_requests=DELAY_BETWEEN_REQUESTS,
            filter_fast_delivery=FILTER_FAST_DELIVERY,
            use_blacklist=USE_BLACKLIST,
            zipcode=BUYER_ZIPCODE,
            max_delivery_days=MAX_DELIVERY_DAYS,
            min_price=MIN_PRICE,
            max_price=MAX_PRICE,
            check_variants=CHECK_VARIANTS
        )
        results.extend(keyword_results)

        # Recolectar ASINs de keywords
        for result in keyword_results:
            if not result["error"]:
                total_variants_found += result.get("variants_found", 0)
                for asin in result["asins"]:
                    all_asins.add(asin)

        print()

    # Procesar ASINs directamente
    if asins:
        log("═" * 70, Colors.BLUE)
        log("🔖 PROCESANDO ASINs DIRECTAMENTE", Colors.BLUE)
        log("═" * 70, Colors.BLUE)
        print()

        asin_results = process_asins_directly(
            asins=asins,
            zipcode=BUYER_ZIPCODE,
            min_price=MIN_PRICE,
            max_price=MAX_PRICE,
            max_delivery_days=MAX_DELIVERY_DAYS
        )

        # Agregar ASINs de procesamiento directo
        for asin in asin_results["all_asins"]:
            all_asins.add(asin)
        total_variants_found += asin_results["total_variants"]

        print()

    elapsed = (datetime.now() - start_time).total_seconds()

    print()
    log("═" * 70, Colors.BLUE)
    log("📊 PROCESANDO RESULTADOS...", Colors.BLUE)
    log("═" * 70, Colors.BLUE)
    print()

    # Procesar estadísticas de keywords
    successful_keywords = 0
    failed_keywords = 0
    total_filtered_by_blacklist = 0
    total_filtered_by_price = 0

    for result in results:
        if result["error"]:
            failed_keywords += 1
        else:
            successful_keywords += 1
            total_filtered_by_blacklist += result.get("filtered_by_blacklist", 0)
            total_filtered_by_price += result.get("filtered_by_price", 0)

    # Guardar en data/asins.txt
    output_file = PROJECT_ROOT / "data" / "asins.txt"
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, "w") as f:
        for asin in sorted(all_asins):
            f.write(f"{asin}\n")

    # Guardar reporte detallado en JSON
    report_file = PROJECT_ROOT / "data" / f"search_glow_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "config": {
            "max_results": MAX_RESULTS,
            "max_delivery_days": MAX_DELIVERY_DAYS,
            "min_price": MIN_PRICE,
            "max_price": MAX_PRICE,
            "buyer_zipcode": BUYER_ZIPCODE,
            "keywords_file": KEYWORDS_FILE,
            "filter_fast_delivery": FILTER_FAST_DELIVERY,
            "use_blacklist": USE_BLACKLIST,
            "check_variants": CHECK_VARIANTS
        },
        "summary": {
            "mode": mode,
            "total_keywords": len(keywords_only) if keywords_only else 0,
            "total_asins_input": len(asins) if asins else 0,
            "successful_keywords": successful_keywords,
            "failed_keywords": failed_keywords,
            "total_asins_unique": len(all_asins),
            "total_filtered_by_blacklist": total_filtered_by_blacklist,
            "total_filtered_by_price": total_filtered_by_price,
            "total_variants_found": total_variants_found,
            "elapsed_seconds": elapsed
        },
        "results": results
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    # Resumen final
    print()
    log("╔════════════════════════════════════════════════════════════════╗", Colors.GREEN)
    log("║                    ✅ BÚSQUEDA COMPLETADA                      ║", Colors.GREEN)
    log("╚════════════════════════════════════════════════════════════════╝", Colors.GREEN)
    print()
    log("📊 RESUMEN:", Colors.GREEN)

    # Mostrar stats según el modo
    if mode == "keywords":
        log(f"   Keywords procesadas:         {Colors.YELLOW}{len(keywords_only)}{Colors.NC}")
        log(f"   Exitosas:                    {Colors.GREEN}{successful_keywords}{Colors.NC}")
        if failed_keywords > 0:
            log(f"   Fallidas:                    {Colors.RED}{failed_keywords}{Colors.NC}")
    elif mode == "asins":
        log(f"   ASINs procesados:            {Colors.YELLOW}{len(asins)}{Colors.NC}")
    else:  # mixed
        log(f"   Keywords procesadas:         {Colors.YELLOW}{len(keywords_only)}{Colors.NC}")
        log(f"   ASINs procesados:            {Colors.YELLOW}{len(asins)}{Colors.NC}")
        if failed_keywords > 0:
            log(f"   Keywords fallidas:           {Colors.RED}{failed_keywords}{Colors.NC}")

    log(f"   Total ASINs únicos:          {Colors.YELLOW}{len(all_asins)}{Colors.NC}")
    if CHECK_VARIANTS and total_variants_found > 0:
        log(f"   Variantes encontradas:       {Colors.CYAN}{total_variants_found}{Colors.NC}")
    if USE_BLACKLIST and total_filtered_by_blacklist > 0:
        log(f"   Filtrados por blacklist:     {Colors.YELLOW}{total_filtered_by_blacklist}{Colors.NC}")
    if total_filtered_by_price > 0:
        log(f"   Filtrados por precio:        {Colors.YELLOW}{total_filtered_by_price}{Colors.NC}")
    log(f"   Tiempo total:                {Colors.CYAN}{elapsed / 60:.1f} minutos{Colors.NC}")
    print()
    log(f"💾 Archivos generados:", Colors.CYAN)
    log(f"   ASINs:    {Colors.YELLOW}{output_file}{Colors.NC}")
    log(f"   Reporte:  {Colors.YELLOW}{report_file}{Colors.NC}")
    print()

    # Mostrar algunos ASINs de ejemplo
    if all_asins:
        log("📦 Primeros 10 ASINs encontrados:", Colors.BLUE)
        for i, asin in enumerate(sorted(all_asins)[:10]):
            log(f"   {i+1}. {asin}", Colors.GREEN)
        if len(all_asins) > 10:
            log(f"   ... y {len(all_asins) - 10} más", Colors.YELLOW)
        print()

        # Calcular promedio de ASINs por keyword
        avg_asins = len(all_asins) / successful_keywords if successful_keywords > 0 else 0
        log(f"📈 Promedio de ASINs únicos por keyword: {avg_asins:.1f}", Colors.CYAN)
        print()
    else:
        log("⚠️  No se encontraron ASINs", Colors.YELLOW)
        print()

    # Mostrar errores si los hay
    if failed_keywords > 0:
        log("⚠️  KEYWORDS CON ERRORES:", Colors.YELLOW)
        for result in results:
            if result["error"]:
                log(f"   - {result['keyword']}: {result['error']}", Colors.RED)
        print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Búsqueda detenida por usuario (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        log(f"\n❌ Error: {e}", Colors.RED)
        import traceback
        traceback.print_exc()
        sys.exit(1)
