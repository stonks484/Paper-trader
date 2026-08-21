from statistics import mean

def trade_metrics(trades):
    closed=[t for t in trades if t.get('action')=='SELL' and t.get('pnl') is not None]
    pnls=[float(t['pnl']) for t in closed]
    wins=[p for p in pnls if p>0]; losses=[p for p in pnls if p<0]
    gross_profit=sum(wins); gross_loss=abs(sum(losses))
    pf=(gross_profit/gross_loss) if gross_loss else None
    equity=0; peak=0; max_dd=0
    curve=[]
    for p in pnls:
        equity+=p; peak=max(peak,equity); max_dd=min(max_dd,equity-peak); curve.append(equity)
    return {'trades':len(closed),'wins':len(wins),'losses':len(losses),'win_rate':round(100*len(wins)/len(closed),2) if closed else 0,'net_pnl':round(sum(pnls),2),'avg_win':round(mean(wins),2) if wins else 0,'avg_loss':round(mean(losses),2) if losses else 0,'profit_factor':round(pf,2) if pf is not None else None,'expectancy':round(mean(pnls),2) if pnls else 0,'max_drawdown':round(max_dd,2),'equity_curve':curve}

def setup_metrics(trades):
    groups={}
    for t in trades:
        tag=t.get('setup','UNCLASSIFIED'); groups.setdefault(tag,[]).append(t)
    return {k:trade_metrics(v) for k,v in groups.items()}
