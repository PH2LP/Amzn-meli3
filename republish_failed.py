#!/usr/bin/env python3
"""
Republica el ASIN fallido usando el sistema de retry inteligente.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.publish_with_retry import publish_with_smart_retry
import json
from dotenv import load_dotenv

load_dotenv()

def main():
    """Republica B0DRW69H11 con retry inteligente"""

    ml_token = os.getenv('ML_TOKEN')
    if not ml_token:
        print("❌ ML_TOKEN no encontrado")
        return

    asin = 'B0DRW69H11'

    print("=" * 70)
    print(f"🔄 REPUBLICANDO {asin} CON SISTEMA DE RETRY")
    print("=" * 70)

    # Cargar mini_ml
    mini_path = Path(f"storage/logs/publish_ready/{asin}_mini_ml.json")

    if not mini_path.exists():
        print(f"❌ Mini ML no existe")
        return

    with open(mini_path) as f:
        mini_ml = json.load(f)

    print(f"\n📋 Datos actuales:")
    print(f"   Categoría: {mini_ml.get('category_id')}")
    print(f"   GTINs: {mini_ml.get('gtins', [])}")
    print(f"   Atributos: {len(mini_ml.get('attributes_mapped', {}))}")

    # Publicar con retry inteligente
    result = publish_with_smart_retry(mini_ml, ml_token, max_retries=3)

    if result:
        print(f"\n✅ {asin}: PUBLICADO EXITOSAMENTE!")
        print(f"   Item ID: {result}")

        # Actualizar reporte
        report_path = Path("storage/publish_report.json")
        if report_path.exists():
            with open(report_path) as f:
                report = json.load(f)

            # Mover de failed a published
            if asin in report.get('failed', []):
                report['failed'].remove(asin)
                report['published'].append(asin)

            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)

            print(f"\n📊 REPORTE ACTUALIZADO:")
            print(f"   ✅ Publicados: {len(report['published'])}/14")
            print(f"   ❌ Fallidos: {len(report['failed'])}/14")
    else:
        print(f"\n❌ {asin}: Falló después de todos los reintentos")

if __name__ == "__main__":
    main()
