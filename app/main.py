import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from .config import settings
from .db import init_db,signals,orders
from .data import Massive
from .strategy import score,levels
from .risk import RiskManager
from .broker import PaperBroker

risk=RiskManager(); broker=PaperBroker(risk); data=Massive(); latest=[]

async def scan_once():
    global latest
    if not settings.massive_key: return []
    raw=await data.tickers(); rows=(raw or {}).get('results',[]); candidates=[]
    for t in rows:
        cap=t.get('market_cap') or 0; price=t.get('last_trade',{}).get('price') if isinstance(t.get('last_trade'),dict) else None
        if cap and cap>settings.small_cap_max: continue
        if price and not(settings.min_price<=price<=settings.max_price): continue
        candidates.append(t.get('ticker'))
    out=[]
    for ticker in candidates[:40]:
        try:
            df=await data.minute(ticker,180)
            s=score(df,'')
            if s and s['score']>=65:
                lv=levels(s); out.append({'ticker':ticker,**s,**lv})
        except Exception: continue
        await asyncio.sleep(.05)
    latest=sorted(out,key=lambda x:x['score'],reverse=True)[:20]; return latest

@asynccontextmanager
async def lifespan(app):
    init_db(); yield
app=FastAPI(title='AI Small-Cap Paper Trader',lifespan=lifespan)

@app.get('/',response_class=HTMLResponse)
async def home(): return HTML

@app.get('/api/status')
async def status(): return {'mode':'PAPER_ONLY','data':'MASSIVE_FREE' if settings.massive_key else 'NO_KEY','equity':risk.p.equity,'cash':risk.p.cash,'daily_loss_pct':round(risk.daily_loss()*100,2),'kill_switch':risk.p.kill_switch,'open_positions':risk.p.open_positions}

@app.get('/api/scan')
async def scan(): return {'rows':await scan_once(),'data_note':'Free-tier data is not tick-real-time.'}

@app.post('/api/paper/buy/{ticker}')
async def buy(ticker:str):
    row=next((x for x in latest if x['ticker']==ticker),None)
    if not row: raise HTTPException(404,'Ticker not in latest qualifying scan')
    return broker.buy(ticker,row['entry'],row['stop'],row['target1'],row['target2'],row['score'])

@app.post('/api/paper/sell/{ticker}')
async def sell(ticker:str,price:float): return broker.sell(ticker,price)

@app.get('/api/orders')
async def get_orders(): return orders()

@app.get('/api/signals')
async def get_signals(): return signals()

HTML='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Small-Cap Paper Trader</title><style>body{margin:0;background:#070b12;color:#edf2fa;font:14px system-ui}main{max-width:1200px;margin:auto;padding:18px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.card,table{background:#101722;border:1px solid #26344d;border-radius:12px}.card{padding:14px}.muted{color:#91a0b6}.good{color:#39d98a}.bad{color:#ff6575}button{padding:8px 12px;border:0;border-radius:8px;cursor:pointer}table{width:100%;border-collapse:collapse;margin-top:14px}th,td{padding:9px;border-bottom:1px solid #26344d;text-align:left}@media(max-width:700px){.grid{grid-template-columns:repeat(2,1fr)}table{font-size:12px}} </style></head><body><main><h1>🤖 Small-Cap Paper Trader</h1><p class="muted">Professional-style research controls. PAPER ONLY — no broker orders.</p><div class="grid"><div class="card">Equity<br><b id="equity">$0</b></div><div class="card">Cash<br><b id="cash">$0</b></div><div class="card">Daily loss<br><b id="loss">0%</b></div><div class="card">Kill switch<br><b id="kill">OFF</b></div></div><h2>Scanner</h2><button onclick="scan()">Refresh scan</button><table><thead><tr><th>Ticker</th><th>Score</th><th>Confidence</th><th>Price</th><th>RVOL</th><th>Stop</th><th>Target 1</th><th></th></tr></thead><tbody id="rows"></tbody></table><h2>Orders</h2><pre id="orders" class="card"></pre></main><script>async function status(){let x=await fetch('/api/status').then(r=>r.json());equity.textContent='$'+x.equity.toFixed(2);cash.textContent='$'+x.cash.toFixed(2);loss.textContent=x.daily_loss_pct+'%';kill.textContent=x.kill_switch?'ON':'OFF'}async function scan(){let x=await fetch('/api/scan').then(r=>r.json());rows.innerHTML=x.rows.map(r=>`<tr><td><b>${r.ticker}</b></td><td>${r.score}</td><td>${r.confidence}</td><td>${r.price.toFixed(2)}</td><td>${r.rvol.toFixed(2)}x</td><td>${r.stop}</td><td>${r.target1}</td><td><button onclick="buy('${r.ticker}')">Paper BUY</button></td></tr>`).join('')}async function buy(t){await fetch('/api/paper/buy/'+t,{method:'POST'});await status();await getOrders()}async function getOrders(){let x=await fetch('/api/orders').then(r=>r.json());orders.textContent=JSON.stringify(x,null,2)}status();getOrders();</script></body></html>'''
