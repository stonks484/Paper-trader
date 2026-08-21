from datetime import datetime,timezone
from .db import conn,event
from .config import settings

class PaperBroker:
    def __init__(self,risk): self.risk=risk
    def buy(self,ticker,price,stop,target1,target2,score):
        ok,reason=self.risk.check(price,stop,score)
        if not ok: event('ORDER_REJECTED',{'ticker':ticker,'reason':reason}); return {'ok':False,'reason':reason}
        qty=self.risk.size(price,stop)
        if qty<=0: return {'ok':False,'reason':'SIZE_ZERO'}
        fill=price*(1+settings.max_slippage_pct*.25)
        cost=qty*fill
        if cost>self.risk.p.cash: return {'ok':False,'reason':'INSUFFICIENT_CASH'}
        now=datetime.now(timezone.utc).isoformat(); c=conn(); c.execute('INSERT INTO orders(ticker,side,qty,limit_price,fill_price,status,reason,created_at,filled_at) VALUES(?,?,?,?,?,?,?,?,?)',(ticker,'BUY',qty,price,fill,'FILLED','signal',now,now)); c.execute('INSERT OR REPLACE INTO positions VALUES(?,?,?,?,?,?,?,?)',(ticker,'LONG',qty,fill,stop,target1,target2,now)); c.commit(); c.close(); self.risk.p.cash-=cost; self.risk.p.open_positions+=1; event('ORDER_FILLED',{'ticker':ticker,'qty':qty,'fill':fill}); return {'ok':True,'ticker':ticker,'qty':qty,'fill':fill,'stop':stop,'target1':target1,'target2':target2}
    def sell(self,ticker,price,reason='manual'):
        c=conn(); row=c.execute('SELECT * FROM positions WHERE ticker=?',(ticker,)).fetchone()
        if not row: return {'ok':False,'reason':'NO_POSITION'}
        fill=price*(1-settings.max_slippage_pct*.25); proceeds=row['qty']*fill; pnl=(fill-row['entry'])*row['qty']; now=datetime.now(timezone.utc).isoformat(); c.execute('INSERT INTO orders(ticker,side,qty,limit_price,fill_price,status,reason,created_at,filled_at) VALUES(?,?,?,?,?,?,?,?,?)',(ticker,'SELL',row['qty'],price,fill,'FILLED',reason,now,now)); c.execute('DELETE FROM positions WHERE ticker=?',(ticker,)); c.commit(); c.close(); self.risk.p.cash+=proceeds; self.risk.p.equity=self.risk.p.cash; self.risk.p.open_positions=max(0,self.risk.p.open_positions-1); event('POSITION_CLOSED',{'ticker':ticker,'pnl':pnl,'reason':reason}); return {'ok':True,'ticker':ticker,'pnl':round(pnl,2),'fill':fill}
