"""Estrategia intradía: cruce alcista de EMAs confirmado por RSI y VWAP."""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .data import Candle
from .indicators import atr, ema, rsi, session_vwap


@dataclass
class Indicators:
    ema_fast: list
    ema_slow: list
    rsi: list
    atr: list
    vwap: list


def compute(candles: list[Candle], cfg: Config) -> Indicators:
    closes = [c.close for c in candles]
    return Indicators(
        ema_fast=ema(closes, cfg.ema_fast),
        ema_slow=ema(closes, cfg.ema_slow),
        rsi=rsi(closes, cfg.rsi_period),
        atr=atr(candles, cfg.atr_period),
        vwap=session_vwap(candles),
    )


def _ready(ind: Indicators, i: int) -> bool:
    return i >= 1 and None not in (
        ind.ema_fast[i], ind.ema_slow[i], ind.ema_fast[i - 1], ind.ema_slow[i - 1], ind.rsi[i], ind.atr[i]
    )


def entry_signal(candles: list[Candle], ind: Indicators, i: int, cfg: Config) -> bool:
    """Compra si la EMA rápida cruza por encima de la lenta, el RSI muestra
    momentum sin sobrecompra y el precio está por encima del VWAP del día."""
    if not _ready(ind, i):
        return False
    crossed_up = ind.ema_fast[i - 1] <= ind.ema_slow[i - 1] and ind.ema_fast[i] > ind.ema_slow[i]
    return crossed_up and cfg.rsi_min <= ind.rsi[i] <= cfg.rsi_max and candles[i].close > ind.vwap[i]


def exit_signal(ind: Indicators, i: int) -> bool:
    """Sale si la EMA rápida cruza por debajo de la lenta."""
    if not _ready(ind, i):
        return False
    return ind.ema_fast[i - 1] >= ind.ema_slow[i - 1] and ind.ema_fast[i] < ind.ema_slow[i]
