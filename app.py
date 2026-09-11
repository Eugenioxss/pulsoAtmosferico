import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import timedelta
import os

# Configuración de la página
st.set_page_config(page_title="Pulso Atmosférico", page_icon="🌩️", layout="wide")

# CSS personalizado para hacerlo más estético
st.markdown("""
<style>
.big-font { font-size: 22px !important; font-weight: bold; color: #2E86C1; margin-bottom: 0px;}
.sub-font { font-size: 16px !important; color: #7F8C8D; margin-bottom: 20px;}
</style>
""", unsafe_allow_html=True)

st.title("🌩️ Pulso Atmosférico")
st.markdown("**Monitor Inteligente y Pronóstico Multi-Horizonte de Calidad del Aire (O₃)**")
st.markdown("---")

@st.cache_data
def cargar_datos():
    horizontes = [1, 4, 8, 12, 24, 48]
    df_completo = []

    for h in horizontes:
        ruta = f"results/multihorizonte_v2/pred_test_{h}h.parquet"
        if os.path.exists(ruta):
            df = pd.read_parquet(ruta).reset_index()

            col_fecha = 'Date' if 'Date' in df.columns else df.columns[0]
            col_est = 'Estacion' if 'Estacion' in df.columns else 'estacion'
            cols_numericas = df.select_dtypes(include=['float64', 'float32']).columns
            col_real = [c for c in cols_numericas if 'real' in c.lower() or c == 'O3' or c == 'Real'][0]
            col_pred = [c for c in cols_numericas if 'pred' in c.lower()][0]

            df = df[[col_fecha, col_est, col_real, col_pred]].copy()
            df.columns = ['Fecha', 'Estacion', 'Real', 'Prediccion']
            df['Horizonte'] = h
            df_completo.append(df)

    if not df_completo:
        return None

    df_final = pd.concat(df_completo, ignore_index=True)
    df_final['Fecha'] = pd.to_datetime(df_final['Fecha'])
    return df_final

df_all = cargar_datos()

if df_all is None:
    st.error("❌ No se encontraron los datos de predicción.")
    st.stop()

# --- BARRA LATERAL (CONTROLES) ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3204/3204121.png", width=80)
st.sidebar.header("⚙️ Parámetros de Simulación")

estaciones = sorted(df_all['Estacion'].unique())
estacion_sel = st.sidebar.selectbox("📍 Estación de Monitoreo:", estaciones)

df_est = df_all[df_all['Estacion'] == estacion_sel]
fechas_disponibles = sorted(df_est['Fecha'].dt.date.unique())

# Selector de fecha tipo calendario
fecha_sel = st.sidebar.date_input("📅 Fecha de evaluación (2025):", value=fechas_disponibles[-1], min_value=fechas_disponibles[0], max_value=fechas_disponibles[-1])

df_dia = df_est[df_est['Fecha'].dt.date == fecha_sel]
if df_dia.empty:
    st.warning("No hay registros para este día. Por favor elige otro.")
    st.stop()

horas_disponibles = sorted(df_dia['Fecha'].dt.time.unique())

# Slider para la hora, se ve mucho mejor que una lista desplegable
hora_sel = st.sidebar.select_slider("🕒 Hora del día:", options=horas_disponibles, format_func=lambda x: x.strftime("%H:00 hrs"))

t0 = pd.to_datetime(f"{fecha_sel} {hora_sel}")

# --- PROCESAMIENTO ---
df_real = df_est[df_est['Horizonte'] == 1].copy()
historial = df_real[(df_real['Fecha'] > t0 - timedelta(hours=24)) & (df_real['Fecha'] <= t0)].copy()

puntos_pred = []
for h in [1, 4, 8, 12, 24, 48]:
    target_time = t0 + timedelta(hours=h)
    match = df_est[(df_est['Horizonte'] == h) & (df_est['Fecha'] == target_time)]
    if not match.empty:
        puntos_pred.append({
            'Fecha': target_time,
            'Prediccion': match['Prediccion'].values[0],
            'Horizonte': f"+{h}h",
            'H_num': h
        })
df_futuro = pd.DataFrame(puntos_pred)

# --- PANEL SUPERIOR ---
st.markdown(f"<p class='big-font'>📍 SIMA {estacion_sel}</p>", unsafe_allow_html=True)
st.markdown(f"<p class='sub-font'>Momento de emisión del pronóstico: <b>{t0.strftime('%A, %d de %B de %Y a las %H:%M')}</b></p>", unsafe_allow_html=True)

# --- TARJETAS DE PRONÓSTICO (RANGOS) ---
st.markdown("### Evolución del Pronóstico (O₃ ppb)")
cols = st.columns(6)
if not df_futuro.empty:
    for idx, h in enumerate([1, 4, 8, 12, 24, 48]):
        match = df_futuro[df_futuro['H_num'] == h]
        if not match.empty:
            val = match['Prediccion'].values[0]
            status = "🔴" if val > 70 else "🟢"
            cols[idx].metric(f"{status} a +{h}h", f"{val:.1f}")
        else:
            cols[idx].metric(f"a +{h}h", "--")

st.markdown("---")

# --- GRÁFICA INTERACTIVA PLOTLY ---
fig = go.Figure()

if not historial.empty:
    fig.add_trace(go.Scatter(
        x=historial['Fecha'], y=historial['Real'],
        mode='lines', name='O₃ Histórico (Pasado)',
        line=dict(color='#2C3E50', width=3), fill='tozeroy', fillcolor='rgba(44, 62, 80, 0.1)'
    ))

if not df_futuro.empty:
    if not historial.empty:
        punto_conexion = pd.DataFrame([{'Fecha': t0, 'Prediccion': historial['Real'].iloc[-1]}])
        df_plot_futuro = pd.concat([punto_conexion, df_futuro[['Fecha', 'Prediccion']]])
    else:
        df_plot_futuro = df_futuro

    fig.add_trace(go.Scatter(
        x=df_plot_futuro['Fecha'], y=df_plot_futuro['Prediccion'],
        mode='lines+markers', name='O₃ Pronóstico (Futuro)',
        line=dict(color='#E74C3C', width=3, dash='dash'), marker=dict(size=9, symbol='circle', color='#E74C3C', line=dict(color='white', width=1))
    ))

    # Realidad futura transparente
    real_futuro = df_real[(df_real['Fecha'] > t0) & (df_real['Fecha'] <= t0 + timedelta(hours=48))]
    if not real_futuro.empty:
        fig.add_trace(go.Scatter(
            x=real_futuro['Fecha'], y=real_futuro['Real'],
            mode='lines', name='O₃ Realizado (Lo que ocurrió)',
            line=dict(color='rgba(52, 152, 219, 0.4)', width=2)
        ))

fig.add_hline(y=70, line_dash="dot", line_color="red", annotation_text="Límite NOM-020 (70 ppb)", annotation_position="top left")
fig.add_vline(x=t0, line_dash="dash", line_color="#7F8C8D", annotation_text="AHORA", annotation_position="top right")

fig.update_layout(
    height=450, margin=dict(l=0, r=0, t=30, b=0),
    xaxis_title="", yaxis_title="Concentración O₃ (ppb)",
    hovermode="x unified", template="plotly_white",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

st.plotly_chart(fig, use_container_width=True)
