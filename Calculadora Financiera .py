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
        ancho_col = 277 / len(cols) # Distribuir ancho dinámicamente
        
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
    st.session_state.monto_base = c2.number_input("💰 Monto Portafolio Base ($):", value=st.session_state.monto_base, step=100000.0)
    
    # Barra de Progreso del Dinero Base
    total_asignado = sum(i['Monto (MXN)'] for i in st.session_state.instrumentos)
    falta_asignar = st.session_state.monto_base - total_asignado
    pct_asignado = min(total_asignado / st.session_state.monto_base, 1.0) if st.session_state.monto_base > 0 else 0
    
    st.markdown(f"<div class='progress-text'>Distribución del Capital: ${total_asignado:,.2f} asignados | Falta: ${falta_asignar:,.2f}</div>", unsafe_allow_html=True)
    st.progress(pct_asignado)
    
    st.divider()
    st.subheader("➕ Agregar Instrumento")
    
    with st.form("form_inst"):
        f1, f2, f3 = st.columns([1, 2, 2])
        cat = f1.selectbox("Categoría", ["Conservador", "Moderado", "Especulativo"])
        nombre = f2.text_input("Nombre (Ej. CETES)")
        tasa = f3.number_input("Rendimiento Anual %", min_value=0.0, step=0.5)
        
        st.write("¿Cómo deseas asignar el capital a este instrumento?")
        modo_captura = st.radio("Modo de captura:", ["Por Monto ($)", "Por Porcentaje (%)"], horizontal=True)
        
        m_col1, m_col2, m_col3 = st.columns(3)
        if modo_captura == "Por Monto ($)":
            valor_capturado = m_col1.number_input("Monto a Invertir ($)", min_value=0.0, max_value=float(falta_asignar), value=float(falta_asignar), step=10000.0)
            monto_final = valor_capturado
            pct_calculado = (monto_final / st.session_state.monto_base) * 100 if st.session_state.monto_base > 0 else 0
            m_col2.info(f"Equivale al **{pct_calculado:.2f}%** del portafolio.")
        else:
            pct_restante = (falta_asignar / st.session_state.monto_base) * 100 if st.session_state.monto_base > 0 else 0
            valor_capturado = m_col1.number_input("Porcentaje a Invertir (%)", min_value=0.0, max_value=float(pct_restante), value=float(pct_restante), step=1.0)
            monto_final = (valor_capturado / 100) * st.session_state.monto_base
            m_col2.info(f"Equivale a **${monto_final:,.2f}**.")
            
        horizonte = m_col3.selectbox("Horizonte", ["1 Año", "3 Años", "5 Años", "10 Años"])
        liquidez = st.selectbox("Liquidez", ["Diaria", "Mensual", "Anual", "Al Vencimiento"])

        if st.form_submit_button("Guardar Instrumento"):
            if monto_final > 0:
                st.session_state.instrumentos.append({
                    "Categoría": cat[0], "Instrumento": nombre, "Monto (MXN)": monto_final, 
                    "Tasa Anual %": tasa, "Horizonte": horizonte, "Liquidez": liquidez, "Inyección": 0.0
                })
                st.rerun()

    if st.session_state.instrumentos:
        st.write("### 🗂️ Instrumentos Activos")
        for i, inst in enumerate(st.session_state.instrumentos):
            c_inf, c_btn = st.columns([6, 1])
            c_inf.markdown(f"**{inst['Categoría']}** | {inst['Instrumento']} | Monto: **${inst['Monto (MXN)']:,.2f}** | Rendimiento: **{inst['Tasa Anual %']}%**")
            if c_btn.button("❌ Borrar", key=f"del_{i}"):
                st.session_state.instrumentos.pop(i)
                st.rerun()

    df_actual = generar_df_actual(st.session_state.instrumentos, st.session_state.monto_base)
    if not df_actual.empty:
        st.dataframe(df_actual.style.format({'% Asignación': '{:.2f}%', 'Monto (MXN)': '${:,.2f}', 'Flujo Mensual': '${:,.2f}', 'Flujo Anual': '${:,.2f}', 'Tasa Anual %': '{:.2f}%'}), use_container_width=True)

