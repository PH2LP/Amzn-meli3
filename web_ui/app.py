#!/usr/bin/env python3
"""
Web UI Minimalista para Sistema AMZ → ML
Dashboard de servicios + Visor de logs
"""

from flask import Flask, render_template, jsonify
import subprocess
import os
import platform
from pathlib import Path

app = Flask(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_system_stats():
    """Obtiene estadísticas del sistema (RAM, CPU, Disco)"""
    stats = {}

    try:
        # RAM
        result = subprocess.run(
            ['free', '-m'],
            capture_output=True,
            text=True,
            timeout=5
        )
        lines = result.stdout.split('\n')
        mem_line = [l for l in lines if l.startswith('Mem:')][0]
        parts = mem_line.split()
        total_ram = int(parts[1])
        used_ram = int(parts[2])
        stats['ram_used_mb'] = used_ram
        stats['ram_total_mb'] = total_ram
        stats['ram_percent'] = round((used_ram / total_ram) * 100, 1)
    except Exception as e:
        print(f"Error getting RAM stats: {e}")
        stats['ram_used_mb'] = 0
        stats['ram_total_mb'] = 0
        stats['ram_percent'] = 0

    try:
        # CPU - usando top
        result = subprocess.run(
            ['top', '-bn1'],
            capture_output=True,
            text=True,
            timeout=5
        )
        # Buscar línea con %Cpu
        for line in result.stdout.split('\n'):
            if '%Cpu' in line or 'Cpu(s)' in line:
                # Extraer el valor de idle y calcular usado
                parts = line.split(',')
                for part in parts:
                    if 'id' in part:  # idle
                        idle = float(part.replace('id', '').strip().split()[0])
                        stats['cpu_percent'] = round(100 - idle, 1)
                        break
                break
    except Exception as e:
        print(f"Error getting CPU stats: {e}")
        stats['cpu_percent'] = 0

    try:
        # Disco
        result = subprocess.run(
            ['df', '-h', '/'],
            capture_output=True,
            text=True,
            timeout=5
        )
        lines = result.stdout.split('\n')
        if len(lines) > 1:
            parts = lines[1].split()
            stats['disk_total'] = parts[1]
            stats['disk_used'] = parts[2]
            stats['disk_percent'] = int(parts[4].replace('%', ''))
    except Exception as e:
        print(f"Error getting disk stats: {e}")
        stats['disk_total'] = '0G'
        stats['disk_used'] = '0G'
        stats['disk_percent'] = 0

    return stats

def check_process_running(process_name):
    """Verifica si un proceso está corriendo usando ps"""
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Buscar el proceso en la salida (ignorar grep y web_ui si estamos buscando otro proceso)
        for line in result.stdout.split('\n'):
            # Ignorar líneas con grep
            if 'grep' in line:
                continue

            # Buscar el nombre del proceso en la línea completa
            # Funciona con rutas absolutas: /opt/amz-ml-system/scripts/tools/auto_answer_questions.py
            if process_name in line and 'python' in line:
                return True

        return False
    except Exception as e:
        print(f"Error checking process {process_name}: {e}")
        return False

def get_process_info(process_name):
    """
    Obtiene información detallada de un proceso (PID, uptime, CPU, RAM)
    Retorna dict con info o None si no está corriendo
    """
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Buscar el proceso en la salida (ignorar grep)
        # Si encontramos múltiples instancias (ej: parent + worker), usar la primera
        for line in result.stdout.split('\n'):
            # Ignorar líneas con grep
            if 'grep' in line:
                continue

            # Buscar el nombre del proceso en la línea completa
            # Funciona con rutas absolutas: /opt/amz-ml-system/venv/bin/python3 /opt/.../script.py
            if process_name in line and 'python' in line:
                parts = line.split()
                if len(parts) >= 11:
                    return {
                        'pid': parts[1],
                        'cpu': parts[2],
                        'mem': parts[3],
                        'running': True
                    }

        return None
    except Exception as e:
        print(f"Error getting process info {process_name}: {e}")
        return None

def get_log_last_activity(log_file):
    """
    Obtiene la última actividad del log (última línea con timestamp)
    Retorna string con resumen de última actividad o None
    """
    try:
        log_path = PROJECT_ROOT / 'logs' / log_file
        if not log_path.exists():
            return "Log no existe"

        # Leer últimas 5 líneas
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            if not lines:
                return "Log vacío"

            # Obtener última línea no vacía
            for line in reversed(lines[-5:]):
                if line.strip():
                    # Truncar a 100 caracteres
                    return line.strip()[:100]

        return "Sin actividad"
    except Exception as e:
        return f"Error: {str(e)}"

# ============================================================
# ROUTES - PÁGINAS
# ============================================================

@app.route('/')
def index():
    """Dashboard de servicios"""
    return render_template('index.html')

@app.route('/logs')
def logs():
    """Visor de logs"""
    return render_template('logs.html')

# ============================================================
# API ENDPOINTS
# ============================================================

@app.route('/api/services/status')
def services_status():
    """
    Obtiene el estado REAL de todos los servicios en tiempo real
    Con PID, CPU, RAM y última actividad del log
    """
    services = [
        {
            'id': 'auto_answer',
            'name': 'Auto Answer Questions',
            'description': 'Responde preguntas de clientes automáticamente',
            'process': 'auto_answer_questions.py',
            'log': 'auto_answer.log',
            'expected_running': True
        },
        {
            'id': 'telegram_sales',
            'name': 'Telegram Sales Bot',
            'description': 'Notifica ventas (ejecutado por CRON cada 5 min)',
            'process': 'telegram_sales_notifier.py',
            'log': 'telegram_sales.log',
            'expected_running': False,
            'note': 'Se ejecuta por CRON cada 5 minutos'
        },
        {
            'id': 'sync_amazon_ml',
            'name': 'Sync Amazon → ML',
            'description': 'Actualiza precios/stock (ejecutado por CRON cada hora)',
            'process': 'sync_amazon_ml.py',
            'log': 'sync/sync_cron.log',
            'expected_running': False,
            'note': 'Se ejecuta por CRON cada hora'
        },
        {
            'id': 'pipeline',
            'name': 'Pipeline Autónomo',
            'description': 'Búsqueda + Publicación automática (corre en VPS)',
            'process': 'pipeline.py',
            'log': 'pipeline.log',
            'expected_running': False,
            'note': 'Se ejecuta manualmente según demanda'
        },
        {
            'id': 'web_ui',
            'name': 'Web UI',
            'description': 'Panel de control web',
            'process': 'web_ui/app.py',
            'log': 'web_ui.log',
            'expected_running': True
        }
    ]

    status_list = []

    for service in services:
        # Obtener info detallada del proceso
        process_info = get_process_info(service['process'])

        if process_info:
            # Proceso CORRIENDO - obtener info real
            running = True
            pid = process_info['pid']
            cpu = process_info['cpu'] + '%'
            mem = process_info['mem'] + '%'
            status_type = 'success'
        else:
            # Proceso NO corriendo
            running = False
            pid = None
            cpu = '0%'
            mem = '0%'

            # Determinar si es normal que no esté corriendo
            if service.get('expected_running', True):
                status_type = 'error'
            else:
                status_type = 'info'

        # Obtener última actividad del log
        last_activity = get_log_last_activity(service['log'])

        status_list.append({
            'id': service['id'],
            'name': service['name'],
            'description': service['description'],
            'running': running,
            'pid': pid,
            'cpu': cpu,
            'mem': mem,
            'log': service['log'],
            'last_activity': last_activity,
            'status_type': status_type,
            'note': service.get('note', ''),
            'is_cron': not service.get('expected_running', True)  # CRON si no se espera que esté corriendo 24/7
        })

    return jsonify(status_list)


@app.route('/api/system/stats')
def system_stats():
    """
    Obtiene estadísticas del sistema (RAM, CPU, Disco)
    """
    stats = get_system_stats()
    return jsonify(stats)


@app.route('/api/logs/<log_type>')
def get_logs(log_type):
    """
    Obtiene logs de un servicio específico
    """
    log_map = {
        'auto_answer': 'logs/auto_answer.log',
        'auto_sync': 'logs/auto_sync_ml_db.log',
        'sync_amazon_ml': 'logs/sync/sync_cron.log',
        'token_refresh': 'logs/ml_token_refresh.log',
        'telegram_sales': 'logs/telegram_sales.log',
        'web_ui': 'logs/web_ui.log',
        'autonomous': 'logs/Sistema_Autónomo_(Búsqueda).log',
        'publication': 'logs/Main2_(Publicación).log',
    }

    log_file = log_map.get(log_type)

    if not log_file:
        return jsonify({
            'success': False,
            'content': 'Tipo de log inválido'
        }), 400

    log_path = PROJECT_ROOT / log_file

    if not log_path.exists():
        return jsonify({
            'success': True,
            'content': f'📄 Log aún no creado: {log_file}'
        })

    try:
        # Leer últimas 300 líneas
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            last_lines = lines[-300:] if len(lines) > 300 else lines
            content = ''.join(last_lines)

        return jsonify({
            'success': True,
            'content': content
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'content': f'Error leyendo log: {str(e)}'
        }), 500


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print("🚀 Web UI Minimalista - Servicios VPS")
    print(f"📂 Project root: {PROJECT_ROOT}")
    print(f"🌐 Access: http://0.0.0.0:5001")
    print(f"🛑 Stop: Ctrl+C")

    app.run(host='0.0.0.0', port=5001, debug=True)
