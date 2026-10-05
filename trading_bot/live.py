"""Bucle de paper trading en tiempo real: espera a cada cierre de vela, descarga
datos, decide y registra las operaciones simuladas en un CSV."""

from __future__ import annotations

import csv
import os
import time

from .config import Config
from .data import INTERVAL_MS, fetch_candles, utc_day_start_ms
from .engine import Engine, fmt_time
from .strategy import compute


def _append_trades_csv(path: str, trades) -> None:
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["entrada", "salida", "precio_entrada", "precio_salida", "cantidad", "pnl", "motivo"])
        for t in trades:
            w.writerow([fmt_time(t.entry_time), fmt_time(t.exit_time), f"{t.entry_price:.4f}",
                        f"{t.exit_price:.4f}", f"{t.qty:.8f}", f"{t.pnl:.2f}", t.reason])


def run_paper(cfg: Config, trades_csv: str = "trades_hoy.csv") -> Engine:
    engine = Engine(cfg)
    step = INTERVAL_MS[cfg.interval]
    today = utc_day_start_ms(int(time.time() * 1000))
    last_processed: int | None = None
    saved = 0
    print(f"Paper trading {cfg.symbol} ({cfg.source}, {cfg.interval}) | capital {cfg.starting_cash:,.2f}")
    print(f"Cierre de sesión {cfg.session_end_utc} UTC. Ctrl+C para detener.\n")
    try:
        while True:
            try:
                candles = fetch_candles(cfg.source, cfg.symbol, cfg.interval, cfg.warmup)
            except Exception as exc:  # red caída, límite de peticiones, etc.
                print(f"Error descargando datos: {exc}. Reintento en 15 s")
                time.sleep(15)
                continue
            if not candles:
                time.sleep(15)
                continue

            if last_processed is None:
                # Arrancamos desde la última vela cerrada: no operamos el pasado.
                last_processed = candles[-1].open_time
                print(f"Última vela cerrada {fmt_time(last_processed)}  precio {candles[-1].close:,.2f}")
            else:
                ind = compute(candles, cfg)
                for i, c in enumerate(candles):
                    if c.open_time > last_processed:
                        for line in engine.on_candle(candles, ind, i):
                            print(line)
                        last_processed = c.open_time
                eq = engine.broker.equity(candles[-1].close)
                pos = "en posición" if engine.broker.position else "sin posición"
                print(f"[{fmt_time(last_processed + step)}] precio {candles[-1].close:,.2f} | "
                      f"capital {eq:,.2f} | {pos}")

            if len(engine.broker.trades) > saved:
                _append_trades_csv(trades_csv, engine.broker.trades[saved:])
                saved = len(engine.broker.trades)

            now = int(time.time() * 1000)
            if engine._past_session_end(last_processed + step) and engine.broker.position is None \
                    and last_processed >= today:
                print("Sesión terminada.")
                break
            next_close = (now // step + 1) * step
            time.sleep(max(1.0, (next_close - now) / 1000 + 3))
    except KeyboardInterrupt:
        print("\nDetenido por el usuario.")
    if engine.broker.position is not None:
        print("Aviso: queda una posición simulada abierta.")
    trades = engine.broker.trades
    pnl = sum(t.pnl for t in trades)
    print(f"\nOperaciones: {len(trades)} | PnL total {pnl:+,.2f} | registro en {trades_csv}")
    return engine
