"""Parámetros del bot. Todos se pueden sobrescribir desde la línea de comandos."""

from dataclasses import dataclass


@dataclass
class Config:
    # Mercado
    source: str = "binance"  # "binance" (cripto, 24/7) o "yahoo" (acciones/ETF)
    symbol: str = "BTCUSDT"
    interval: str = "5m"

    # Estrategia: cruce de EMAs + filtro RSI + precio sobre VWAP del día
    ema_fast: int = 9
    ema_slow: int = 21
    rsi_period: int = 14
    rsi_min: float = 50.0  # momentum alcista mínimo para entrar
    rsi_max: float = 70.0  # no comprar en sobrecompra
    atr_period: int = 14
    stop_atr: float = 1.5  # stop-loss = entrada - 1.5 * ATR
    take_profit_atr: float = 3.0  # take-profit = entrada + 3 * ATR (R:R 1:2)

    # Gestión de riesgo
    starting_cash: float = 10_000.0
    risk_per_trade: float = 0.01  # arriesgar 1% del capital por operación
    max_position_pct: float = 0.95  # nunca más del 95% del capital en una posición
    max_daily_loss: float = 0.03  # parar de operar hoy al perder un 3%
    max_trades_per_day: int = 10
    session_end_utc: str = "23:50"  # cerrar todo a esta hora (HH:MM UTC)

    # Costes simulados
    fee_rate: float = 0.001  # 0.1% por lado
    slippage: float = 0.0005  # 0.05% contra nosotros en cada ejecución
    min_notional: float = 5.0  # importe mínimo por orden (Binance exige ~5 EUR/USDT)

    @property
    def warmup(self) -> int:
        """Velas necesarias antes de que los indicadores sean fiables."""
        return max(self.ema_slow, self.rsi_period, self.atr_period) * 3
