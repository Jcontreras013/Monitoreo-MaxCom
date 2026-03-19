import pandas as pd
import re
from fpdf import FPDF
from datetime import datetime, timedelta

# 1. MAPEO UNIVERSAL DE COLUMNAS
# Permite que el sistema reconozca el Excel aunque cambien ligeramente los nombres
COLUMNS_MAPPING = {
    'HORA_INI': ['HORA ENTRADA', 'HORA INICIO', 'HORA_INICIO_ORDEN', 'FECHA ENTRADA'],
    'HORA_LIQ': ['HORA LIQUIDADO', 'HORA CIERRE', 'HORA_CIERRE_ORDEN', 'FECHA LIQUIDADO'],
    'TECNICO': ['TÉCNICO', 'TECNICO', 'OPERADOR'],
    'ACTIVIDAD': ['NOMBRE ACTIVIDAD', 'TIPO ORDEN', 'ACTIVIDAD'],
    'FECHA_APE': ['FECHA APERTURA', 'APERTURA', 'DIAS_ASIGNADA', 'Días'],
    'ESTADO': ['ESTADO', 'STATUS'],
    'SECTOR': ['SECTOR', 'Sect', 'Sector', 'CIUDAD', 'Ciudad'],
    'COLONIA': ['COLONIA', 'BARRIO', 'DIRECCION', 'LOCALIDAD'],
    'NUM': ['NUM', 'ID_ORDEN', 'NÚMERO'],
    'CLIENTE': ['CLIENTE', 'NOMBRE CLIENTE', 'SUSCRIPTOR'],
    'COMENTARIO': ['COMENTARIO', 'OBSERVACIONES'],
    'MX': ['MX', 'VEHICULO', 'UNIDAD']
}

# 2. LISTAS PARA AUDITORÍA DE FACTURACIÓN
ESTADOS_RIESGO = ['INACTIVO', 'ACTCCVEO', 'ACTIVARRES', 'ANULAFACTURA', 'CORTEMORA', 'NOINSTALADO']
JERGA_NO_INSTALABLE = ['NO SE PUDO', 'NO INSTALADO', 'CLIENTE NO QUISO', 'SIN ACCESO', 'CANCELADA', 'FACHADA', 'POSTE LEJOS']

