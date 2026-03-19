import streamlit as st
import pandas as pd
import os
import plotly.express as px
from datetime import datetime, timedelta
import re

try:
    from tools import *
except ImportError:
    st.error("⚠️ No se encontró 'tools.py'.")

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(layout="wide", page_title="Monitor Operativo Maxcom PRO", page_icon="⚡")

# --- DIÁLOGO DE DETALLES ---
@st.dialog("Detalle de Gestión")
def mostrar_comentario_cierre(fila):
    st.markdown(f"### 📋 Orden: {fila['NUM']}")
    st.write(f"**Cliente:** {fila['CLIENTE']} | **Estado:** {fila['ESTADO']}")
    st.write(f"**Técnico:** {fila['TECNICO']} ({fila.get('MX', 'S/N')})")
    st.divider()
    st.info(fila['COMENTARIO'] if pd.notnull(fila['COMENTARIO']) else "Sin comentarios registrados.")
    if st.button("Cerrar"): st.rerun()

# --- CARGA Y LIMPIEZA ---
@st.cache_data(show_spinner="Actualizando base de datos...")
def cargar_y_limpiar(path):
    if not os.path.exists(path): return None
    try:
        xls = pd.ExcelFile(path)
        df = pd.read_excel(xls, sheet_name='Prueba', dtype={'NUM': str})
        df = procesar_dataframe_base(df)
        
        if 'utilerias' in xls.sheet_names:
            df_u = pd.read_excel(xls, sheet_name='utilerias')
            df_u.columns = df_u.columns.str.strip()
            if 'TECNICO' in df_u.columns:
                col_mx = next((c for c in ['MX','VEHICULO','UNIDAD'] if c in df_u.columns), None)
                if col_mx:
                    m = df_u[['TECNICO', col_mx]].dropna().drop_duplicates('TECNICO')
                    df = df.merge(m, on='TECNICO', how='left').rename(columns={col_mx: 'MX_final'})
                    df['MX'] = df['MX_final'].combine_first(df.get('MX', pd.Series(dtype=str)))

        for c in ['HORA_INI', 'HORA_LIQ', 'FECHA_APE']:
            if c in df.columns: df[c] = pd.to_datetime(df[c], dayfirst=True, errors='coerce')

        hoy_dt = pd.Timestamp(datetime.now())
        limite = hoy_dt - timedelta(days=7) 
        df = df[(df['HORA_LIQ'] >= limite) | (df['FECHA_APE'] >= limite) | (df['HORA_LIQ'].isna())].copy()

        df['DIAS_RETRASO'] = (hoy_dt.normalize() - df['FECHA_APE'].dt.normalize()).dt.days.fillna(0).clip(lower=0).astype(int)
        
        # --- LÓGICA DE DETECCIÓN OFFLINE PRECISA ---
        def detectar_offline_real(row):
            actividad = str(row.get('ACTIVIDAD', '')).upper()
            comentario = str(row.get('COMENTARIO', '')).upper()
            palabras_ins = ['INS', 'NUEVA', 'ADIC', 'CAMBIO', 'RECU']
            if any(p in actividad for p in palabras_ins): return False
            return es_offline_preciso(comentario)

        df['ES_OFFLINE'] = df.apply(detectar_offline_real, axis=1)
        df['MINUTOS_CALC'] = (df['HORA_LIQ'] - df['HORA_INI']).dt.total_seconds() / 60
        
        def asignar_segmento(row):
            texto = f"{row.get('ACTIVIDAD', '')} {row.get('CLIENTE', '')} {row.get('COMENTARIO', '')}".upper()
            return 'PLEX' if 'PLEX' in texto else 'RESIDENCIAL'
        df['SEGMENTO'] = df.apply(asignar_segmento, axis=1)
        
        def format_duracion(row):
            if pd.isnull(row['HORA_INI']) or pd.isnull(row['HORA_LIQ']): return "---"
            d = row['HORA_LIQ'] - row['HORA_INI']
            h, rem = divmod(d.total_seconds(), 3600)
            m, _ = divmod(rem, 60)
            return f"{int(h)}h {int(m)}m"
        df['TIEMPO_REAL'] = df.apply(format_duracion, axis=1)

        return df
    except Exception as e:
        st.error(f"Error: {e}"); return None

