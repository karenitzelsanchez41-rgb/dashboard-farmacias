"""Lógica de datos y cálculos del tablero (pandas puro, sin Streamlit)."""
from pathlib import Path

import numpy as np
import pandas as pd

ARCHIVO = Path(__file__).parent / "Farmacias_Valle_Demanda_1200.xlsx"
ORDEN_TEMP = ["Alta", "Media", "Baja"]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def cargar_datos(ruta=ARCHIVO) -> pd.DataFrame:
    df = pd.read_excel(ruta)
    # Calidad de datos: 30 precios (p. ej. 25.08) quedaron guardados como fecha
    # (25-ago). Se recalcula el precio como Ingreso / Unidades, que es exacto
    # porque Ingreso_Mensual = Unidades_Vendidas x Precio_Promedio.
    df["Precio_Promedio"] = df["Ingreso_Mensual"] / df["Unidades_Vendidas"]
    df["Anio"] = df["Mes"].dt.year
    df["MesNum"] = df["Mes"].dt.month
    # Cobertura de inventario = meses de venta que cubre el stock disponible
    df["Cobertura"] = df["Stock_Disponible"] / df["Unidades_Vendidas"]
    # Índice de ventas: unidades vs. el promedio del mismo producto en la misma
    # temporada (así se aísla el efecto de la promoción del efecto estacional)
    base = df.groupby(["Producto_ID", "Temporada"])["Unidades_Vendidas"].transform("mean")
    df["Indice_Ventas"] = df["Unidades_Vendidas"] / base
    return df


def pct_cambio(actual, anterior):
    if anterior is None or pd.isna(anterior) or anterior == 0:
        return None
    return (actual / anterior - 1) * 100


def efecto_promocion(d: pd.DataFrame):
    """% de ventas con promoción vs. sin promoción (a igual producto y temporada)."""
    con = d.loc[d["Promocion"] == 1, "Indice_Ventas"]
    sin = d.loc[d["Promocion"] == 0, "Indice_Ventas"]
    if con.empty or sin.empty:
        return np.nan
    return (con.mean() / sin.mean() - 1) * 100


def efecto_por_categoria(d: pd.DataFrame) -> pd.DataFrame:
    filas = [{"Categoria": c, "Efecto_pct": efecto_promocion(g)}
             for c, g in d.groupby("Categoria")]
    return pd.DataFrame(filas).dropna()


def kpis(act: pd.DataFrame, ant: pd.DataFrame) -> dict:
    def resumen(d):
        if d.empty:
            return dict(ingreso=np.nan, unidades=np.nan, precio=np.nan, cobertura=np.nan)
        return dict(
            ingreso=d["Ingreso_Mensual"].sum(),
            unidades=d["Unidades_Vendidas"].sum(),
            precio=d["Ingreso_Mensual"].sum() / d["Unidades_Vendidas"].sum(),
            cobertura=d["Stock_Disponible"].sum() / d["Unidades_Vendidas"].sum(),
        )
    return {"act": resumen(act), "ant": resumen(ant)}


def indice_anual(d: pd.DataFrame) -> pd.DataFrame:
    """Ingreso, unidades y precio por año, base 100 = primer año."""
    a = d.groupby("Anio").agg(Ingreso=("Ingreso_Mensual", "sum"),
                              Unidades=("Unidades_Vendidas", "sum"))
    a["Precio"] = a["Ingreso"] / a["Unidades"]
    return a / a.iloc[0] * 100
