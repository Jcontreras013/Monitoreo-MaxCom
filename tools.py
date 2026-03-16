import pandas as pd
import re

# 1. MAPEO UNIVERSAL DE COLUMNAS
# Centraliza los nombres de las columnas para que el Excel de Prueba e Histórico sean compatibles
COLUMNS_MAPPING = {
    'HORA_INI': ['HORA ENTRADA', 'HORA INICIO', 'HORA_INICIO_ORDEN', 'FECHA ENTRADA'],
    'HORA_LIQ': ['HORA LIQUIDADO', 'HORA CIERRE', 'HORA_CIERRE_ORDEN', 'FECHA LIQUIDADO'],
    'TECNICO': ['TÉCNICO', 'TECNICO', 'OPERADOR'],
    'ACTIVIDAD': ['NOMBRE ACTIVIDAD', 'TIPO ORDEN', 'ACTIVIDAD'],
    'FECHA_APE': ['FECHA APERTURA', 'APERTURA', 'DIAS_ASIGNADA', 'Días'],
    'ESTADO': ['ESTADO', 'STATUS'],
    'SECTOR': ['SECTOR', 'Sect', 'Sector'],
    'COLONIA': ['COLONIA', 'BARRIO', 'DIRECCION', 'LOCALIDAD'],
    'NUM': ['NUM', 'ID_ORDEN', 'NÚMERO'],
    'CLIENTE': ['CLIENTE', 'NOMBRE CLIENTE', 'SUSCRIPTOR'],
    'COMENTARIO': ['COMENTARIO', 'OBSERVACIONES'],
    'MX': ['MX', 'VEHICULO', 'UNIDAD']
}

# 2. LISTAS PARA AUDITORÍA DE FACTURACIÓN (Lo que pediste detectar)
# Estados que generan discrepancia si la orden no se instaló
ESTADOS_RIESGO = [
    'INACTIVO',     # El caso principal que mencionas
    'ACTCCVEO',     # Activaciones que generan cobro
    'ACTIVARRES',   # Activaciones residenciales
    'ANULAFACTURA', # Procesos de anulación mal cerrados
    'CORTEMORA',    # Estados que implican que el servicio "existe"
    'NOINSTALADO'   # Si el sistema lo deja así sin cerrar la orden
]

# Palabras clave que usa el técnico para confirmar que NO hubo instalación
JERGA_NO_INSTALABLE = [
    'NO SE PUDO', 'NO INSTALADO', 'CLIENTE NO QUISO', 'SIN ACCESO', 
    'FACHADA', 'POSTE LEJOS', 'CANCELADA', 'NO PERMITIO', 'NO SE INSTALA',
    'CANCELO', 'DEVOLUCION', 'ANULACION'
]

# 3. LÓGICA DE DETECCIÓN DE OFFLINE (Para app.py)
def es_offline_preciso(comentario):
    texto = str(comentario).upper().strip()
    if not texto or texto == 'NAN': return False
    
    # Palabras de éxito que cancelan la alerta
    jerga_solucionado = ['YA QUEDO', 'OK', 'LISTO', 'RECUPERADO', 'SOLUCIONADO', 'ONLINE', 'NAVEGA']
    if any(f in texto for f in jerga_solucionado): return False
    
    # Detección directa
    keywords_directas = ['OFFLINE', 'OFF LINE', 'OFF-LINE', 'SIN SEÑAL', 'SIN INTERNET', 'LOS RED']
    if any(word in texto for word in keywords_directas): return True
    
    # Detección por patrones técnicos
    keywords_ambiguas = [r'\bLOS\b', r'\bONT\b', r'\bONU\b']
    terminos_tecnicos = ['POTENCIA', 'DB', 'PON', 'ROJO', 'DATOS', 'RX', 'TX']
    
    if re.search('|'.join(keywords_ambiguas), texto):
        if any(tec in texto for tec in terminos_tecnicos):
            return True
    return False

# 4. FUNCIÓN DE COTEJO PARA AUDITORÍA (Para historico.py)
def es_alerta_administrativa(row):
    """
    Detecta órdenes que debieron quedar CERRADAS (por anulación/devolución)
    pero quedaron en estados como INACTIVO mientras el comentario dice que no se instaló.
    """
    estado_sis = str(row.get('ESTADO', '')).upper().strip()
    comentario_tec = str(row.get('COMENTARIO', '')).upper()
    
    # Si el estado NO es el final correcto ('CERRADA' o 'ANULADA')
    # Y está dentro de los estados que generan cobro o mora (Riesgo)
    if any(est == estado_sis for est in ESTADOS_RIESGO):
        # Y el técnico dejó evidencia de que la instalación NO se hizo
        if any(neg in comentario_tec for neg in JERGA_NO_INSTALABLE):
            return True
            
    return False

# 5. PROCESADOR DE DATAFRAME UNIVERSAL
def procesar_dataframe_base(df):
    """Limpia espacios en encabezados y aplica el mapeo de nombres de columnas"""
    df.columns = df.columns.str.strip()
    rename_dict = {}
    for internal_name, options in COLUMNS_MAPPING.items():
        for opt in options:
            if opt in df.columns:
                rename_dict[opt] = internal_name
                break
    return df.rename(columns=rename_dict)