# --- ESTILOS ---
def aplicar_estilos_df(df):
    df_display = df.copy()
    def row_styler(row):
        styles = [''] * len(row)
        if row.get('ES_OFFLINE') == True:
            if 'NUM' in row.index: styles[row.index.get_loc('NUM')] = 'background-color: #9b111e; color: white; font-weight: bold'
        if 'DIAS_RETRASO' in row.index:
            idx_d = row.index.get_loc('DIAS_RETRASO'); d = row['DIAS_RETRASO']
            if d >= 7: styles[idx_d] = 'background-color: #d32f2f; color: white'
            elif 4 <= d <= 6: styles[idx_d] = 'background-color: #ef6c00; color: white'
            elif 1 <= d <= 3: styles[idx_d] = 'background-color: #fdd835; color: black'
            elif d == 0: styles[idx_d] = 'background-color: #4caf50; color: white'
        if pd.notnull(row.get('HORA_INI')) and pd.isnull(row.get('HORA_LIQ')):
            if 'HORA_INI' in row.index: styles[row.index.get_loc('HORA_INI')] = 'background-color: #2196F3; color: white'
        return styles

    for col in ['HORA_INI', 'HORA_LIQ']:
        if col in df_display.columns: df_display[col] = df_display[col].dt.strftime('%H:%M').fillna("---")
    
    display_cols = ['DIAS_RETRASO', 'NUM', 'CLIENTE', 'ACTIVIDAD', 'SECTOR', 'TECNICO', 'MX', 'HORA_INI', 'HORA_LIQ', 'TIEMPO_REAL', 'ESTADO', 'COMENTARIO', 'ES_OFFLINE']
    cols_p = [c for c in display_cols if c in df_display.columns]
    return df_display[cols_p], row_styler

