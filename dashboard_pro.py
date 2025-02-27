import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import logging
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import re

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
    
    # Acceder a la hoja de gastos
    gastos_sheet = spreadsheet.worksheet("Gastos")
    logging.info("Hoja 'Gastos' encontrada")
    
    # Extraer ID de la hoja de cálculo desde la URL
    try:
        spreadsheet_id = re.search(r'/d/([a-zA-Z0-9-_]+)', SPREADSHEET_URL).group(1)
        logging.info(f"ID de la hoja de cálculo: {spreadsheet_id}")
    except Exception as e:
        spreadsheet_id = "spreadsheet_id"
        logging.error(f"No se pudo extraer ID de la hoja: {e}")
    
    logging.info(f"Acceso a Google Sheets exitoso: {spreadsheet.title}")
except Exception as e:
    logging.error(f"Error al acceder a las hojas de Google Sheets: {e}")
    raise

# ================================
# Funciones para procesar datos
# ================================
def get_gastos_data():
    """
    Obtiene todos los datos de la hoja de gastos y los convierte en un DataFrame con formato adecuado
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
        'categoria': ['categoría', 'categoria', 'category', 'tipo', 'type'],
        'forma_pago': ['forma de pago', 'metodo de pago', 'payment method', 'pago']
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
    if 'forma_pago' not in df.columns:
        df['forma_pago'] = 'Desconocido'
    
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