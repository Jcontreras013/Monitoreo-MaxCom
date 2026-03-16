import streamlit as st
import pandas as pd
import os
import plotly.express as px
from datetime import datetime
import re
# IMPORTACIÓN DE TUS HERRAMIENTAS
from tools import COLUMNS_MAPPING, es_offline_preciso, procesar_dataframe_base

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    layout="wide", 
    page_title="Monitor Operativo Maxcom",
    page_icon="⚡"
)

# --- VENTANA EMERGENTE PARA COMENTARIOS ---
@st.dialog("Detalle de Gestión")
def mostrar_comentario_cierre(fila):
    st.markdown(f"### Orden: {fila['NUM']}")
    st.write(f"**Cliente:** {fila['CLIENTE']}")
    st.write(f"**Estado:** {fila['ESTADO']}")
    st.divider()
    st.markdown("**Comentario de Cierre:**")
    st.info(fila['COMENTARIO'] if pd.notnull(fila['COMENTARIO']) else "Sin comentarios.")

# --- LÓGICA DE PROCESAMIENTO COMPLETA ---
@st.cache_data
def cargar_y_limpiar(file_path):
    if not os.path.exists(file_path): return None
    try:
        xls = pd.ExcelFile(file_path)
        df = pd.read_excel(xls, sheet_name='Prueba', dtype={'NUM': str})
        
        df = procesar_dataframe_base(df)

        if 'utilerias' in xls.sheet_names:
            df_util = pd.read_excel(xls, sheet_name='utilerias')
            df_util.columns = df_util.columns.str.strip()
            if 'TECNICO' in df_util.columns and ('MX' in df_util.columns or 'VEHICULO' in df_util.columns):
                col_v = 'MX' if 'MX' in df_util.columns else 'VEHICULO'
                mapeo_v = df_util[['TECNICO', col_v]].dropna().drop_duplicates('TECNICO')
                df = df.merge(mapeo_v, on='TECNICO', how='left')
                df = df.rename(columns={col_v: 'MX_final'})
                if 'MX' in df.columns: df['MX'] = df['MX_final'].combine_first(df['MX'])
                else: df['MX'] = df['MX_final']

        for col in ['HORA_INI', 'HORA_LIQ', 'FECHA_APE']:
            if col in df.columns: df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')

        hoy_dt = pd.Timestamp(datetime.now())
        if 'FECHA_APE' in df.columns:
            hoy_norm = hoy_dt.normalize()
            condicion = (df['HORA_LIQ'].dt.normalize() == hoy_norm) | \
                        (df['FECHA_APE'].dt.normalize() == hoy_norm) | \
                        (df['HORA_LIQ'].isna())
            df = df[condicion].copy()

        # --- LÓGICA DE OFFLINE BLINDADA ---
        df['ES_OFFLINE'] = df.apply(es_offline_preciso, axis=1)
        
        def validar_si_es_critico(row):
            estado = str(row.get('ESTADO', '')).upper()
            if row.get('HORA_LIQ') is not pd.NaT and pd.notnull(row.get('HORA_LIQ')): return False
            if 'PENDIENTE' not in estado: return False
            
            actividad = str(row.get('ACTIVIDAD', '')).upper()
            comentario = str(row.get('COMENTARIO', '')).upper()
            palabras_ignorar = ["INSTALACION", "INSFIBRA", "INSTALACIÓN"]
            if any(p in actividad for p in palabras_ignorar) or any(p in comentario for p in palabras_ignorar):
                return False
                
            return row['ES_OFFLINE']

        df['ES_OFFLINE'] = df.apply(validar_si_es_critico, axis=1)

        delta = df['HORA_LIQ'] - df['HORA_INI']
        df['MINUTOS_CALC'] = delta.dt.total_seconds() / 60
        horas = delta.dt.components.hours.fillna(0).astype(int).astype(str)
        minutos = delta.dt.components.minutes.fillna(0).astype(int).astype(str)
        df['TIEMPO_REAL'] = horas + 'h ' + minutos + 'm'
        df.loc[df['HORA_INI'].isna() | df['HORA_LIQ'].isna(), 'TIEMPO_REAL'] = "---"
        df['DIAS_RETRASO'] = (hoy_dt.normalize() - df['FECHA_APE'].dt.normalize()).dt.days.fillna(0).clip(lower=0).astype(int)
        
        if 'ACTIVIDAD' in df.columns:
            df['SEGMENTO'] = df['ACTIVIDAD'].apply(lambda x: 'PLEX' if 'PLEX' in str(x).upper() else 'RESIDENCIAL')
        
        return df
    except Exception as e:
        st.error(f"❌ Error en carga: {e}")
        return None

