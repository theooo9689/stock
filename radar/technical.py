from __future__ import annotations

import math
import numpy as np
import pandas as pd


def clean(value):
    return float(value) if value is not None and np.isfinite(value) else None


def wilder(series, n=14):
    """Wilder: initial SMA of n observations, followed by alpha=1/n recursion."""
    out = pd.Series(np.nan, index=series.index, dtype=float)
    valid = series.dropna()
    if len(valid) < n:
        return out
    seed = valid.index[n - 1]
    out.loc[seed] = valid.iloc[:n].mean()
    indices = list(series.index)
    start = indices.index(seed)
    for i in range(start + 1, len(series)):
        if pd.notna(series.iloc[i]):
            out.iloc[i] = (out.iloc[i - 1] * (n - 1) + series.iloc[i]) / n
    return out


def indicators(frame, crypto=False):
    f = frame.sort_index().copy()
    close, high, low, vol = (f[x].astype(float) for x in ("close", "high", "low", "volume"))
    if len(close) < 35:
        return {"error": "Histórico insuficiente: pelo menos 35 candles necessários"}
    delta = close.diff()
    up, down = wilder(delta.clip(lower=0)), wilder(-delta.clip(upper=0))
    rs = up / down.replace(0, np.nan)
    rsi = (100 - 100 / (1 + rs)).where(down != 0, 100).where((up != 0) | (down != 0), 50)
    macd = close.ewm(span=12, adjust=False, min_periods=12).mean() - close.ewm(span=26, adjust=False, min_periods=26).mean()
    signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    sma = {n: clean(close.rolling(n).mean().iloc[-1]) for n in (20, 50, 200)}
    days = 365 if crypto else 252
    last, s50, s200 = close.iloc[-1], sma[50], sma[200]
    trend = "indeterminada"
    if s50 is not None and s200 is not None:
        trend = "alta" if last > s50 > s200 else "baixa" if last < s50 < s200 else "lateralização"
    result = {
        "rsi14": clean(rsi.iloc[-1]), "macd": clean(macd.iloc[-1]), "macd_signal": clean(signal.iloc[-1]),
        "macd_histogram": clean((macd-signal).iloc[-1]), "atr14": clean(wilder(tr).iloc[-1]),
        "sma20": sma[20], "sma50": s50, "sma200": s200,
        "relative_volume": clean(vol.iloc[-1] / vol.iloc[-21:-1].mean()) if vol.iloc[-21:-1].mean() else None,
        "annualized_volatility": clean(close.pct_change().tail(60).std() * math.sqrt(days)),
        "high52w": clean(high.tail(days).max()), "low52w": clean(low.tail(days).min()),
        "drawdown": clean(last / close.cummax().iloc[-1] - 1),
        "max_drawdown": clean((close / close.cummax() - 1).min()),
        "support": clean(low.tail(20).min()), "resistance": clean(high.tail(20).max()),
        "trend": trend, "bars": len(f), "start": str(f.index[0]), "end": str(f.index[-1]),
        "method": "Candles diários completos; RSI/ATR Wilder 14 (SMA inicial); MACD EMA 12/26/9 adjust=False; suporte/máxima e resistência/mínima da janela de 20 pregões; volatilidade desvio-padrão 60 retornos × raiz 252 (cripto 365); níveis 52s: 252/365 dias.",
    }
    result["method"] = result["method"].replace("suporte/máxima e resistência/mínima", "suporte/mínima e resistência/máxima")
    return result


def returns(frame):
    # adjclose accounts for distributions/splits where supplied; crypto uses close.
    series = frame.get("adjclose", frame["close"]).dropna()
    out = {}
    for n in (7, 30, 252):
        out[f"return_{n}_bars"] = clean(series.iloc[-1] / series.iloc[-n-1] - 1) if len(series) > n else None
    return out