# --- CLASE BASE PARA ESTRUCTURA DEL PDF ---
class ReporteGenerencialPDF(FPDF):
    def header(self):
        # Encabezado azul corporativo (Estilo Macro)
        self.set_fill_color(31, 73, 125)
        self.rect(0, 0, 210, 30, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "SISTEMA DE CONTROL OPERATIVO - MAXCOM", ln=True, align="C")
        self.set_font("Arial", "", 9)
        self.cell(0, 5, f"Fecha de Emisión: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
        self.ln(15)

    def seccion_titulo(self, t):
        self.set_text_color(0, 0, 0)
        self.set_fill_color(235, 235, 235)
        self.set_font("Arial", "B", 10)
        self.cell(0, 8, f" {t}", ln=True, fill=True)
        self.ln(2)

    def dibujar_tabla(self, df, anchos=None):
        if df.empty: return
        self.set_font("Arial", "B", 8)
        self.set_fill_color(200, 200, 200)
        
        # Calcular anchos automáticos si no se pasan
        w_total = 190
        w = w_total / len(df.columns) if not anchos else anchos
        
        for i, col in enumerate(df.columns):
            width = w if isinstance(w, (int, float)) else w[i]
            self.cell(width, 7, str(col).upper()[:15], border=1, align="C", fill=True)
        self.ln()
        
        self.set_font("Arial", "", 7)
        for _, fila in df.iterrows():
            for i, item in enumerate(fila):
                width = w if isinstance(w, (int, float)) else w[i]
                self.cell(width, 6, str(item)[:30], border=1, align="C")
            self.ln()
        self.ln(5)

# --- FUNCIÓN 1: REPORTE GERENCIAL (PRODUCTIVIDAD) ---
def logica_generar_pdf(df_base):
    pdf = ReporteGenerencialPDF()
    pdf.add_page()
    
    # Análisis de Eficiencia (8 Horas = 480 Min)
    pdf.seccion_titulo("INDICADORES DE EFICIENCIA POR TÉCNICO (JORNADA 8H)")
    res_tec = df_base.groupby('TECNICO').agg(
        Ordenes=('NUM', 'count'),
        Minutos=('MINUTOS_CALC', 'sum')
    ).reset_index()
    
    res_tec['Minutos'] = res_tec['Minutos'].fillna(0).round(0)
    res_tec['Ocupacion'] = ((res_tec['Minutos'] / 480) * 100).round(1).astype(str) + "%"
    res_tec['Disp_Restante'] = (480 - res_tec['Minutos']).clip(lower=0).astype(int).astype(str) + " min"
    
    pdf.dibujar_tabla(res_tec, anchos=[60, 30, 30, 35, 35])

    # Gráfico Gantt Simulado (Barras de tiempo)
    pdf.seccion_titulo("LÍNEA DE TIEMPO OPERATIVA (GANTT)")
    df_g = df_base[df_base['MINUTOS_CALC'] > 0].sort_values(['TECNICO', 'HORA_INI'])
    for tec in df_g['TECNICO'].unique()[:15]:
        pdf.set_font("Arial", "B", 8)
        pdf.cell(40, 5, str(tec)[:25])
        pdf.set_fill_color(100, 150, 250)
        # Escala: 1 unit = 4 min
        ancho_barra = min(df_g[df_g['TECNICO']==tec]['MINUTOS_CALC'].sum() / 4, 140)
        pdf.cell(ancho_barra, 4, "", fill=True, border=1)
        pdf.ln(6)

    return finalizar_pdf(pdf)

# --- FUNCIÓN 2: REPORTE DE CIERRE DIARIO (ARCHIVO DE RESPALDO) ---
def generar_pdf_cierre_diario(df_base):
    pdf = ReporteGenerencialPDF()
    pdf.add_page()
    
    hoy = datetime.now().date()
    # Filtrar datos de producción real de hoy
    df_cerradas = df_base[(df_base['HORA_LIQ'].dt.date == hoy) & (df_base['ESTADO'].str.contains('CERRADA', na=False, case=False))]
    df_pendientes = df_base[df_base['ESTADO'].str.contains('PENDIENTE|ASIGNADA|PROCESO|DESPACHO', na=False, case=False)]

    pdf.seccion_titulo(f"RESUMEN DE CIERRE DIARIO - {hoy.strftime('%d/%m/%Y')}")
    
    resumen_data = pd.DataFrame({
        'CONCEPTO': ['Órdenes Cerradas Hoy', 'Órdenes Pendientes (Backlog)', 'Efectividad Diaria'],
        'TOTAL': [
            len(df_cerradas),
            len(df_pendientes),
            f"{round((len(df_cerradas)/(len(df_cerradas)+len(df_pendientes))*100),1)}%" if (len(df_cerradas)+len(df_pendientes)) > 0 else "0%"
        ]
    })
    pdf.dibujar_tabla(resumen_data, anchos=[130, 60])

    pdf.seccion_titulo("DETALLE DE PRODUCCIÓN (CERRADAS HOY)")
    if not df_cerradas.empty:
        pdf.dibujar_tabla(df_cerradas[['NUM', 'TECNICO', 'ACTIVIDAD', 'TIEMPO_REAL']].head(40))

    pdf.add_page()
    pdf.seccion_titulo("PENDIENTES QUE PASAN AL SIGUIENTE DÍA")
    if not df_pendientes.empty:
        pdf.dibujar_tabla(df_pendientes[['NUM', 'CLIENTE', 'TECNICO', 'DIAS_RETRASO']].head(45))

    return finalizar_pdf(pdf)

# --- UTILIDAD: CONVERSIÓN A BYTES PARA STREAMLIT ---
def finalizar_pdf(pdf):
    try:
        # Intenta obtener salida directa (fpdf2)
        out = pdf.output()
        if isinstance(out, bytearray) or isinstance(out, bytes):
            return bytes(out)
        return out.encode('latin-1')
    except:
        # Fallback para fpdf clásica
        return bytes(pdf.output(dest='S'), encoding='latin-1')

# --- LÓGICA DE DETECCIÓN OFFLINE ---
def es_offline_preciso(com):
    t = str(com).upper().strip()
    if not t or t == 'NAN': return False
    # Palabras que descartan una falla real
    if any(x in t for x in ['OK', 'LISTO', 'RECUPERADO', 'SOLUCIONADO', 'NAVEGA', 'YA QUEDO']): return False
    # Palabras que confirman falla
    keywords = ['OFFLINE', 'SIN INTERNET', 'LOS RED', 'ROJO', 'SIN SEÑAL', 'ONT', 'ONU', 'DATOS']
    return any(word in t for word in keywords)

# --- FUNCIÓN DE COTEJO PARA AUDITORÍA ---
def es_alerta_administrativa(row):
    estado = str(row.get('ESTADO', '')).upper().strip()
    comentario = str(row.get('COMENTARIO', '')).upper()
    if any(est == estado for est in ESTADOS_RIESGO):
        if any(neg in comentario for neg in JERGA_NO_INSTALABLE): return True
    return False

# --- PROCESADOR DE DATAFRAME UNIVERSAL ---
def procesar_dataframe_base(df):
    df.columns = df.columns.str.strip()
    rename_dict = {}
    for internal_name, options in COLUMNS_MAPPING.items():
        for opt in options:
            if opt in df.columns:
                rename_dict[opt] = internal_name
                break
    return df.rename(columns=rename_dict)
