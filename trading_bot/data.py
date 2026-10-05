"""Descarga de velas (OHLCV) desde APIs públicas, sin claves ni dependencias."""

from __future__ import annotations

import json
import math
import random
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

BINANCE_URL = "https://data-api.binance.vision/api/v3/klines"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

INTERVAL_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
}


@dataclass(frozen=True)
class Candle:
    open_time: int  # epoch en milisegundos (UTC)
    open: float
    high: float
    low: float
    close: float
    volume: float


def _get_json(url: str, params: dict) -> object:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full, headers={"User-Agent": "Mozilla/5.0 trading-bot"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def utc_day_start_ms(now_ms: int) -> int:
    return now_ms - now_ms % 86_400_000


def fetch_binance(symbol: str, interval: str, start_ms: int, now_ms: int | None = None) -> list[Candle]:
    """Velas cerradas desde start_ms hasta ahora (pagina de 1000 en 1000)."""
    now_ms = now_ms or int(time.time() * 1000)
    step = INTERVAL_MS[interval]
    candles: list[Candle] = []
    cursor = start_ms
    while cursor < now_ms:
        rows = _get_json(
            BINANCE_URL,
            {"symbol": symbol.upper(), "interval": interval, "startTime": cursor, "limit": 1000},
        )
        if not rows:
            break
        for r in rows:
            candles.append(Candle(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])))
        cursor = int(rows[-1][0]) + step
        if len(rows) < 1000:
            break
    # Descartar la vela que aún se está formando.
    return [c for c in candles if c.open_time + step <= now_ms]


def fetch_yahoo(symbol: str, interval: str, now_ms: int | None = None) -> list[Candle]:
    """Velas intradía de los últimos 5 días (acciones, ETF, índices)."""
    now_ms = now_ms or int(time.time() * 1000)
    step = INTERVAL_MS[interval]
    data = _get_json(YAHOO_URL.format(symbol=urllib.parse.quote(symbol)), {"interval": interval, "range": "5d"})
    result = data["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    candles = []
    for i, ts in enumerate(result.get("timestamp") or []):
        o, h, l, c, v = (quote[k][i] for k in ("open", "high", "low", "close", "volume"))
        if None in (o, h, l, c):
            continue
        candles.append(Candle(ts * 1000, float(o), float(h), float(l), float(c), float(v or 0)))
    return [c for c in candles if c.open_time + step <= now_ms]


def fetch_candles(source: str, symbol: str, interval: str, warmup: int, now_ms: int | None = None) -> list[Candle]:
    """Velas de hoy (UTC) más `warmup` velas previas para calentar indicadores."""
    if interval not in INTERVAL_MS:
        raise ValueError(f"Intervalo no soportado: {interval}. Usa uno de {list(INTERVAL_MS)}")
    now_ms = now_ms or int(time.time() * 1000)
    if source == "binance":
        start = utc_day_start_ms(now_ms) - warmup * INTERVAL_MS[interval]
        return fetch_binance(symbol, interval, start, now_ms)
    if source == "yahoo":
        return fetch_yahoo(symbol, interval, now_ms)
    raise ValueError(f"Fuente desconocida: {source}")


def synthetic_candles(n: int = 600, interval: str = "5m", seed: int = 7, start_price: float = 60_000.0,
                      end_ms: int | None = None) -> list[Candle]:
    """Paseo aleatorio con regímenes de tendencia, para probar sin conexión."""
    rng = random.Random(seed)
    step = INTERVAL_MS[interval]
    end_ms = end_ms or int(time.time() * 1000)
    t0 = end_ms - end_ms % step - n * step
    price = start_price
    drift = 0.0
    candles = []
    for i in range(n):
        if i % 60 == 0:
            drift = rng.choice([-1, 0, 1]) * 0.0006
        vol = 0.002 * (1 + 0.5 * math.sin(i / 25))
        o = price
        c = o * (1 + drift + rng.gauss(0, vol))
        h = max(o, c) * (1 + abs(rng.gauss(0, vol / 2)))
        l = min(o, c) * (1 - abs(rng.gauss(0, vol / 2)))
        candles.append(Candle(t0 + i * step, o, h, l, c, rng.uniform(5, 50)))
        price = c
    return candles
