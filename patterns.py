"""
Detección del patrón de suelo en V/U y su retroceso.

Idea (temporalidad alta = semanal o mensual):
  R  -> máximo desde el que empieza la última caída (borde izquierdo)
  L1 -> primer suelo, mínimo de las últimas `lookback` velas
  H1 -> máximo de la recuperación: la "primera parte de la V/U" está hecha
        cuando el precio recupera al menos `min_recovery` de la caída R->L1
  Zona de retroceso -> el precio vuelve hacia L1 (retrocede `retr_min` de la
        subida L1->H1) sin cerrar por debajo de L1 * (1 - max_break)

Gatillo (temporalidad diaria): dentro de la zona se forma una W diaria
(suelo, rebote, segundo suelo no mucho más bajo) y el precio cierra por
encima del rebote. Se entra en la apertura del día siguiente.

Todo es causal: un pivote sólo existe a partir de la vela que lo confirma,
así que el backtest no mira al futuro.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Pivot:
    idx: int  # vela del extremo
    price: float
    kind: str  # "H" o "L"
    confirm: int  # vela en la que queda confirmado


def zigzag(high, low, pct):
    """Zigzag causal: un extremo se confirma cuando el precio se aleja `pct` de él."""
    high, low = np.asarray(high, float), np.asarray(low, float)
    pivots = []
    n = len(high)
    if n < 2:
        return pivots
    trend, hi_i, lo_i = 0, 0, 0
    for t in range(1, n):
        if trend == 0:
            if high[t] > high[hi_i]:
                hi_i = t
            if low[t] < low[lo_i]:
                lo_i = t
            if lo_i < t and high[t] >= low[lo_i] * (1 + pct):
                pivots.append(Pivot(lo_i, low[lo_i], "L", t))
                trend, hi_i = 1, t
            elif hi_i < t and low[t] <= high[hi_i] * (1 - pct):
                pivots.append(Pivot(hi_i, high[hi_i], "H", t))
                trend, lo_i = -1, t
        elif trend == 1:
            if high[t] > high[hi_i]:
                hi_i = t
            elif low[t] <= high[hi_i] * (1 - pct):
                pivots.append(Pivot(hi_i, high[hi_i], "H", t))
                trend, lo_i = -1, t
        else:
            if low[t] < low[lo_i]:
                lo_i = t
            elif high[t] >= low[lo_i] * (1 + pct):
                pivots.append(Pivot(lo_i, low[lo_i], "L", t))
                trend, hi_i = 1, t
    return pivots


@dataclass
class Params:
    pct: float = 0.15  # umbral del zigzag en la temporalidad alta
    min_drop: float = 0.30  # caída mínima R -> L1
    min_recovery: float = 0.50  # parte de la caída que hay que recuperar (V hecha)
    lookback: int = 52  # L1 debe ser el mínimo de estas velas previas
    ma_len: int = 50  # entre L1 y la V hecha debe haber un cierre sobre esta media
    retr_min: float = 0.618  # retroceso de la subida L1->H1 para entrar en zona
    max_break: float = 0.10  # cierre por debajo de L1*(1-max_break) invalida
    max_wait: int = 52  # velas máximas esperando retroceso / segundo suelo


PARAMS = {
    "W": Params(),
    "M": Params(pct=0.20, min_drop=0.40, lookback=24, ma_len=20, max_wait=24),
}


@dataclass
class Setup:
    tf: str
    r_idx: int
    r: float
    l1_idx: int
    l1: float
    h1_idx: int
    h1: float
    v_idx: int  # vela en la que la primera parte de la V/U queda hecha
    retr_min: float
    max_break: float
    zone_idx: int | None = None  # vela en la que el precio entra en la zona
    l2_idx: int | None = None  # mínimo del retroceso (segundo suelo en curso)
    l2: float | None = None
    end_idx: int | None = None
    end_reason: str | None = None  # "rotura", "invalidado", "caducado"
    dates: dict = field(default_factory=dict)

    @property
    def zone_top(self):
        return self.h1 - self.retr_min * (self.h1 - self.l1)

    @property
    def floor(self):
        return self.l1 * (1 - self.max_break)

    @property
    def state(self):
        if self.end_reason:
            return self.end_reason.upper()
        return "EN_ZONA" if self.zone_idx is not None else "V_HECHA"


def find_setups(df, tf="W", params=None):
    """Busca todos los patrones en un DataFrame OHLC de temporalidad alta."""
    p = params or PARAMS[tf]
    h, l, c = (df[k].to_numpy(float) for k in ("High", "Low", "Close"))
    n = len(df)
    sma = pd.Series(c).rolling(p.ma_len).mean().to_numpy()
    piv = zigzag(h, l, p.pct)
    setups = []
    busy_until = -1  # evita patrones solapados con uno ya en curso
    for k in range(1, len(piv)):
        L1, R = piv[k], piv[k - 1]
        if L1.kind != "L" or L1.idx <= busy_until:
            continue
        if 1 - L1.price / R.price < p.min_drop:
            continue
        prev = l[max(0, L1.idx - p.lookback):L1.idx]
        if prev.size and prev.min() < L1.price:
            continue

        need = L1.price + p.min_recovery * (R.price - L1.price)
        h1_i, ma_ok, v_idx = None, False, None
        for t in range(L1.idx + 1, n):
            if l[t] < L1.price:
                break
            if np.isnan(sma[t]) or c[t] > sma[t]:
                ma_ok = True
            if h1_i is None or h[t] > h[h1_i]:
                h1_i = t
            if h[h1_i] >= need and ma_ok and t >= L1.confirm:
                v_idx = t
                break
        if v_idx is None:
            continue

        s = Setup(tf, R.idx, R.price, L1.idx, L1.price, h1_i, h[h1_i], v_idx,
                  p.retr_min, p.max_break)
        for t in range(v_idx + 1, n):
            if s.zone_idx is None:
                if h[t] > s.h1:
                    s.h1_idx, s.h1 = t, h[t]
                if l[t] <= s.zone_top:
                    s.zone_idx, s.l2_idx, s.l2 = t, t, l[t]
                elif t - v_idx > p.max_wait:
                    s.end_idx, s.end_reason = t, "caducado"
                    break
            else:
                if l[t] < s.l2:
                    s.l2_idx, s.l2 = t, l[t]
                if c[t] < s.floor:
                    s.end_idx, s.end_reason = t, "invalidado"
                    break
                if c[t] > s.h1:
                    s.end_idx, s.end_reason = t, "rotura"
                    break
                if t - s.zone_idx > p.max_wait:
                    s.end_idx, s.end_reason = t, "caducado"
                    break
            if s.zone_idx == t and c[t] < s.floor:
                s.end_idx, s.end_reason = t, "invalidado"
                break
        idx = df.index
        s.dates = {k: idx[getattr(s, k + "_idx")] for k in ("r", "l1", "h1", "v", "zone", "l2", "end")
                   if getattr(s, k + "_idx") is not None}
        setups.append(s)
        busy_until = s.end_idx if s.end_idx is not None else n
    return setups


@dataclass
class DailyW:
    a_idx: int  # primer suelo diario
    a: float
    b_idx: int  # rebote (línea de cuello)
    b: float
    c_idx: int  # segundo suelo diario
    c: float
    trigger_idx: int  # cierre por encima de b


def daily_w_triggers(daily, setup, htf_index, pct=0.08, w_tol=0.03, pivots=None):
    """W diarias dentro de la zona de retroceso de `setup`, en orden temporal."""
    if setup.zone_idx is None:
        return []
    didx = daily.index
    start_date = htf_index[max(setup.h1_idx, setup.v_idx)]
    end_date = htf_index[setup.end_idx] if setup.end_idx is not None else didx[-1]
    start = int(didx.searchsorted(start_date, side="right"))
    stop = int(didx.searchsorted(end_date, side="right"))
    h, l, c = (daily[k].to_numpy(float) for k in ("High", "Low", "Close"))
    piv = pivots if pivots is not None else zigzag(h, l, pct)
    out = []
    for k in range(2, len(piv)):
        a, b, cc = piv[k - 2], piv[k - 1], piv[k]
        if cc.kind != "L" or a.idx < start or cc.confirm >= stop:
            continue
        if a.price > setup.zone_top or min(a.price, cc.price) < setup.floor:
            continue
        if cc.price < a.price * (1 - w_tol):
            continue
        low_w = min(a.price, cc.price)
        for d in range(cc.confirm, stop):
            if l[d] < low_w:
                break
            if c[d] > b.price:
                out.append(DailyW(a.idx, a.price, b.idx, b.price, cc.idx, cc.price, d))
                break
    return out