# --- LÓGICA DE ESTILOS ---
def aplicar_estilos_df(df):
    df_display = df.copy()
    def row_styler(row):
        styles = [''] * len(row)
        idx_num = row.index.get_loc('NUM') if 'NUM' in row.index else -1
        if row.get('ES_OFFLINE', False) and idx_num != -1:
            styles[idx_num] = 'background-color: #9b111e; color: white; font-weight: bold'
        if 'TIEMPO_REAL' in row.index and pd.notnull(row['MINUTOS_CALC']):
            idx_t = row.index.get_loc('TIEMPO_REAL')
            if row['MINUTOS_CALC'] >= 120: styles[idx_t] = 'background-color: #ef5350; color: white'
            elif 0 < row['MINUTOS_CALC'] < 45: styles[idx_t] = 'background-color: #66bb6a; color: white'
        if 'DIAS_RETRASO' in row.index:
            idx_d = row.index.get_loc('DIAS_RETRASO')
            d = row['DIAS_RETRASO']
            if d >= 7: styles[idx_d] = 'background-color: #FF0000; color: white'
            elif d >= 4: styles[idx_d] = 'background-color: #FFFF00; color: black'
            elif d >= 1: styles[idx_d] = 'background-color: #CCFFCC; color: black'
            else: styles[idx_d] = 'background-color: #00B050; color: white'
        return styles

    for col in ['HORA_INI', 'HORA_LIQ']:
        if col in df_display.columns: df_display[col] = df_display[col].dt.strftime('%H:%M').fillna("---")

    display_cols = ['DIAS_RETRASO', 'NUM', 'CLIENTE', 'ACTIVIDAD', 'SECTOR', 'COLONIA', 'TECNICO', 'MX', 'HORA_INI', 'HORA_LIQ', 'TIEMPO_REAL', 'ESTADO', 'COMENTARIO', 'ES_OFFLINE', 'MINUTOS_CALC']
    cols_presentes = [c for c in display_cols if c in df_display.columns]
    return df_display[cols_presentes], row_styler

