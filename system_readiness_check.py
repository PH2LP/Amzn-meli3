#!/usr/bin/env python3
"""
Verificación completa del sistema antes de producción
Chequea que TODO esté listo para empezar a subir productos
"""

import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

def check_env_variables():
    """Verifica variables de entorno críticas"""
    print("📋 Variables de entorno:")

    required = {
        "ML_ACCESS_TOKEN": "Token de MercadoLibre",
        "LWA_CLIENT_ID": "Amazon SP-API Client ID",
        "LWA_CLIENT_SECRET": "Amazon SP-API Secret",
        "REFRESH_TOKEN": "Amazon Refresh Token",
        "OPENAI_API_KEY": "OpenAI API Key",
        "ANTHROPIC_API_KEY": "Anthropic API Key"
    }

    all_ok = True
    for var, desc in required.items():
        value = os.getenv(var)
        if value and len(value) > 10:
            masked = f"{value[:8]}...{value[-4:]}"
            print(f"   ✅ {var}: {masked}")
        else:
            print(f"   ❌ {var}: NO CONFIGURADO")
            all_ok = False

    # Variables de configuración
    print(f"\n📋 Configuración de precios:")
    print(f"   PRICE_MARKUP: {os.getenv('PRICE_MARKUP', 'NO DEFINIDO')}%")
    print(f"   THREE_PL_FEE: ${os.getenv('THREE_PL_FEE', '4.0')}")
    print(f"   FLORIDA_TAX_PERCENT: {os.getenv('FLORIDA_TAX_PERCENT', '7')}%")
    print(f"   TAX_EXEMPT: {os.getenv('TAX_EXEMPT', 'false')}")

    return all_ok


def check_database():
    """Verifica estado de la base de datos"""
    print("\n📊 Base de datos:")

    db_path = "storage/listings_database.db"

    if not os.path.exists(db_path):
        print(f"   ❌ Base de datos NO existe")
        return False

    size = os.path.getsize(db_path) / 1024  # KB
    print(f"   ✅ Existe: {size:.1f} KB")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Verificar estructura
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"   ✅ Tablas: {', '.join(tables)}")

    # Contar productos
    cursor.execute("SELECT COUNT(*) FROM listings;")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM listings WHERE item_id IS NOT NULL;")
    publicados = cursor.fetchone()[0]

    print(f"   📦 Total productos: {total}")
    print(f"   ✅ Publicados en ML: {publicados}")

    if publicados > 0:
        cursor.execute("SELECT asin, item_id, price_usd FROM listings WHERE item_id IS NOT NULL LIMIT 3;")
        print(f"\n   Últimos publicados:")
        for row in cursor.fetchall():
            print(f"      • {row[0]} → {row[1]} (${row[2]} USD)")

    conn.close()

    if total <= 1:
        print(f"\n   ⚠️ Base de datos casi vacía (solo producto de prueba)")
        print(f"   💡 Está lista para recibir productos nuevos")

    return True


def check_directories():
    """Verifica directorios necesarios"""
    print("\n📁 Directorios:")

    dirs = [
        "storage/asins_json",
        "storage/logs/publish_ready",
        "logs/sync",
        "data/schemas",
        "cache"
    ]

    all_ok = True
    for d in dirs:
        path = Path(d)
        if path.exists():
            count = len(list(path.glob("*")))
            print(f"   ✅ {d}: {count} archivos")
        else:
            print(f"   ❌ {d}: NO EXISTE")
            all_ok = False

    return all_ok


def check_scripts():
    """Verifica scripts principales"""
    print("\n🔧 Scripts principales:")

    scripts = {
        "main2.py": "Pipeline de publicación",
        "scripts/tools/sync_amazon_ml.py": "Sincronización Amazon→ML"
    }

    all_ok = True
    for script, desc in scripts.items():
        if Path(script).exists():
            print(f"   ✅ {script}: {desc}")
        else:
            print(f"   ❌ {script}: NO EXISTE")
            all_ok = False

    return all_ok


def check_asins_file():
    """Verifica archivo de ASINs"""
    print("\n📄 Archivo de ASINs:")

    asins_paths = ["asins.txt", "data/asins.txt"]

    for path in asins_paths:
        if Path(path).exists():
            with open(path) as f:
                asins = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            print(f"   ✅ {path}: {len(asins)} ASINs")
            if asins:
                print(f"      Primeros: {', '.join(asins[:3])}")
            return True

    print(f"   ⚠️ No se encontró archivo de ASINs")
    print(f"   💡 Crea asins.txt con los ASINs a publicar")
    return False


def check_sync_system():
    """Verifica sistema de sincronización"""
    print("\n🔄 Sistema de sincronización:")

    try:
        from scripts.tools.sync_amazon_ml import calculate_new_ml_price
        test_price = calculate_new_ml_price(35.99)
        if abs(test_price - 55.26) < 0.01:
            print(f"   ✅ Cálculo de precios: OK ($35.99 → ${test_price})")
        else:
            print(f"   ❌ Cálculo de precios: ERROR")
            return False
    except Exception as e:
        print(f"   ❌ Error importando sync: {e}")
        return False

    return True


def main():
    print("=" * 80)
    print("🔍 VERIFICACIÓN DE SISTEMA - PRE-PRODUCCIÓN")
    print("=" * 80)
    print()

    checks = {
        "Variables de entorno": check_env_variables(),
        "Base de datos": check_database(),
        "Directorios": check_directories(),
        "Scripts": check_scripts(),
        "Archivo ASINs": check_asins_file(),
        "Sistema Sync": check_sync_system()
    }

    print("\n" + "=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)

    for name, status in checks.items():
        icon = "✅" if status else "❌"
        print(f"   {icon} {name}")

    all_ready = all(checks.values())

    print("\n" + "=" * 80)

    if all_ready:
        print("✅ SISTEMA LISTO PARA PRODUCCIÓN")
        print("=" * 80)
        print("""
TODO ESTÁ CONFIGURADO CORRECTAMENTE:

✅ Credenciales de Amazon y ML configuradas
✅ Base de datos creada y funcionando
✅ Sistema de precios configurado (Amazon + 7% + $4) × 1.30
✅ Sistema de sync probado y funcional
✅ Directorios creados

PRÓXIMOS PASOS:
1. Agrega ASINs a asins.txt (uno por línea)
2. Ejecuta: python3 main2.py
3. Los productos se publicarán automáticamente
4. El sync mantendrá precios actualizados cada 3 días

FÓRMULA DE PRECIOS:
(Amazon + Tax 7% + $4 USD) × (1 + Markup 30%)

Ejemplo: Amazon $35.99 → ML $55.26
        """)
    else:
        print("⚠️ SISTEMA NO ESTÁ COMPLETAMENTE LISTO")
        print("=" * 80)
        print("""
Hay algunas configuraciones pendientes.
Revisa los ❌ arriba y corrígelos antes de continuar.
        """)

    print("=" * 80)

    return all_ready


if __name__ == "__main__":
    ready = main()
    sys.exit(0 if ready else 1)