# ----------------- PESTAÑA 2: APALANCAMIENTO (INYECCIÓN DE CAPITAL) -----------------
with t2:
    st.subheader("Estrategia de Crédito e Inyección")
    col1, col2, col3 = st.columns(3)
    st.session_state.prestamo = col1.number_input("Monto del Préstamo Autorizado ($)", value=st.session_state.prestamo, step=50000.0)
    pago_mensual = col2.number_input("Pago Mensual Estimado ($)", value=45000.0, step=1000.0)
    tasa_prestamo = col3.number_input("Tasa Préstamo (% Anual)", value=12.0, step=0.5)

    if not st.session_state.instrumentos:
        st.warning("Agrega instrumentos en la pestaña 1 primero para poder inyectarles capital.")
    else:
        st.divider()
        st.write("### 💸 Distribuir el Préstamo en los Instrumentos")
        
        # Calcular cuánto se ha distribuido del préstamo
        total_inyeccion = sum(inst.get('Inyección', 0.0) for inst in st.session_state.instrumentos)
        falta_prestamo = st.session_state.prestamo - total_inyeccion
        pct_prestamo = min(total_inyeccion / st.session_state.prestamo, 1.0) if st.session_state.prestamo > 0 else 0
        
        color_falta = "green" if falta_prestamo == 0 else "red"
        st.markdown(f"<div class='progress-text'>Préstamo asignado: ${total_inyeccion:,.2f} | <span style='color:{color_falta};'>Falta por asignar: ${falta_prestamo:,.2f}</span></div>", unsafe_allow_html=True)
        st.progress(pct_prestamo)

        for idx, inst in enumerate(st.session_state.instrumentos):
            c_nom, c_in, c_res = st.columns([2, 2, 3])
            c_nom.markdown(f"<br>👉 **{inst['Instrumento']}**<br>Saldo actual: ${inst['Monto (MXN)']:,.0f}", unsafe_allow_html=True)
            
            # Selector dinámico de inyección
            nueva_inyeccion = c_in.number_input(f"Inyectar Capital ($)", min_value=0.0, max_value=float(inst.get('Inyección', 0.0) + falta_prestamo), value=float(inst.get('Inyección', 0.0)), step=10000.0, key=f"iny_{idx}")
            
            if nueva_inyeccion != inst.get('Inyección', 0.0):
                st.session_state.instrumentos[idx]['Inyección'] = nueva_inyeccion
                st.rerun()
                
            flujo_extra = (nueva_inyeccion * (inst['Tasa Anual %']/100)) / 12
            c_res.info(f"**Nuevo Saldo:** ${(inst['Monto (MXN)'] + nueva_inyeccion):,.2f} | **Flujo Extra:** +${flujo_extra:,.2f}/mes")

        df_prop = generar_df_propuesto(st.session_state.instrumentos, st.session_state.monto_base, st.session_state.prestamo)
        st.write("### Vista Final del Portafolio Apalancado")
        st.dataframe(df_prop.style.format({
            'Monto Anterior': '${:,.2f}', 'Inyección Préstamo': '${:,.2f}', 'Nuevo Saldo': '${:,.2f}', 
            '% Nuevo Portafolio': '{:.2f}%', 'Tasa Anual %': '{:.2f}%', 'Flujo Extra Mensual': '${:,.2f}', 'Nuevo Flujo Mensual': '${:,.2f}'
        }), use_container_width=True)