# --- MAIN ---
def main():
    path = os.path.join(os.path.dirname(__file__), 'reporte.xlsx')
    df_base = cargar_y_limpiar(path)
    hoy_dt = datetime.now().date()
    patron_act = 'PENDIENTE|INICIADA|PROCESO|ASIGNADA|DESPACHO'
    
    if df_base is None: return

    with st.sidebar:
        st.title("🧭 Panel PRO")
        nav = st.radio("Navegación:", ["⚡ Monitor", "📚 Histórico Asignadas", "🚫 NOINSTALADO", "📦 Cierre Diario"])
        
        # --- FILTROS LATERALES ---
        if nav == "⚡ Monitor":
            st.divider()
            st.header("🔍 Filtros")
            mask_asignadas = df_base['ESTADO'].str.contains(patron_act, na=False, case=False)
            total_off_asig = int((df_base['ES_OFFLINE'] & mask_asignadas).sum())
            solo_off = st.toggle(f"Ver solo Offline Asignadas ({total_off_asig})")
            tec_sel = st.selectbox("👤 Técnico:", ["Todos"] + sorted(df_base['TECNICO'].dropna().unique()))
            sec_sel = st.selectbox("📍 Sector:", ["Todos"] + sorted(df_base['SECTOR'].dropna().unique()))
            act_sel = st.multiselect("🛠️ Actividades:", sorted(df_base['ACTIVIDAD'].dropna().unique()))
            
            df_f = df_base.copy()
            if solo_off: df_f = df_f[df_f['ES_OFFLINE'] & mask_asignadas]
            if tec_sel != "Todos": df_f = df_f[df_f['TECNICO'] == tec_sel]
            if sec_sel != "Todos": df_f = df_f[df_f['SECTOR'] == sec_sel]
            if act_sel: df_f = df_f[df_f['ACTIVIDAD'].isin(act_sel)]
        else:
            df_f = df_base

        # --- BOTÓN DE REPORTE GERENCIAL (RESTAURADO) ---
        st.divider()
        if st.button("📄 GENERAR REPORTE EFICIENCIA", use_container_width=True):
            pdf_efi = logica_generar_pdf(df_base)
            st.download_button("Descargar PDF", data=pdf_efi, file_name="Eficiencia_7D.pdf", mime="application/pdf", use_container_width=True)

    # --- PÁGINAS ---
    if nav == "📦 Cierre Diario":
        st.title("📦 Cierre de Jornada")
        fecha_sel = st.date_input("Fecha:", value=hoy_dt)
        df_c = df_base[(df_base['HORA_LIQ'].dt.date == fecha_sel) & (df_base['ESTADO'].str.contains('CERRADA', na=False))]
        if st.button("🚀 GENERAR PDF DE CIERRE"):
            pdf = generar_pdf_cierre_diario(df_base, fecha_sel)
            st.download_button("Descargar", data=pdf, file_name=f"Cierre_{fecha_sel}.pdf")
        st.dataframe(df_c[['NUM', 'TECNICO', 'ACTIVIDAD', 'TIEMPO_REAL']], use_container_width=True)
        return

    if nav == "🚫 NOINSTALADO":
        st.title("🚫 NOINSTALADO (Hoy)")
        mask = (df_base['ACTIVIDAD'].str.upper().str.contains('NOINSTALADO', na=False)) & (df_base['HORA_LIQ'].dt.date == hoy_dt)
        st.dataframe(df_base[mask][['NUM','CLIENTE','TECNICO','HORA_LIQ','COMENTARIO']], use_container_width=True)
        return

    if nav == "📚 Histórico Asignadas":
        from historico import main_historico; main_historico(); return

    # --- MONITOR KPIs ---
    df_hoy = df_f[(df_f['HORA_LIQ'].dt.date == hoy_dt) | (df_f['HORA_LIQ'].isna())].copy()
    df_kpi = df_hoy[df_hoy['ESTADO'].str.contains(patron_act, na=False, case=False)]

    st.title("⚡ Monitor Operativo Maxcom")

    with st.expander("📊 CARGA DE TRABAJO ACTUAL (SOLO ASIGNADAS)", expanded=True):
        c_dias, c_sop, c_ins, c_otros = st.columns([1, 1.2, 1.2, 1])
        with c_dias:
            st.caption("📅 Resumen de Retraso")
            df_kpi['CatD'] = df_kpi['DIAS_RETRASO'].apply(lambda d: ">= 7 Dia" if d>=7 else (f"= {d} Dia"))
            res_d = df_kpi['CatD'].value_counts().reindex([">= 7 Dia", "= 4 Dia", "= 1 Dia", "= 0 Dia"], fill_value=0).reset_index()
            res_d.columns = ['Dias', 'Cant']
            tot = res_d['Cant'].sum()
            res_d['%'] = res_d['Cant'].apply(lambda x: f"{(x/tot*100):.0f}%" if tot > 0 else "0%")
            st.dataframe(res_d, hide_index=True, use_container_width=True)

        with c_sop:
            st.caption("🛠️ SOP / Mantenimiento")
            act_k = df_kpi['ACTIVIDAD'].str.upper()
            com_k = df_kpi['COMENTARIO'].str.upper()
            res_s = {
                "RECONEXION": len(df_kpi[act_k.str.contains("RECONEX", na=False)]),
                "FTTH / FIBRA": len(df_kpi[act_k.str.contains("FIBRA|FTTH", na=False)]),
                "ONT/ONU Offline": int(df_kpi['ES_OFFLINE'].sum()),
                "Niveles / Señal": len(df_kpi[com_k.str.contains("NIVEL|DB|SEÑAL", na=False)])
            }
            st.dataframe(pd.DataFrame(list(res_s.items()), columns=['SOP', 'Cant']), hide_index=True, use_container_width=True)

        with c_ins:
            st.caption("📦 Instalaciones")
            res_i = {
                "Adicion": len(df_kpi[act_k.str.contains("ADIC", na=False)]),
                "Cambio Medio": len(df_kpi[act_k.str.contains("CAMBIO", na=False)]),
                "Nueva": len(df_kpi[act_k.str.contains("NUEVA|INS", na=False) & ~act_k.str.contains("SOP", na=False)]),
                "Recuperado": len(df_kpi[act_k.str.contains("RECUP", na=False)])
            }
            st.dataframe(pd.DataFrame(list(res_i.items()), columns=['Instalaciones', 'Cant']), hide_index=True, use_container_width=True)

        with c_otros:
            st.caption("⚙️ Otros")
            df_o = df_kpi[~act_k.str.contains("SOP|FALLA|MANT|INS|NUEVA|ADIC|CAMBIO|RECONEX", na=False)]
            st.dataframe(df_o['ACTIVIDAD'].value_counts().reset_index().head(5), hide_index=True, use_container_width=True)

    with st.expander("📊 CONSOLIDADO PLEX / RESIDENCIAL", expanded=False):
        res_p = df_kpi.groupby(['TECNICO', 'SEGMENTO']).size().reset_index(name='Cant')
        col1, col2 = st.columns(2)
        with col1:
            st.write("🏢 PLEX ASIGNADOS"); st.dataframe(res_p[res_p['SEGMENTO']=='PLEX'][['TECNICO','Cant']], hide_index=True, use_container_width=True)
        with col2:
            st.write("🏠 RESIDENCIAL ASIGNADOS"); st.dataframe(res_p[res_p['SEGMENTO']=='RESIDENCIAL'][['TECNICO','Cant']], hide_index=True, use_container_width=True)

    st.divider()
    if 'status_v' not in st.session_state: st.session_state.status_v = "PENDIENTE"
    b1, b2, b3 = st.columns(3)
    if b1.button("⏳ ACTIVAS", use_container_width=True): st.session_state.status_v = "PENDIENTE"; st.rerun()
    if b2.button("✅ CERRADAS HOY", use_container_width=True): st.session_state.status_v = "C_HOY"; st.rerun()
    if b3.button("❌ ANULADAS HOY", use_container_width=True): st.session_state.status_v = "A_HOY"; st.rerun()

    status = st.session_state.status_v
    df_v_hoy = df_f[(df_f['HORA_LIQ'].dt.date == hoy_dt) | (df_f['HORA_LIQ'].isna())].copy()

    if status == "PENDIENTE": df_view = df_kpi
    elif status == "C_HOY": df_view = df_v_hoy[(df_v_hoy['ESTADO'].str.contains('CERRADA', na=False)) & (df_v_hoy['HORA_LIQ'].dt.date == hoy_dt)]
    else: df_view = df_v_hoy[(df_v_hoy['ESTADO'].str.contains('ANULADA', na=False)) & (df_v_hoy['HORA_LIQ'].dt.date == hoy_dt)]

    t1, t2 = st.tabs(["📋 PANEL", "📊 GANTT"])
    with t1:
        if not df_view.empty:
            df_s, styler = aplicar_estilos_df(df_view)
            event = st.dataframe(df_s.style.apply(styler, axis=1).hide(axis=1, subset=['ES_OFFLINE']), use_container_width=True, height=500, hide_index=True, on_select="rerun", selection_mode="single-row")
            if event.selection.rows: mostrar_comentario_cierre(df_view.iloc[event.selection.rows[0]])
    with t2:
        df_g = df_view[df_view['HORA_INI'].notnull()].copy()
        if not df_g.empty:
            df_g['FIN'] = df_g['HORA_LIQ'].fillna(datetime.now())
            fig = px.timeline(df_g, x_start="HORA_INI", x_end="FIN", y="TECNICO", color="ACTIVIDAD", template="plotly_dark", height=600)
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__": main()
