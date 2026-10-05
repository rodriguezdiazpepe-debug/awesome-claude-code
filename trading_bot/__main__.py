"""Uso:
    python -m trading_bot backtest                 # backtest con las velas de hoy
    python -m trading_bot paper                    # paper trading en tiempo real
    python -m trading_bot demo                     # backtest con datos sintéticos (sin red)
    python -m trading_bot backtest --source yahoo --symbol SPY --session-end 19:55
    python -m trading_bot paper --symbol BTCEUR --cash 5 --min-notional 0   # simular con 5 €
"""

from __future__ import annotations

import argparse
import sys
import time

from .backtest import run_backtest
from .config import Config
from .data import fetch_candles, synthetic_candles, utc_day_start_ms


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="trading_bot", description="Bot de trading intradía (simulado).")
    p.add_argument("mode", choices=["backtest", "paper", "demo"])
    p.add_argument("--source", choices=["binance", "yahoo"], default=Config.source)
    p.add_argument("--symbol", default=Config.symbol)
    p.add_argument("--interval", default=Config.interval, choices=["1m", "5m", "15m", "30m", "1h"])
    p.add_argument("--cash", type=float, default=Config.starting_cash)
    p.add_argument("--risk", type=float, default=Config.risk_per_trade, help="fracción del capital por operación")
    p.add_argument("--max-daily-loss", type=float, default=Config.max_daily_loss)
    p.add_argument("--session-end", default=Config.session_end_utc, help="HH:MM UTC para cerrar posiciones")
    p.add_argument("--min-notional", type=float, default=Config.min_notional,
                   help="importe mínimo por orden; 0 para simular capitales muy pequeños")
    p.add_argument("--quiet", action="store_true", help="solo mostrar el resumen")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config(
        source=args.source, symbol=args.symbol, interval=args.interval, starting_cash=args.cash,
        risk_per_trade=args.risk, max_daily_loss=args.max_daily_loss, session_end_utc=args.session_end,
        min_notional=args.min_notional,
    )
    print("AVISO: modo simulado. Ninguna orden se envía a un exchange. No es asesoramiento financiero.\n")
    if cfg.starting_cash * cfg.max_position_pct < cfg.min_notional:
        print(f"AVISO: con {cfg.starting_cash:,.2f} de capital no se alcanza el mínimo por orden "
              f"({cfg.min_notional:,.2f}); el bot no podrá abrir operaciones. "
              "Usa --min-notional 0 para simularlo de todos modos.\n")

    if args.mode == "paper":
        from .live import run_paper
        run_paper(cfg)
        return 0

    if args.mode == "demo":
        candles = synthetic_candles(n=cfg.warmup + 288, interval=cfg.interval)
        trade_from = candles[cfg.warmup].open_time
        print(f"Datos sintéticos: {len(candles)} velas de {cfg.interval}\n")
    else:
        try:
            candles = fetch_candles(cfg.source, cfg.symbol, cfg.interval, cfg.warmup)
        except Exception as exc:
            print(f"No se pudieron descargar datos de {cfg.source}: {exc}", file=sys.stderr)
            return 1
        trade_from = utc_day_start_ms(int(time.time() * 1000))
        print(f"{cfg.symbol}: {len(candles)} velas descargadas ({cfg.interval})\n")

    try:
        report, _ = run_backtest(candles, cfg, trade_from, verbose=not args.quiet)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
