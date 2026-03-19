import streamlit as st
import pandas as pd
import os
# Importamos las herramientas compartidas
from tools import procesar_dataframe_base, es_alerta_administrativa

def main_historico():
    st.title("📚 Centro de Auditoría (Órdenes Asignadas)")
    st.markdown("---")

    dir_app = os.path.dirname(os.path.abspath(__file__))
    path_xlsx = os.path.join(dir_app, 'reporte.xlsx')

    if not os.path.exists(path_xlsx):
        st.error("⚠️ No se encontró el archivo 'reporte.xlsx'.")
        return

    try:
        # 1. CARGA DE DATOS
        df_raw = pd.read_excel(path_xlsx, sheet_name='Historico_No_Instaladas', dtype={'NUM': str})
        
        # 2. LIMPIEZA INICIAL
        df_h = procesar_dataframe_base(df_raw)
        
        # --- NUEVO: FILTRO DE ÓRDENES ASIGNADAS/ACTIVAS ---
        # Definimos el mismo patrón que usamos en app.py para consistencia
        patron_activos = 'PENDIENTE|INICIADA|PROCESO|ASIGNADA|DESPACHO'
        
        # Aplicamos el filtro para que solo trabaje con lo que está "vivo"
        df_h = df_h[df_h['ESTADO'].str.contains(patron_activos, na=False, case=False)].copy()

        if df_h.empty:
            st.warning("✅ No hay órdenes asignadas o pendientes en la base de datos de Histórico.")
            return

        # 3. IDENTIFICACIÓN DE ÓRDENES MAL CERRADAS (Auditoría)
        df_h['ALERTA_AUDIT'] = df_h.apply(es_alerta_administrativa, axis=1)

        # --- PESTAÑAS DE TRABAJO ---
        tab_auditoria, tab_general = st.tabs(["🚨 AUDITORÍA DE FACTURACIÓN (PENDIENTES)", "📋 BUSCADOR DE ASIGNADAS"])

        with tab_auditoria:
            st.subheader("Riesgo de Facturación Indebida (Órdenes Activas)")
            st.write("Muestra órdenes en sistema con estado administrativo pero donde el técnico reportó que NO instaló.")
            
            # Filtramos solo las que tienen la alerta
            df_audit = df_h[df_h['ALERTA_AUDIT'] == True].copy()
            
            if not df_audit.empty:
                st.error(f"Se han detectado {len(df_audit)} casos críticos en proceso que requieren corrección.")
                
                search_audit = st.text_input("🔍 Filtrar auditoría (Cliente/NUM):", key="search_audit")
                if search_audit:
                    df_audit = df_audit[df_audit.apply(lambda r: search_audit.lower() in str(r).lower(), axis=1)]

                st.dataframe(
                    df_audit.drop(columns=['ALERTA_AUDIT']), 
                    use_container_width=True, 
                    height=400,
                    hide_index=True
                )
            else:
                st.success("✅ No se detectaron discrepancias en las órdenes actuales.")

        with tab_general:
            st.subheader("Buscador de Órdenes Pendientes")
            
            col1, col2 = st.columns(2)
            with col1:
                if 'TECNICO' in df_h.columns:
                    tec_list = ["Todos"] + sorted(df_h['TECNICO'].dropna().unique().tolist())
                    tec_h = st.selectbox("Filtrar Técnico:", tec_list)
            with col2:
                search_h = st.text_input("🔍 Buscar por Cliente o Número:")

            df_display = df_h.copy()
            if tec_h != "Todos":
                df_display = df_display[df_display['TECNICO'] == tec_h]
            if search_h:
                df_display = df_display[df_display.apply(lambda r: search_h.lower() in str(r).lower(), axis=1)]

            st.dataframe(
                df_display.drop(columns=['ALERTA_AUDIT']), 
                use_container_width=True, 
                height=500,
                hide_index=True
            )

    except Exception as e:
        st.error(f"❌ Error al procesar la hoja de históricos: {e}")

if __name__ == "__main__":
    main_historico()
