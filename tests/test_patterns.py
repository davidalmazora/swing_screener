import numpy as np
import pandas as pd

from backtest import trades_for
from data import resample
from patterns import daily_w_triggers, find_setups, zigzag
from screener import scan_ticker


def synthetic(points, seed=0, noise=0.004):
    """Serie diaria que pasa por los puntos (día, precio) interpolando en log."""
    days, prices = zip(*points)
    t = np.arange(days[-1] + 1)
    path = np.exp(np.interp(t, days, np.log(prices)))
    rng = np.random.default_rng(seed)
    close = path * (1 + rng.normal(0, noise, len(t)))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * 1.004
    low = np.minimum(open_, close) * 0.996
    idx = pd.bdate_range("2015-01-01", periods=len(t))
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": 1e6}, idx)


# caída 120 -> 40, V hasta 80, retroceso a 44, W diaria (52 / 45) y subida a 95
W_PATTERN = [(0, 100), (100, 120), (300, 40), (450, 80), (560, 44), (590, 52), (620, 45), (800, 95)]


def test_zigzag_confirma_sin_mirar_al_futuro():
    df = synthetic(W_PATTERN)
    piv = zigzag(df.High, df.Low, 0.15)
    assert all(p.confirm > p.idx for p in piv)
    kinds = [p.kind for p in piv]
    assert all(a != b for a, b in zip(kinds, kinds[1:]))


def test_detecta_v_retroceso_y_rotura_semanal():
    df = synthetic(W_PATTERN)
    wk = resample(df, "W")
    setups = find_setups(wk, "W")
    assert len(setups) == 1
    s = setups[0]
    assert abs(s.r / 120 - 1) < 0.03 and abs(s.l1 / 40 - 1) < 0.03 and abs(s.h1 / 80 - 1) < 0.03
    assert s.zone_idx is not None and s.l2 < s.zone_top
    assert s.end_reason == "rotura"


def test_w_diaria_en_zona():
    df = synthetic(W_PATTERN)
    wk = resample(df, "W")
    s = find_setups(wk, "W")[0]
    trig = daily_w_triggers(df, s, wk.index)
    assert trig
    w = trig[0]
    assert abs(w.b / 52 - 1) < 0.03 and abs(w.c / 45 - 1) < 0.03
    assert df.Close.iloc[w.trigger_idx] > w.b
    assert 620 < w.trigger_idx < 700


def test_backtest_llega_a_h1():
    df = synthetic(W_PATTERN)
    tr = trades_for("SYN", df, "W")
    main = [t for t in tr if t["entrada"] == "w_diaria" and t["salida"] == "tp_h1"]
    assert len(main) == 1 and main[0]["motivo"] == "objetivo" and main[0]["R"] > 1


def test_invalidado_si_pierde_el_suelo():
    df = synthetic([(0, 100), (100, 120), (300, 40), (450, 80), (560, 44), (650, 30), (700, 32)])
    s = find_setups(resample(df, "W"), "W")[0]
    assert s.end_reason == "invalidado"


def test_screener_en_zona():
    # termina dentro de la zona, antes de la W diaria
    df = synthetic(W_PATTERN[:5] + [(575, 47)])
    rows = scan_ticker("SYN", df, tfs=("W",))
    assert rows and rows[0]["estado"] == "EN_ZONA"
