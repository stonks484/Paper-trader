import pandas as pd
from .indicators import add_features
from .strategy import score,levels

def run(df,catalyst='',starting=1000,risk=.005,fee_bps=10,slippage=.005):
    cash=starting; qty=0; entry=stop=target=0; trades=[]; curve=[]
    x=add_features(df)
    for i in range(55,len(x)):
        row=x.iloc[:i+1]; price=float(row.close.iloc[-1]);
        if qty:
            if price<=stop or price>=target:
                fill=price*(1-slippage); cash+=qty*fill; trades.append({'side':'SELL','price':fill,'pnl':(fill-entry)*qty}); qty=0
        if not qty:
            s=score(row,catalyst)
            if s and s['score']>=75:
                lv=levels(s); stop=lv['stop']; risk_share=price-stop; qty=min(cash*.10/price,(cash*risk)/risk_share)
                if qty>0: fill=price*(1+slippage); cash-=qty*fill; entry=fill; target=lv['target1']; trades.append({'side':'BUY','price':fill,'qty':qty,'score':s['score']})
        equity=cash+(qty*price if qty else 0); curve.append(equity)
    if qty:
        fill=float(x.close.iloc[-1])*(1-slippage); cash+=qty*fill; trades.append({'side':'SELL_END','price':fill,'pnl':(fill-entry)*qty})
    eq=pd.Series(curve or [starting]); peak=eq.cummax(); dd=(eq-peak)/peak; sells=[t for t in trades if t['side'].startswith('SELL')]
    wins=[t['pnl'] for t in sells if t.get('pnl',0)>0]; losses=[t['pnl'] for t in sells if t.get('pnl',0)<0]
    return {'ending_equity':round(float(cash),2),'return_pct':round((cash/starting-1)*100,2),'trades':len(sells),'win_rate':round(len(wins)/len(sells)*100,2) if sells else 0,'max_drawdown_pct':round(float(dd.min()*100),2),'profit_factor':round(sum(wins)/abs(sum(losses)),2) if losses else None,'trade_log':trades}
