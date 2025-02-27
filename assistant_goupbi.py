import gspread
from oauth2client.service_account import ServiceAccountCredentials
import base64
import requests
import json
import os
import csv
import logging
import io
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Librerías para la API de Google Drive
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Configuración del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Determinamos la ubicación del script y el archivo .env
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(SCRIPT_DIR, ".env")

# Comprobamos si existe el archivo .env
if not os.path.exists(ENV_FILE):
    logging.warning(f"No se encontró el archivo .env en {ENV_FILE}")
    logging.info("Usando valores predeterminados o hardcodeados si están disponibles")
else:
    logging.info(f"Cargando variables de entorno desde {ENV_FILE}")

# Cargar variables de entorno
load_dotenv(ENV_FILE)

# ================================
# Usar credenciales de las variables de entorno o valores predeterminados
# ================================
# Verificamos si las credenciales están en las variables de entorno
GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE')
if not GOOGLE_CREDENTIALS_FILE or not os.path.exists(GOOGLE_CREDENTIALS_FILE):
    # Si no está en el .env o la ruta no existe, usamos la ubicación original
    GOOGLE_CREDENTIALS_FILE = "C:/Users/nicol/OneDrive/Desktop/Asistente/credentials.json"
    logging.info(f"Usando ruta a credenciales predeterminada: {GOOGLE_CREDENTIALS_FILE}")

# Spreadsheet URL
SPREADSHEET_URL = os.getenv('SPREADSHEET_URL', "https://docs.google.com/spreadsheets/d/1_fOKbe6g5dlkRNJl4nWujfcLh7if_5oD4oLBJWPPvJI/edit?usp=drive_link")
logging.info(f"URL de la hoja de cálculo: {SPREADSHEET_URL}")

# API Key de OpenAI
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
# IDs de carpetas
TICKETS_FOLDER_ID = os.getenv('TICKETS_FOLDER_ID', '1o7ODEc36bYV0cKWP9gxIgr4cWSvCRz6A')
TICKETS_CARGADOS_FOLDER_ID = os.getenv('TICKETS_CARGADOS_FOLDER_ID', '1U_QB29Xeg8fAF_aLLB9nFqKG5LTJsBSu')

# Verificamos que el archivo de credenciales exista
if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
    logging.error(f"No se encontró el archivo de credenciales en {GOOGLE_CREDENTIALS_FILE}")
    logging.error("Por favor, verifica la ubicación del archivo o crea un archivo .env con la ruta correcta")
    raise FileNotFoundError(f"No se encontró el archivo de credenciales: {GOOGLE_CREDENTIALS_FILE}")

# ================================
# Configuración de Google APIs
# ================================
# Define el alcance de los permisos necesarios para Sheets y Drive
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']

try:
    # Carga y autoriza las credenciales desde el archivo definido
    logging.info(f"Intentando cargar credenciales desde: {GOOGLE_CREDENTIALS_FILE}")
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    logging.info(f"Autenticación con Google API exitosa usando {GOOGLE_CREDENTIALS_FILE}")
except Exception as e:
    logging.error(f"Error al autenticar con Google API: {e}")
    raise

# Inicializar el servicio de Google Drive
try:
    drive_service = build('drive', 'v3', credentials=creds)
    logging.info("Servicio de Google Drive inicializado.")
except Exception as e:
    logging.error(f"Error al inicializar Google Drive: {e}")
    raise

try:
    # Abre el documento de Google Sheets por URL
    logging.info(f"Intentando abrir hoja de cálculo: {SPREADSHEET_URL}")
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    
    # Intenta acceder primero a "Gastos" y si no existe, busca otras hojas
    try:
        gastos_sheet = spreadsheet.worksheet("Gastos")
        logging.info("Hoja 'Gastos' encontrada")
    except:
        # Si no encuentra "Gastos", intenta con el nombre de la primera hoja
        worksheet_list = spreadsheet.worksheets()
        if worksheet_list:
            gastos_sheet = worksheet_list[0]
            logging.warning(f"No se encontró hoja 'Gastos'. Usando la primera hoja: {gastos_sheet.title}")
        else:
            # Si no hay hojas, crear una llamada "Gastos"
            gastos_sheet = spreadsheet.add_worksheet(title="Gastos", rows=1000, cols=10)
            logging.info("Creada nueva hoja 'Gastos'")
    
    logging.info(f"Acceso a Google Sheets exitoso: {spreadsheet.title}")
