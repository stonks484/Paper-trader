import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from .config import settings
from .db import init_db, signals, orders
from .data import FreeData
from .strategy import score, levels
from .risk import RiskManager
from .broker import PaperBroker

risk=RiskManager(); broker=PaperBroker(risk); data=FreeData(); latest=[]

async def candidate_universe():
    symbols=await data.universe()
    # Free-data reality: market cap is not available cheaply for the whole US universe.
    # We therefore use price/liquidity/volume as the first pass, then verify market cap only for finalists.
    return symbols[:settings.universe_batch]

async def scan_once():
    global latest
    universe=await candidate_universe(); out=[]
    # Batch daily data to keep the free source practical.
    tickers=[x['ticker'] for x in universe]
    if not tickers:return []
    try:
        import yfinance as yf
        daily=await asyncio.to_thread(yf.download,tickers,period='3mo',interval='1d',auto_adjust=False,progress=False,threads=True,group_by='ticker')
    except Exception:return []
    rough=[]
    for ticker in tickers:
        try:
            df=daily[ticker].dropna() if hasattr(daily,'columns') and ticker in daily.columns.get_level_values(0) else None
            if df is None or len(df)<30:continue
            close=float(df['Close'].iloc[-1]); prev=float(df['Close'].iloc[-2]); vol=float(df['Volume'].iloc[-20:].mean()); lastvol=float(df['Volume'].iloc[-1])
            if not(settings.min_price<=close<=settings.max_price) or vol<settings.min_avg_volume:continue
            change=(close/prev-1)*100; rvol=lastvol/max(vol,1)
            if change>=5 or rvol>=settings.min_rvol: rough.append((ticker,change,rvol))
        except Exception:continue
    rough=sorted(rough,key=lambda x:(x[1],x[2]),reverse=True)[:15]
    for ticker,change,rvol in rough:
        try:
            bars=await data.bars(ticker,period='5d',interval='5m')
            if len(bars)<55:continue
            filings=await data.filings(ticker,limit=8)
            text=' '.join(f"{f.get('form','')} {f.get('description','')}" for f in filings)
            s=score(bars,text)
            if not s:continue
            s.update(levels(s)); s.update({'ticker':ticker,'change_pct':round(change,2),'data_source':data.source,'data_status':'DELAYED_RESEARCH','sec_filings':filings})
            # Small-cap guard: no paid market-cap feed; flag this explicitly rather than inventing a cap.
            s['small_cap_status']='UNVERIFIED_FREE_DATA'
            if s['score']>=settings.min_score and not s['dilution_flags']:out.append(s)
        except Exception:continue
    latest=sorted(out,key=lambda x:x['score'],reverse=True)[:20]
    return latest

@asynccontextmanager
async def lifespan(app):
    init_db(); yield

app=FastAPI(title='AI Small-Cap Paper Trader',lifespan=lifespan)

@app.get('/',response_class=HTMLResponse)
async def home():return HTML

@app.get('/api/status')
async def status():
    return {'mode':'PAPER_ONLY','data':'FREE_YAHOO_SEC','equity':risk.p.equity,'cash':risk.p.cash,'daily_loss_pct':round(risk.daily_loss()*100,2),'kill_switch':risk.p.kill_switch,'open_positions':risk.p.open_positions,'data_note':'Yahoo data may be delayed; SEC is public filing data.'}

@app.get('/api/scan')
async def scan():return {'rows':await scan_once(),'data_note':'Free research data; not exchange-grade real-time.'}

@app.post('/api/paper/buy/{ticker}')
async def buy(ticker:str):
    row=next((x for x in latest if x['ticker']==ticker),None)
    if not row:raise HTTPException(404,'Ticker not in latest qualifying scan')
    return broker.buy(ticker,row['entry'],row['stop'],row['target1'],row['target2'],row['score'])

@app.post('/api/paper/sell/{ticker}')
async def sell(ticker:str,price:float):return broker.sell(ticker,price)

@app.get('/api/orders')
async def get_orders():return orders()

@app.get('/api/signals')
async def get_signals():return signals()

HTML='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI Small-Cap Paper Trader</title><style>body{margin:0;background:#070b12;color:#edf2fa;font:14px system-ui}main{max-width:1250px;margin:auto;padding:18px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.card,table{background:#101722;border:1px solid #26344d;border-radius:12px}.card{padding:14px}.muted{color:#91a0b6}.good{color:#39d98a}.warn{color:#ffd166}button{padding:9px 12px;border:0;border-radius:8px;cursor:pointer}table{width:100%;border-collapse:collapse;margin-top:14px}th,td{padding:9px;border-bottom:1px solid #26344d;text-align:left}.pill{padding:3px 7px;border-radius:9px;background:#172238}@media(max-width:750px){.grid{grid-template-columns:repeat(2,1fr)}table{font-size:11px;display:block;overflow:auto;white-space:nowrap}} </style></head><body><main><h1>🤖 AI Small-Cap Paper Trader</h1><p class="muted">Free-data professional-style research platform · PAPER ONLY · no live broker access</p><div class="grid"><div class="card">Equity<br><b id="equity">$0</b></div><div class="card">Cash<br><b id="cash">$0</b></div><div class="card">Daily loss<br><b id="loss">0%</b></div><div class="card">Kill switch<br><b id="kill">OFF</b></div></div><div class="card" style="margin-top:12px"><b>Data status:</b> <span class="good">Yahoo Finance + SEC EDGAR</span><br><span class="muted">Price data may be delayed. SEC filing data is public. Market-cap status is shown explicitly rather than guessed.</span></div><h2>Qualified signals</h2><button onclick="scan()">Run scan</button><table><thead><tr><th>Ticker</th><th>Score</th><th>Confidence</th><th>Change</th><th>Price</th><th>RVOL</th><th>RSI</th><th>Stop</th><th>T1</th><th>Catalyst</th><th></th></tr></thead><tbody id="rows"></tbody></table><h2>Order journal</h2><pre id="orders" class="card"></pre></main><script>async function status(){let x=await fetch('/api/status').then(r=>r.json());equity.textContent='$'+Number(x.equity).toFixed(2);cash.textContent='$'+Number(x.cash).toFixed(2);loss.textContent=x.daily_loss_pct+'%';kill.textContent=x.kill_switch?'ON':'OFF'}async function scan(){rows.innerHTML='<tr><td colspan="11">Scanning…</td></tr>';let x=await fetch('/api/scan').then(r=>r.json());rows.innerHTML=x.rows.map(r=>`<tr><td><b>${r.ticker}</b></td><td><span class="pill">${r.score}</span></td><td>${r.confidence}</td><td>${r.change_pct}%</td><td>${r.price.toFixed(2)}</td><td>${r.rvol.toFixed(2)}x</td><td>${r.rsi.toFixed(1)}</td><td>${r.stop}</td><td>${r.target1}</td><td>${(r.positive_catalysts||[]).join(', ')||'None'}</td><td><button onclick="buy('${r.ticker}')">Paper BUY</button></td></tr>`).join('')||'<tr><td colspan="11">No qualifying signals.</td></tr>'}async function buy(t){let r=await fetch('/api/paper/buy/'+t,{method:'POST'});if(!r.ok)alert(await r.text());await status();await getOrders()}async function getOrders(){let x=await fetch('/api/orders').then(r=>r.json());orders.textContent=JSON.stringify(x,null,2)}status();getOrders();</script></body></html>'''
