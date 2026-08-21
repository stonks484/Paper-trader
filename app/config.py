import os
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()

def f(name, default):
    try: return float(os.getenv(name, default))
    except Exception: return float(default)

def i(name, default):
    try: return int(os.getenv(name, default))
    except Exception: return int(default)

@dataclass(frozen=True)
class Settings:
    sec_user_agent: str = os.getenv('SEC_USER_AGENT','SmallCapPaperTrader/1.0 contact@example.com')
    starting_equity: float = f('STARTING_EQUITY',1000)
    risk_per_trade: float = f('RISK_PER_TRADE',0.005)
    max_position_pct: float = f('MAX_POSITION_PCT',0.10)
    max_portfolio_heat: float = f('MAX_PORTFOLIO_HEAT',0.02)
    max_open_positions: int = i('MAX_OPEN_POSITIONS',5)
    daily_loss_limit: float = f('DAILY_LOSS_LIMIT',0.02)
    max_slippage_pct: float = f('MAX_SLIPPAGE_PCT',0.01)
    min_price: float = f('MIN_PRICE',1)
    max_price: float = f('MAX_PRICE',20)
    small_cap_max: float = f('SMALL_CAP_MAX',2_000_000_000)
    min_avg_volume: float = f('MIN_AVG_VOLUME',100_000)
    min_rvol: float = f('MIN_RVOL',1.5)
    min_score: float = f('MIN_SCORE',70)
    max_spread_pct: float = f('MAX_SPREAD_PCT',1.5)
    universe_batch: int = i('UNIVERSE_BATCH',80)
    refresh_seconds: int = max(300,i('REFRESH_SECONDS',300))

settings=Settings()
