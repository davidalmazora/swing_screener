"""Gráficos de velas con el patrón marcado (matplotlib)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

UP, DOWN = "#26a69a", "#ef5350"
MAS = {20: "#f4c430", 50: "#ff9800", 100: "#e65100", 200: "#d50000"}


def candles(ax, df):
    x = np.arange(len(df))
    o, h, l, c = (df[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
    col = np.where(c >= o, UP, DOWN)
    ax.vlines(x, l, h, color=col, linewidth=0.8)
    ax.bar(x, np.maximum(np.abs(c - o), (h - l) * 0.02), bottom=np.minimum(o, c), color=col, width=0.7)
    for n, color in MAS.items():
        ma = df["Close"].rolling(n).mean()
        if ma.notna().any():
            ax.plot(x, ma.to_numpy(), color=color, linewidth=1, label=f"SMA{n}")
    step = max(1, len(df) // 8)
    ax.set_xticks(x[::step])
    ax.set_xticklabels([d.strftime("%Y-%m") for d in df.index[::step]], fontsize=8)
    ax.set_xlim(-1, len(df))
    ax.grid(alpha=0.2)
    return x


def setup_figure(ticker, daily, htf, setup, trig=None, log=True):
    s = setup
    fig, axes = plt.subplots(2 if trig else 1, 1, figsize=(13, 9 if trig else 5.5), squeeze=False)
    ax = axes[0][0]
    lo = max(0, s.r_idx - 40)
    hi = min(len(htf), (s.end_idx if s.end_idx is not None else len(htf) - 1) + 25)
    view = htf.iloc[lo:hi]
    candles(ax, view)
    if log:
        ax.set_yscale("log")
    for name, i, p, va in (("R", s.r_idx, s.r, "bottom"), ("L1", s.l1_idx, s.l1, "top"),
                           ("H1", s.h1_idx, s.h1, "bottom")):
        ax.annotate(name, (i - lo, p), ha="center", va=va, fontsize=11, weight="bold", color="navy",
                    xytext=(0, 8 if va == "bottom" else -8), textcoords="offset points")
    if s.zone_idx is not None:
        x0 = s.h1_idx - lo
        x1 = (s.end_idx if s.end_idx is not None else len(htf) - 1) - lo
        ax.fill_between([x0, x1], s.floor, s.zone_top, color="gold", alpha=0.25, label="zona retroceso")
        ax.annotate("L2", (s.l2_idx - lo, s.l2), ha="center", va="top", fontsize=10, color="navy",
                    xytext=(0, -8), textcoords="offset points")
    ax.axhline(s.h1, color="navy", linestyle=":", linewidth=1)
    ax.axhline(s.r, color=UP, linestyle="--", linewidth=1, label="objetivo espejo (R)")
    tf_name = {"W": "semanal", "M": "mensual"}[s.tf]
    ax.set_title(f"{ticker} · {tf_name} · estado: {s.state}", loc="left")
    ax.legend(loc="upper right", fontsize=8)

    if trig:
        w = trig[0]
        ax2 = axes[1][0]
        a = max(0, min(w.a_idx - 80, w.d0_idx - 10 if w.d0_idx is not None else w.a_idx))
        b = min(len(daily), w.trigger_idx + 80)
        dv = daily.iloc[a:b]
        candles(ax2, dv)
        stop = min(w.a, w.c) * 0.995
        for name, i, p, va in (("a", w.a_idx, w.a, "top"), ("b", w.b_idx, w.b, "bottom"),
                               ("c", w.c_idx, w.c, "top")):
            ax2.annotate(name, (i - a, p), ha="center", va=va, fontsize=11, weight="bold", color="navy",
                         xytext=(0, 8 if va == "bottom" else -8), textcoords="offset points")
        ax2.axvline(w.trigger_idx + 1 - a, color="green", linewidth=1, label="entrada")
        ax2.axhline(stop, color=DOWN, linestyle="--", linewidth=1, label="stop")
        if w.d0:
            ax2.axhline(w.d0, color=UP, linestyle="--", linewidth=1, label="objetivo espejo diario (D0)")
            if w.d0_idx >= a:
                ax2.annotate("D0", (w.d0_idx - a, w.d0), ha="center", va="bottom", fontsize=11,
                             weight="bold", color="navy", xytext=(0, 8), textcoords="offset points")
        ax2.axhline(w.b, color="gray", linestyle=":", linewidth=1)
        ax2.set_title(f"diario · W en la zona · entrada {daily.index[min(w.trigger_idx + 1, len(daily) - 1)].date()}",
                      loc="left")
        ax2.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    return fig
