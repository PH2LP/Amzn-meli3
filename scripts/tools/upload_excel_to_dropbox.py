#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upload Excel to Dropbox
=======================
Sube el Excel de ventas a Dropbox para acceso desde cualquier dispositivo.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(override=True)

def upload_to_dropbox(local_file_path, dropbox_path="/VENTAS_MERCADOLIBRE.xlsx"):
    """
    Sube un archivo a Dropbox.

    Args:
        local_file_path: Ruta local del archivo
        dropbox_path: Ruta en Dropbox (debe empezar con /)

    Returns:
        bool: True si se subió correctamente
    """
    try:
        import dropbox
    except ImportError:
        print("❌ Error: dropbox no está instalado. Ejecuta: pip3 install dropbox")
        return False

    # Obtener token
    access_token = os.getenv("DROPBOX_ACCESS_TOKEN")
    if not access_token:
        print("❌ Error: DROPBOX_ACCESS_TOKEN no configurado en .env")
        return False

    try:
        # Conectar a Dropbox
        dbx = dropbox.Dropbox(access_token)

        # Verificar que el archivo existe
        if not os.path.exists(local_file_path):
            print(f"❌ Error: Archivo no encontrado: {local_file_path}")
            return False

        # Leer archivo
        with open(local_file_path, 'rb') as f:
            file_data = f.read()

        # Subir a Dropbox (sobrescribir si existe)
        print(f"📤 Subiendo a Dropbox: {dropbox_path}")
        dbx.files_upload(
            file_data,
            dropbox_path,
            mode=dropbox.files.WriteMode.overwrite
        )

        print(f"✅ Excel subido exitosamente a Dropbox")
        print(f"   Ruta: {dropbox_path}")
        print(f"   Tamaño: {len(file_data) / 1024:.1f} KB")

        return True

    except Exception as e:
        print(f"❌ Error subiendo a Dropbox: {e}")
        return False


if __name__ == "__main__":
    # Obtener ruta del archivo
    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
    else:
        # Usar el archivo del día
        excel_path = f"/Users/felipemelucci/Desktop/{datetime.now().strftime('%Y%m%d')}_VENTAS_MERCADOLIBRE.xlsx"

    # Subir a Dropbox
    upload_to_dropbox(excel_path)
