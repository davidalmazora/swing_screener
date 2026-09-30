"""Screener: acciones con el patrón V/U detectado y en qué fase está cada una."""
import argparse

import pandas as pd

from data import load_daily, resample
from patterns import daily_w_triggers, find_setups
import universe

ORDEN = {"ENTRADA_DIARIA": 0, "EN_ZONA": 1, "V_HECHA": 2, "ROTURA": 3}


def scan_ticker(ticker, daily, tfs=("W", "M"), recent=6, fresh_days=10):
    """Último patrón de cada temporalidad, si sigue vivo o acaba de romper."""
    rows = []
    for tf in tfs:
        htf = resample(daily, tf)
        if len(htf) < 30:
            continue
        setups = find_setups(htf, tf)
        if not setups:
            continue
        s = setups[-1]
        n = len(htf)
        if s.end_reason and not (s.end_reason == "rotura" and n - 1 - s.end_idx <= recent):
            continue
        estado = s.state
        trig = daily_w_triggers(daily, s, htf.index)
        w = trig[-1] if trig else None
        if w and s.end_reason is None and len(daily) - 1 - w.trigger_idx <= fresh_days:
            estado = "ENTRADA_DIARIA"
        close = float(daily["Close"].iloc[-1])
        row = {
            "ticker": ticker, "tf": tf, "estado": estado, "precio": close,
            "pico_R": s.r, "L1": s.l1, "H1": s.h1, "zona_hasta": s.zone_top, "invalida_bajo": s.floor,
            "dist_zona_%": (close / s.zone_top - 1) * 100,
            "espejo_%": (close - s.l1) / (s.r - s.l1) * 100,  # 100% = vuelve al pico R
            "simetria_t": (s.h1_idx - s.l1_idx) / max(1, s.l1_idx - s.r_idx),
            "fecha_R": s.dates["r"].date(), "fecha_L1": s.dates["l1"].date(),
            "fecha_H1": s.dates["h1"].date(),
        }
        if w:
            stop = min(w.a, w.c) * 0.995
            row.update({
                "W_fecha": daily.index[w.trigger_idx].date(), "W_cuello": w.b, "W_stop": stop,
                "W_D0": w.d0,
                "W_rr_a_R": (s.r - close) / (close - stop) if close > stop else None,
            })
        rows.append(row)
    return rows


def run(tickers, tfs=("W", "M"), refresh=False):
    data = load_daily(tickers, refresh=refresh)
    rows = []
    for t, df in data.items():
        rows += scan_ticker(t, df, tfs)
    res = pd.DataFrame(rows)
    if res.empty:
        return res
    res["_o"] = res["estado"].map(ORDEN)
    return res.sort_values(["_o", "dist_zona_%"]).drop(columns="_o").reset_index(drop=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Screener del patrón V/U + retroceso")
    ap.add_argument("--lista", default="Ejemplos (AMRN, DPRO, MTS)", choices=list(universe.LISTAS))
    ap.add_argument("--tickers", nargs="*", help="tickers concretos (sustituye a --lista)")
    ap.add_argument("--tf", nargs="*", default=["W", "M"], choices=["W", "M"])
    ap.add_argument("--csv", help="guardar resultados en este CSV")
    a = ap.parse_args()
    tick = a.tickers or universe.LISTAS[a.lista]()
    out = run(tick, tuple(a.tf))
    pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 500)
    print(out.round(2).to_string() if not out.empty else "Sin patrones.")
    if a.csv and not out.empty:
        out.to_csv(a.csv, index=False)
