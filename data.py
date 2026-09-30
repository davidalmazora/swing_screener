"""Descarga de datos (yfinance) con caché local y cambio de temporalidad."""
import datetime as dt
from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE = Path(__file__).parent / "data_cache"
RULES = {"W": "W-FRI", "M": "ME"}


def _clean(df):
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df = df[(df["High"] > 0) & (df["Low"] > 0)]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df[["Open", "High", "Low", "Close", "Volume"]].astype(float)


def load_daily(tickers, period="max", refresh=False, chunk=80):
    """Devuelve {ticker: DataFrame diario}. Reutiliza la caché del mismo día."""
    CACHE.mkdir(exist_ok=True)
    today = dt.date.today()
    out, missing = {}, []
    for t in tickers:
        f = CACHE / f"{t}.pkl"
        if not refresh and f.exists() and dt.date.fromtimestamp(f.stat().st_mtime) == today:
            out[t] = pd.read_pickle(f)
        else:
            missing.append(t)
    for i in range(0, len(missing), chunk):
        part = missing[i:i + chunk]
        raw = yf.download(part, period=period, auto_adjust=True, group_by="ticker",
                          threads=True, progress=False)
        if raw is None or raw.empty:
            continue
        for t in part:
            try:
                df = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
                df = _clean(df)
            except (KeyError, ValueError):
                continue
            if len(df) > 60:
                df.to_pickle(CACHE / f"{t}.pkl")
                out[t] = df
    return out


def resample(df, tf):
    """Pasa de diario a semanal ("W") o mensual ("M")."""
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return df.resample(RULES[tf]).agg(agg).dropna(subset=["Close"])
