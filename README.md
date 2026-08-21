# AI Small-Cap Paper Trader

A **free-first, paper-only** research and trading simulation platform for US small-cap equities. It is designed with professional-style controls without requiring a paid market-data subscription.

## Data architecture — no Massive, no paid API

- **Nasdaq Trader public symbol directory** — US-listed symbol universe.
- **Yahoo Finance via `yfinance`** — historical OHLCV and available intraday bars for research.
- **SEC EDGAR** — public submissions and filing metadata for catalyst and dilution-risk detection.
- Technical indicators are calculated locally.

The application deliberately labels Yahoo data as delayed/research data. It does **not** claim to be an exchange-grade real-time feed.

## Strategy

- Small-cap-oriented price/liquidity universe filters
- Gap and momentum pre-filter
- Relative volume (RVOL)
- EMA 9/20/50 trend structure
- VWAP
- RSI
- ATR
- 20-bar breakout
- Catalyst scoring
- SEC filing classification
- Strong penalties for offerings, ATM programs, convertibles, warrants, dilution, reverse splits and going-concern risk
- Composite 0–100 signal score
- Confidence score
- ATR-based stop and 1.5R/3R targets

## Risk engine

- Starting equity: $1,000
- Risk per trade: 0.5%
- Maximum position: 10%
- Maximum portfolio heat: 2%
- Maximum open positions: 5
- Daily loss limit: 2%
- Maximum assumed slippage: 1%
- Minimum price: $1
- Maximum price: $20
- Minimum average volume: 100,000 shares

These are research defaults and can be changed through environment variables.

## Paper execution

The broker is simulation-only. It supports paper buys/sells, stops, targets, position sizing, portfolio state and a trade journal. **No Trading 212 credentials or live order functionality is present.**

## GitHub Pages

The Pages dashboard is a static front-end. GitHub Actions runs the research engine and updates repository state on a schedule. GitHub scheduled workflows have a minimum interval of five minutes, but scheduled jobs can be delayed under GitHub load, so this is not a low-latency trading system.

## Local setup

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set a descriptive SEC User-Agent, for example:

```text
SEC_USER_AGENT=YourName your-email@example.com
```

Then:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000`.

## Important limitations

Free public data cannot reproduce a professional exchange feed, Level 2/order book, NBBO or premium news terminal. The platform therefore prioritizes **research integrity**: every data limitation is surfaced rather than hidden, and no live-trading claims are made.

This is software for research and paper trading, not financial advice.
