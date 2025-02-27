import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import numpy as np
import logging
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from gspread_formatting import *

# Configuración del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Determinamos la ubicación del script y el archivo .env
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(SCRIPT_DIR, ".env")

# Cargar variables de entorno
load_dotenv(ENV_FILE)

# ================================
# Verificar y cargar credenciales
# ================================
GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE')
if not GOOGLE_CREDENTIALS_FILE or not os.path.exists(GOOGLE_CREDENTIALS_FILE):
    # Si no está en el .env o la ruta no existe, usamos la ubicación original
    GOOGLE_CREDENTIALS_FILE = "C:/Users/nicol/OneDrive/Desktop/Asistente/credentials.json"
    logging.info(f"Usando ruta a credenciales predeterminada: {GOOGLE_CREDENTIALS_FILE}")

# Spreadsheet URL
SPREADSHEET_URL = os.getenv('SPREADSHEET_URL', "https://docs.google.com/spreadsheets/d/1_fOKbe6g5dlkRNJl4nWujfcLh7if_5oD4oLBJWPPvJI/edit?usp=drive_link")
logging.info(f"URL de la hoja de cálculo: {SPREADSHEET_URL}")

# ================================
# Configuración de Google APIs
# ================================
# Define el alcance de los permisos necesarios para Sheets y Drive
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']

try:
    # Carga y autoriza las credenciales
    logging.info(f"Intentando cargar credenciales desde: {GOOGLE_CREDENTIALS_FILE}")
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    logging.info(f"Autenticación con Google API exitosa")
except Exception as e:
    logging.error(f"Error al autenticar con Google API: {e}")
    raise

try:
    # Abre el documento de Google Sheets por URL
    logging.info(f"Intentando abrir hoja de cálculo: {SPREADSHEET_URL}")
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    
    # Acceder a las hojas
    gastos_sheet = spreadsheet.worksheet("Gastos")
    logging.info("Hoja 'Gastos' encontrada")
    
    try:
        dashboard_sheet = spreadsheet.worksheet("Dashboard")
        logging.info("Hoja 'Dashboard' encontrada")
    except:
        # Si no existe la hoja Dashboard, la creamos
        dashboard_sheet = spreadsheet.add_worksheet(title="Dashboard", rows=50, cols=15)
        logging.info("Hoja 'Dashboard' creada")
    
    logging.info(f"Acceso a Google Sheets exitoso: {spreadsheet.title}")
except Exception as e:
    logging.error(f"Error al acceder a las hojas de Google Sheets: {e}")
    raise

# ================================
# Funciones para procesar datos
# ================================
def get_gastos_data():
    """
    Obtiene todos los datos de la hoja de gastos y los convierte en un DataFrame
    """
    # Obtener todos los datos incluyendo encabezados
    all_values = gastos_sheet.get_all_values()
    
    if not all_values or len(all_values) <= 1:  # Si no hay datos o solo hay encabezados
        logging.warning("No hay datos en la hoja de Gastos o solo hay encabezados")
        return None
    
    # Obtener encabezados y datos
    headers = all_values[0]
    data = all_values[1:]
    
    # Verificar que haya datos
    if not data:
        logging.warning("No hay datos en la hoja de Gastos (solo encabezados)")
        return None
    
    # Convertir a DataFrame
    df = pd.DataFrame(data, columns=headers)
    
    # Imprimir los nombres de las columnas para diagnóstico
    logging.info(f"Columnas detectadas: {df.columns.tolist()}")
    
    # Mapeo de nombres esperados a posibles nombres en la hoja
    column_map = {
        'fecha': ['fecha', 'date', 'fecha_gasto', 'día', 'dia'],
        'descripcion': ['descripción', 'descripcion', 'description', 'concepto', 'detalle'],
        'importe': ['importe', 'monto', 'amount', 'valor', 'precio', 'total'],
        'empresa': ['empresa', 'negocio', 'comercio', 'tienda', 'proveedor', 'business'],
        'categoria': ['categoría', 'categoria', 'category', 'tipo', 'type']
    }
    
    # Renombrar columnas al formato esperado (primera columna que coincida)
    rename_map = {}
    for expected_col, possible_cols in column_map.items():
        for col in possible_cols:
            for actual_col in df.columns:
                if col.lower() == actual_col.lower():
                    rename_map[actual_col] = expected_col
                    break
            if expected_col in rename_map.values():
                break
    
    # Verificar si encontramos todas las columnas necesarias
    required_cols = ['fecha', 'importe']
    missing_cols = [col for col in required_cols if col not in rename_map.values()]
    
    if missing_cols:
        logging.error(f"Columnas requeridas no encontradas: {missing_cols}")
        # Intentar asignar nombres según posición si falta alguna columna crítica
        if 'fecha' not in rename_map.values() and len(df.columns) > 0:
            rename_map[df.columns[0]] = 'fecha'
            logging.warning(f"Asignando primera columna como 'fecha': {df.columns[0]}")
        if 'importe' not in rename_map.values() and len(df.columns) > 3:
            rename_map[df.columns[3]] = 'importe'
            logging.warning(f"Asignando cuarta columna como 'importe': {df.columns[3]}")
    
    # Mostrar el mapeo de columnas para diagnóstico
    logging.info(f"Mapeo de columnas: {rename_map}")
    
    # Renombrar las columnas
    df = df.rename(columns=rename_map)
    
    # Para las columnas que no se encuentran, crear con valores predeterminados
    if 'empresa' not in df.columns:
        df['empresa'] = 'Desconocido'
    if 'descripcion' not in df.columns:
        df['descripcion'] = 'Sin descripción'
    if 'categoria' not in df.columns:
        df['categoria'] = 'Sin categoría'
    
    # Asegurarse de que 'Fecha' sea datetime
    try:
        df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    except:
        logging.warning("Error al convertir fechas. Usando formato estándar.")
        # Intentar detectar el formato de fecha
        sample_dates = df['fecha'].dropna().head(5).tolist()
        logging.info(f"Ejemplos de fechas: {sample_dates}")
        
        # Intentar diferentes formatos comunes
        formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d']
        for fmt in formats:
            try:
                df['fecha'] = pd.to_datetime(df['fecha'], format=fmt, errors='coerce')
                if not df['fecha'].isna().all():
                    logging.info(f"Formato de fecha detectado: {fmt}")
                    break
            except:
                continue
    
    # Convertir 'Importe' a numérico
    try:
        # Primero limpiar posibles símbolos de moneda o comas
        df['importe'] = df['importe'].astype(str).str.replace('€', '')
        df['importe'] = df['importe'].str.replace('$', '')
        df['importe'] = df['importe'].str.replace(',', '.')
        df['importe'] = pd.to_numeric(df['importe'], errors='coerce')
    except Exception as e:
        logging.error(f"Error al convertir importe a numérico: {e}")
    
    # Eliminar filas con datos inválidos críticos
    df = df.dropna(subset=['fecha', 'importe'])
    
    return df

