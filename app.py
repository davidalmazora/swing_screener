"""
SMC Pro - Screener
"""
import warnings
warnings.filterwarnings("ignore")
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="SMC Pro", layout="wide")
st.title("SMC Pro - Screener")

ticker = st.text_input("Ticker", "NVDA")
if ticker:
    df = yf.download(ticker, period="2y", auto_adjust=True, progress=False)
    if df is not None and len(df) >= 200:
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df.index = pd.to_datetime(df.index)
        o, h, l_, c = df["Open"].values, df["High"].values, df["Low"].values, df["Close"].values
        sma50 = pd.Series(c).rolling(50).mean().values
        sma200 = pd.Series(c).rolling(200).mean().values
        trades = []
        for j in range(220, len(df) - 2):
            if c[j] <= o[j] or sma200[j] <= sma200[j-1] or sma50[j] <= sma50[j-1]:
                continue
            for i in range(max(0, j-30), j-5):
                if c[i] >= o[i]: continue
                zone_lo, zone_hi = l_[i], max(o[i], c[i])
                ob = (zone_hi + zone_lo) / 2
                if zone_lo < l_[j] <= zone_hi and abs(l_[j] - ob) / ob < 0.01:
                    entry_price, sl = float(o[j+1]), float(zone_lo)
                    risk = entry_price - sl
                    if risk <= 0: continue
                    tp = entry_price + risk * 2.5
                    found_exit = False
                    for k in range(j+1, len(df)):
                        if l_[k] <= sl:
                            trades.append((entry_price, sl, (sl - entry_price) / entry_price))
                            found_exit = True
                            break
                        elif h[k] >= tp:
                            trades.append((entry_price, tp, (tp - entry_price) / entry_price))
                            found_exit = True
                            break
                    if not found_exit:
                        ret = (c[-1] - entry_price) / entry_price
                        trades.append((entry_price, c[-1], ret))
                    break
        if trades:
            rets = [t[2] for t in trades]
            pf = sum(r for r in rets if r > 0) / (abs(sum(r for r in rets if r <= 0)) or 0.001)
            cum = 1.0
            for r in rets: cum *= 1 + r
            cagr = ((cum) ** 0.5 - 1) * 100
            st.metric("Operaciones", len(trades))
            st.metric("Profit Factor", f"{pf:.2f}")
            st.metric("CAGR 2y", f"{cagr:.1f}%")
            fig = go.Figure(data=[go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"])])
            fig.update_layout(height=450, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay señales SMC.")
    else:
        st.error("Datos insuficientes.")
