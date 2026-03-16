import streamlit as st
import pandas as pd
import os
import plotly.express as px
# Importamos las herramientas compartidas
from tools import procesar_dataframe_base, es_alerta_administrativa

def main_historico():
    st.title("📚 Centro de Auditoría e Históricos")
    st.markdown("---")

    dir_app = os.path.dirname(os.path.abspath(__file__))
    path_xlsx = os.path.join(dir_app, 'reporte.xlsx')

    if not os.path.exists(path_xlsx):
        st.error("⚠️ No se encontró el archivo 'reporte.xlsx'.")
        return

    try:
        # 1. CARGA DE DATOS (Hoja de Históricos)
        df_raw = pd.read_excel(path_xlsx, sheet_name='Historico_No_Instaladas', dtype={'NUM': str})
        
        # 2. LIMPIEZA INICIAL
        df_h = procesar_dataframe_base(df_raw)
        
        # 3. IDENTIFICACIÓN DE ÓRDENES MAL CERRADAS
        # Aplicamos la lógica de cotejo que pediste (Estado vs Comentario)
        df_h['ALERTA_AUDIT'] = df_h.apply(es_alerta_administrativa, axis=1)

        # --- PESTAÑAS DE TRABAJO ---
        tab_auditoria, tab_general = st.tabs(["🚨 AUDITORÍA DE FACTURACIÓN", "📋 HISTORIAL COMPLETO"])

        with tab_auditoria:
            st.subheader("Órdenes con Riesgo de Facturación Indebida")
            st.write("Estas órdenes tienen estados administrativos (INACTIVO, ACTCCVEO, etc.) pero el técnico reportó que NO se instaló.")
            
            # Filtramos solo las que tienen la alerta
            df_audit = df_h[df_h['ALERTA_AUDIT'] == True].copy()
            
            if not df_audit.empty:
                st.error(f"Se han detectado {len(df_audit)} casos críticos que requieren corrección en sistema.")
                
                # Buscador interno para la auditoría
                search_audit = st.text_input("🔍 Filtrar auditoría (Cliente/NUM):", key="search_audit")
                if search_audit:
                    df_audit = df_audit[df_audit.apply(lambda r: search_audit.lower() in str(r).lower(), axis=1)]

                st.dataframe(
                    df_audit.drop(columns=['ALERTA_AUDIT']), 
                    use_container_width=True, 
                    height=400,
                    hide_index=True
                )
                
                # Botón para descargar y pasar a facturación
                csv = df_audit.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Reporte para Corrección",
                    data=csv,
                    file_name=f"auditoria_riesgo_{pd.Timestamp.now().strftime('%d_%m_%Y')}.csv",
                    mime="text/csv",
                )
            else:
                st.success("✅ No se detectaron discrepancias entre estados y comentarios.")

        with tab_general:
            st.subheader("Buscador de Histórico General")
            
            # Filtros laterales para el histórico
            col1, col2 = st.columns(2)
            with col1:
                if 'TECNICO' in df_h.columns:
                    tec_h = st.selectbox("Filtrar Técnico:", ["Todos"] + sorted(df_h['TECNICO'].dropna().unique().tolist()))
            with col2:
                search_h = st.text_input("🔍 Buscar en todo el histórico:")

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
        st.error(f"❌ Error al procesar la hoja 'Historico_No_Instaladas': {e}")

if __name__ == "__main__":
    main_historico()