# ----------------- PESTAÑA 3: FLUJOS -----------------
with t3:
    st.subheader("Proyección de Amortización y Flujos")
    plazo_meses = st.number_input("Meses a proyectar", min_value=12, max_value=360, value=60, step=12)
    
    flujo_inversiones = df_prop['Nuevo Flujo Mensual'].sum() if 'df_prop' in locals() and not df_prop.empty else 0
    datos_flujo = []
    saldo_deuda = st.session_state.prestamo
    mes_liquidacion = None
    
    for m in range(1, int(plazo_meses) + 1):
        int_d = saldo_deuda * ((tasa_prestamo/100)/12)
        cap_d = pago_mensual - int_d
        saldo_deuda = max(0, saldo_deuda - cap_d)
        f_neto = flujo_inversiones - pago_mensual if saldo_deuda > 0 else flujo_inversiones
        if saldo_deuda <= 0 and mes_liquidacion is None: mes_liquidacion = m
        datos_flujo.append({"Mes": m, "Flujo Positivo (Inv)": flujo_inversiones, "Flujo Negativo (Deuda)": pago_mensual if saldo_deuda>0 else 0, "Flujo Neto": f_neto, "Deuda Restante": saldo_deuda})
            
    df_flujo = pd.DataFrame(datos_flujo)
    fecha_fin = (datetime.now() + timedelta(days=(mes_liquidacion or 0)*30)).strftime("%B %Y") if mes_liquidacion else "Fuera del plazo proyectado"
    mes_txt = f"en el Mes {mes_liquidacion} ({fecha_fin})" if mes_liquidacion else "aún con saldo pendiente al finalizar"
    texto_resumen = f"El portafolio total será de ${(st.session_state.monto_base + st.session_state.prestamo):,.2f}. Generará flujos mensuales de ${flujo_inversiones:,.2f}. El crédito quedará liquidado {mes_txt}."
    
    st.dataframe(df_flujo.style.format("${:,.2f}"), use_container_width=True)

# ----------------- PESTAÑA 4: RESUMEN GENERAL -----------------
with t4:
    st.subheader("📊 Dashboard Directivo")
    if 'df_prop' not in locals() or df_prop.empty:
        st.warning("Completa la distribución para ver el resumen.")
    else:
        st.markdown(f"<div class='resumen-card'><h4>💡 Resumen:</h4><p>{texto_resumen}</p></div><br>", unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        m1.markdown(f"<div class='metric-box'>Capital Base<br><h2>${st.session_state.monto_base:,.0f}</h2></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-box'>Préstamo Inyectado<br><h2>${total_inyeccion:,.0f}</h2></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-box'>Portafolio Activo<br><h2>${(st.session_state.monto_base + total_inyeccion):,.0f}</h2></div>", unsafe_allow_html=True)
        
        st.write("")
        m4, m5, m6 = st.columns(3)
        rendimiento_promedio = (df_prop['Nuevo Flujo Anual'].sum() / (st.session_state.monto_base + total_inyeccion)) * 100 if (st.session_state.monto_base + total_inyeccion) > 0 else 0
        m4.markdown(f"<div class='metric-box'>Rendimiento Ponderado<br><h2>{rendimiento_promedio:.2f}%</h2></div>", unsafe_allow_html=True)
        m5.markdown(f"<div class='metric-box'>Flujo Total Generado<br><h2>${flujo_inversiones:,.0f}/mes</h2></div>", unsafe_allow_html=True)
        
        flujo_libre = flujo_inversiones - pago_mensual
        c_flujo = "#006400" if flujo_libre > 0 else "#8B0000"
        m6.markdown(f"<div class='metric-box'>Flujo Neto (Durante Deuda)<br><h2 style='color:{c_flujo};'>${flujo_libre:,.0f}</h2></div>", unsafe_allow_html=True)

# ----------------- PESTAÑA 5: EXPORTACIÓN -----------------
with t5:
    st.subheader("📥 Exportar Documentos")
    seleccion = st.multiselect("Módulos:", ["Resumen Ejecutivo", "Portafolio Actual", "Portafolio Propuesto", "Desglose de Flujos"], default=["Resumen Ejecutivo", "Portafolio Propuesto", "Desglose de Flujos"])
    
    st.divider()
    c_btn1, c_btn2 = st.columns(2)
    if len(seleccion) > 0 and 'df_actual' in locals() and not df_actual.empty:
        with c_btn1:
            pdf_data = generar_pdf_custom(cliente, seleccion, df_actual, df_prop, df_flujo, texto_resumen)
            st.download_button("📄 PDF Oficial", pdf_data, f"Confidelis_{cliente}.pdf", "application/pdf")
        with c_btn2:
            excel_data = generar_excel_custom(seleccion, df_actual, df_prop, df_flujo)
            st.download_button("📊 Excel de Datos", excel_data, f"Confidelis_{cliente}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("⚠️ Asegúrate de tener instrumentos registrados para descargar.")