def prepare_dashboard_data(df):
    """
    Prepara los datos para el dashboard
    """
    if df is None or df.empty:
        return None
    
    # Datos para el dashboard
    dashboard_data = {
        'total_gastos': df['importe'].sum(),
        'promedio_gasto': df['importe'].mean(),
        'max_gasto': df['importe'].max(),
        'min_gasto': df['importe'].min(),
        'num_transacciones': len(df),
        'ultimo_gasto': df.sort_values('fecha', ascending=False).iloc[0] if not df.empty else None,
        'gastos_por_categoria': df.groupby('categoria')['importe'].sum().sort_values(ascending=False),
        'gastos_por_mes': df.groupby(df['fecha'].dt.strftime('%Y-%m'))['importe'].sum().sort_index(),
        'gastos_por_empresa': df.groupby('empresa')['importe'].sum().sort_values(ascending=False).head(10),
        'ultimos_5_gastos': df.sort_values('fecha', ascending=False).head(5)
    }
    
    return dashboard_data

# ================================
# Funciones para generar el dashboard
# ================================
def clear_dashboard():
    """
    Limpia la hoja de dashboard para actualizarla
    """
    dashboard_sheet.clear()
    logging.info("Dashboard limpiado")

def format_currency(value):
    """
    Formatea un valor como moneda
    """
    if pd.isna(value):
        return "€0.00"
    return f"€{value:.2f}"

def format_header_cell(sheet, cell_range):
    """
    Aplica formato a una celda de encabezado
    """
    fmt = CellFormat(
        backgroundColor=Color(0.2, 0.4, 0.5),
        textFormat=TextFormat(bold=True, foregroundColor=Color(1, 1, 1)),
        horizontalAlignment='CENTER',
        verticalAlignment='MIDDLE'
    )
    format_cell_range(sheet, cell_range, fmt)

def format_title_cell(sheet, cell_range):
    """
    Aplica formato a una celda de título
    """
    fmt = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=14),
        horizontalAlignment='CENTER',
        verticalAlignment='MIDDLE'
    )
    format_cell_range(sheet, cell_range, fmt)

def format_subtitle_cell(sheet, cell_range):
    """
    Aplica formato a una celda de subtítulo
    """
    fmt = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=12),
        horizontalAlignment='LEFT',
        verticalAlignment='MIDDLE'
    )
    format_cell_range(sheet, cell_range, fmt)

