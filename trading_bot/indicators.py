"""Indicadores técnicos en Python puro. Devuelven listas alineadas con la entrada
(None mientras no hay datos suficientes)."""

from __future__ import annotations

from .data import Candle


def ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2 / (period + 1)
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(closes: list[float], period: int) -> list[float | None]:
    """RSI con suavizado de Wilder."""
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    avg_g, avg_l = gains / period, losses / period

    def value(g: float, l: float) -> float:
        return 100.0 if l == 0 else 100 - 100 / (1 + g / l)

    out[period] = value(avg_g, avg_l)
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(d, 0)) / period
        avg_l = (avg_l * (period - 1) + max(-d, 0)) / period
        out[i] = value(avg_g, avg_l)
    return out


def atr(candles: list[Candle], period: int) -> list[float | None]:
    """Average True Range con suavizado de Wilder."""
    out: list[float | None] = [None] * len(candles)
    if len(candles) <= period:
        return out
    trs = [candles[0].high - candles[0].low]
    for i in range(1, len(candles)):
        c, prev = candles[i], candles[i - 1].close
        trs.append(max(c.high - c.low, abs(c.high - prev), abs(c.low - prev)))
    prev_atr = sum(trs[1 : period + 1]) / period
    out[period] = prev_atr
    for i in range(period + 1, len(candles)):
        prev_atr = (prev_atr * (period - 1) + trs[i]) / period
        out[i] = prev_atr
    return out


def session_vwap(candles: list[Candle]) -> list[float]:
    """VWAP que se reinicia a las 00:00 UTC de cada día."""
    out = []
    day = None
    pv = vol = 0.0
    for c in candles:
        d = c.open_time // 86_400_000
        if d != day:
            day, pv, vol = d, 0.0, 0.0
        typical = (c.high + c.low + c.close) / 3
        pv += typical * c.volume
        vol += c.volume
        out.append(pv / vol if vol else typical)
    return out
