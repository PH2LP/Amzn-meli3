#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_pricing_to_server.py
═══════════════════════════════════════════════════════════════════════════════
SINCRONIZAR VALORES DE PRICING LOCAL → SERVIDOR VPS
═══════════════════════════════════════════════════════════════════════════════

Este script exporta SOLO los valores de pricing del .env local al servidor VPS.

VALORES QUE SINCRONIZA:
- PRICE_MARKUP: Porcentaje de markup (ej: 150 para 150%)
- USE_TAX: true/false para aplicar tax 7%
- FULFILLMENT_FEE: Fee 3PL en USD (default: 4.0)

USO:
    python3 sync_pricing_to_server.py

REQUISITOS:
- Tener SSH configurado con el servidor
- Las credenciales SSH deben estar en .env:
  VPS_HOST=tu-servidor.com
  VPS_USER=root
  VPS_PATH=/root/revancha
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Colores
class Colors:
    BLUE = '\033[0;34m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'

def log(msg, color=Colors.NC):
    print(f"{color}{msg}{Colors.NC}")

def read_local_pricing_values():
    """Lee los valores de pricing del .env local"""
    load_dotenv(override=True)

    values = {
        'PRICE_MARKUP': os.getenv('PRICE_MARKUP', '150'),
        'USE_TAX': os.getenv('USE_TAX', 'true'),
        'FULFILLMENT_FEE': os.getenv('FULFILLMENT_FEE', '4.0')
    }

    return values

def get_server_config():
    """Lee configuración del servidor desde .env"""
    load_dotenv(override=True)

    host = os.getenv('VPS_HOST')
    user = os.getenv('VPS_USER', 'root')
    path = os.getenv('VPS_PATH', '/root/revancha')

    if not host:
        log("❌ Error: VPS_HOST no está configurado en .env", Colors.RED)
        log("   Agregá: VPS_HOST=tu-servidor.com", Colors.YELLOW)
        return None

    return {
        'host': host,
        'user': user,
        'path': path,
        'ssh': f"{user}@{host}"
    }

def update_server_env(server_config, pricing_values):
    """Actualiza los valores de pricing en el .env del servidor"""

    ssh_target = server_config['ssh']
    env_path = f"{server_config['path']}/.env"

    log(f"\n🔄 Actualizando valores en {ssh_target}:{env_path}", Colors.BLUE)

    success_count = 0

    for key, value in pricing_values.items():
        # Comando SSH que actualiza o agrega la variable en .env
        # Usa sed para reemplazar si existe, sino la agrega al final
        cmd = f'''ssh {ssh_target} "
            if grep -q '^{key}=' {env_path} 2>/dev/null; then
                sed -i 's|^{key}=.*|{key}={value}|' {env_path}
                echo 'UPDATED'
            else
                echo '{key}={value}' >> {env_path}
                echo 'ADDED'
            fi
        "'''

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                action = result.stdout.strip()
                if action == 'UPDATED':
                    log(f"   ✅ {key} = {value} (actualizado)", Colors.GREEN)
                elif action == 'ADDED':
                    log(f"   ✅ {key} = {value} (agregado)", Colors.GREEN)
                else:
                    log(f"   ✅ {key} = {value}", Colors.GREEN)
                success_count += 1
            else:
                log(f"   ❌ Error actualizando {key}: {result.stderr}", Colors.RED)

        except subprocess.TimeoutExpired:
            log(f"   ❌ Timeout actualizando {key}", Colors.RED)
        except Exception as e:
            log(f"   ❌ Error actualizando {key}: {e}", Colors.RED)

    return success_count == len(pricing_values)

def verify_server_values(server_config, pricing_values):
    """Verifica que los valores se actualizaron correctamente en el servidor"""

    ssh_target = server_config['ssh']
    env_path = f"{server_config['path']}/.env"

    log(f"\n🔍 Verificando valores en el servidor...", Colors.BLUE)

    all_ok = True

    for key, expected_value in pricing_values.items():
        cmd = f"ssh {ssh_target} \"grep '^{key}=' {env_path} 2>/dev/null || echo 'NOT_FOUND'\""

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                if output == 'NOT_FOUND':
                    log(f"   ❌ {key} no encontrado en servidor", Colors.RED)
                    all_ok = False
                else:
                    # Extraer el valor
                    server_value = output.split('=', 1)[1].strip()
                    # Limpiar comentarios
                    server_value = server_value.split('#')[0].strip()

                    if server_value == expected_value:
                        log(f"   ✅ {key} = {server_value} (correcto)", Colors.GREEN)
                    else:
                        log(f"   ⚠️  {key} = {server_value} (esperado: {expected_value})", Colors.YELLOW)
                        all_ok = False
            else:
                log(f"   ❌ Error verificando {key}", Colors.RED)
                all_ok = False

        except Exception as e:
            log(f"   ❌ Error verificando {key}: {e}", Colors.RED)
            all_ok = False

    return all_ok

def main():
    """Función principal"""

    log("\n" + "=" * 70, Colors.BLUE)
    log("  SINCRONIZAR VALORES DE PRICING: LOCAL → SERVIDOR", Colors.BLUE)
    log("=" * 70 + "\n", Colors.BLUE)

    # 1. Leer valores locales
    log("📊 Leyendo valores de pricing del .env local...", Colors.BLUE)
    pricing_values = read_local_pricing_values()

    log("\n   Valores a sincronizar:", Colors.NC)
    for key, value in pricing_values.items():
        log(f"   • {key} = {value}", Colors.YELLOW)

    # 2. Leer configuración del servidor
    log("\n🔧 Leyendo configuración del servidor...", Colors.BLUE)
    server_config = get_server_config()

    if not server_config:
        sys.exit(1)

    log(f"   Servidor: {server_config['ssh']}", Colors.NC)
    log(f"   Path: {server_config['path']}", Colors.NC)

    # 3. Confirmar
    log("\n⚠️  Esto actualizará los valores de pricing en el servidor.", Colors.YELLOW)
    confirm = input("   ¿Continuar? (s/N): ")

    if confirm.lower() != 's':
        log("\n❌ Sincronización cancelada", Colors.YELLOW)
        return

    # 4. Actualizar valores en el servidor
    success = update_server_env(server_config, pricing_values)

    if not success:
        log("\n❌ Hubo errores al actualizar algunos valores", Colors.RED)
        sys.exit(1)

    # 5. Verificar
    verified = verify_server_values(server_config, pricing_values)

    # 6. Resumen final
    log("\n" + "=" * 70, Colors.BLUE)
    if verified:
        log("✅ SINCRONIZACIÓN COMPLETADA EXITOSAMENTE", Colors.GREEN)
        log("=" * 70 + "\n", Colors.BLUE)
        log("Los valores de pricing se actualizaron en el servidor.", Colors.GREEN)
        log("La próxima vez que corra sync en el servidor, usará estos valores.", Colors.GREEN)
    else:
        log("⚠️  SINCRONIZACIÓN COMPLETADA CON ADVERTENCIAS", Colors.YELLOW)
        log("=" * 70 + "\n", Colors.BLUE)
        log("Algunos valores podrían no haberse actualizado correctamente.", Colors.YELLOW)
        log("Verificá manualmente con: ssh user@server 'cat /root/revancha/.env'", Colors.YELLOW)

    log("\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n\n❌ Sincronización cancelada por usuario (Ctrl+C)", Colors.YELLOW)
        sys.exit(0)
    except Exception as e:
        log(f"\n❌ Error: {e}", Colors.RED)
        import traceback
        traceback.print_exc()
        sys.exit(1)
