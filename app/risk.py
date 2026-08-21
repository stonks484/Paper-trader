from dataclasses import dataclass
from .config import settings

@dataclass
class Portfolio:
    equity: float
    cash: float
    open_positions: int=0
    portfolio_heat: float=0.0
    day_start_equity: float=0.0
    kill_switch: bool=False

    def __post_init__(self):
        if not self.day_start_equity: self.day_start_equity=self.equity

class RiskManager:
    def __init__(self): self.p=Portfolio(settings.starting_equity,settings.starting_equity)
    def daily_loss(self): return max(0,(self.p.day_start_equity-self.p.equity)/self.p.day_start_equity)
    def check(self,price,stop,score):
        if self.p.kill_switch: return False,'KILL_SWITCH'
        if self.daily_loss()>=settings.daily_loss_limit: self.p.kill_switch=True; return False,'DAILY_LOSS_LIMIT'
        if self.p.open_positions>=settings.max_open_positions: return False,'MAX_POSITIONS'
        if price<=0 or stop>=price: return False,'BAD_STOP'
        if score<70: return False,'SIGNAL_BELOW_THRESHOLD'
        return True,'OK'
    def size(self,price,stop):
        risk_dollars=self.p.equity*settings.risk_per_trade; risk_per_share=price-stop
        by_risk=risk_dollars/risk_per_share
        by_value=(self.p.equity*settings.max_position_pct)/price
        return max(0,round(min(by_risk,by_value,self.p.cash/price),4))
