"""Small-cap momentum strategy: trend + RVOL + VWAP + breakout + catalyst risk."""
from .indicators import add_features

BAD={
 'offering':-25,'registered direct':-25,'atm offering':-28,'convertible':-24,
 'warrant':-12,'dilution':-25,'dilutive':-25,'reverse split':-20,
 'going concern':-30,'bankruptcy':-40,'nasdaq deficiency':-15,'share issuance':-18
}
GOOD={
 'fda':18,'approval':16,'contract':14,'award':14,'acquisition':15,'partnership':10,
 'agreement':8,'government':15,'order':10,'guidance':10,'earnings':10,'revenue':8,
 'clinical':10,'trial':8,'strategic investment':12
}

def catalyst_score(text):
    t=(text or '').lower(); negatives=[k for k in BAD if k in t]; positives=[k for k in GOOD if k in t]
    score=max(0,min(100,50+sum(GOOD[k] for k in positives)+sum(BAD[k] for k in negatives)))
    return score,negatives,positives

def score(df,catalyst=''):
    if len(df)<55:return None
    x=add_features(df).iloc[-1]
    cs,bad,good=catalyst_score(catalyst)
    trend=25 if x.ema9>x.ema20>x.ema50 else 13 if x.ema9>x.ema20 else 0
    rvol=min(25,max(0,(float(x.rvol)-1)*10))
    breakout=20 if x.close>=x.high20*.995 else 9 if x.close>x.ema20 else 0
    vwap=15 if x.close>x.vwap else 0
    rsi=10 if 52<=x.rsi<=78 else 5 if 45<=x.rsi<85 else 0
    raw=trend+rvol+breakout+vwap+rsi+cs*.15
    confidence=max(0,min(100,raw-abs(float(x.rsi)-65)*.3-len(bad)*5))
    total=max(0,min(100,raw+sum(BAD[k] for k in bad)*.35))
    return {'score':round(total,1),'confidence':round(confidence,1),'price':float(x.close),'atr':float(x.atr) if x.atr==x.atr else 0,'rvol':float(x.rvol) if x.rvol==x.rvol else 0,'rsi':float(x.rsi) if x.rsi==x.rsi else 0,'vwap':float(x.vwap) if x.vwap==x.vwap else 0,'features':{'trend':trend,'relative_volume':round(rvol,2),'breakout':breakout,'vwap':vwap,'rsi':rsi,'catalyst':cs},'catalyst_score':cs,'dilution_flags':bad,'positive_catalysts':good}

def levels(signal):
    p=signal['price']; a=signal['atr'] or p*.05
    stop=max(.01,p-1.5*a); risk=p-stop
    return {'entry':round(p,4),'stop':round(stop,4),'target1':round(p+1.5*risk,4),'target2':round(p+3*risk,4),'risk_per_share':round(risk,4)}
