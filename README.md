# 🛠️ Asistente de Gestión de Gastos

Este proyecto es una **herramienta de automatización** que procesa recibos de gastos, extrae información clave utilizando **OpenAI y Google Sheets API**, y almacena los datos en una hoja de cálculo y un archivo CSV.

## 🚀 Funcionalidades

✅ **Procesamiento de imágenes de recibos** mediante OpenAI API.  
✅ **Extracción de datos clave**: fecha, importe, negocio, descripción y categoría.  
✅ **Almacenamiento automático** en **Google Sheets** y en un **archivo CSV local**.  
✅ **Manejo de credenciales seguro** con `.env` (sin exponer claves en GitHub).  
✅ **Integración con Google Drive** para descargar y procesar recibos.  

---

## ⚡ Instalación y Configuración

### **1️⃣ Clonar el repositorio**
```bash
git clone https://github.com/IamNiko/Asistente.git
cd Asistente
```

### **2️⃣ Crear y activar el entorno virtual (opcional pero recomendado)**
```bash
python -m venv venv
source venv/bin/activate  # En Mac/Linux
venv\Scripts\activate      # En Windows
```

### **3️⃣ Instalar las dependencias**
```bash
pip install -r requirements.txt
```

### **4️⃣ Configurar las credenciales en `.env`**
Crea un archivo **`.env`** en la raíz del proyecto con la siguiente estructura:

```ini
GOOGLE_CREDENTIALS_FILE=C:/Users/nicol/OneDrive/Desktop/Asistente/credentials.json
SPREADSHEET_URL=https://docs.google.com/spreadsheets/d/tu-spreadsheet-id
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxx
TICKETS_FOLDER_ID=1o7ODEc36bYV0cKWP9gxIgr4cWSvCRz6A
TICKETS_CARGADOS_FOLDER_ID=1U_QB29Xeg8fAF_aLLB9nFqKG5LTJsBSu
```

> **Importante**: Asegúrate de que `.env` **NO se suba a GitHub** (ya está en `.gitignore`).

### **5️⃣ Ejecutar el proyecto**
Para procesar los recibos en la carpeta de Google Drive:

```bash
python assistant_goupbi.py
```

Para analizar datos almacenados:

```bash
python analisis_datos.py
```

---

## 📂 **Estructura del Proyecto**
```
/Asistente
│── .gitignore              # Archivos ignorados en Git (incluye .env y credenciales)
│── .env                    # Variables de entorno (⚠️ No se sube a Git)
│── requirements.txt         # Dependencias del proyecto
│── registro_gastos.csv      # Archivo CSV donde se guardan los gastos
│── dashboard.html           # Interfaz web para visualizar datos
│── dashboard.py             # Backend para la interfaz de visualización
│── dashboard_pro.py         # Versión avanzada del dashboard
│── assistant_goupbi.py      # Script principal que conecta con OpenAI y Google Sheets
│── analisis_datos.py        # Análisis de datos y generación de métricas
└── import base64.py         # Módulo para codificación de archivos en Base64
```

---

## 📌 **Mejoras Futuras**
🔹 Agregar una interfaz gráfica con **Flask o Streamlit**.  
🔹 Implementar autenticación segura para evitar accesos no autorizados.  
🔹 Optimizar la clasificación de gastos con **machine learning**.  

---

## 📝 **Licencia**
Este proyecto es de uso libre. Sin embargo, **las claves API y credenciales son responsabilidad del usuario**.

---

## 🤝 **Contribuciones**
Si deseas contribuir, haz un **fork** del repositorio, crea una rama con tus cambios y envía un **pull request**.

```
git checkout -b feature-nueva
git commit -m "Agregado nueva funcionalidad"
git push origin feature-nueva
```

¡Espero tu colaboración! 🚀
