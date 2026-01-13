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
from src.integrations.amazon_glow_search import search_multiple_keywords

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

def main():
    # Leer configuración desde .env
    MAX_RESULTS = int(os.getenv("GLOW_MAX_RESULTS", "10"))
    MAX_DELIVERY_DAYS = int(os.getenv("GLOW_MAX_DELIVERY_DAYS", "4"))
    MAX_PRICE = float(os.getenv("GLOW_MAX_PRICE", "450"))
    KEYWORDS_FILE = os.getenv("KEYWORDS_FILE", "keywords.txt")
    BUYER_ZIPCODE = os.getenv("BUYER_ZIPCODE", "33172")
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
    import os
    cookies_file = "cache/amazon_session_cookies.json"
    has_prime_cookies = os.path.exists(cookies_file)

    log("📋 Configuración:", Colors.GREEN)
    log(f"   ASINs por keyword:           {Colors.YELLOW}{MAX_RESULTS}{Colors.NC}")
    log(f"   Máx días de envío:           {Colors.YELLOW}{MAX_DELIVERY_DAYS} días{Colors.NC}")
    log(f"   Precio máximo:               {Colors.YELLOW}${MAX_PRICE}{Colors.NC}")
    log(f"   Archivo de keywords:         {Colors.YELLOW}{KEYWORDS_FILE}{Colors.NC}")
    log(f"   Sesión Prime:                {Colors.YELLOW}{'🔐 ACTIVA' if has_prime_cookies else '❌ NO (anónima)'}{Colors.NC}")
    log(f"   Buyer zipcode:               {Colors.YELLOW}{BUYER_ZIPCODE}{Colors.NC}")
    print()

    # Verificar que existe el archivo de keywords
    keywords_path = PROJECT_ROOT / KEYWORDS_FILE
    if not keywords_path.exists():
        log(f"❌ Error: No se encontró el archivo de keywords: {KEYWORDS_FILE}", Colors.RED)
        log(f"   Creá el archivo en: {keywords_path}", Colors.YELLOW)
        sys.exit(1)

    # Leer keywords (soporta .txt y .json)
    log(f"📖 Leyendo keywords desde {KEYWORDS_FILE}...", Colors.CYAN)
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
        # Formato TXT simple (una keyword por línea)
        with open(keywords_path, "r", encoding="utf-8") as f:
            keywords = [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith("#")
            ]

    total_keywords = len(keywords)
    log(f"   ✅ {total_keywords} keywords cargadas", Colors.GREEN)
    print()

    if total_keywords == 0:
        log("❌ Error: No hay keywords para buscar", Colors.RED)
        sys.exit(1)

    # Mostrar preview de keywords
    log("🔍 Keywords a buscar:", Colors.CYAN)
    preview_count = min(5, total_keywords)
    for i, kw in enumerate(keywords[:preview_count], 1):
        log(f"   {i}. {kw}", Colors.YELLOW)
    if total_keywords > preview_count:
        log(f"   ... y {total_keywords - preview_count} más", Colors.YELLOW)
    print()

    # Confirmar
    log(f"⏱️  Tiempo estimado: ~{total_keywords * DELAY_BETWEEN_REQUESTS / 60:.1f} minutos", Colors.CYAN)
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

    results = search_multiple_keywords(
        keywords=keywords,
        max_results_per_keyword=MAX_RESULTS,
        delay_between_requests=DELAY_BETWEEN_REQUESTS,
        filter_fast_delivery=FILTER_FAST_DELIVERY,
        use_blacklist=USE_BLACKLIST,
        zipcode=BUYER_ZIPCODE,
        max_delivery_days=MAX_DELIVERY_DAYS,
        max_price=MAX_PRICE
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    print()
    log("═" * 70, Colors.BLUE)
    log("📊 PROCESANDO RESULTADOS...", Colors.BLUE)
    log("═" * 70, Colors.BLUE)
    print()

    # Combinar todos los ASINs y eliminar duplicados
    all_asins = set()
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
            for asin in result["asins"]:
                all_asins.add(asin)

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
        "config": {
            "max_results": MAX_RESULTS,
            "max_delivery_days": MAX_DELIVERY_DAYS,
            "max_price": MAX_PRICE,
            "buyer_zipcode": BUYER_ZIPCODE,
            "keywords_file": KEYWORDS_FILE,
            "filter_fast_delivery": FILTER_FAST_DELIVERY,
            "use_blacklist": USE_BLACKLIST
        },
        "summary": {
            "total_keywords": total_keywords,
            "successful_keywords": successful_keywords,
            "failed_keywords": failed_keywords,
            "total_asins_unique": len(all_asins),
            "total_filtered_by_blacklist": total_filtered_by_blacklist,
            "total_filtered_by_price": total_filtered_by_price,
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
    log(f"   Keywords procesadas:         {Colors.YELLOW}{total_keywords}{Colors.NC}")
    log(f"   Exitosas:                    {Colors.GREEN}{successful_keywords}{Colors.NC}")
    if failed_keywords > 0:
        log(f"   Fallidas:                    {Colors.RED}{failed_keywords}{Colors.NC}")
    log(f"   Total ASINs únicos:          {Colors.YELLOW}{len(all_asins)}{Colors.NC}")
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
