from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

@dataclass
class Position:
    ticker: str
    side: str
    qty: float
    entry: float
    stop: Optional[float] = None
    target: Optional[float] = None
    opened_at: str = ""

    def market_value(self, price: float) -> float:
        return self.qty * price

class PaperTrader:
    """In-memory paper broker. No live orders are possible through this class."""
    def __init__(self, starting_cash: float = 1000.0, risk_per_trade: float = 0.01,
                 max_position_pct: float = 0.10, max_daily_loss_pct: float = 0.03):
        self.starting_cash = float(starting_cash)
        self.cash = float(starting_cash)
        self.risk_per_trade = float(risk_per_trade)
        self.max_position_pct = float(max_position_pct)
        self.max_daily_loss_pct = float(max_daily_loss_pct)
        self.positions: dict[str, Position] = {}
        self.trades: list[dict] = []
        self.day_start_equity = float(starting_cash)
        self.lock = Lock()
        self.enabled = True

    def equity(self, prices=None) -> float:
        prices = prices or {}
        return self.cash + sum(p.market_value(float(prices.get(p.ticker, p.entry))) for p in self.positions.values())

    def daily_loss_pct(self, prices=None) -> float:
        return max(0.0, (self.day_start_equity - self.equity(prices)) / self.day_start_equity)

    def can_trade(self, prices=None):
        if not self.enabled:
            return False, "Paper trading is disabled"
        if self.daily_loss_pct(prices) >= self.max_daily_loss_pct:
            self.enabled = False
            return False, "Daily loss limit reached; kill switch activated"
        return True, "OK"

    def open_long(self, ticker, price, stop, target=None, risk_score=0.0):
        with self.lock:
            ok, reason = self.can_trade({ticker: price})
            if not ok: raise ValueError(reason)
            if ticker in self.positions: raise ValueError(f"Already holding {ticker}")
            if price <= 0 or stop >= price: raise ValueError("For a long trade, stop must be below entry")
            equity = self.equity({ticker: price})
            qty = min(equity*self.max_position_pct/price, equity*self.risk_per_trade/(price-stop), self.cash/price)
            qty = round(max(0.0, qty), 4)
            if qty <= 0: raise ValueError("Insufficient paper cash for position")
            cost = qty * price
            self.cash -= cost
            opened = datetime.now(timezone.utc).isoformat()
            self.positions[ticker] = Position(ticker, "long", qty, price, stop, target, opened)
            trade = {"action":"BUY","ticker":ticker,"qty":qty,"price":price,"stop":stop,"target":target,"risk_score":risk_score,"time":opened,"paper":True}
            self.trades.append(trade)
            return trade

    def close(self, ticker, price, reason="manual"):
        with self.lock:
            p = self.positions.get(ticker)
            if not p: raise ValueError(f"No open position for {ticker}")
            proceeds = p.qty * price
            pnl = (price-p.entry)*p.qty if p.side == "long" else 0.0
            self.cash += proceeds
            del self.positions[ticker]
            trade = {"action":"SELL","ticker":ticker,"qty":p.qty,"price":price,"entry":p.entry,"pnl":round(pnl,2),"reason":reason,"time":datetime.now(timezone.utc).isoformat(),"paper":True}
            self.trades.append(trade)
            return trade

    def mark_to_market(self, prices):
        closed=[]
        for ticker,p in list(self.positions.items()):
            price=float(prices.get(ticker,p.entry))
            if p.stop is not None and price <= p.stop: closed.append(self.close(ticker,price,"stop_loss"))
            elif p.target is not None and price >= p.target: closed.append(self.close(ticker,price,"take_profit"))
        return closed

    def snapshot(self, prices=None):
        prices=prices or {}
        return {"mode":"PAPER","enabled":self.enabled,"starting_cash":self.starting_cash,"cash":round(self.cash,2),"equity":round(self.equity(prices),2),"daily_loss_pct":round(self.daily_loss_pct(prices)*100,2),"positions":[asdict(p) for p in self.positions.values()],"trades":self.trades[-100:],"limits":{"risk_per_trade_pct":self.risk_per_trade*100,"max_position_pct":self.max_position_pct*100,"max_daily_loss_pct":self.max_daily_loss_pct*100}}

    def reset(self,cash=None):
        with self.lock:
            self.starting_cash=float(cash if cash is not None else self.starting_cash)
            self.cash=self.starting_cash
            self.day_start_equity=self.starting_cash
            self.positions.clear(); self.trades.clear(); self.enabled=True
