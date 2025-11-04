#!/usr/bin/env python3
"""
retry_failed.py - Script para reintentar los 4 ASINs fallidos con auto-fixer
"""
import sys
import os

# Cambiar temporalmente el archivo de ASINs
original_file = "resources/asins.txt"
retry_file = "resources/asins_retry.txt"

# Hacer backup y usar retry
os.rename(original_file, f"{original_file}.bak")
os.rename(retry_file, original_file)

try:
    # Ejecutar main2
    exec(open("main2.py").read())
finally:
    # Restaurar archivo original
    os.rename(original_file, retry_file)
    os.rename(f"{original_file}.bak", original_file)
