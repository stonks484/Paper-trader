import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

DB=Path(__file__).resolve().parent.parent/'paper_trader.db'

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    c=conn(); c.executescript('''
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,ticker TEXT,side TEXT,qty REAL,limit_price REAL,fill_price REAL,status TEXT,reason TEXT,created_at TEXT,filled_at TEXT);
    CREATE TABLE IF NOT EXISTS positions(ticker TEXT PRIMARY KEY,side TEXT,qty REAL,entry REAL,stop REAL,target1 REAL,target2 REAL,opened_at TEXT);
    CREATE TABLE IF NOT EXISTS equity(ts TEXT,equity REAL,cash REAL,drawdown REAL);
    CREATE TABLE IF NOT EXISTS signals(id INTEGER PRIMARY KEY AUTOINCREMENT,ticker TEXT,score REAL,confidence REAL,features TEXT,catalyst TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,payload TEXT,created_at TEXT);
    '''); c.commit(); c.close()

def event(kind,payload):
    c=conn(); c.execute('INSERT INTO events(kind,payload,created_at) VALUES(?,?,?)',(kind,json.dumps(payload),datetime.now(timezone.utc).isoformat())); c.commit(); c.close()

def record_signal(s):
    c=conn(); c.execute('INSERT INTO signals(ticker,score,confidence,features,catalyst,created_at) VALUES(?,?,?,?,?,?)',(s['ticker'],s['score'],s['confidence'],json.dumps(s.get('features',{})),s.get('catalyst',''),datetime.now(timezone.utc).isoformat())); c.commit(); c.close()

def orders(limit=100):
    c=conn(); rows=[dict(x) for x in c.execute('SELECT * FROM orders ORDER BY id DESC LIMIT ?', (limit,))]; c.close(); return rows

def signals(limit=100):
    c=conn(); rows=[dict(x) for x in c.execute('SELECT * FROM signals ORDER BY id DESC LIMIT ?', (limit,))]; c.close(); return rows
