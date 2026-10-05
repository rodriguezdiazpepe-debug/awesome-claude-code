# Bot de trading intradía (simulado)

Bot de trading para operar **el día de hoy** en modo *paper trading* (dinero ficticio).
Solo usa la biblioteca estándar de Python 3.10+, así que no hay que instalar nada.

> ⚠️ **No envía órdenes reales.** Es una herramienta educativa y no es asesoramiento financiero.
> La mayoría de las estrategias intradía pierden dinero tras comisiones. Pruébalo en simulado varios días
> antes de plantearte usar dinero real.

## Uso rápido

Ejecútalo desde la raíz del repositorio:

```bash
# Backtest con las velas de hoy (BTC/USDT, velas de 5 min, datos públicos de Binance)
python -m trading_bot backtest

# Paper trading en tiempo real: decide a cada cierre de vela y guarda las operaciones en trades_hoy.csv
python -m trading_bot paper

# Con euros (5 € de capital; --min-notional 0 permite simular por debajo del mínimo del exchange)
python -m trading_bot paper --symbol BTCEUR --cash 5 --min-notional 0

# Acciones/ETF con Yahoo Finance (la sesión de EE. UU. cierra a las 20:00 UTC en horario de verano)
python -m trading_bot backtest --source yahoo --symbol SPY --session-end 19:55

# Prueba sin conexión con datos sintéticos
python -m trading_bot demo
```

Opciones: `--interval {1m,5m,15m,30m,1h}`, `--cash`, `--risk` (fracción arriesgada por operación),
`--max-daily-loss`, `--session-end HH:MM` (UTC), `--min-notional`, `--quiet`.
El resto de parámetros (periodos de EMA/RSI/ATR, comisiones…) están en `config.py`.

## Estrategia

Solo largos (compra y vende, sin apalancamiento ni cortos):

- **Entrada:** la EMA 9 cruza por encima de la EMA 21, el RSI(14) está entre 50 y 70
  (momentum sin sobrecompra) y el precio está por encima del VWAP del día.
- **Salida:** stop-loss a 1,5 × ATR, take-profit a 3 × ATR (relación riesgo/beneficio 1:2),
  cruce bajista de EMAs o cierre de sesión (`--session-end`).

## Gestión de riesgo

- Arriesga un 1 % del capital por operación (tamaño = riesgo / distancia al stop), con un máximo del 95 % del capital.
- Deja de operar el resto del día si pierde un 3 %.
- Máximo 10 operaciones al día.
- Comisión simulada 0,1 % por lado y deslizamiento 0,05 %.
- Respeta un importe mínimo por orden (5 por defecto, como Binance).

### Sobre capitales muy pequeños (p. ej. 5 €)

Con 5 € el bot **no puede abrir operaciones reales**: el 95 % del capital (4,75 €) queda por debajo del
mínimo por orden del exchange (~5 €). Además, las comisiones (~0,2 % por operación completa) se comen
gran parte de los movimientos intradía: una ganancia típica serían céntimos. Usa `--min-notional 0` para
ver en simulado cómo habría ido en porcentaje.

## Estructura

| Archivo | Contenido |
|---|---|
| `config.py` | Parámetros de estrategia y riesgo |
| `data.py` | Descarga de velas (Binance, Yahoo) y datos sintéticos |
| `indicators.py` | EMA, RSI, ATR y VWAP en Python puro |
| `strategy.py` | Señales de entrada y salida |
| `engine.py` | Motor común: stops, límites de riesgo y tamaño de posición |
| `broker.py` | Broker simulado |
| `backtest.py` | Backtest e informe de resultados |
| `live.py` | Bucle de paper trading en tiempo real |

## Tests

```bash
python -m unittest discover -s trading_bot/tests -t .
```
