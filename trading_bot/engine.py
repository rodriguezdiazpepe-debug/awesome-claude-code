"""Motor de decisión compartido por el backtest y el modo paper en vivo.
Procesa una vela cerrada cada vez y aplica estrategia + gestión de riesgo."""

from __future__ import annotations

from datetime import datetime, timezone

from .broker import PaperBroker
from .config import Config
from .data import INTERVAL_MS, Candle
from .strategy import Indicators, entry_signal, exit_signal


def fmt_time(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


class Engine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.broker = PaperBroker(cfg.starting_cash, cfg.fee_rate, cfg.slippage)
        self.step_ms = INTERVAL_MS[cfg.interval]
        h, m = (int(x) for x in cfg.session_end_utc.split(":"))
        self.session_end_offset_ms = (h * 60 + m) * 60_000
        self.day: int | None = None
        self.day_start_equity = cfg.starting_cash
        self.trades_today = 0
        self.halted = False  # límite de pérdida diaria alcanzado
        self.log: list[str] = []

    def _emit(self, ms: int, msg: str) -> str:
        line = f"[{fmt_time(ms)}] {msg}"
        self.log.append(line)
        return line

    def _past_session_end(self, close_ms: int) -> bool:
        return close_ms % 86_400_000 >= self.session_end_offset_ms

    def _close(self, price: float, ms: int, reason: str, slippage: bool = True) -> list[str]:
        t = self.broker.sell(price, ms, reason, apply_slippage=slippage)
        return [self._emit(ms, f"VENTA  {t.qty:.6f} @ {t.exit_price:,.2f} ({reason}) PnL {t.pnl:+,.2f}")]

    def on_candle(self, candles: list[Candle], ind: Indicators, i: int) -> list[str]:
        """Procesa la vela cerrada `i`. Devuelve los eventos ocurridos."""
        cfg, broker, c = self.cfg, self.broker, candles[i]
        close_ms = c.open_time + self.step_ms
        events: list[str] = []

        day = c.open_time // 86_400_000
        if day != self.day:
            self.day = day
            self.day_start_equity = broker.equity(c.open)
            self.trades_today = 0
            self.halted = False

        # 1) Stop-loss / take-profit dentro de la vela (si ambos se tocan, asumimos el stop).
        pos = broker.position
        if pos is not None:
            if c.open <= pos.stop:  # hueco por debajo del stop: ejecuta a la apertura
                events += self._close(c.open, close_ms, "stop (hueco)")
            elif c.low <= pos.stop:
                events += self._close(pos.stop, close_ms, "stop-loss")
            elif c.high >= pos.take_profit:
                events += self._close(max(pos.take_profit, c.open), close_ms, "take-profit", slippage=False)

        # 2) Límite de pérdida diaria.
        equity = broker.equity(c.close)
        if not self.halted and equity <= self.day_start_equity * (1 - cfg.max_daily_loss):
            self.halted = True
            if broker.position is not None:
                events += self._close(c.close, close_ms, "límite de pérdida diaria")
            events.append(self._emit(close_ms, "Límite de pérdida diaria alcanzado: no se opera más hoy"))

        # 3) Salida por señal o por fin de sesión.
        if broker.position is not None:
            if self._past_session_end(close_ms):
                events += self._close(c.close, close_ms, "fin de sesión")
            elif exit_signal(ind, i):
                events += self._close(c.close, close_ms, "cruce bajista EMA")

        # 4) Entrada.
        if (
            broker.position is None
            and not self.halted
            and self.trades_today < cfg.max_trades_per_day
            and not self._past_session_end(close_ms)
            and entry_signal(candles, ind, i, cfg)
        ):
            events += self._open(c.close, ind.atr[i], close_ms)
        return events

    def _open(self, price: float, atr_value: float, ms: int) -> list[str]:
        cfg, broker = self.cfg, self.broker
        stop_dist = cfg.stop_atr * atr_value
        if stop_dist <= 0:
            return []
        fill = price * (1 + cfg.slippage)
        risk_qty = broker.cash * cfg.risk_per_trade / stop_dist
        max_qty = broker.cash * cfg.max_position_pct / (fill * (1 + cfg.fee_rate))
        qty = min(risk_qty, max_qty)
        if qty * fill < cfg.min_notional:
            return [self._emit(ms, f"Señal de compra ignorada: {qty * fill:,.2f} < mínimo por orden {cfg.min_notional:,.2f}")]
        pos = broker.buy(price, qty, ms, stop=price - stop_dist, take_profit=price + cfg.take_profit_atr * atr_value)
        self.trades_today += 1
        return [self._emit(ms, f"COMPRA {qty:.6f} @ {pos.entry_price:,.2f}  stop {pos.stop:,.2f}  objetivo {pos.take_profit:,.2f}")]

    def force_close(self, price: float, ms: int, reason: str) -> list[str]:
        return self._close(price, ms, reason) if self.broker.position is not None else []
