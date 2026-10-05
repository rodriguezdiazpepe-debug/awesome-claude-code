import unittest

from trading_bot.backtest import run_backtest
from trading_bot.config import Config
from trading_bot.data import Candle, synthetic_candles
from trading_bot.engine import Engine
from trading_bot.indicators import ema, rsi, session_vwap
from trading_bot.strategy import Indicators

DAY = 86_400_000
STEP = 300_000


def candle(i, o, h, l, c, day=0):
    return Candle(day * DAY + i * STEP, o, h, l, c, 1.0)


def flat_indicators(n, atr_value=1.0):
    """Indicadores neutros (sin cruces) para probar la gestión de riesgo aislada."""
    return Indicators([1.0] * n, [1.0] * n, [50.0] * n, [atr_value] * n, [0.0] * n)


class IndicatorTests(unittest.TestCase):
    def test_ema_seeds_with_sma(self):
        out = ema([1, 2, 3, 4, 5], 3)
        self.assertEqual(out[:2], [None, None])
        self.assertAlmostEqual(out[2], 2.0)
        self.assertAlmostEqual(out[3], 3.0)

    def test_rsi_extremes(self):
        self.assertEqual(rsi(list(range(1, 30)), 14)[-1], 100.0)
        self.assertAlmostEqual(rsi(list(range(30, 1, -1)), 14)[-1], 0.0)

    def test_vwap_resets_each_day(self):
        cs = [candle(0, 10, 10, 10, 10), candle(1, 20, 20, 20, 20), candle(0, 50, 50, 50, 50, day=1)]
        self.assertEqual(session_vwap(cs), [10, 15, 50])


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(fee_rate=0.0, slippage=0.0, session_end_utc="23:50")

    def open_position(self, engine, price=100.0, atr_value=1.0):
        engine._open(price, atr_value, 0)
        return engine.broker.position

    def test_position_size_risks_one_percent(self):
        engine = Engine(self.cfg)
        pos = self.open_position(engine, price=100.0, atr_value=2.0)
        # Riesgo 1% de 10.000 = 100; distancia al stop 1.5*2 = 3 → 33.3 uds, limitado al 95% del capital.
        self.assertAlmostEqual(pos.qty, min(100 / 3, 9_500 / 100))
        self.assertAlmostEqual(pos.stop, 97.0)
        self.assertAlmostEqual(pos.take_profit, 106.0)

    def test_stop_loss_hit(self):
        engine = Engine(self.cfg)
        self.open_position(engine)
        cs = [candle(0, 100, 100, 100, 100), candle(1, 100, 100.5, 98, 99)]
        engine.day = 0
        engine.on_candle(cs, flat_indicators(2), 1)
        self.assertIsNone(engine.broker.position)
        self.assertEqual(engine.broker.trades[-1].reason, "stop-loss")
        self.assertAlmostEqual(engine.broker.trades[-1].exit_price, 98.5)

    def test_take_profit_hit(self):
        engine = Engine(self.cfg)
        self.open_position(engine)
        cs = [candle(0, 100, 100, 100, 100), candle(1, 100, 104, 99.5, 103)]
        engine.day = 0
        engine.on_candle(cs, flat_indicators(2), 1)
        self.assertEqual(engine.broker.trades[-1].reason, "take-profit")
        self.assertGreater(engine.broker.trades[-1].pnl, 0)

    def test_session_end_closes_position(self):
        engine = Engine(self.cfg)
        self.open_position(engine)
        i = (23 * 60 + 50) // 5 - 1  # vela que cierra a las 23:50
        cs = [candle(j, 100, 100.2, 99.9, 100) for j in range(i + 1)]
        engine.day = 0
        engine.on_candle(cs, flat_indicators(len(cs)), i)
        self.assertEqual(engine.broker.trades[-1].reason, "fin de sesión")

    def test_daily_loss_limit_halts_trading(self):
        cfg = Config(fee_rate=0.0, slippage=0.0, max_position_pct=1.0, risk_per_trade=1.0, stop_atr=50)
        engine = Engine(cfg)
        engine.day = 0
        engine._open(100.0, 1.0, 0)
        cs = [candle(0, 100, 100, 100, 100), candle(1, 100, 100, 95, 95)]
        engine.on_candle(cs, flat_indicators(2), 1)
        self.assertTrue(engine.halted)
        self.assertIsNone(engine.broker.position)

    def test_min_notional_blocks_tiny_accounts(self):
        engine = Engine(Config(starting_cash=5.0))
        self.assertIsNone(self.open_position(engine))
        engine = Engine(Config(starting_cash=5.0, min_notional=0.0))
        self.assertIsNotNone(self.open_position(engine))


class BacktestTests(unittest.TestCase):
    def test_backtest_runs_and_ends_flat(self):
        cfg = Config()
        cs = synthetic_candles(n=cfg.warmup + 288, end_ms=10 * DAY)
        report, engine = run_backtest(cs, cfg, cs[cfg.warmup].open_time, verbose=False)
        self.assertIsNone(engine.broker.position)
        self.assertEqual(report.candles, 288)
        self.assertAlmostEqual(report.end_equity, cfg.starting_cash + sum(t.pnl for t in engine.broker.trades))


if __name__ == "__main__":
    unittest.main()
