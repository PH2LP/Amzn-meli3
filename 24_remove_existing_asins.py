#!/usr/bin/env python3
"""
Script para eliminar de asins.txt los ASINs que ya existen en la DB
"""
import sqlite3

# Rutas
ASINS_FILE = '/Users/felipemelucci/Desktop/revancha/asins.txt'
DB_PATH = '/Users/felipemelucci/Desktop/revancha/storage/listings_database.db'

def main():
    # Leer ASINs del archivo
    print("📖 Leyendo asins.txt...")
    with open(ASINS_FILE, 'r') as f:
        asins_from_file = [line.strip() for line in f if line.strip()]
    
    print(f"   Total ASINs en archivo: {len(asins_from_file)}")
    
    # Conectar a la DB
    print("\n🔍 Verificando cuáles existen en la DB...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Obtener ASINs únicos que ya existen en la DB
    placeholders = ','.join(['?' for _ in asins_from_file])
    cursor.execute(f"SELECT DISTINCT asin FROM listings WHERE asin IN ({placeholders})", asins_from_file)
    asins_in_db = set(row[0] for row in cursor.fetchall())
    
    conn.close()
    
    print(f"   ASINs que ya existen en DB: {len(asins_in_db)}")
    
    # Filtrar ASINs que NO están en la DB
    asins_to_keep = [asin for asin in asins_from_file if asin not in asins_in_db]
    
    print(f"   ASINs que se mantendrán: {len(asins_to_keep)}")
    print(f"   ASINs eliminados del archivo: {len(asins_from_file) - len(asins_to_keep)}")
    
    # Hacer backup del archivo original
    backup_file = ASINS_FILE + '.backup'
    with open(backup_file, 'w') as f:
        f.write('\n'.join(asins_from_file))
    print(f"\n💾 Backup creado: {backup_file}")
    
    # Escribir el nuevo archivo con solo los ASINs que NO están en la DB
    with open(ASINS_FILE, 'w') as f:
        f.write('\n'.join(asins_to_keep))
        if asins_to_keep:  # Agregar salto de línea final si hay contenido
            f.write('\n')
    
    print(f"\n✅ Archivo asins.txt actualizado")
    print(f"   Antes: {len(asins_from_file)} ASINs")
    print(f"   Ahora: {len(asins_to_keep)} ASINs")
    
    # Mostrar algunos ASINs que fueron removidos
    if asins_in_db:
        print(f"\n📋 Ejemplos de ASINs removidos (ya estaban en DB):")
        for asin in list(asins_in_db)[:10]:
            print(f"   - {asin}")
        if len(asins_in_db) > 10:
            print(f"   ... y {len(asins_in_db) - 10} más")

if __name__ == '__main__':
    main()
