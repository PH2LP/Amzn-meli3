#!/usr/bin/env python3
"""
Regenerar y publicar todos los ASINs del archivo asins.txt
con validación IA integrada para prevenir rechazos.
"""

import sys
from pathlib import Path

# Auto-activar venv
if sys.prefix == sys.base_prefix:
    vpy = Path(__file__).parent / "venv" / "bin" / "python"
    if vpy.exists():
        import os
        os.execv(str(vpy), [str(vpy)] + sys.argv)

import json
import time
from dotenv import load_dotenv
from src.unified_transformer import transform_amazon_to_ml_unified
from src.ai_validators import validate_listing_complete
from src.mainglobal import publish_item

load_dotenv(override=True)

# Leer ASINs del archivo
asins_file = Path("resources/asins.txt")
if not asins_file.exists():
    print(f"❌ {asins_file} no encontrado")
    sys.exit(1)

asins = [line.strip() for line in asins_file.read_text().splitlines() if line.strip()]

print(f"\n{'='*70}")
print(f"🔄 REGENERAR Y PUBLICAR {len(asins)} ASINS CON VALIDACIÓN IA")
print(f"{'='*70}\n")

results = {
    "regenerated": [],
    "validation_failed": [],
    "published": [],
    "publish_failed": []
}

for i, asin in enumerate(asins, 1):
    print(f"\n{'='*70}")
    print(f"{i}/{len(asins)}. {asin}")
    print(f"{'='*70}\n")

    # 1. Leer JSON de Amazon
    amazon_json_path = Path(f"storage/asins_json/{asin}.json")

    if not amazon_json_path.exists():
        print(f"⚠️ No existe {amazon_json_path}")
        results["validation_failed"].append(asin)
        continue

    with open(amazon_json_path, "r", encoding="utf-8") as f:
        amazon_json = json.load(f)

    # 2. Regenerar con unified transformer (usa IA para categoría)
    print(f"🤖 Regenerando con IA (categorización + transformación)...")
    try:
        unified_result = transform_amazon_to_ml_unified(amazon_json)

        if not unified_result:
            print(f"❌ Unified transformer falló")
            results["validation_failed"].append(asin)
            continue

        # Construir mini_ml con formato esperado
        mini_ml = {
            "asin": asin,
            "brand": unified_result.get("brand", ""),
            "model": unified_result.get("model", ""),
            "category_id": unified_result["category_id"],
            "category_name": unified_result["category_name"],
            "title_ai": unified_result["title"],
            "description_ai": unified_result["description"],
            "package": unified_result["dimensions"],
            "price": unified_result["price"],
            "gtins": unified_result.get("gtins", []),
            "images": unified_result["images"],
            "attributes_mapped": {
                attr["id"]: {"value_name": attr["value_name"]}
                for attr in unified_result.get("attributes", [])
            }
        }

        print(f"✅ Regenerado: {unified_result['category_name']}")

    except Exception as e:
        print(f"❌ Error regenerando: {e}")
        import traceback
        traceback.print_exc()
        results["validation_failed"].append(asin)
        continue

    # 3. Validar con IA
    print(f"\n🤖 Validando con IA...")
    validation_result = validate_listing_complete(mini_ml)

    if not validation_result["ready_to_publish"]:
        print(f"❌ VALIDACIÓN FALLIDA")

        if validation_result["critical_issues"]:
            print("🚨 Problemas críticos:")
            for issue in validation_result["critical_issues"]:
                print(f"   • {issue}")

        if validation_result["warnings"]:
            print("⚠️ Advertencias:")
            for warning in validation_result["warnings"]:
                print(f"   • {warning}")

        # Guardar para revisión manual
        failed_path = Path(f"storage/logs/validation_failed/{asin}_failed.json")
        failed_path.parent.mkdir(parents=True, exist_ok=True)
        with open(failed_path, "w", encoding="utf-8") as f:
            json.dump({
                "mini_ml": mini_ml,
                "validation": validation_result
            }, f, indent=2, ensure_ascii=False)

        print(f"💾 Guardado en {failed_path} para revisión")
        results["validation_failed"].append(asin)
        continue

    print(f"✅ Validación aprobada")
    img_val = validation_result["image_validation"]
    cat_val = validation_result["category_validation"]
    print(f"   • Imágenes: {'✅' if img_val.get('valid') else '❌'}")
    print(f"   • Categoría: {'✅' if cat_val.get('valid') else '❌'} (confianza: {cat_val.get('confidence', 0):.0%})")

    # 4. Guardar mini_ml validado
    mini_ml_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")
    mini_ml_path.parent.mkdir(parents=True, exist_ok=True)

    with open(mini_ml_path, "w", encoding="utf-8") as f:
        json.dump(mini_ml, f, indent=2, ensure_ascii=False)

    print(f"💾 Guardado: {mini_ml_path}")
    results["regenerated"].append(asin)

    # 5. Publicar
    print(f"\n🚀 Publicando a MercadoLibre...")
    try:
        result = publish_item(mini_ml)

        if result:
            item_id = result.get("item_id") or result.get("id")
            if item_id:
                print(f"✅ Publicado: {item_id}")

                # Contar países exitosos
                site_items = result.get("site_items", [])
                successful = [s for s in site_items if s.get("item_id")]
                failed = [s for s in site_items if s.get("error")]
                print(f"   → {len(successful)} países exitosos, {len(failed)} con errores")

                results["published"].append(asin)
            else:
                print(f"⚠️ Sin item_id en respuesta")
                site_items = result.get("site_items", [])
                successful = [s for s in site_items if s.get("item_id")]
                if successful:
                    print(f"   → Publicado parcialmente en {len(successful)} países")
                    results["published"].append(asin)
                else:
                    results["publish_failed"].append(asin)
        else:
            print(f"❌ Publicación falló (validation bloqueó)")
            results["publish_failed"].append(asin)

    except Exception as e:
        print(f"❌ Error publicando: {e}")
        import traceback
        traceback.print_exc()
        results["publish_failed"].append(asin)

    # Rate limiting
    if i < len(asins):
        print(f"\n⏱️  Esperando 3 segundos...")
        time.sleep(3)

# REPORTE FINAL
print(f"\n{'='*70}")
print(f"📊 REPORTE FINAL")
print(f"{'='*70}")
print(f"✅ Regenerados y validados: {len(results['regenerated'])}/{len(asins)}")
print(f"❌ Fallaron validación: {len(results['validation_failed'])}/{len(asins)}")
print(f"🚀 Publicados exitosamente: {len(results['published'])}/{len(asins)}")
print(f"⚠️ Fallaron publicación: {len(results['publish_failed'])}/{len(asins)}")

if results["regenerated"]:
    print(f"\n✅ Regenerados: {', '.join(results['regenerated'])}")
if results["validation_failed"]:
    print(f"\n❌ Fallaron validación: {', '.join(results['validation_failed'])}")
if results["published"]:
    print(f"\n🚀 Publicados: {', '.join(results['published'])}")
if results["publish_failed"]:
    print(f"\n⚠️ Fallaron publicación: {', '.join(results['publish_failed'])}")

# Guardar reporte
report_path = Path("storage/regeneration_report.json")
with open(report_path, "w") as f:
    json.dump(results, f, indent=2)

print(f"\n💾 Reporte guardado en {report_path}")
print(f"{'='*70}\n")