def format_number_cell(sheet, cell_range):
    """
    Aplica formato a una celda de números
    """
    fmt = CellFormat(
        numberFormat=NumberFormat(type='CURRENCY', pattern='€#,##0.00'),
        horizontalAlignment='RIGHT'
    )
    format_cell_range(sheet, cell_range, fmt)

def create_header():
    """
    Crea el encabezado del dashboard
    """
    # Título
    dashboard_sheet.update('A1', 'DASHBOARD DE GASTOS')
    dashboard_sheet.merge_cells('A1:G1')
    format_title_cell(dashboard_sheet, 'A1:G1')
    
    # Fecha de actualización
    dashboard_sheet.update('A2', f'Última actualización: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    dashboard_sheet.merge_cells('A2:G2')
    
    # Espacio
    dashboard_sheet.update('A3', '')

def create_summary_section(data):
    """
    Crea la sección de resumen con los indicadores principales
    """
    if data is None:
        return
    
    # Título de la sección
    dashboard_sheet.update('A4', 'RESUMEN DE GASTOS')
    dashboard_sheet.merge_cells('A4:G4')
    format_subtitle_cell(dashboard_sheet, 'A4:G4')
    
    # Indicadores
    metrics = [
        ['Total de gastos', format_currency(data['total_gastos'])],
        ['Promedio por transacción', format_currency(data['promedio_gasto'])],
        ['Gasto máximo', format_currency(data['max_gasto'])],
        ['Gasto mínimo', format_currency(data['min_gasto'])],
        ['Número de transacciones', data['num_transacciones']]
    ]
    
    # Actualizar celdas
    dashboard_sheet.update('A5:B9', metrics)
    
    # Formatear celdas
    format_header_cell(dashboard_sheet, 'A5:A9')
    format_number_cell(dashboard_sheet, 'B6:B8')  # Solo las celdas de moneda

def create_category_section(data):
    """
    Crea la sección de gastos por categoría
    """
    if data is None or data['gastos_por_categoria'].empty:
        return
    
    # Título de la sección
    dashboard_sheet.update('A11', 'GASTOS POR CATEGORÍA')
    dashboard_sheet.merge_cells('A11:C11')
    format_subtitle_cell(dashboard_sheet, 'A11:C11')
    
    # Encabezados
    dashboard_sheet.update('A12:C12', [['Categoría', 'Importe', 'Porcentaje']])
    format_header_cell(dashboard_sheet, 'A12:C12')
    
    # Datos
    category_data = []
    for category, amount in data['gastos_por_categoria'].items():
        percentage = (amount / data['total_gastos']) * 100
        category_data.append([category, format_currency(amount), f"{percentage:.1f}%"])
    
    # Actualizar celdas
    end_row = 12 + len(category_data)
    dashboard_sheet.update(f'A13:C{end_row}', category_data)
    
    # Formatear celdas
    format_number_cell(dashboard_sheet, f'B13:B{end_row}')

def create_monthly_section(data):
    """
    Crea la sección de gastos por mes
    """
    if data is None or data['gastos_por_mes'].empty:
        return
    
    # Título de la sección
    dashboard_sheet.update('E11', 'GASTOS POR MES')
    dashboard_sheet.merge_cells('E11:G11')
    format_subtitle_cell(dashboard_sheet, 'E11:G11')
    
    # Encabezados
    dashboard_sheet.update('E12:G12', [['Mes', 'Importe', 'Tendencia']])
    format_header_cell(dashboard_sheet, 'E12:G12')
    
    # Datos
    monthly_data = []
    prev_amount = None
    
    for month, amount in data['gastos_por_mes'].items():
        # Determinar tendencia
        trend = ""
        if prev_amount is not None:
            if amount > prev_amount:
                trend = "▲"  # Aumento
            elif amount < prev_amount:
                trend = "▼"  # Disminución
            else:
                trend = "−"  # Sin cambio
        
        monthly_data.append([month, format_currency(amount), trend])
        prev_amount = amount
    
    # Actualizar celdas
    end_row = 12 + len(monthly_data)
    dashboard_sheet.update(f'E13:G{end_row}', monthly_data)
    
    # Formatear celdas
    format_number_cell(dashboard_sheet, f'F13:F{end_row}')

def create_empresa_section(data):
    """
    Crea la sección de gastos por empresa
    """
    if data is None or data['gastos_por_empresa'].empty:
        return
    
    start_row = 25  # Ajusta según necesidad
    
    # Título de la sección
    dashboard_sheet.update(f'A{start_row}', 'TOP EMPRESAS POR GASTO')
    dashboard_sheet.merge_cells(f'A{start_row}:C{start_row}')
    format_subtitle_cell(dashboard_sheet, f'A{start_row}:C{start_row}')
    
    # Encabezados
    header_row = start_row + 1
    dashboard_sheet.update(f'A{header_row}:C{header_row}', [['Empresa', 'Importe', 'Porcentaje']])
    format_header_cell(dashboard_sheet, f'A{header_row}:C{header_row}')
    
    # Datos
    company_data = []
    for company, amount in data['gastos_por_empresa'].items():
        percentage = (amount / data['total_gastos']) * 100
        company_data.append([company, format_currency(amount), f"{percentage:.1f}%"])
    
    # Actualizar celdas
    start_data_row = header_row + 1
    end_row = start_data_row + len(company_data) - 1
    dashboard_sheet.update(f'A{start_data_row}:C{end_row}', company_data)
    
    # Formatear celdas
    format_number_cell(dashboard_sheet, f'B{start_data_row}:B{end_row}')

def create_latest_transactions(data):
    """
    Crea la sección de últimas transacciones
    """
    if data is None or data['ultimos_5_gastos'].empty:
        return
    
    start_row = 25  # Ajusta según necesidad
    
    # Título de la sección
    dashboard_sheet.update(f'E{start_row}', 'ÚLTIMAS TRANSACCIONES')
    dashboard_sheet.merge_cells(f'E{start_row}:I{start_row}')
    format_subtitle_cell(dashboard_sheet, f'E{start_row}:I{start_row}')
    
    # Encabezados
    header_row = start_row + 1
    dashboard_sheet.update(f'E{header_row}:I{header_row}', [['Fecha', 'Empresa', 'Descripción', 'Importe', 'Categoría']])
    format_header_cell(dashboard_sheet, f'E{header_row}:I{header_row}')
    
    # Datos
    transaction_data = []
    for _, row in data['ultimos_5_gastos'].iterrows():
        transaction_data.append([
            row['fecha'].strftime('%Y-%m-%d'),
            row['empresa'],
            row['descripcion'],
            format_currency(row['importe']),
            row['categoria']
        ])
    
    # Actualizar celdas
    start_data_row = header_row + 1
    end_row = start_data_row + len(transaction_data) - 1
    dashboard_sheet.update(f'E{start_data_row}:I{end_row}', transaction_data)
    
    # Formatear celdas
    format_number_cell(dashboard_sheet, f'H{start_data_row}:H{end_row}')

# ================================
# Función principal para generar el dashboard
# ================================
def generate_dashboard():
    """
    Función principal que genera el dashboard completo
    """
    logging.info("Iniciando generación del dashboard")
    
    # Obtener los datos
    df = get_gastos_data()
    if df is None or df.empty:
        logging.warning("No hay datos suficientes para generar el dashboard")
        dashboard_sheet.update('A1', 'No hay datos suficientes para generar el dashboard')
        return
    
    # Imprimir el dataframe para diagnóstico
    logging.info(f"DataFrame creado con {len(df)} filas y las siguientes columnas: {df.columns.tolist()}")
    
    # Preparar los datos para el dashboard
    data = prepare_dashboard_data(df)
    
    # Limpiar el dashboard actual
    clear_dashboard()
    
    # Crear las diferentes secciones
    create_header()
    create_summary_section(data)
    create_category_section(data)
    create_monthly_section(data)
    create_empresa_section(data)
    create_latest_transactions(data)
    
    # Ajustar anchos de columna
    try:
        set_column_widths(dashboard_sheet)
    except Exception as e:
        logging.warning(f"No se pudieron ajustar los anchos de columna: {e}")
    
    logging.info("Dashboard generado con éxito")

def set_column_widths(sheet):
    """
    Ajusta los anchos de columna. Maneja posibles errores.
    """
    try:
        sheet.set_column_width(1, 200)  # Columna A
        sheet.set_column_width(2, 150)  # Columna B
        sheet.set_column_width(3, 100)  # Columna C
        sheet.set_column_width(5, 150)  # Columna E
        sheet.set_column_width(6, 150)  # Columna F
        sheet.set_column_width(7, 250)  # Columna G
        sheet.set_column_width(8, 150)  # Columna H
        sheet.set_column_width(9, 150)  # Columna I
    except AttributeError:
        # Si set_column_width no está disponible, usar la API de formato
        fmt = CellFormat(horizontalAlignment='LEFT')
        format_cell_range(sheet, 'A:A', fmt)
        format_cell_range(sheet, 'E:E', fmt)
        format_cell_range(sheet, 'F:F', fmt)
        format_cell_range(sheet, 'G:G', fmt)
    except Exception as e:
        logging.error(f"Error al ajustar anchos de columna: {e}")

# ================================
# Punto de entrada principal
# ================================
if __name__ == "__main__":
    logging.info("=== Iniciando la generación del dashboard ===")
    
    try:
        generate_dashboard()
        logging.info("=== Dashboard generado correctamente ===")
    except Exception as e:
        logging.error(f"Error al generar el dashboard: {e}")
        import traceback
        logging.error(traceback.format_exc())