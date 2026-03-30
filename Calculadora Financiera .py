import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
import io
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN E IDENTIDAD ---
st.set_page_config(page_title="Confidelis - Wealth Management", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f4f6f9; }
    .stButton>button { background-color: #002147; color: #D4AF37; border-radius: 8px; font-weight: bold; width: 100%;}
    .metric-box { background-color: white; padding: 15px; border-radius: 10px; text-align: center; border-top: 4px solid #002147; box-shadow: 0 2px 5px rgba(0,0,0,0.1);}
    .header-box { background-color: #002147; color: #D4AF37; padding: 15px; border-radius: 10px; margin-bottom: 20px;}
    .resumen-card { background-color: #002147; color: white; padding: 20px; border-radius: 10px; border-left: 8px solid #D4AF37; margin-top: 15px;}
    .progress-text { font-weight: bold; color: #002147; font-size: 1.1em;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. VARIABLES DE SESIÓN ---
if 'instrumentos' not in st.session_state: st.session_state.instrumentos = []
if 'monto_base' not in st.session_state: st.session_state.monto_base = 5000000.0
if 'prestamo' not in st.session_state: st.session_state.prestamo = 2000000.0

# --- 3. FUNCIONES DE CÁLCULO Y PDF ---
def generar_df_actual(instrumentos, monto_base):
    if not instrumentos: return pd.DataFrame()
    df = pd.DataFrame(instrumentos)
    df['% Asignación'] = (df['Monto (MXN)'] / monto_base) * 100 if monto_base > 0 else 0
    df['Flujo Anual'] = df['Monto (MXN)'] * (df['Tasa Anual %'] / 100)
    df['Flujo Mensual'] = df['Flujo Anual'] / 12
    return df[['Categoría', 'Instrumento', '% Asignación', 'Monto (MXN)', 'Tasa Anual %', 'Flujo Mensual', 'Flujo Anual', 'Horizonte', 'Liquidez']]

def generar_df_propuesto(instrumentos, monto_base, total_prestamo):
    if not instrumentos: return pd.DataFrame()
    df = pd.DataFrame(instrumentos)
    monto_total_nuevo = monto_base + total_prestamo
    
    df['Monto Anterior'] = df['Monto (MXN)']
    df['Inyección Préstamo'] = df.get('Inyección', 0.0)
    df['Nuevo Saldo'] = df['Monto Anterior'] + df['Inyección Préstamo']
    
    df['% Nuevo Portafolio'] = (df['Nuevo Saldo'] / monto_total_nuevo) * 100 if monto_total_nuevo > 0 else 0
    df['Flujo Extra Mensual'] = (df['Inyección Préstamo'] * (df['Tasa Anual %'] / 100)) / 12
    df['Nuevo Flujo Mensual'] = (df['Nuevo Saldo'] * (df['Tasa Anual %'] / 100)) / 12
    df['Nuevo Flujo Anual'] = df['Nuevo Flujo Mensual'] * 12
    
    return df[['Categoría', 'Instrumento', 'Monto Anterior', 'Inyección Préstamo', 'Nuevo Saldo', '% Nuevo Portafolio', 'Tasa Anual %', 'Flujo Extra Mensual', 'Nuevo Flujo Mensual']]

class ConfidelisPDF(FPDF):
    def header(self):
        self.set_fill_color(0, 33, 71)
        self.rect(0, 0, 297, 30, 'F')
        self.set_font('Arial', 'B', 16)
        self.set_text_color(212, 175, 55)
        self.cell(0, 10, 'CONFIDELIS: ESTRATEGIA PATRIMONIAL', 0, 1, 'C')
        self.ln(5)

def generar_pdf_custom(cliente, modulos, df_act, df_prop, df_flujo, resumen_txt):
    pdf = ConfidelisPDF(orientation='L')
    if "Resumen Ejecutivo" in modulos:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.set_text_color(0, 33, 71)
        pdf.cell(0, 10, f"Resumen Ejecutivo para: {cliente}", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 8, resumen_txt)
    
    def imprimir_tabla(pdf_obj, titulo, df):
        if df.empty: return
        pdf_obj.add_page()
        pdf_obj.set_font("Arial", 'B', 14)
        pdf_obj.set_text_color(0, 33, 71)
        pdf_obj.cell(0, 10, titulo, ln=True)
        pdf_obj.ln(3)
        pdf_obj.set_fill_color(212, 175, 55)
        pdf_obj.set_text_color(255, 255, 255)
        pdf_obj.set_font("Arial", 'B', 7)
        
        cols = df.columns.tolist()
        ancho_col = 277 / len(cols)
        
        for col in cols: pdf_obj.cell(ancho_col, 8, str(col)[:15], 1, 0, 'C', True)
        pdf_obj.ln()
        
        pdf_obj.set_text_color(0, 0, 0)
        pdf_obj.set_font("Arial", size=7)
        for idx, row in df.iterrows():
            es_tot = (idx == 'TOTAL')
            if es_tot:
                pdf_obj.set_font("Arial", 'B', 7)
                pdf_obj.set_fill_color(230, 230, 230)
            for i, val in enumerate(row):
                texto = f"${val:,.0f}" if isinstance(val, (int, float)) and val > 100 else str(val)
                if isinstance(val, float) and val <= 100 and '%' in cols[i]: texto = f"{val:.2f}%"
                if pd.isna(val) or val == "": texto = "-"
                pdf_obj.cell(ancho_col, 8, texto[:20], 1, 0, 'C', fill=es_tot)
            pdf_obj.ln()

    def add_totals(df):
        df_c = df.copy()
        if not df_c.empty:
            t = pd.Series(index=df_c.columns, dtype=object)
            t['Categoría'] = 'TOTAL'; t['Instrumento'] = '-'
            for col in df_c.columns:
                if 'Monto' in col or 'Flujo' in col or 'Saldo' in col or 'Inyección' in col:
                    t[col] = df_c[col].sum()
                elif '%' in col:
                    t[col] = df_c[col].sum() if 'Nuevo Portafolio' in col or 'Asignación' in col else ""
            df_c.loc['TOTAL'] = t
        return df_c

    if "Portafolio Actual" in modulos: imprimir_tabla(pdf, "Portafolio Actual", add_totals(df_act))
    if "Portafolio Propuesto" in modulos: imprimir_tabla(pdf, "Portafolio Propuesto (Apalancado)", add_totals(df_prop))
    if "Desglose de Flujos" in modulos and not df_flujo.empty:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "Proyección de Flujos", ln=True)
        pdf.set_font("Arial", size=8)
        pdf.set_fill_color(0, 33, 71)
        pdf.set_text_color(255, 255, 255)
        for col in df_flujo.columns: pdf.cell(35, 8, col, 1, 0, 'C', True)
        pdf.ln()
        pdf.set_text_color(0, 0, 0)
        for i, r in df_flujo.iterrows():
            if i % 12 == 0 or i == len(df_flujo)-1:
                for val in r:
                    txt = f"${val:,.0f}" if isinstance(val, float) else str(val)
                    pdf.cell(35, 8, txt, 1, 0, 'C')
                pdf.ln()

    return pdf.output(dest='S').encode('latin-1')

def generar_excel_custom(modulos, df_act, df_prop, df_flujo):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        if "Portafolio Actual" in modulos and not df_act.empty: df_act.to_excel(writer, index=False, sheet_name='Actual')
        if "Portafolio Propuesto" in modulos and not df_prop.empty: df_prop.to_excel(writer, index=False, sheet_name='Propuesto')
        if "Desglose de Flujos" in modulos and not df_flujo.empty: df_flujo.to_excel(writer, index=False, sheet_name='Flujos')
    return output.getvalue()

# --- 4. INTERFAZ GRÁFICA ---
st.markdown("<div class='header-box'><h2 style='margin:0;'>🏛️ Estructuración Patrimonial Confidelis</h2></div>", unsafe_allow_html=True)

t1, t2, t3, t4, t5 = st.tabs(["1️⃣ Portafolio Base", "2️⃣ Apalancamiento", "3️⃣ Flujos", "4️⃣ Resumen General", "📥 Exportar"])

# ----------------- PESTAÑA 1: PORTAFOLIO BASE -----------------
with t1:
    c1, c2 = st.columns([2, 1])
    cliente = c1.text_input("👤 Cliente:", value="Familia Demo")
    st.session_state.monto_base = c2.number_input("💰 Monto Portafolio Base ($):", value=st.session_state.monto_base, step=100000.0, format="%.2f")
    
    st.divider()
    
    # ----------------- PERFIL DE RIESGO Y BARRAS -----------------
    st.subheader("📊 Perfil de Riesgo Objetivo (%)")
    rp1, rp2, rp3 = st.columns(3)
    p_c = rp1.number_input("Conservador (C)", 0, 100, 40)
    p_m = rp2.number_input("Moderado (M)", 0, 100, 40)
    p_e = rp3.number_input("Especulativo (E)", 0, 100, 20)
    
    sum_c = sum((i['Monto (MXN)'] / st.session_state.monto_base * 100) for i in st.session_state.instrumentos if i['Categoría'] == 'C') if st.session_state.monto_base > 0 else 0
    sum_m = sum((i['Monto (MXN)'] / st.session_state.monto_base * 100) for i in st.session_state.instrumentos if i['Categoría'] == 'M') if st.session_state.monto_base > 0 else 0
    sum_e = sum((i['Monto (MXN)'] / st.session_state.monto_base * 100) for i in st.session_state.instrumentos if i['Categoría'] == 'E') if st.session_state.monto_base > 0 else 0

    st.write("Progreso de asignación por categoría:")
    col_prog1, col_prog2, col_prog3 = st.columns(3)
    col_prog1.progress(min(sum_c / p_c if p_c > 0 else 0, 1.0)); col_prog1.caption(f"Conservador: {sum_c:.1f}% / {p_c}%")
    col_prog2.progress(min(sum_m / p_m if p_m > 0 else 0, 1.0)); col_prog2.caption(f"Moderado: {sum_m:.1f}% / {p_m}%")
    col_prog3.progress(min(sum_e / p_e if p_e > 0 else 0, 1.0)); col_prog3.caption(f"Especulativo: {sum_e:.1f}% / {p_e}%")

    if sum_c > p_c or sum_m > p_m or sum_e > p_e:
        st.error("🛑 **Alerta:** Has asignado a una categoría un porcentaje mayor al definido en tu perfil de riesgo.")
    elif (sum_c + sum_m + sum_e) < 100 and len(st.session_state.instrumentos) > 0:
        st.warning(f"💡 Aún falta el {(100 - (sum_c + sum_m + sum_e)):.1f}% de tu portafolio por asignar.")

    st.divider()
    
    # ----------------- BARRA DE DINERO RESTANTE -----------------
    total_asignado = sum(i['Monto (MXN)'] for i in st.session_state.instrumentos)
    falta_asignar = st.session_state.monto_base - total_asignado
    pct_asignado = min(total_asignado / st.session_state.monto_base, 1.0) if st.session_state.monto_base > 0 else 0
    
    st.markdown(f"<div class='progress-text'>Dinero Asignado: ${total_asignado:,.2f} | Restante para asignar: ${falta_asignar:,.2f}</div>", unsafe_allow_html=True)
    st.progress(pct_asignado)
    
    st.subheader("➕ Agregar Instrumento")
    
    # NOTA: Quité el "st.form" para que se actualice EN VIVO mientras escribes
    f1, f2, f3 = st.columns([1, 2, 2])
    cat = f1.selectbox("Categoría", ["Conservador", "Moderado", "Especulativo"])
    nombre = f2.text_input("Nombre (Ej. CETES)")
    tasa = f3.number_input("Rendimiento Anual %", min_value=0.0, step=0.5, format="%.2f")
    
    st.write("¿Cómo deseas asignar el capital a este instrumento?")
    modo_captura = st.radio("Modo de captura:", ["Por Monto ($)", "Por Porcentaje (%)"], horizontal=True)
    
    m_col1, m_col2, m_col3 = st.columns(3)
    if modo_captura == "Por Monto ($)":
        valor_capturado = m_col1.number_input("Monto a Invertir ($)", min_value=0.0, max_value=float(falta_asignar) if falta_asignar > 0 else 0.0, value=0.0, step=10000.0, format="%.2f")
        monto_final = valor_capturado
        pct_calculado = (monto_final / st.session_state.monto_base) * 100 if st.session_state.monto_base > 0 else 0
        m_col2.info(f"Equivale al **{pct_calculado:.2f}%** del portafolio.")
    else:
        pct_restante = (falta_asignar / st.session_state.monto_base) * 100 if st.session_state.monto_base > 0 else 0
        valor_capturado = m_col1.number_input("Porcentaje a Invertir (%)", min_value=0.0, max_value=float(pct_restante) if pct_restante > 0 else 0.0, value=0.0, step=1.0, format="%.2f")
        monto_final = (valor_capturado / 100) * st.session_state.monto_base
        m_col2.info(f"Equivale a **${monto_final:,.2f} MXN**.")
        
    horizonte = m_col3.selectbox("Horizonte", ["1 Año",
