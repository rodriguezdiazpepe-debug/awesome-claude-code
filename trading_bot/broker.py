"""Broker simulado (paper trading): nunca envía órdenes reales."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Position:
    qty: float
    entry_price: float
    entry_time: int
    stop: float
    take_profit: float
    cost: float  # efectivo gastado, comisiones incluidas


@dataclass
class Trade:
    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    qty: float
    pnl: float
    reason: str


@dataclass
class PaperBroker:
    cash: float
    fee_rate: float
    slippage: float
    position: Position | None = None
    trades: list[Trade] = field(default_factory=list)

    def equity(self, mark_price: float) -> float:
        if self.position is None:
            return self.cash
        return self.cash + self.position.qty * mark_price * (1 - self.fee_rate)

    def buy(self, price: float, qty: float, time_ms: int, stop: float, take_profit: float) -> Position:
        if self.position is not None:
            raise RuntimeError("Ya hay una posición abierta")
        fill = price * (1 + self.slippage)
        cost = fill * qty * (1 + self.fee_rate)
        if cost > self.cash + 1e-9:
            raise ValueError("Efectivo insuficiente")
        self.cash -= cost
        self.position = Position(qty, fill, time_ms, stop, take_profit, cost)
        return self.position

    def sell(self, price: float, time_ms: int, reason: str, apply_slippage: bool = True) -> Trade:
        pos = self.position
        if pos is None:
            raise RuntimeError("No hay posición abierta")
        fill = price * (1 - self.slippage) if apply_slippage else price
        proceeds = fill * pos.qty * (1 - self.fee_rate)
        self.cash += proceeds
        trade = Trade(pos.entry_time, time_ms, pos.entry_price, fill, pos.qty, proceeds - pos.cost, reason)
        self.trades.append(trade)
        self.position = None
        return trade