except Exception as e:
    logging.error(f"Error al acceder a las hojas de Google Sheets: {e}")
    raise

# Ruta al archivo CSV local para guardar los datos
CSV_FILE_PATH = os.path.join(SCRIPT_DIR, "registro_gastos.csv")
logging.info(f"Archivo CSV local: {CSV_FILE_PATH}")

# ================================
# Función para descargar un archivo de Drive
# ================================
def download_file(file_id):
    """
    Descarga un archivo de Google Drive y devuelve un objeto BytesIO.
    
    :param file_id: ID del archivo en Drive.
    :return: BytesIO con el contenido del archivo o None en caso de error.
    """
    try:
        request = drive_service.files().get_media(fileId=file_id)
        file_bytes = io.BytesIO()
        downloader = MediaIoBaseDownload(file_bytes, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        file_bytes.seek(0)
        logging.info(f"Archivo descargado correctamente (ID: {file_id}).")
        return file_bytes
    except Exception as e:
        logging.error(f"Error al descargar el archivo (ID: {file_id}): {e}")
        return None

# ================================
# Función para verificar y asegurar la estructura de la hoja de cálculo
# ================================
def verify_sheet_structure():
    """
    Verifica que la estructura de la hoja 'Gastos' tenga las columnas necesarias.
    Si es necesario, actualiza el encabezado.
    """
    try:
        # Obtener el encabezado actual
        header_row = gastos_sheet.row_values(1)
        
        # Encabezado esperado
        expected_header = [
            "Fecha", "Negocio", "Descripción", "Importe", "Categoría", 
            "Archivo", "Fecha Procesamiento"
        ]
        
        # Verificar si el encabezado existe y si es correcto
        if not header_row:
            # Si no hay encabezado, lo creamos
            logging.info("Creando encabezado en la hoja de gastos.")
            gastos_sheet.append_row(expected_header)
            logging.info("Encabezado creado correctamente.")
            return True
            
        # Si hay encabezado pero no tiene todas las columnas necesarias
        if len(header_row) < len(expected_header):
            # Actualizamos el encabezado
            logging.warning("El encabezado existente no tiene todas las columnas necesarias. Actualizando...")
            gastos_sheet.update("A1:G1", [expected_header])
            logging.info("Encabezado actualizado correctamente.")
            return True
            
        # Si hay encabezado pero tiene diferencias con el esperado
        differences = [i for i, (actual, expected) in enumerate(zip(header_row, expected_header)) 
                      if actual.lower() != expected.lower()]
        
        if differences:
            logging.warning(f"El encabezado tiene diferencias en las columnas: {differences}")
            logging.warning(f"Actual: {[header_row[i] for i in differences]}")
            logging.warning(f"Esperado: {[expected_header[i] for i in differences]}")
            
            # Actualizamos solo las celdas necesarias
            for i in differences:
                col_letter = chr(65 + i)  # A, B, C, etc.
                gastos_sheet.update(f"{col_letter}1", expected_header[i])
                
            logging.info("Encabezado corregido.")
            return True
            
        logging.info("La estructura de la hoja 'Gastos' es correcta.")
        return False
        
    except Exception as e:
        logging.error(f"Error al verificar/actualizar la estructura de la hoja: {e}")
        return False

# ================================
# Función para obtener archivos por fecha de creación/modificación
# ================================
def get_files_by_creation_date(folder_id, days_threshold=7):
    """
    Obtiene archivos de una carpeta de Google Drive que fueron creados/modificados 
    en los últimos días_threshold días.
    
    :param folder_id: ID de la carpeta en Google Drive
    :param days_threshold: Número de días hacia atrás para considerar
    :return: Lista de archivos (con id y nombre)
    """
    try:
        # Calculamos la fecha límite
        date_threshold = (datetime.now() - timedelta(days=days_threshold)).strftime('%Y-%m-%dT%H:%M:%S')
        
        # Consultamos archivos de imagen en la carpeta especificada, creados después de la fecha límite
        query = f"'{folder_id}' in parents and mimeType contains 'image/' and (createdTime > '{date_threshold}' or modifiedTime > '{date_threshold}')"
        
        results = drive_service.files().list(
            q=query,
            fields="files(id, name, createdTime, modifiedTime)",
            orderBy="createdTime desc"
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            logging.info(f"No se encontraron archivos nuevos (últimos {days_threshold} días) en la carpeta.")
            return []
            
        logging.info(f"Se encontraron {len(files)} archivos nuevos (últimos {days_threshold} días).")
        
        # Mostramos información detallada de los archivos encontrados
        for file in files:
            created = datetime.fromisoformat(file.get('createdTime', '').replace('Z', '+00:00'))
            modified = datetime.fromisoformat(file.get('modifiedTime', '').replace('Z', '+00:00'))
            logging.info(f"Archivo: {file['name']}, Creado: {created}, Modificado: {modified}")
            
        return files
        
    except Exception as e:
        logging.error(f"Error al listar archivos por fecha: {e}")
        return []

# ================================
# Función para procesar imagen usando OpenAI API
# ================================
def process_ticket_image_with_openai(file_bytes):
    """
    Procesa una imagen usando la API de OpenAI para extraer datos estructurados.
    
    :param file_bytes: Objeto BytesIO con los datos de la imagen.
    :return: Diccionario con datos estructurados (fecha, descripción, importe, negocio, categoría)
    """
    try:
        # Codificar la imagen en base64
        encoded_image = base64.b64encode(file_bytes.read()).decode('utf-8')
        file_bytes.seek(0)  # Reiniciar el puntero para futuros usos
        
        # Configurar la solicitud a la API de OpenAI
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        
        # Modificar el prompt para solicitar la extracción de datos específicos
        prompt = """
        Analiza esta imagen de un recibo o factura y extrae la siguiente información en formato JSON:
        1. fecha: la fecha de la transacción (formato YYYY-MM-DD)
        2. descripcion: breve descripción de la compra o servicio
        3. importe: cantidad total pagada (número decimal)
        4. negocio: nombre del negocio o entidad que emitió el recibo
        5. categoria: asigna una de estas categorías al gasto:
           - Suscripciones
           - Salud
           - Vivienda
           - Movilidad
           - Educación
           - Alimentos
           - Salidas
           - Gastos extraordinarios

        Responde ÚNICAMENTE con el objeto JSON puro, sin marcadores de código (```), comillas ni texto adicional.
        """
        
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 500
        }
        
        # Realizar la solicitud a la API
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        
        # Procesar y mostrar la respuesta
        if response.status_code == 200:
            resultado = response.json()
            datos_extraidos = resultado['choices'][0]['message']['content']
            
            logging.info("Datos extraídos del recibo con OpenAI:")
            logging.info(datos_extraidos)
            
            # Limpiar la respuesta JSON si contiene marcadores de código
            datos_limpios = datos_extraidos.strip()
            if datos_limpios.startswith("```json"):
                datos_limpios = datos_limpios[7:]  # Eliminar ```json del inicio
            if datos_limpios.endswith("```"):
                datos_limpios = datos_limpios[:-3]  # Eliminar ``` del final
            datos_limpios = datos_limpios.strip()
            
            try:
                # Intentar parsear el JSON
                datos_json = json.loads(datos_limpios)
                
                # Asegurarse que todos los campos estén presentes
                required_fields = ['fecha', 'descripcion', 'importe', 'negocio', 'categoria']
                for field in required_fields:
                    if field not in datos_json:
                        logging.warning(f"Campo '{field}' no encontrado en la respuesta de OpenAI. Añadiendo valor por defecto.")
                        if field == 'fecha':
                            datos_json[field] = datetime.now().strftime('%Y-%m-%d')
                        elif field == 'importe':
                            datos_json[field] = 0.0
                        else:
                            datos_json[field] = "No especificado"
                
                return datos_json
            
            except json.JSONDecodeError as e:
                logging.error(f"Error al parsear JSON: {e}. Contenido: {datos_limpios}")
                return None
            
        else:
            logging.error(f"Error en la API de OpenAI: {response.status_code}")
            logging.error(response.text)
            return None
            
    except Exception as e:
        logging.error(f"Error al procesar la imagen con OpenAI: {e}")
        return None

# ================================
# Función para copiar archivo a otra carpeta en Drive
# ================================
def copy_file_to_folder(file_id, destination_folder_id):
    """
    Copia un archivo de Google Drive a una carpeta específica sin eliminar el original.
    
    :param file_id: ID del archivo a copiar
    :param destination_folder_id: ID de la carpeta destino
    :return: ID del archivo copiado o None si hay error
    """
    try:
        # 1. Obtener metadata del archivo original
        file_metadata = drive_service.files().get(
            fileId=file_id, 
            fields='name,mimeType',
            supportsAllDrives=True
        ).execute()
        
        # 2. Crear una copia del archivo en la carpeta destino
        copy_metadata = {
            'name': file_metadata['name'],
            'parents': [destination_folder_id]
        }
        
        logging.info(f"Copiando archivo {file_id} con nombre {file_metadata['name']} a carpeta {destination_folder_id}")
        
        copied_file = drive_service.files().copy(
            fileId=file_id,
            body=copy_metadata,
            supportsAllDrives=True
        ).execute()
        
        logging.info(f"Archivo copiado correctamente. Nuevo ID: {copied_file['id']}")
        return copied_file['id']
        
    except Exception as e:
        logging.error(f"Error al copiar el archivo {file_id} a la carpeta {destination_folder_id}: {e}")
        return None

# ================================
# Función para comprobar si un archivo ya ha sido procesado
# ================================
def is_file_already_processed(file_name):
    """
    Verifica si un archivo ya ha sido procesado anteriormente.
    Comprueba tanto en el CSV local como en la hoja de Google Sheets.
    
    :param file_name: Nombre del archivo a verificar
    :return: True si ya ha sido procesado, False en caso contrario
    """
    # Verificar en el CSV local
    try:
        if os.path.exists(CSV_FILE_PATH):
            with open(CSV_FILE_PATH, 'r', newline='', encoding='utf-8') as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    if 'Archivo' in row and row['Archivo'] == file_name:
                        logging.info(f"Archivo {file_name} encontrado en CSV local. Omitiendo.")
                        return True
    except Exception as e:
        logging.warning(f"Error al verificar en CSV local: {e}")
    
    # Verificar en Google Sheets
    try:
        # Obtener todos los valores de la columna Archivo (columna 6)
        processed_files = gastos_sheet.col_values(6)[1:]  # Omitir encabezado
        if file_name in processed_files:
            logging.info(f"Archivo {file_name} encontrado en Google Sheets. Omitiendo.")
            return True
    except Exception as e:
        logging.warning(f"Error al verificar en Google Sheets: {e}")
    
    # Comprobar si ya existe en la carpeta de destino
    try:
        query = f"name = '{file_name}' and '{TICKETS_CARGADOS_FOLDER_ID}' in parents"
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        if files:
            logging.info(f"Archivo {file_name} encontrado en carpeta destino. Omitiendo.")
            return True
    except Exception as e:
        logging.warning(f"Error al verificar en carpeta destino: {e}")
    
    return False

# ================================
# Función para guardar datos en CSV local
# ================================
def save_to_csv(datos, file_name):
    """
    Guarda los datos extraídos en un archivo CSV local.
    
    :param datos: Diccionario con los datos extraídos
    :param file_name: Nombre del archivo procesado
    :return: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Preparar datos para CSV
        row_data = {
            'Fecha': datos['fecha'],
            'Negocio': datos['negocio'],
            'Descripción': datos['descripcion'],
            'Importe': datos['importe'],
            'Categoría': datos['categoria'],
            'Archivo': file_name,
            'Fecha Procesamiento': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Verificar si el archivo existe
        file_exists = os.path.isfile(CSV_FILE_PATH)
        
        # Crear o abrir el archivo CSV
        with open(CSV_FILE_PATH, 'a', newline='', encoding='utf-8') as csv_file:
            fieldnames = ['Fecha', 'Negocio', 'Descripción', 'Importe', 'Categoría', 'Archivo', 'Fecha Procesamiento']
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            
            # Escribir encabezado si es un archivo nuevo
            if not file_exists:
                writer.writeheader()
            
            # Escribir datos
            writer.writerow(row_data)
        
        logging.info(f"Datos guardados correctamente en CSV: {CSV_FILE_PATH}")
        return True
    
    except Exception as e:
        logging.error(f"Error al guardar en CSV: {e}")
        return False

# ================================
# Función para guardar datos en Google Sheets
# ================================
def save_to_google_sheets(datos, file_name):
    """
    Guarda los datos extraídos en la hoja de Google Sheets.
    
    :param datos: Diccionario con los datos extraídos
    :param file_name: Nombre del archivo procesado
    :return: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Preparar fila para Google Sheets
        row_data = [
            datos['fecha'],
            datos['negocio'],
            datos['descripcion'],
            datos['importe'],
            datos['categoria'],
            file_name,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ]
        
        # Añadir la fila a Google Sheets
        gastos_sheet.append_row(row_data)
        
        logging.info(f"Datos guardados correctamente en Google Sheets")
        return True
    
    except Exception as e:
        logging.error(f"Error al guardar en Google Sheets: {e}")
        return False

# ================================
# Función principal para procesar tickets
# ================================
def process_tickets(days_threshold=7):
    """
    Procesa los tickets de imágenes en la carpeta de origen que fueron creados/modificados
    en los últimos days_threshold días.
    
    1. Extrae datos estructurados usando OpenAI
    2. Guarda la información en un CSV local
    3. Guarda la información en la hoja de Google Sheets
    4. Copia el archivo a la carpeta de destino
    
    :param days_threshold: Número de días hacia atrás para considerar
    """
    # Primero verificamos y actualizamos la estructura de la hoja si es necesario
    verify_sheet_structure()
    
    # Obtener archivos recientes
    files = get_files_by_creation_date(TICKETS_FOLDER_ID, days_threshold)
    
    if not files:
        logging.info(f"No hay archivos nuevos para procesar en los últimos {days_threshold} días.")
        return 0  # No hay archivos para procesar
    
    # Contadores para estadísticas
    total_files = len(files)
    processed_files = 0
    skipped_files = 0
    
    # Procesar cada archivo
    for file in files:
        file_id = file['id']
        file_name = file['name']
        logging.info(f"Procesando el archivo: {file_name} (ID: {file_id})")
        
        # Verificar si este archivo ya fue procesado antes (evitar duplicados)
        if is_file_already_processed(file_name):
            logging.info(f"El archivo {file_name} ya fue procesado anteriormente. Omitiendo.")
            skipped_files += 1
            continue
        
        # Descargar y procesar el archivo
        file_bytes = download_file(file_id)
        if not file_bytes:
            logging.error(f"No se pudo descargar el archivo {file_name}. Omitiendo.")
            skipped_files += 1
            continue
        
        # Procesar la imagen con OpenAI para extraer datos
        datos = process_ticket_image_with_openai(file_bytes)
        if not datos:
            logging.error(f"No se pudieron extraer datos del archivo {file_name}. Omitiendo.")
            skipped_files += 1
            continue
        
        # Guardar en CSV local
        csv_saved = save_to_csv(datos, file_name)
        
        # Guardar en Google Sheets
        sheets_saved = save_to_google_sheets(datos, file_name)
        
        # Si se guardó correctamente en ambos lugares, copiar el archivo a la carpeta de destino
        if csv_saved and sheets_saved:
            copied_id = copy_file_to_folder(file_id, TICKETS_CARGADOS_FOLDER_ID)
            if copied_id:
                logging.info(f"✅ Archivo {file_name} procesado completamente y copiado a la carpeta de destino.")
                processed_files += 1
            else:
                logging.warning(f"⚠️ Archivo {file_name} procesado pero no se pudo copiar a la carpeta de destino.")
                # Aún contamos como procesado porque los datos se guardaron
                processed_files += 1
        else:
            logging.error(f"❌ Error al guardar los datos del archivo {file_name}.")
            skipped_files += 1
    
    # Mostrar estadísticas
    logging.info(f"Procesamiento completado.")
    logging.info(f"Total de archivos: {total_files}")
    logging.info(f"Archivos procesados: {processed_files}")
    logging.info(f"Archivos omitidos: {skipped_files}")
    
    return processed_files

# ================================
# Punto de entrada principal
# ================================
if __name__ == "__main__":
    logging.info("=== Iniciando el sistema de procesamiento de tickets ===")
    logging.info(f"Carpeta de tickets origen: {TICKETS_FOLDER_ID}")
    logging.info(f"Carpeta de tickets destino: {TICKETS_CARGADOS_FOLDER_ID}")
    logging.info(f"Archivo CSV local: {CSV_FILE_PATH}")
    
    # Procesar tickets de los últimos 7 días (puedes ajustar este valor)
    processed_count = process_tickets(days_threshold=7)
    
    if processed_count > 0:
        logging.info(f"Se procesaron {processed_count} tickets correctamente.")
    else:
        logging.info("No se procesaron tickets nuevos.")
    
    logging.info("=== Procesamiento finalizado ===")