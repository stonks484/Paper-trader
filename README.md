# AI Small-Cap Paper Trader

A free-first research and paper-trading platform for US small-cap equities. It is designed around professional-style controls: universe construction, catalyst scoring, technical regime detection, liquidity/slippage checks, position sizing, portfolio risk, daily loss limits, trade journaling, and backtesting.

## Important
This repository is **paper trading only**. It cannot place live Trading 212 orders. The Trading 212 API should only be connected after the strategy has been independently validated.

## Free-first data design
The default adapter supports Massive's free Stocks Basic plan. That plan currently provides US ticker/reference data, corporate actions, technical indicators and minute aggregates, but only 5 API calls/minute and not real-time trades/quotes. Therefore this project deliberately labels data as `FREE_DELAYED` when it is not live and never pretends delayed data is real-time. See https://massive.com/pricing.

For catalyst research the platform can also consume public SEC EDGAR submissions/XBRL and public RSS feeds without a paid news terminal. Paid real-time feeds can be added later but are not required to develop or paper-test the system.

## Features
- Small-cap universe filters (exchange, market cap, price, float, volume)
- Premarket / regular-session / after-hours session awareness
- Momentum, relative volume, VWAP, ATR, EMA, RSI and breakout features
- Catalyst classifier with dilution/offering/reverse-split risk penalties
- Composite signal score and confidence
- Spread/liquidity/slippage guardrails
- ATR/structure-based stops and multiple profit targets
- Risk-based position sizing
- Portfolio heat, max positions, sector/exposure controls
- Daily loss kill switch and circuit breakers
- SQLite trade journal and equity curve
- Paper order lifecycle: pending -> filled -> partial/closed
- Backtest engine with fees/slippage assumptions
- Walk-forward-friendly signal logging
- REST API and mobile-friendly dashboard
- Audit/event log for every decision
- Configurable strategy; no hard-coded account credentials

## Quick start

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

Open `http://127.0.0.1:8000`.

### Data key
Create a free Massive account and put the API key in `.env` as `MASSIVE_API_KEY`. The free tier is rate limited, so use a sensible refresh interval (default 60 seconds) and avoid claiming tick-level execution.

### Optional SEC data
SEC endpoints are public and require a descriptive User-Agent. Set `SEC_USER_AGENT` in `.env` to something like `YourName your-email@example.com`.

## Risk defaults
- Starting equity: $1,000
- Risk per trade: 0.5%
- Maximum position: 10%
- Maximum portfolio heat: 2%
- Maximum open positions: 5
- Daily loss limit: 2%
- Maximum slippage assumption: 1%
- Minimum price: $1
- Maximum price: $20
- Small-cap ceiling: $2B

These are research defaults, not financial advice.
