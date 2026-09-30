"""
Swing Screener - suelo en V/U, retroceso al primer suelo y W diaria
Arrancar con:  streamlit run app.py
"""
import warnings

warnings.filterwarnings("ignore")
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import backtest  # noqa: E402
import screener  # noqa: E402
import universe  # noqa: E402
from charts import setup_figure  # noqa: E402
from data import load_daily, resample  # noqa: E402
from patterns import daily_w_triggers, find_setups  # noqa: E402

st.set_page_config(page_title="Swing Screener", layout="wide")
st.title("Swing Screener · V/U + retroceso + W diaria")

with st.sidebar:
    lista = st.selectbox("Lista de acciones", list(universe.LISTAS))
    extra = st.text_input("O tickers separados por comas (p. ej. AMRN, DPRO, MTS.MC)")
    tfs = st.multiselect("Temporalidad del patrón", ["W", "M"], default=["W", "M"],
                         format_func={"W": "Semanal", "M": "Mensual"}.get)
    refresh = st.checkbox("Forzar descarga de datos", value=False)


def tickers():
    if extra.strip():
        return [t.strip().upper() for t in extra.split(",") if t.strip()]
    return universe.LISTAS[lista]()


tab_scan, tab_chart, tab_bt = st.tabs(["Screener", "Gráfico", "Backtest"])

with tab_scan:
    st.caption("ENTRADA_DIARIA: W diaria reciente dentro de la zona · EN_ZONA: retrocediendo hacia el "
               "primer suelo, vigilar el diario · V_HECHA: primera parte hecha, esperando retroceso · "
               "ROTURA: acaba de superar H1")
    if st.button("Escanear", type="primary"):
        with st.spinner("Descargando datos y buscando patrones..."):
            st.session_state["scan"] = screener.run(tickers(), tuple(tfs), refresh)
    res = st.session_state.get("scan")
    if res is not None:
        if res.empty:
            st.info("Ninguna acción con el patrón.")
        else:
            st.dataframe(res.round(2), use_container_width=True, hide_index=True)
            st.download_button("Descargar CSV", res.to_csv(index=False), "screener.csv")

with tab_chart:
    c1, c2 = st.columns([2, 1])
    tk = c1.text_input("Ticker", "DPRO").strip().upper()
    tf = c2.selectbox("Temporalidad", ["W", "M"], format_func={"W": "Semanal", "M": "Mensual"}.get)
    if tk:
        daily = load_daily([tk]).get(tk)
        if daily is None:
            st.error("No hay datos para ese ticker.")
        else:
            htf = resample(daily, tf)
            setups = find_setups(htf, tf)
            if not setups:
                st.info("No se ha encontrado el patrón en este ticker.")
            else:
                labels = [f"{s.dates['l1'].date()} · L1 {s.l1:.2f} · {s.state}" for s in setups]
                i = st.selectbox("Patrón", range(len(setups)), index=len(setups) - 1,
                                 format_func=lambda k: labels[k])
                s = setups[i]
                st.pyplot(setup_figure(tk, daily, htf, s, daily_w_triggers(daily, s, htf.index)))

with tab_bt:
    st.caption("Resultados en R (múltiplos del riesgo). La lista de acciones es la actual, sin empresas "
               "deslistadas, así que el resultado es algo optimista.")
    retr = st.select_slider("Profundidad mínima del retroceso (de la subida L1→H1)",
                            [0.382, 0.5, 0.618, 0.786], value=0.618)
    if st.button("Lanzar backtest"):
        with st.spinner("Calculando..."):
            tr, res = backtest.run(tickers(), tuple(tfs), retr, refresh)
        if tr.empty:
            st.info("Sin operaciones.")
        else:
            st.subheader("Resumen por estrategia")
            st.dataframe(res.round(2), use_container_width=True, hide_index=True)
            st.subheader("Operaciones")
            st.dataframe(tr.round(2), use_container_width=True, hide_index=True)
            eq = tr[(tr.entrada == "w_diaria") & (tr.salida == "tp_h1")].sort_values("fecha_entrada")
            if not eq.empty:
                st.subheader("Curva en R · tu entrada (W diaria, objetivo H1)")
                st.line_chart(pd.Series(eq["R"].cumsum().values, index=eq["fecha_entrada"]))
