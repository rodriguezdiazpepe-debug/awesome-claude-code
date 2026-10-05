"""Backtest sobre las velas de hoy y resumen de resultados."""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .data import INTERVAL_MS, Candle
from .engine import Engine
from .strategy import compute


@dataclass
class Report:
    start_equity: float
    end_equity: float
    trades: int
    wins: int
    gross_profit: float
    gross_loss: float
    max_drawdown: float
    buy_and_hold: float
    candles: int

    @property
    def return_pct(self) -> float:
        return (self.end_equity / self.start_equity - 1) * 100

    @property
    def win_rate(self) -> float:
        return self.wins / self.trades * 100 if self.trades else 0.0

    @property
    def profit_factor(self) -> float:
        return self.gross_profit / self.gross_loss if self.gross_loss else float("inf") if self.gross_profit else 0.0

    def __str__(self) -> str:
        return "\n".join([
            "=" * 46,
            f"Velas analizadas:      {self.candles}",
            f"Capital inicial:       {self.start_equity:,.2f}",
            f"Capital final:         {self.end_equity:,.2f}",
            f"Rentabilidad:          {self.return_pct:+.2f}%",
            f"Comprar y mantener:    {self.buy_and_hold:+.2f}%",
            f"Operaciones:           {self.trades}  (aciertos {self.win_rate:.0f}%)",
            f"Profit factor:         {self.profit_factor:.2f}",
            f"Máximo drawdown:       {self.max_drawdown:.2f}%",
            "=" * 46,
        ])


def run_backtest(candles: list[Candle], cfg: Config, trade_from_ms: int, verbose: bool = True) -> tuple[Report, Engine]:
    """Opera solo velas con open_time >= trade_from_ms; las anteriores calientan indicadores."""
    engine = Engine(cfg)
    ind = compute(candles, cfg)
    first = next((i for i, c in enumerate(candles) if c.open_time >= trade_from_ms), len(candles))
    if first >= len(candles):
        raise ValueError("No hay velas en el periodo a operar")
    peak = cfg.starting_cash
    max_dd = 0.0
    for i in range(first, len(candles)):
        for line in engine.on_candle(candles, ind, i):
            if verbose:
                print(line)
        eq = engine.broker.equity(candles[i].close)
        peak = max(peak, eq)
        max_dd = max(max_dd, (peak - eq) / peak * 100)
    last = candles[-1]
    for line in engine.force_close(last.close, last.open_time + INTERVAL_MS[cfg.interval], "fin de datos"):
        if verbose:
            print(line)
    trades = engine.broker.trades
    report = Report(
        start_equity=cfg.starting_cash,
        end_equity=engine.broker.cash,
        trades=len(trades),
        wins=sum(t.pnl > 0 for t in trades),
        gross_profit=sum(t.pnl for t in trades if t.pnl > 0),
        gross_loss=-sum(t.pnl for t in trades if t.pnl < 0),
        max_drawdown=max_dd,
        buy_and_hold=(last.close / candles[first].open - 1) * 100,
        candles=len(candles) - first,
    )
    return report, engine
