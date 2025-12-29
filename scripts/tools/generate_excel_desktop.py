#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_excel_desktop.py
Genera Excel profesional con ventas en el Desktop
"""

import sqlite3
import pandas as pd
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Configuración
DB_PATH = "storage/sales_tracking.db"
EXCEL_PATH = f"{datetime.now().strftime('%Y%m%d')}_VENTAS_MERCADOLIBRE.xlsx"

# Detectar si estamos en servidor o local
import os
if os.path.exists("/opt/amz-ml-system"):
    # Estamos en el servidor
    DESKTOP_PATH = f"/opt/amz-ml-system/storage/{EXCEL_PATH}"
else:
    # Estamos en local (Mac)
    DESKTOP_PATH = f"/Users/felipemelucci/Desktop/{EXCEL_PATH}"

def create_professional_excel():
    """Crea Excel profesional en el Desktop"""

    # Conectar a DB
    conn = sqlite3.connect(DB_PATH)

    # Leer datos con TODAS las columnas (orden optimizado)
    df = pd.read_sql_query("""
        SELECT
            sale_date as 'Fecha',
            marketplace as 'MKT',
            product_title as 'Producto',
            quantity as 'Cant',
            sale_price_usd as 'Precio Venta',
            ml_fee as 'Fee ML',
            shipping_cost as 'Envío',
            net_proceeds as 'Neto ML',
            amazon_cost as 'Costo AMZ',
            fulfillment_fee as '3PL',
            total_cost as 'Total Costo',
            profit as 'GANANCIA',
            profit_margin as 'Margen %',
            asin as 'ASIN',
            order_id as 'Orden ML',
            ml_item_id as 'CBT ID',
            buyer_nickname as 'Comprador',
            country as 'País',
            status as 'Estado'
        FROM sales
        ORDER BY sale_date DESC
    """, conn)

    conn.close()

    # Si no hay datos, crear archivo vacío con headers
    if len(df) == 0:
        print("⚠️  No hay ventas aún. Creando Excel vacío...")

        # Crear DataFrame vacío con columnas
        df = pd.DataFrame(columns=[
            'Fecha', 'MKT', 'Producto', 'Cant',
            'Precio Venta', 'Fee ML', 'Envío', 'Neto ML',
            'Costo AMZ', '3PL', 'Total Costo',
            'GANANCIA', 'Margen %', 'ASIN', 'Orden ML', 'CBT ID',
            'Comprador', 'País', 'Estado'
        ])

    # Formatear fecha (maneja múltiples formatos: ISO y simples)
    if 'Fecha' in df.columns and len(df) > 0:
        df['Fecha'] = pd.to_datetime(df['Fecha'], format='mixed', errors='coerce')
        df['Fecha'] = df['Fecha'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M') if pd.notna(x) else '')

    # Exportar a Excel
    df.to_excel(DESKTOP_PATH, index=False, sheet_name='Ventas')

    # Aplicar formato profesional
    wb = load_workbook(DESKTOP_PATH)
    ws = wb['Ventas']

    # Colores
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    ganancia_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    costo_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    # Fonts
    header_font = Font(name='Arial', size=11, bold=True, color="FFFFFF")
    normal_font = Font(name='Arial', size=10)

    # Border
    thin_border = Border(
        left=Side(style='thin', color='D3D3D3'),
        right=Side(style='thin', color='D3D3D3'),
        top=Side(style='thin', color='D3D3D3'),
        bottom=Side(style='thin', color='D3D3D3')
    )

    # Formatear headers
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = thin_border

    # Ajustar anchos de columna (más espaciosos para evitar texto apretado)
    column_widths = {
        'A': 18,  # Fecha
        'B': 8,   # MKT
        'C': 50,  # Producto (más ancho)
        'D': 6,   # Cant
        'E': 13,  # Precio Venta
        'F': 11,  # Fee ML
        'G': 10,  # Envío
        'H': 12,  # Neto ML
        'I': 12,  # Costo AMZ
        'J': 8,   # 3PL
        'K': 13,  # Total Costo
        'L': 13,  # GANANCIA
        'M': 11,  # Margen %
        'N': 14,  # ASIN
        'O': 18,  # Orden ML
        'P': 16,  # CBT ID
        'Q': 22,  # Comprador
        'R': 12,  # País
        'S': 10,  # Estado
    }

    for col, width in column_widths.items():
        ws.column_dimensions[col].width = width

    # Formatear celdas de datos con todas las líneas gruesas
    thick_border = Border(
        left=Side(style='medium', color='000000'),
        right=Side(style='medium', color='000000'),
        top=Side(style='medium', color='000000'),
        bottom=Side(style='medium', color='000000')
    )

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            # Todas las letras en negrita
            cell.font = Font(name='Arial', size=10, bold=True)

            # Todas las líneas gruesas
            cell.border = thick_border

            cell.alignment = Alignment(vertical='center')

            # Formatear números como moneda (columnas financieras)
            col_letter = get_column_letter(cell.column)
            # E=Precio Venta, F=Fee ML, G=Envío, H=Neto ML,
            # I=Costo AMZ, J=3PL, K=Total Costo, L=GANANCIA
            if col_letter in ['E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']:
                cell.number_format = '$#,##0.00'

            # Formatear porcentaje (M=Margen %)
            elif col_letter == 'M':
                cell.number_format = '0.00"%"'

            # Resaltar ganancia (L=GANANCIA)
            if col_letter == 'L':
                cell.fill = ganancia_fill
                cell.font = Font(name='Arial', size=10, bold=True, color="006100")

            # Resaltar costos (I=Costo AMZ, J=3PL, K=Total Costo)
            elif col_letter in ['I', 'J', 'K']:
                cell.fill = costo_fill

    # Fijar primera fila
    ws.freeze_panes = 'A2'

    # Agregar filtros
    ws.auto_filter.ref = ws.dimensions

    # Agregar hoja de resumen PRO con gráficos
    ws_summary = wb.create_sheet("Dashboard", 0)

    if len(df) > 0:
        from openpyxl.chart import BarChart, PieChart, Reference, LineChart
        from openpyxl.chart.label import DataLabelList

        # Calcular métricas clave
        total_ventas = len(df)
        total_revenue = df['Precio Venta'].sum()
        total_ml_fees = df['Fee ML'].sum()
        total_net_ml = df['Neto ML'].sum()
        total_amazon_cost = df['Costo AMZ'].sum()
        total_3pl = df['3PL'].sum()
        total_costs = df['Total Costo'].sum()
        total_profit = df['GANANCIA'].sum()
        avg_margin = df['Margen %'].mean()
        avg_ticket = df['Precio Venta'].mean()
        roi = (total_profit / total_costs * 100) if total_costs > 0 else 0

        # Ventas por marketplace
        by_marketplace = df.groupby('MKT').agg({
            'GANANCIA': 'sum',
            'Producto': 'count'
        }).reset_index()

        # Top productos
        top_products = df.nlargest(5, 'GANANCIA')[['Producto', 'GANANCIA', 'Margen %']]

        # ═══ SECCIÓN 1: HEADER ═══
        ws_summary['A1'] = '📊 DASHBOARD DE VENTAS - AMAZON → MERCADOLIBRE'
        ws_summary['A1'].font = Font(name='Arial', size=18, bold=True, color="FFFFFF")
        ws_summary['A1'].fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        ws_summary.merge_cells('A1:F1')
        ws_summary['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws_summary.row_dimensions[1].height = 30

        # ═══ SECCIÓN 2: KPIs PRINCIPALES ═══
        ws_summary['A3'] = '💰 RESUMEN FINANCIERO'
        ws_summary['A3'].font = Font(name='Arial', size=14, bold=True, color="1F4E78")

        kpis = [
            ['Total Ventas:', total_ventas, 'unidades'],
            ['Revenue Total:', total_revenue, 'USD'],
            ['Ganancia Total:', total_profit, 'USD'],
            ['ROI:', roi, '%'],
            ['Ticket Promedio:', avg_ticket, 'USD'],
            ['Margen Promedio:', avg_margin, '%'],
        ]

        row = 4
        for label, value, unit in kpis:
            ws_summary[f'A{row}'] = label
            ws_summary[f'A{row}'].font = Font(name='Arial', size=11, bold=True)

            if unit == 'USD':
                ws_summary[f'B{row}'] = f'${value:,.2f}'
                ws_summary[f'B{row}'].font = Font(name='Arial', size=12, bold=True, color="006100")
            elif unit == '%':
                ws_summary[f'B{row}'] = f'{value:.2f}%'
                ws_summary[f'B{row}'].font = Font(name='Arial', size=12, bold=True, color="0066CC")
            else:
                ws_summary[f'B{row}'] = int(value)
                ws_summary[f'B{row}'].font = Font(name='Arial', size=12, bold=True)

            row += 1

        # ═══ SECCIÓN 3: DESGLOSE DE COSTOS ═══
        ws_summary['D3'] = '📉 DESGLOSE DE COSTOS'
        ws_summary['D3'].font = Font(name='Arial', size=14, bold=True, color="1F4E78")

        costs_breakdown = [
            ['Comisiones ML:', total_ml_fees],
            ['Costos Amazon:', total_amazon_cost],
            ['3PL Fulfillment:', total_3pl],
            ['Total Costos:', total_costs],
        ]

        row = 4
        for label, value in costs_breakdown:
            ws_summary[f'D{row}'] = label
            ws_summary[f'D{row}'].font = Font(name='Arial', size=11, bold=True)
            ws_summary[f'E{row}'] = f'${value:,.2f}'
            ws_summary[f'E{row}'].font = Font(name='Arial', size=11)
            if 'Total' in label:
                ws_summary[f'E{row}'].font = Font(name='Arial', size=12, bold=True, color="CC0000")
            row += 1

        # ═══ SECCIÓN 4: TOP PRODUCTOS ═══
        ws_summary['A12'] = '🏆 TOP 5 PRODUCTOS MÁS RENTABLES'
        ws_summary['A12'].font = Font(name='Arial', size=14, bold=True, color="1F4E78")

        # Headers
        headers = ['Producto', 'Ganancia', 'Margen %']
        for col_idx, header in enumerate(headers, 1):
            cell = ws_summary.cell(row=13, column=col_idx, value=header)
            cell.font = Font(name='Arial', size=10, bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            cell.alignment = Alignment(horizontal='center')

        # Data
        row = 14
        for idx, prod_row in top_products.iterrows():
            ws_summary[f'A{row}'] = prod_row['Producto'][:40]
            ws_summary[f'B{row}'] = f"${prod_row['GANANCIA']:,.2f}"
            ws_summary[f'C{row}'] = f"{prod_row['Margen %']:.1f}%"
            row += 1

        # ═══ SECCIÓN 5: GRÁFICO DE GANANCIA POR PRODUCTO ═══
        # Preparar datos para gráfico
        ws_summary['G3'] = 'GANANCIA POR PRODUCTO'
        ws_summary['G3'].font = Font(name='Arial', size=12, bold=True, color="1F4E78")

        chart_row = 4
        for idx, prod_row in top_products.iterrows():
            ws_summary[f'G{chart_row}'] = prod_row['Producto'][:25]
            ws_summary[f'H{chart_row}'] = prod_row['GANANCIA']
            chart_row += 1

        # Crear gráfico de barras
        chart1 = BarChart()
        chart1.type = "col"
        chart1.style = 10
        chart1.title = "Top 5 Productos por Ganancia"
        chart1.y_axis.title = 'Ganancia (USD)'

        data = Reference(ws_summary, min_col=8, min_row=3, max_row=3 + len(top_products))
        cats = Reference(ws_summary, min_col=7, min_row=4, max_row=3 + len(top_products))
        chart1.add_data(data, titles_from_data=True)
        chart1.set_categories(cats)
        chart1.height = 10
        chart1.width = 15

        ws_summary.add_chart(chart1, "G13")

        # ═══ SECCIÓN 6: PIE CHART - DISTRIBUCIÓN DE INGRESOS ═══
        ws_summary['A22'] = 'DISTRIBUCIÓN DE REVENUE VS COSTOS'
        ws_summary['A22'].font = Font(name='Arial', size=12, bold=True, color="1F4E78")

        ws_summary['A23'] = 'Categoría'
        ws_summary['B23'] = 'Monto'
        ws_summary['A24'] = 'Ganancia Neta'
        ws_summary['B24'] = total_profit
        ws_summary['A25'] = 'Costos Totales'
        ws_summary['B25'] = total_costs

        pie = PieChart()
        labels = Reference(ws_summary, min_col=1, min_row=24, max_row=25)
        data = Reference(ws_summary, min_col=2, min_row=23, max_row=25)
        pie.add_data(data, titles_from_data=True)
        pie.set_categories(labels)
        pie.title = "Revenue vs Costos"
        pie.height = 10
        pie.width = 15

        ws_summary.add_chart(pie, "A27")

        # Ajustar anchos de columna
        ws_summary.column_dimensions['A'].width = 22
        ws_summary.column_dimensions['B'].width = 15
        ws_summary.column_dimensions['C'].width = 12
        ws_summary.column_dimensions['D'].width = 20
        ws_summary.column_dimensions['E'].width = 15
        ws_summary.column_dimensions['F'].width = 15
        ws_summary.column_dimensions['G'].width = 28
        ws_summary.column_dimensions['H'].width = 12

    else:
        ws_summary['A1'] = '📊 DASHBOARD DE VENTAS'
        ws_summary['A1'].font = Font(name='Arial', size=18, bold=True, color="1F4E78")
        ws_summary['A3'] = 'ℹ️ No hay ventas registradas aún'
        ws_summary['A3'].font = Font(name='Arial', size=12)

    # Guardar
    wb.save(DESKTOP_PATH)

    print(f"✅ Excel creado: {DESKTOP_PATH}")
    print(f"   Total ventas: {len(df)}")
    if len(df) > 0:
        print(f"   Ganancia total: ${df['GANANCIA'].sum():,.2f}")

    return DESKTOP_PATH


def upload_to_dropbox(excel_path):
    """Sube el Excel y DBs a Dropbox con auto-refresh de token"""
    try:
        import sys
        from pathlib import Path

        # Add project root to path
        script_dir = Path(__file__).parent
        sys.path.insert(0, str(script_dir))

        # Import dropbox auth utility (handles auto-refresh)
        from dropbox_auth import get_dropbox_client
        import dropbox

        # Get Dropbox client with auto-refresh
        dbx = get_dropbox_client()
        if not dbx:
            print("⚠️  No se pudo obtener cliente Dropbox - Excel no se subió")
            return False

        # Upload Excel
        with open(excel_path, 'rb') as f:
            file_data = f.read()

        dropbox_path = "/VENTAS_MERCADOLIBRE.xlsx"
        dbx.files_upload(
            file_data,
            dropbox_path,
            mode=dropbox.files.WriteMode.overwrite
        )
        file_size = len(file_data) / 1024  # KB
        print(f"✅ Excel subido a Dropbox: {dropbox_path} ({file_size:.1f} KB)")

        # Upload sales database
        if Path(DB_PATH).exists():
            with open(DB_PATH, 'rb') as f:
                db_data = f.read()
            dbx.files_upload(
                db_data,
                "/sales_tracking.db",
                mode=dropbox.files.WriteMode.overwrite
            )
            db_size = len(db_data) / 1024  # KB
            print(f"✅ DB de ventas subida: /sales_tracking.db ({db_size:.1f} KB)")

        # Upload listings database
        listings_db = "storage/listings_database.db"
        if Path(listings_db).exists():
            with open(listings_db, 'rb') as f:
                listings_data = f.read()
            dbx.files_upload(
                listings_data,
                "/listings_database.db",
                mode=dropbox.files.WriteMode.overwrite
            )
            listings_size = len(listings_data) / 1024  # KB
            print(f"✅ DB de productos subida: /listings_database.db ({listings_size:.1f} KB)")

        return True

    except ImportError as e:
        print(f"⚠️  Error de importación: {e}")
        print("   Instalá: pip3 install dropbox")
        return False
    except Exception as e:
        print(f"⚠️  Error subiendo a Dropbox: {e}")
        return False


if __name__ == "__main__":
    excel_path = create_professional_excel()
    upload_to_dropbox(excel_path)
