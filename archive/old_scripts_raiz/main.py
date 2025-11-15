#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - Pipeline completo de Amazon → MercadoLibre CBT
═════════════════════════════════════════════════════════
Flujo:
1. Lee ASINs desde asins.txt
2. Descarga datos de Amazon SP-API
3. Transforma con category matcher + equivalencias
4. Genera mini_ml.json con toda la info relevante
5. Publica en MercadoLibre CBT

Autor: Pipeline automatizado
"""

import os
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# Auto-activar venv
if sys.prefix == sys.base_prefix:
    vpy = Path(__file__).parent / "venv" / "bin" / "python"
    if vpy.exists():
        print(f"⚙️  Activando entorno virtual: {vpy}")
        os.execv(str(vpy), [str(vpy)] + sys.argv)

load_dotenv(override=True)

# Imports de módulos propios
from src.amazon_api import get_product_data_from_asin
from src.transform_mapper_new import build_mini_ml, load_json_file, save_json_file
from src.mainglobal import publish_item

# ═════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═════════════════════════════════════════════════════════

ASINS_FILE = "resources/asins.txt"
AMAZON_JSON_DIR = Path("storage/asins_json")
MINI_ML_DIR = Path("storage/logs/publish_ready")
OUTPUT_JSON_DIR = Path("outputs/json")

# Crear directorios necesarios
AMAZON_JSON_DIR.mkdir(exist_ok=True)
MINI_ML_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_JSON_DIR.mkdir(parents=True, exist_ok=True)

# ═════════════════════════════════════════════════════════
# FUNCIONES DEL PIPELINE
# ═════════════════════════════════════════════════════════

def load_asins():
    """Lee lista de ASINs desde asins.txt"""
    if not Path(ASINS_FILE).exists():
        print(f"❌ No se encontró el archivo {ASINS_FILE}")
        return []

    with open(ASINS_FILE, "r") as f:
        asins = [line.strip().upper() for line in f if line.strip() and not line.startswith("#")]

    print(f"📋 {len(asins)} ASINs encontrados en {ASINS_FILE}")
    return asins


def download_asin(asin: str) -> bool:
    """Descarga datos de Amazon para un ASIN"""
    json_path = AMAZON_JSON_DIR / f"{asin}.json"

    if json_path.exists():
        print(f"✓ {asin} ya descargado, saltando...")
        return True

    try:
        print(f"\n📥 Descargando {asin} desde Amazon SP-API...")
        get_product_data_from_asin(asin)
        return json_path.exists()
    except Exception as e:
        print(f"❌ Error descargando {asin}: {e}")
        return False


def transform_asin(asin: str) -> bool:
    """Transforma JSON de Amazon a mini_ml usando category matcher"""
    amazon_path = AMAZON_JSON_DIR / f"{asin}.json"
    mini_path = MINI_ML_DIR / f"{asin}_mini_ml.json"

    if mini_path.exists():
        print(f"✓ {asin} ya transformado, saltando...")
        return True

    if not amazon_path.exists():
        print(f"❌ No existe JSON de Amazon para {asin}")
        return False

    try:
        print(f"\n🔄 Transformando {asin}...")
        amazon_json = load_json_file(str(amazon_path))

        # Construir mini_ml con category matcher y equivalencias
        mini_ml = build_mini_ml(amazon_json)

        # Guardar mini_ml
        save_json_file(str(mini_path), mini_ml)

        # También copiar a outputs/json para compatibilidad
        output_path = OUTPUT_JSON_DIR / f"{asin}.json"
        save_json_file(str(output_path), amazon_json)

        print(f"✅ Transformación completa: {mini_path}")
        print(f"   → Categoría: {mini_ml.get('category_name')} ({mini_ml.get('category_id')})")
        print(f"   → Atributos mapeados: {len(mini_ml.get('attributes_mapped', {}))}")
        print(f"   → Imágenes: {len(mini_ml.get('images', []))}")

        return True
    except Exception as e:
        print(f"❌ Error transformando {asin}: {e}")
        import traceback
        traceback.print_exc()
        return False


def publish_asin(asin: str) -> bool:
    """Publica producto en MercadoLibre CBT con retry automático"""
    mini_path = MINI_ML_DIR / f"{asin}_mini_ml.json"

    if not mini_path.exists():
        print(f"❌ No existe mini_ml para {asin}")
        return False

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                print(f"\n🔄 Reintento {attempt}/{max_retries} para {asin}...")
            else:
                print(f"\n🚀 Publicando {asin} en MercadoLibre CBT...")

            mini_ml = load_json_file(str(mini_path))

            result = publish_item(mini_ml)

            # Verificar si result es None (publicación abortada)
            if result is None:
                print(f"⚠️ Publicación abortada para {asin} (dimensiones/imágenes inválidas)")
                return False

            # El response de MercadoLibre CBT usa "item_id", no "id"
            item_id = result.get("item_id") or result.get("id")
            if item_id:
                print(f"✅ Publicado exitosamente: {item_id}")
                print(f"   → Precio: ${mini_ml.get('price', {}).get('final_usd', 0)}")

                # Contar publicaciones exitosas por país
                site_items = result.get("site_items", [])
                successful = [s for s in site_items if s.get("item_id")]
                failed = [s for s in site_items if s.get("error")]
                print(f"   → Publicado en {len(successful)} países, {len(failed)} con errores")
                return True
            else:
                print(f"⚠️ Publicación sin ID: {result}")
                return False

        except Exception as e:
            error_str = str(e)
            print(f"❌ Error publicando {asin} (intento {attempt}): {e}")

            # 🔹 Detectar error de GTIN duplicado (código 3701)
            if "3701" in error_str or "invalid_product_identifier" in error_str:
                print("⚠️ GTIN duplicado detectado → Reintentando SIN GTIN...")
                # Marcar para reintentar sin GTIN
                mini_ml = load_json_file(str(mini_path))
                mini_ml["force_no_gtin"] = True
                with open(mini_path, "w", encoding="utf-8") as f:
                    import json
                    json.dump(mini_ml, f, ensure_ascii=False, indent=2)
                continue

            # 🔹 Detectar error de categoría incorrecta
            if "category" in error_str.lower() or "Title and photos did not match" in error_str:
                print("⚠️ Categoría incorrecta detectada → Regenerando categoría...")
                # Eliminar mini_ml y regenerar con nueva categoría
                mini_path.unlink()
                if transform_asin(asin):
                    continue
                else:
                    print(f"❌ Fallo regenerando {asin}")
                    return False

            # Si es el último intento, fallar
            if attempt == max_retries:
                import traceback
                traceback.print_exc()
                return False

            # Esperar antes de reintentar
            import time
            time.sleep(2)

    return False


# ═════════════════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ═════════════════════════════════════════════════════════

def run_pipeline(asins: list, skip_download=False, skip_transform=False, skip_publish=False):
    """Ejecuta el pipeline completo para todos los ASINs"""

    results = {
        "downloaded": [],
        "transformed": [],
        "published": [],
        "failed": []
    }

    print("\n" + "="*60)
    print("🚀 INICIANDO PIPELINE AMAZON → MERCADOLIBRE CBT")
    print("="*60)
    print(f"📦 Total de productos: {len(asins)}")
    print("="*60 + "\n")

    for i, asin in enumerate(asins, 1):
        print(f"\n{'='*60}")
        print(f"📦 Procesando [{i}/{len(asins)}]: {asin}")
        print('='*60)

        # Paso 1: Descargar de Amazon
        if not skip_download:
            if download_asin(asin):
                results["downloaded"].append(asin)
            else:
                results["failed"].append(asin)
                continue

        # Paso 2: Transformar con category matcher
        if not skip_transform:
            if transform_asin(asin):
                results["transformed"].append(asin)
            else:
                results["failed"].append(asin)
                continue

        # Paso 3: Publicar en MercadoLibre
        if not skip_publish:
            if publish_asin(asin):
                results["published"].append(asin)
            else:
                results["failed"].append(asin)
                continue

            # Rate limiting: esperar entre publicaciones
            if i < len(asins):
                print("\n⏱️  Esperando 3 segundos antes del siguiente producto...")
                time.sleep(3)

    # Reporte final
    print("\n" + "="*60)
    print("📊 REPORTE FINAL DEL PIPELINE")
    print("="*60)
    print(f"✅ Descargados: {len(results['downloaded'])}/{len(asins)}")
    print(f"✅ Transformados: {len(results['transformed'])}/{len(asins)}")
    print(f"✅ Publicados: {len(results['published'])}/{len(asins)}")
    print(f"❌ Fallidos: {len(results['failed'])}/{len(asins)}")

    if results["failed"]:
        print(f"\n⚠️  ASINs fallidos: {', '.join(results['failed'])}")

    print("="*60 + "\n")

    return results


# ═════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════

def main():
    """Punto de entrada principal"""

    # Verificar credenciales
    if not os.getenv("ML_ACCESS_TOKEN"):
        print("❌ Error: Falta ML_ACCESS_TOKEN en .env")
        sys.exit(1)

    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Advertencia: Sin OPENAI_API_KEY, se usarán valores fallback")

    if not os.getenv("AMZ_CLIENT_ID"):
        print("❌ Error: Faltan credenciales de Amazon SP-API en .env")
        sys.exit(1)

    # Cargar ASINs
    asins = load_asins()
    if not asins:
        print("❌ No hay ASINs para procesar")
        sys.exit(1)

    # Opciones de línea de comandos
    skip_download = "--skip-download" in sys.argv
    skip_transform = "--skip-transform" in sys.argv
    skip_publish = "--skip-publish" in sys.argv

    if skip_download:
        print("⏭️  Saltando descarga de Amazon")
    if skip_transform:
        print("⏭️  Saltando transformación")
    if skip_publish:
        print("⏭️  Saltando publicación en MercadoLibre")

    # Ejecutar pipeline
    try:
        results = run_pipeline(
            asins,
            skip_download=skip_download,
            skip_transform=skip_transform,
            skip_publish=skip_publish
        )

        # Guardar reporte
        report_path = Path("storage/logs/pipeline_report.json")
        with open(report_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"📄 Reporte guardado en: {report_path}")

    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error fatal en el pipeline: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