# --- INTERFAZ PRINCIPAL ---
def main():
    with st.sidebar:
        st.title("🧭 Menú Principal")
        pagina = st.radio("Selecciona Vista:", ["⚡ Monitor en Vivo", "📚 Histórico No Instaladas"])
        st.divider()

    if pagina == "📚 Histórico No Instaladas":
        from historico import main_historico
        main_historico()
        return

    dir_app = os.path.dirname(os.path.abspath(__file__))
    path_xlsx = os.path.join(dir_app, 'reporte.xlsx')
    df_base = cargar_y_limpiar(path_xlsx)

    if df_base is not None:
        with st.sidebar:
            st.header("🚨 Monitor Crítico")
            total_off = int(df_base['ES_OFFLINE'].sum())
            st.metric("OFFLINE ACTUAL", total_off)
            solo_offline = st.toggle("Ver solo Críticos Offline")
            st.header("🔍 Filtros Operativos")
            tec_sel = st.selectbox("👤 Técnico:", ["-- Todos --"] + sorted(df_base['TECNICO'].dropna().unique()))
            sec_sel = st.selectbox("📍 Sector:", ["-- Todos --"] + sorted(df_base['SECTOR'].dropna().unique())) if 'SECTOR' in df_base.columns else "-- Todos --"
            act_sel = st.multiselect("🛠️ Actividades:", sorted(df_base['ACTIVIDAD'].dropna().unique()))

        df_f = df_base.copy()
        if solo_offline: df_f = df_f[df_f['ES_OFFLINE'] == True]
        if tec_sel != "-- Todos --": df_f = df_f[df_f['TECNICO'] == tec_sel]
        if sec_sel != "-- Todos --": df_f = df_f[df_f['SECTOR'] == sec_sel]
        if act_sel: df_f = df_f[df_f['ACTIVIDAD'].isin(act_sel)]

        st.title("⚡ Monitor Operativo Maxcom")

        if 'status_view' not in st.session_state: st.session_state.status_view = "PENDIENTE"
        status = st.session_state.status_view
        hoy = datetime.now().date()

        if status == "PENDIENTE":
            df_active = df_f[df_f['ESTADO'].str.contains('PENDIENTE', na=False, case=False)]
            label_metrica = "PENDIENTES"
        elif status == "C_HOY":
            df_active = df_f[(df_f['ESTADO'].str.contains('CERRADA', na=False, case=False)) & (df_f['HORA_LIQ'].dt.date == hoy)]
            label_metrica = "CERRADAS"
        else:
            df_active = df_f[(df_f['ESTADO'].str.contains('ANULADA', na=False, case=False)) & (df_f['HORA_LIQ'].dt.date == hoy)]
            label_metrica = "ANULADAS"

        m1, m2, m3 = st.columns(3)
        m1.metric(f"🏢 {label_metrica} PLEX", len(df_active[df_active['SEGMENTO'] == 'PLEX']))
        m2.metric(f"🏠 {label_metrica} RESIDENCIAL", len(df_active[df_active['SEGMENTO'] == 'RESIDENCIAL']))
        m3.metric(f"📋 TOTAL {label_metrica}", len(df_active))
        st.divider()

        c1, c2, c3 = st.columns(3)
        if c1.button("⏳ PENDIENTES", key="btn_p", use_container_width=True): 
            st.session_state.status_view = "PENDIENTE"
            st.rerun()
        if c2.button("✅ CERRADAS HOY", key="btn_c", use_container_width=True): 
            st.session_state.status_view = "C_HOY"
            st.rerun()
        if c3.button("❌ ANULADAS HOY", key="btn_a", use_container_width=True): 
            st.session_state.status_view = "A_HOY"
            st.rerun()

        df_final = df_active

        tab1, tab2 = st.tabs(["📋 PANEL DE CONTROL", "📈 RENDIMIENTO"])
        with tab1:
            if not df_final.empty:
                df_styled, styler = aplicar_estilos_df(df_final)
                event = st.dataframe(
                    df_styled.style.apply(styler, axis=1).hide(['ES_OFFLINE', 'MINUTOS_CALC', 'COMENTARIO'], axis="columns"),
                    use_container_width=True, height=550, on_select="rerun", selection_mode="single-row"
                )
                if event.selection.rows:
                    mostrar_comentario_cierre(df_final.iloc[event.selection.rows[0]])
            else:
                st.warning(f"No hay registros de {label_metrica}.")

        with tab2:
            if not df_final.empty:
                st.subheader("📊 Distribución de Carga")
                res_act = df_final.groupby(['TECNICO', 'ACTIVIDAD']).size().reset_index(name='Cant')
                st.plotly_chart(px.bar(res_act, x='TECNICO', y='Cant', color='ACTIVIDAD', barmode='stack'), use_container_width=True)
                
                st.subheader("⏱️ Tiempos en Campo (Gantt)")
                df_g = df_final.dropna(subset=['HORA_INI', 'HORA_LIQ']).copy()
                if not df_g.empty:
                    # CAMBIO: Se agregó text="ACTIVIDAD" para mostrar el nombre dentro de las barras
                    fig_g = px.timeline(
                        df_g, 
                        x_start="HORA_INI", 
                        x_end="HORA_LIQ", 
                        y="TECNICO", 
                        color="ACTIVIDAD",
                        text="ACTIVIDAD"
                    )
                    fig_g.update_yaxes(autorange="reversed")
                    # Ajuste de posición del texto para que se vea dentro
                    fig_g.update_traces(textposition='inside', textfont_size=10)
                    st.plotly_chart(fig_g, use_container_width=True)

if __name__ == "__main__":
    main()