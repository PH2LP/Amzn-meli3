#!/usr/bin/env python3
"""
Elimina listings con categorías incorrectas y re-publica con categorías corregidas.
"""

import sys
import os
import json
import requests
import time
from pathlib import Path
from typing import List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.mainglobal import publish_item
from dotenv import load_dotenv

load_dotenv()

# ASINs que necesitan re-publicación
ASINS_TO_REPUBLISH = [
    'B092RCLKHN',   # Garmin - categoría cambiada a CBT29890
    'B0BXSLRQH7',   # Golden Hour reloj - categoría cambiada a CBT29890
    'B0DRW69H11',   # LEGO - categoría ya correcta CBT1157
    'B0DCYZJBYD',   # Balón - categoría cambiada a CBT29890
    'B0CLC6NBBX',   # Audífonos - categoría cambiada a CBT29890
    'B0BRNY9HZB'    # Kit pintura - categoría ya correcta CBT29890
]

# Item IDs actuales (de Colombia)
ITEM_IDS_TO_DELETE = {
    'B092RCLKHN': 'CBT2673482687',
    'B0BXSLRQH7': 'CBT2979103096',
    'B0DRW69H11': 'CBT2979177814',
    'B0DCYZJBYD': 'CBT2673456679',
    'B0CLC6NBBX': 'CBT2673419677',
    'B0BRNY9HZB': 'CBT2979027284'
}


def delete_listing(item_id: str, ml_token: str) -> bool:
    """Elimina un listing de MercadoLibre CBT."""
    try:
        print(f"   🗑️  Eliminando {item_id}...")

        # Cambiar status a closed
        response = requests.put(
            f"https://api.mercadolibre.com/items/{item_id}",
            headers={"Authorization": f"Bearer {ml_token}"},
            json={"status": "closed"},
            timeout=30
        )

        if response.status_code in [200, 201]:
            print(f"   ✅ Eliminado exitosamente")
            return True
        else:
            print(f"   ⚠️  Error {response.status_code}: {response.text[:100]}")
            return False

    except Exception as e:
        print(f"   ❌ Error eliminando: {e}")
        return False


def republish_with_correct_category(asin: str, ml_token: str) -> bool:
    """Re-publica un ASIN con la categoría corregida."""

    mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")

    if not mini_path.exists():
        print(f"   ❌ Mini ML no existe")
        return False

    with open(mini_path) as f:
        mini_ml = json.load(f)

    print(f"   📦 Categoría: {mini_ml.get('category_id')} - {mini_ml.get('category_name')}")

    try:
        result = publish_item(mini_ml)

        if result and result.get('item_id'):
            item_id = result['item_id']
            site_items = result.get('site_items', [])

            # Contar éxitos
            success_countries = []
            failed_countries = []

            for site in site_items:
                site_id = site.get('site_id')
                if site.get('item_id'):
                    success_countries.append(site_id)
                elif site.get('error'):
                    failed_countries.append(site_id)

            print(f"   ✅ Publicado: {item_id}")
            print(f"   📍 Países OK: {len(success_countries)}/{len(site_items)}")

            if success_countries:
                print(f"      ✅ {', '.join(success_countries)}")
            if failed_countries:
                print(f"      ❌ {', '.join(failed_countries)}")

            return True
        else:
            print(f"   ❌ Publicación falló")
            return False

    except Exception as e:
        print(f"   ❌ Error publicando: {str(e)[:100]}")
        return False


def main():
    """Proceso principal: eliminar y re-publicar"""

    ml_token = os.getenv('ML_TOKEN')
    if not ml_token:
        print("❌ ML_TOKEN no encontrado")
        return

    print("=" * 70)
    print("🔄 ELIMINAR Y RE-PUBLICAR CON CATEGORÍAS CORREGIDAS")
    print("=" * 70)

    results = {
        'deleted': [],
        'republished': [],
        'failed': []
    }

    for i, asin in enumerate(ASINS_TO_REPUBLISH, 1):
        print(f"\n{i}/{len(ASINS_TO_REPUBLISH)}. {asin}")
        print("-" * 70)

        # Paso 1: Eliminar listing actual
        item_id = ITEM_IDS_TO_DELETE.get(asin)
        if item_id:
            deleted = delete_listing(item_id, ml_token)
            if deleted:
                results['deleted'].append(asin)

            # Esperar 2s después de eliminar
            time.sleep(2)
        else:
            print(f"   ⚠️  No se encontró item_id para eliminar")

        # Paso 2: Re-publicar con categoría correcta
        print(f"   🚀 Re-publicando con categoría corregida...")
        republished = republish_with_correct_category(asin, ml_token)

        if republished:
            results['republished'].append(asin)
        else:
            results['failed'].append(asin)

        # Delay entre publicaciones
        if i < len(ASINS_TO_REPUBLISH):
            print(f"\n   ⏱️  Esperando 5s...")
            time.sleep(5)

    # Reporte final
    print("\n" + "=" * 70)
    print("📊 REPORTE FINAL")
    print("=" * 70)
    print(f"🗑️  Eliminados: {len(results['deleted'])}/{len(ASINS_TO_REPUBLISH)}")
    print(f"✅ Re-publicados: {len(results['republished'])}/{len(ASINS_TO_REPUBLISH)}")
    print(f"❌ Fallidos: {len(results['failed'])}/{len(ASINS_TO_REPUBLISH)}")

    if results['republished']:
        print(f"\n✅ Re-publicados exitosamente:")
        for asin in results['republished']:
            print(f"   • {asin}")

    if results['failed']:
        print(f"\n❌ Fallaron:")
        for asin in results['failed']:
            print(f"   • {asin}")

    # Guardar reporte
    report_path = Path("storage/republish_report.json")
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n💾 Reporte guardado: {report_path}")


if __name__ == "__main__":
    main()
