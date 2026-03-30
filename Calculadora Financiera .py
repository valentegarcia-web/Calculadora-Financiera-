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
    .btn-danger>button { background-color: #8B0000; color: white; border: none; }
    .metric-box { background-color: white; padding: 15px; border-radius: 10px; text-align: center; border-top: 4px solid #002147; box-shadow: 0 2px 5px rgba(0,0,0,0.1);}
    .header-box { background-color: #002147; color: #D4AF37; padding: 15px; border-radius: 10px; margin-bottom: 20px;}
    .resumen-card { background-color: #002147; color: white; padding: 20px; border-radius: 10px; border-left: 8px solid #D4AF37; margin-top: 15px;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. VARIABLES DE SESIÓN ---
if 'instrumentos' not in st.session_state: st.session_state.instrumentos = []
if 'monto_base' not in st.session_state: st.session_state.monto_base = 5000000.0

# --- 3. FUNCIONES DE CÁLCULO Y PDF ---
def calcular_df(instrumentos_list, monto_total):
    if not instrumentos_list:
        return pd.DataFrame(columns=['Categoría', 'Instrumento', '% Asignación', 'Monto (MXN)', 'Monto Aportado', 'Remanente', 'Tasa Anual %', 'Flujo Mensual', 'Flujo Anual', 'Horizonte', 'Liquidez', 'Objetivo'])
    df = pd.DataFrame(instrumentos_list)
    df['Monto (MXN)'] = (df['% Asignación'] / 100) * monto_total
    df['Remanente'] = df['Monto (MXN)'] - df['Monto Aportado']
    df['Flujo Anual'] = df['Monto (MXN)'] * (df['Tasa Anual %'] / 100)
    df['Flujo Mensual'] = df['Flujo Anual'] / 12
    return df

class ConfidelisPDF(FPDF):
    def header(self):
        self.set_fill_color(0, 33, 71)
        self.rect(0, 0, 297, 30, 'F')
        self.set_font('Arial', 'B', 16)
        self.set_text_color(212, 175, 55)
        self.cell(0, 10, 'CONFIDELIS: ESTRATEGIA PATRIMONIAL', 0, 1, 'C')
        self.ln(5)

def generar_pdf_custom(cliente, p_c, p_m, p_e, modulos, df_act, df_prop, df_flujo, resumen_txt):
    pdf = ConfidelisPDF(orientation='L')
    
    if "Resumen Ejecutivo" in modulos:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.set_text_color(0, 33, 71)
        pdf.cell(0, 10, f"Resumen Ejecutivo para: {cliente}", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 8, resumen_txt)
        pdf.ln(10)

    def imprimir_tabla(pdf_obj, titulo, df):
        pdf_obj.add_page()
        pdf_obj.set_font("Arial", 'B', 14)
        pdf_obj.set_text_color(0, 33, 71)
        pdf_obj.cell(0, 10, titulo, ln=True)
        pdf_obj.ln(3)
        pdf_obj.set_fill_color(212, 175, 55)
        pdf_obj.set_text_color(255, 255, 255)
        pdf_obj.set_font("Arial", 'B', 7)
        anchos = [15, 30, 15, 25, 25, 25, 20, 25, 25, 20, 20, 25]
        for i, col in enumerate(df.columns): pdf_obj.cell(anchos[i], 8, str(col)[:15], 1, 0, 'C', True)
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
                if isinstance(val, float) and val <= 100 and i == 2: texto = f"{val:.1f}%"
                if pd.isna(val) or val == "": texto = "-"
                pdf_obj.cell(anchos[i], 8, texto[:20], 1, 0, 'C', fill=es_tot)
            pdf_obj.ln()

    def add_totals(df):
        df_c = df.copy()
        if not df_c.empty:
            t = pd.Series(index=df_c.columns, dtype=object)
            t['Categoría'] = 'TOTAL'; t['Instrumento'] = '-'
            t['% Asignación'] = df_c['% Asignación'].sum()
            t['Monto (MXN)'] = df_c['Monto (MXN)'].sum()
            t['Monto Aportado'] = df_c['Monto Aportado'].sum()
            t['Remanente'] = df_c['Remanente'].sum()
            t['Flujo Mensual'] = df_c['Flujo Mensual'].sum()
            t['Flujo Anual'] = df_c['Flujo Anual'].sum()
            df_c.loc['TOTAL'] = t
        return df_c

    if "Portafolio Actual" in modulos: imprimir_tabla(pdf, "Portafolio Actual", add_totals(df_act))
    if "Portafolio Propuesto" in modulos: imprimir_tabla(pdf, "Portafolio Propuesto (Apalancado)", add_totals(df_prop))
    
    if "Desglose de Flujos" in modulos:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.set_text_color(0, 33, 71)
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
        if "Portafolio Actual" in modulos: df_act.to_excel(writer, index=False, sheet_name='Actual')
        if "Portafolio Propuesto" in modulos: df_prop.to_excel(writer, index=False, sheet_name='Propuesto')
        if "Desglose de Flujos" in modulos: df_flujo.to_excel(writer, index=False, sheet_name='Flujos')
    return output.getvalue()

# --- 4. INTERFAZ GRÁFICA ---
st.markdown("<div class='header-box'><h2 style='margin:0;'>🏛️ Estructuración Patrimonial Confidelis</h2></div>", unsafe_allow_html=True)

t1, t2, t3, t4, t5 = st.tabs(["1️⃣ Portafolio", "2️⃣ Apalancamiento", "3️⃣ Flujos", "4️⃣ Resumen General", "📥 Exportar"])

# ----------------- PESTAÑA 1: PORTAFOLIO -----------------
with t1:
    c1, c2 = st.columns([2, 1])
    cliente = c1.text_input("👤 Cliente:", value="Familia Demo")
    monto_input = c2.number_input("💰 Monto Portafolio Base:", value=st.session_state.monto_base, step=100000.0)
    st.session_state.monto_base = monto_input
    st.info(f"Capital ingresado para análisis: **${monto_input:,.2f} MXN**")
    
    st.divider()
    st.subheader("📊 Perfil de Riesgo Objetivo (%)")
    rp1, rp2, rp3 = st.columns(3)
    p_c = rp1.number_input("Conservador (C)", 0, 100, 40)
    p_m = rp2.number_input("Moderado (M)", 0, 100, 40)
    p_e = rp3.number_input("Especulativo (E)", 0, 100, 20)
    
    # Validaciones Visuales del Perfil vs Instrumentos
    sum_c = sum(i['% Asignación'] for i in st.session_state.instrumentos if i['Categoría'] == 'C')
    sum_m = sum(i['% Asignación'] for i in st.session_state.instrumentos if i['Categoría'] == 'M')
    sum_e = sum(i['% Asignación'] for i in st.session_state.instrumentos if i['Categoría'] == 'E')

    st.write("Progreso de asignación de instrumentos:")
    col_prog1, col_prog2, col_prog3 = st.columns(3)
    col_prog1.progress(min(sum_c / p_c if p_c > 0 else 0, 1.0)); col_prog1.caption(f"Conservador: {sum_c}% / {p_c}%")
    col_prog2.progress(min(sum_m / p_m if p_m > 0 else 0, 1.0)); col_prog2.caption(f"Moderado: {sum_m}% / {p_m}%")
    col_prog3.progress(min(sum_e / p_e if p_e > 0 else 0, 1.0)); col_prog3.caption(f"Especulativo: {sum_e}% / {p_e}%")

    if sum_c > p_c or sum_m > p_m or sum_e > p_e:
        st.warning("⚠️ **Alerta:** Has asignado a una categoría un porcentaje mayor al definido en tu perfil de riesgo. Puedes dejarlo así si es tu estrategia o eliminar instrumentos abajo para corregirlo.")

    st.divider()
    st.subheader("➕ Agregar Instrumentos")
    
    with st.form("form_inst"):
        f1, f2, f3, f4 = st.columns(4)
        cat = f1.selectbox("Categoría", ["Conservador", "Moderado", "Especulativo"])
        nombre = f2.text_input("Nombre (Ej. CETES)")
        pct = f3.number_input("% Asignación", min_value=0.0, step=1.0)
        tasa = f4.number_input("Rendimiento Anual %", min_value=0.0, step=0.5)
        
        f5, f6, f7, f8 = st.columns(4)
        aportado = f5.number_input("Monto Aportado ($)", min_value=0.0, step=10000.0)
        horizonte = f6.selectbox("Horizonte", ["1 Año", "3 Años", "5 Años", "10 Años"])
        liquidez = f7.selectbox("Liquidez", ["Diaria", "Mensual", "Anual", "Al Vencimiento"])
        objetivo = f8.text_input("Objetivo")
        
        if st.form_submit_button("Guardar Instrumento"):
            letra_cat = cat[0]
            st.session_state.instrumentos.append({
                "Categoría": letra_cat, "Instrumento": nombre, "% Asignación": pct, 
                "Tasa Anual %": tasa, "Monto Aportado": aportado, "Horizonte": horizonte, 
                "Liquidez": liquidez, "Objetivo": objetivo
            })
            st.rerun()

    # GESTIÓN DE INSTRUMENTOS INDIVIDUALES
    if st.session_state.instrumentos:
        st.write("### 🗂️ Instrumentos Agregados (Haz clic en ❌ para borrar uno)")
        for i, inst in enumerate(st.session_state.instrumentos):
            c_inf, c_btn = st.columns([5, 1])
            c_inf.markdown(f"**{inst['Categoría']}** | {inst['Instrumento']} | Asignación: **{inst['% Asignación']}%** | Rendimiento: **{inst['Tasa Anual %']}%**")
            if c_btn.button("❌ Borrar", key=f"del_{i}"):
                st.session_state.instrumentos.pop(i)
                st.rerun()

    df_actual = calcular_df(st.session_state.instrumentos, monto_input)

# ----------------- PESTAÑA 2: APALANCAMIENTO -----------------
with t2:
    st.subheader("Estrategia de Crédito")
    col1, col2, col3 = st.columns(3)
    prestamo = col1.number_input("Monto del Préstamo", value=2000000.0, step=50000.0)
    col1.info(f"Monto: **${prestamo:,.2f}**")
    
    pago_mensual = col2.number_input("Pago Mensual Estimado", value=45000.0, step=1000.0)
    col2.info(f"Pago Mensual: **${pago_mensual:,.2f}**")
    
    tasa_prestamo = col3.number_input("Tasa Préstamo (% Anual)", value=12.0, step=0.5)
    
    monto_propuesto = monto_input + prestamo
    st.success(f"**NUEVO CAPITAL DE TRABAJO:** ${monto_input:,.2f} + ${prestamo:,.2f} = **${monto_propuesto:,.2f}**")
    
    df_prop = calcular_df(st.session_state.instrumentos, monto_propuesto)
    if not df_prop.empty:
        st.write("Redistribución del Capital Propuesto:")
        st.dataframe(df_prop.style.format({
            '% Asignación': '{:.2f}%', 'Monto (MXN)': '${:,.2f}', 'Monto Aportado': '${:,.2f}', 
            'Remanente': '${:,.2f}', 'Tasa Anual %': '{:.2f}%', 'Flujo Mensual': '${:,.2f}', 'Flujo Anual': '${:,.2f}'
        }), use_container_width=True)

# ----------------- PESTAÑA 3: FLUJOS -----------------
with t3:
    st.subheader("Proyección de Amortización y Flujos")
    
    plazo_meses = st.number_input("¿A cuántos meses deseas proyectar la tabla?", min_value=12, max_value=360, value=60, step=12)
    
    flujo_inversiones = df_prop['Flujo Mensual'].sum() if not df_prop.empty else 0
    datos_flujo = []
    saldo_deuda = prestamo
    mes_liquidacion = None
    
    for m in range(1, int(plazo_meses) + 1):
        int_d = saldo_deuda * ((tasa_prestamo/100)/12)
        cap_d = pago_mensual - int_d
        saldo_deuda = max(0, saldo_deuda - cap_d)
        
        f_neto = flujo_inversiones - pago_mensual if saldo_deuda > 0 else flujo_inversiones
        
        if saldo_deuda <= 0 and mes_liquidacion is None: mes_liquidacion = m
            
        datos_flujo.append({
            "Mes": m, "Flujo Positivo (Inv)": flujo_inversiones, "Flujo Negativo (Deuda)": pago_mensual if saldo_deuda>0 else 0,
            "Flujo Neto": f_neto, "Deuda Restante": saldo_deuda
        })
            
    df_flujo = pd.DataFrame(datos_flujo)
    
    fecha_fin = (datetime.now() + timedelta(days=(mes_liquidacion or 0)*30)).strftime("%B %Y") if mes_liquidacion else "Fuera del plazo proyectado"
    mes_txt = f"en el Mes {mes_liquidacion} ({fecha_fin})" if mes_liquidacion else "aún con saldo pendiente al finalizar el plazo"
    texto_resumen = f"Con un portafolio de ${monto_propuesto:,.2f} y flujos mensuales de inversiones de ${flujo_inversiones:,.2f}, el crédito quedará liquidado {mes_txt}. A partir de entonces, el cliente retendrá el 100% del flujo neto."
    
    st.write("### Tabla de Proyección a la Medida")
    st.dataframe(df_flujo.style.format("${:,.2f}"), use_container_width=True)

# ----------------- PESTAÑA 4: RESUMEN GENERAL -----------------
with t4:
    st.subheader("📊 Dashboard Directivo del Portafolio")
    
    if df_prop.empty:
        st.warning("Agrega instrumentos para ver el resumen ejecutivo.")
    else:
        st.markdown(f"<div class='resumen-card'><h4>💡 Resumen de la Estrategia:</h4><p>{texto_resumen}</p></div>", unsafe_allow_html=True)
        st.write("")
        
        m1, m2, m3 = st.columns(3)
        m1.markdown(f"<div class='metric-box'>Capital Base<br><h2>${monto_input:,.0f}</h2></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-box'>Línea de Crédito<br><h2>${prestamo:,.0f}</h2></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-box'>Portafolio Activo<br><h2>${monto_propuesto:,.0f}</h2></div>", unsafe_allow_html=True)
        
        st.write("")
        m4, m5, m6 = st.columns(3)
        rendimiento_promedio = (df_prop['Flujo Anual'].sum() / monto_propuesto) * 100 if monto_propuesto > 0 else 0
        m4.markdown(f"<div class='metric-box'>Rendimiento Ponderado<br><h2>{rendimiento_promedio:.2f}%</h2></div>", unsafe_allow_html=True)
        m5.markdown(f"<div class='metric-box'>Flujo a favor (Mensual)<br><h2>${flujo_inversiones:,.0f}</h2></div>", unsafe_allow_html=True)
        
        flujo_libre = flujo_inversiones - pago_mensual
        color_flujo = "#006400" if flujo_libre > 0 else "#8B0000"
        m6.markdown(f"<div class='metric-box'>Flujo Neto (Durante Deuda)<br><h2 style='color:{color_flujo};'>${flujo_libre:,.0f}</h2></div>", unsafe_allow_html=True)

# ----------------- PESTAÑA 5: EXPORTACIÓN -----------------
with t5:
    st.subheader("📥 Selecciona Módulos a Exportar")
    opciones = ["Resumen Ejecutivo", "Portafolio Actual", "Portafolio Propuesto", "Desglose de Flujos"]
    
    seleccion = st.multiselect("¿Qué deseas incluir en los documentos?", opciones, default=["Resumen Ejecutivo", "Portafolio Propuesto", "Desglose de Flujos"])
    
    st.divider()
    c_btn1, c_btn2 = st.columns(2)
    
    if len(seleccion) > 0 and not df_actual.empty:
        with c_btn1:
            pdf_data = generar_pdf_custom(cliente, p_c, p_m, p_e, seleccion, df_actual, df_prop, df_flujo, texto_resumen)
            st.download_button("📄 Generar PDF Oficial", pdf_data, f"Confidelis_{cliente.replace(' ','_')}.pdf", "application/pdf")
        with c_btn2:
            excel_data = generar_excel_custom(seleccion, df_actual, df_prop, df_flujo)
            st.download_button("📊 Generar Hojas de Excel", excel_data, f"Confidelis_Datos_{cliente.replace(' ','_')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("⚠️ Asegúrate de tener al menos 1 instrumento registrado y seleccionar mínimo 1 módulo para habilitar las descargas.")
