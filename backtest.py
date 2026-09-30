"""
Backtest de varias formas de entrar y salir del patrón.

Entradas:
  w_diaria   -> la tuya: retroceso a la zona del primer suelo (semanal/mensual)
                y W diaria; entrada en la apertura siguiente, stop bajo la W.
  rotura_h1  -> esperar a que la W de la temporalidad alta se complete
                (cierre por encima de H1); stop bajo el segundo suelo.
Salidas:
  tp_h1      -> objetivo en H1 (el máximo de la primera parte de la V/U)
  tp_3r      -> objetivo a 3 veces el riesgo
  trailing   -> a +2R el stop pasa a break-even; después, salida al cerrar
                por debajo de la SMA50 diaria

Resultados en múltiplos de R (lo que se gana o pierde por cada unidad de riesgo).
Ojo: la lista de tickers es la actual (sin empresas deslistadas), así que los
resultados salen algo optimistas.
"""
import argparse
from dataclasses import replace

import numpy as np
import pandas as pd

from data import load_daily, resample
from patterns import PARAMS, daily_w_triggers, find_setups, zigzag
import universe

ENTRADAS = ("w_diaria", "rotura_h1")
SALIDAS = ("tp_h1", "tp_3r", "trailing")


def simulate(daily, sma50, i0, stop, target, salida):
    """Recorre el diario desde la vela de entrada i0. Devuelve (salida, vela, motivo)."""
    o, h, l, c = (daily[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
    entry = o[i0]
    risk = entry - stop
    be = False
    for k in range(i0, len(daily)):
        if k > i0 and o[k] <= stop:
            return o[k], k, "stop"
        if l[k] <= stop:
            return stop, k, "stop"
        if target is not None and h[k] >= target:
            return max(target, o[k]) if k > i0 else target, k, "objetivo"
        if salida == "trailing":
            if not be and h[k] >= entry + 2 * risk:
                be, stop = True, max(stop, entry)
            if be and not np.isnan(sma50[k]) and c[k] < sma50[k]:
                return c[k], k, "trailing"
    return c[-1], len(daily) - 1, "abierta"


def trades_for(ticker, daily, tf, params=None, entradas=ENTRADAS, salidas=SALIDAS, min_rr=1.0):
    p = params or PARAMS[tf]
    htf = resample(daily, tf)
    if len(htf) < 30:
        return []
    setups = find_setups(htf, tf, p)
    if not setups:
        return []
    didx = daily.index
    dpiv = zigzag(daily["High"].to_numpy(float), daily["Low"].to_numpy(float), 0.08)
    sma50 = daily["Close"].rolling(50).mean().to_numpy()
    out = []
    for s in setups:
        cand = []
        if "w_diaria" in entradas:
            trig = daily_w_triggers(daily, s, htf.index, pivots=dpiv)
            if trig:
                w = trig[0]
                cand.append(("w_diaria", w.trigger_idx + 1, min(w.a, w.c) * 0.995))
        if "rotura_h1" in entradas and s.end_reason == "rotura":
            i0 = int(didx.searchsorted(htf.index[s.end_idx], side="right"))
            cand.append(("rotura_h1", i0, s.l2 * 0.995))
        for entrada, i0, stop in cand:
            if i0 >= len(daily):
                continue
            entry = float(daily["Open"].iloc[i0])
            risk = entry - stop
            if risk <= 0:
                continue
            if entrada == "w_diaria" and (s.h1 - entry) / risk < min_rr:
                continue
            for salida in salidas:
                target = {"tp_h1": s.h1, "tp_3r": entry + 3 * risk}.get(salida)
                if target is not None and target <= entry:
                    continue
                px, k, motivo = simulate(daily, sma50, i0, stop, target, salida)
                out.append({
                    "ticker": ticker, "tf": tf, "entrada": entrada, "salida": salida,
                    "fecha_entrada": didx[i0].date(), "fecha_salida": didx[k].date(),
                    "precio_entrada": entry, "stop": stop, "precio_salida": px, "motivo": motivo,
                    "R": (px - entry) / risk, "ret_%": (px / entry - 1) * 100, "dias": (didx[k] - didx[i0]).days,
                    "L1": s.l1, "H1": s.h1,
                })
    return out


def resumen(trades):
    if trades.empty:
        return trades
    rows = []
    for key, g in trades.groupby(["tf", "entrada", "salida"]):
        g = g.sort_values("fecha_entrada")
        r = g["R"]
        eq = r.cumsum()
        pos, neg = r[r > 0].sum(), -r[r <= 0].sum()
        rows.append({
            "tf": key[0], "entrada": key[1], "salida": key[2], "ops": len(g),
            "acierto_%": (r > 0).mean() * 100, "R_medio": r.mean(), "R_total": r.sum(),
            "profit_factor": pos / neg if neg else np.inf,
            "max_dd_R": (eq.cummax() - eq).max(), "ret_medio_%": g["ret_%"].mean(),
            "dias_medio": g["dias"].mean(),
        })
    return pd.DataFrame(rows).sort_values("R_medio", ascending=False).reset_index(drop=True)


def run(tickers, tfs=("W", "M"), retr=None, refresh=False):
    data = load_daily(tickers, refresh=refresh)
    all_trades = []
    for tf in tfs:
        p = PARAMS[tf] if retr is None else replace(PARAMS[tf], retr_min=retr)
        for t, df in data.items():
            all_trades += trades_for(t, df, tf, p)
    tr = pd.DataFrame(all_trades)
    return tr, resumen(tr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Backtest del patrón V/U + retroceso")
    ap.add_argument("--lista", default="Ejemplos (AMRN, DPRO, MTS)", choices=list(universe.LISTAS))
    ap.add_argument("--tickers", nargs="*")
    ap.add_argument("--tf", nargs="*", default=["W", "M"], choices=["W", "M"])
    ap.add_argument("--retr", nargs="*", type=float, help="probar varias profundidades de zona, p. ej. 0.5 0.618 0.786")
    ap.add_argument("--csv", help="guardar operaciones en este CSV")
    a = ap.parse_args()
    tick = a.tickers or universe.LISTAS[a.lista]()
    pd.set_option("display.width", 250, "display.max_columns", 30)
    for retr in a.retr or [None]:
        tr, res = run(tick, tuple(a.tf), retr)
        print(f"\n=== zona: retroceso >= {retr or 'por defecto'} ===")
        print(res.round(2).to_string() if not res.empty else "Sin operaciones.")
        if a.csv and not tr.empty:
            tr.to_csv(a.csv if retr is None else a.csv.replace(".csv", f"_{retr}.csv"), index=False)
