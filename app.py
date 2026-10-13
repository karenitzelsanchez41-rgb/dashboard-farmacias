"""Tablero de mando – Farmacias Valle (Streamlit).

Problema de negocio: ¿Debemos mantener el gasto en promociones y la política de
inventario actual, o reasignarlos? Audiencia: Dirección Comercial / Abastecimiento.
Ejecutar:  streamlit run app.py
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from calculos import (MESES, ORDEN_TEMP, cargar_datos, efecto_por_categoria,
                      efecto_promocion, indice_anual, kpis, pct_cambio)

st.set_page_config(page_title="Farmacias Valle · Tablero de mando",
                   page_icon="💊", layout="wide")


@st.cache_data
def datos():
    return cargar_datos()


df = datos()

# ───────────────────────── Filtros (slicers) ─────────────────────────
st.sidebar.header("Filtros")
anios = sorted(df["Anio"].unique())
anio = st.sidebar.selectbox("Año de análisis", anios, index=len(anios) - 1)
m1, m2 = st.sidebar.select_slider("Rango de meses", options=list(range(1, 13)),
                                  value=(1, 12), format_func=lambda m: MESES[m - 1])
cats = st.sidebar.multiselect("Categoría", sorted(df["Categoria"].unique()),
                              default=sorted(df["Categoria"].unique()))
temps = st.sidebar.multiselect("Temporada", ORDEN_TEMP, default=ORDEN_TEMP)
meta_cob = st.sidebar.slider("Meta de cobertura de inventario (meses)", 1.0, 2.5, 1.5, 0.1,
                             help="Supuesto de trabajo: la meta no viene en los datos.")

filtrado = df[df["Categoria"].isin(cats) & df["Temporada"].isin(temps)]
periodo = filtrado[filtrado["MesNum"].between(m1, m2)]
act = periodo[periodo["Anio"] == anio]
ant = periodo[periodo["Anio"] == anio - 1]

if act.empty:
    st.warning("No hay datos con esta combinación de filtros. Amplía la selección.")
    st.stop()

# ───────────────────────── Título narrativo ─────────────────────────
st.title("💊 El ingreso crece más por precio que por volumen — y las promociones no están moviendo las ventas")
st.caption("Decisión que apoya: ¿mantener el gasto en promociones y la política de inventario actual? "
           "· Audiencia: Dirección Comercial y de Abastecimiento · 20 productos, ene-2020 a dic-2024")

# ───────────────────────── KPIs con contexto ─────────────────────────
k = kpis(act, ant)
a, p = k["act"], k["ant"]
tiene_ant = not ant.empty
lift = efecto_promocion(periodo)


def delta(v, ref):
    d = pct_cambio(v, ref) if tiene_ant else None
    return None if d is None else f"{d:+.1f}% vs {anio - 1}"


c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Ingreso", f"${a['ingreso']:,.0f}", delta(a["ingreso"], p["ingreso"]))
c2.metric("Unidades vendidas", f"{a['unidades']:,.0f}", delta(a["unidades"], p["unidades"]))
c3.metric("Precio promedio ponderado", f"${a['precio']:,.2f}", delta(a["precio"], p["precio"]))
c4.metric("Cobertura de inventario", f"{a['cobertura']:.2f} meses",
          f"{a['cobertura'] - meta_cob:+.2f} vs meta {meta_cob:.1f}", delta_color="inverse")
c5.metric("Efecto de la promoción en unidades",
          "s/d" if pd.isna(lift) else f"{lift:+.1f}%",
          "vs. mismas ventas sin promoción", delta_color="off")

st.divider()

# ───────────────────── Fila 1: tendencia + comparación ─────────────────────
col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("Tendencia: el ingreso sube en diciembre-enero y cae en abril-mayo")
    meses = list(range(m1, m2 + 1))
    s_act = act.groupby("MesNum")["Ingreso_Mensual"].sum().reindex(meses)
    fig = go.Figure()
    fig.add_scatter(x=[MESES[m - 1] for m in meses], y=s_act.values,
                    mode="lines+markers", name=str(anio), line=dict(width=3))
    if tiene_ant:
        s_ant = ant.groupby("MesNum")["Ingreso_Mensual"].sum().reindex(meses)
        fig.add_scatter(x=[MESES[m - 1] for m in meses], y=s_ant.values,
                        mode="lines", name=str(anio - 1), line=dict(dash="dot"))
    pico = int(s_act.idxmax())
    fig.add_annotation(x=MESES[pico - 1], y=s_act.max(), text=f"Pico: {MESES[pico - 1]}",
                       showarrow=True, arrowhead=2, ay=-40)
    fig.update_layout(height=340, margin=dict(t=10, b=10), yaxis_title="Ingreso (MXN)",
                      legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Comparación: Crónicos pesa ~1/3 del ingreso")
    partes = [act.assign(Periodo=str(anio))]
    if tiene_ant:
        partes.append(ant.assign(Periodo=str(anio - 1)))
    por_cat = (pd.concat(partes).groupby(["Categoria", "Periodo"], as_index=False)
               ["Ingreso_Mensual"].sum())
    fig = px.bar(por_cat, x="Categoria", y="Ingreso_Mensual", color="Periodo", barmode="group")
    fig.update_layout(height=340, margin=dict(t=10, b=10), yaxis_title="Ingreso (MXN)",
                      xaxis_title=None, legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

# ───────────────────── Fila 2: ¿precio o volumen? + inventario ─────────────────────
col3, col4 = st.columns(2)

with col3:
    st.subheader("¿Qué explica el crecimiento? Precio más que volumen")
    ia = indice_anual(filtrado)
    fig = go.Figure()
    for col, nombre in [("Ingreso", "Ingreso"), ("Unidades", "Unidades"), ("Precio", "Precio promedio")]:
        fig.add_scatter(x=ia.index, y=ia[col], mode="lines+markers", name=nombre)
    fig.add_annotation(x=ia.index[-1], y=ia["Ingreso"].iloc[-1],
                       text=f"Ingreso {ia['Ingreso'].iloc[-1] - 100:+.0f}%<br>"
                            f"Unidades {ia['Unidades'].iloc[-1] - 100:+.0f}%",
                       showarrow=True, ax=-70, ay=-20)
    fig.update_layout(height=340, margin=dict(t=10, b=10),
                      yaxis_title=f"Índice (base {ia.index[0]} = 100)",
                      xaxis=dict(dtick=1), legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

with col4:
    st.subheader("Distribución: el inventario no se ajusta a la temporada")
    fig = px.box(act, x="Temporada", y="Cobertura", color="Temporada",
                 category_orders={"Temporada": ORDEN_TEMP}, points="all")
    fig.add_hline(y=meta_cob, line_dash="dash", annotation_text=f"Meta {meta_cob:.1f} meses")
    fig.update_layout(height=340, margin=dict(t=10, b=10), showlegend=False,
                      yaxis_title="Meses de inventario por producto-mes", xaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

# ───────────────────── Fila 3: promociones + top productos ─────────────────────
col5, col6 = st.columns(2)

with col5:
    st.subheader("Promociones: sin efecto claro en unidades")
    ef = efecto_por_categoria(periodo)
    fig = px.bar(ef, x="Categoria", y="Efecto_pct", text=ef["Efecto_pct"].map("{:+.1f}%".format))
    fig.add_hline(y=0, line_color="gray")
    fig.update_layout(height=340, margin=dict(t=10, b=10), xaxis_title=None,
                      yaxis_title="% unidades con promo vs sin promo")
    st.plotly_chart(fig, use_container_width=True)

with col6:
    st.subheader("Top 10 productos por ingreso")
    top = (act.groupby("Producto_Nombre")["Ingreso_Mensual"].sum()
           .nlargest(10).sort_values().reset_index())
    fig = px.bar(top, x="Ingreso_Mensual", y="Producto_Nombre", orientation="h")
    fig.update_layout(height=340, margin=dict(t=10, b=10), xaxis_title="Ingreso (MXN)", yaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

# ───────────────────────── Lectura y limitaciones ─────────────────────────
st.divider()
cob_alta = act.loc[act["Temporada"] == "Alta", "Cobertura"].mean()
cob_baja = act.loc[act["Temporada"] == "Baja", "Cobertura"].mean()
st.info(
    "**Lectura del tablero.** "
    f"En {anio} el ingreso es ${a['ingreso']:,.0f}. El crecimiento histórico del ingreso supera al de las "
    "unidades: la diferencia es precio. "
    + ("" if pd.isna(lift) else f"Las ventas con promoción son {lift:+.1f}% frente a las ventas sin promoción "
       "(a igual producto y temporada): no hay evidencia de que las promociones muevan volumen. ")
    + ("" if pd.isna(cob_alta) or pd.isna(cob_baja) else
       f"La cobertura de inventario es casi igual en temporada alta ({cob_alta:.2f} meses) y baja ({cob_baja:.2f}): "
       "el stock sigue a las ventas en lugar de anticiparse a la estacionalidad.")
)
with st.expander("Limitaciones de los datos y calidad"):
    st.markdown(
        "- **Corrección aplicada:** 30 valores de *Precio_Promedio* (todos de Vitamina C 1g) estaban guardados como "
        "fechas; se recalcularon como Ingreso ÷ Unidades.\n"
        "- **Sin costos ni márgenes:** el ingreso no es utilidad; no se puede medir el ROI de las promociones.\n"
        "- **Sin costo de la promoción ni descuento aplicado**, solo un indicador 0/1.\n"
        "- **Una sola fuente y sin sucursales:** no hay dimensión de tienda ni de competencia.\n"
        "- **Stock a nivel mensual:** no permite detectar quiebres intra-mes; la meta de cobertura es un supuesto.\n"
        "- **Datos aparentemente simulados:** patrones muy regulares (p. ej. cobertura siempre entre 1.3 y 2.0)."
    )
