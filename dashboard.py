import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


app = FastAPI(title="Firi Simple ETH Bot")


state = {
    "status": "STARTING",
    "dry_run": True,
    "price": 0.0,
    "bid": 0.0,
    "ask": 0.0,
    "spread_percent": 0.0,
    "binance_price": 0.0,
    "ema9": None,
    "ema21": None,
    "rsi14": None,
    "trend": "UNKNOWN",
    "signal": "HOLD",
    "reason": "Starter...",
    "position": False,
    "entry_price": 0.0,
    "take_profit": 0.0,
    "stop_loss": 0.0,
    "nok": 0.0,
    "eth": 0.0,
    "daily_trades": 0,
    "max_daily_trades": 10,
    "market_data_ok": False,
    "firi_ok": False,
    "strategy_ok": False,
    "last_error": "Ingen feil",
    "last_update": "-",
    "logs": [],
}


def add_log(message: str):
    state["logs"].append(message)
    state["logs"] = state["logs"][-150:]


def fmt(value, decimals=2):
    if value is None:
        return "N/A"
    return f"{value:,.{decimals}f}"


def health(ok: bool):
    return '<span class="ok">● OK</span>' if ok else '<span class="bad">● FEIL</span>'


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    signal = state["signal"]
    signal_class = (
        "buy" if signal == "BUY"
        else "sell" if signal == "SELL"
        else "hold"
    )

    logs = "<br>".join(
        str(item).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        for item in reversed(state["logs"][-40:])
    )

    return f"""
<!doctype html>
<html lang="no">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="10">
<title>Firi ETH Bot</title>
<style>
body {{
    background:#0f1115;
    color:#e8eaf0;
    font-family:Arial,sans-serif;
    margin:0;
    padding:30px;
}}
.container {{ max-width:1100px; margin:auto; }}
h1 {{ margin-bottom:25px; }}
.section {{ margin-bottom:25px; }}
.title {{ color:#9da7b8; font-size:14px; margin-bottom:8px; }}
.card {{
    background:#181c23;
    border:1px solid #2b313c;
    border-radius:10px;
    padding:18px;
}}
.grid {{
    display:grid;
    grid-template-columns:repeat(2,minmax(0,1fr));
    gap:10px;
}}
.row {{
    display:flex;
    justify-content:space-between;
    border-bottom:1px solid #2a3039;
    padding:10px 0;
}}
.value {{ font-weight:bold; }}
.buy {{ color:#40d98a; font-size:28px; font-weight:bold; }}
.sell {{ color:#ff6574; font-size:28px; font-weight:bold; }}
.hold {{ color:#e5c85c; font-size:28px; font-weight:bold; }}
.ok {{ color:#35dc83; font-weight:bold; }}
.bad {{ color:#ff5969; font-weight:bold; }}
.logs {{
    background:#0a0c10;
    border-radius:8px;
    padding:15px;
    font-family:monospace;
    font-size:12px;
    line-height:1.6;
    max-height:400px;
    overflow:auto;
}}
.error {{
    background:#31171c;
    border:1px solid #693039;
    padding:12px;
    border-radius:8px;
}}
</style>
</head>
<body>
<div class="container">

<h1>Firi ETH Daytrading Bot</h1>

<div class="section card">
<div class="title">SIGNAL</div>
<div class="{signal_class}">{signal}</div>
<div>{state["reason"]}</div>
</div>

<div class="section">
<div class="grid">

<div class="card">
<div class="title">MARKED</div>
<div class="row"><span>Firi ETH/NOK</span><span class="value">{fmt(state["price"])} kr</span></div>
<div class="row"><span>Binance ETHUSDT</span><span class="value">{fmt(state["binance_price"])} USDT</span></div>
<div class="row"><span>Bid</span><span class="value">{fmt(state["bid"])} kr</span></div>
<div class="row"><span>Ask</span><span class="value">{fmt(state["ask"])} kr</span></div>
<div class="row"><span>Spread</span><span class="value">{fmt(state["spread_percent"])} %</span></div>
</div>

<div class="card">
<div class="title">INDIKATORER</div>
<div class="row"><span>EMA 9</span><span class="value">{fmt(state["ema9"])} USDT</span></div>
<div class="row"><span>EMA 21</span><span class="value">{fmt(state["ema21"])} USDT</span></div>
<div class="row"><span>RSI 14</span><span class="value">{fmt(state["rsi14"],1)}</span></div>
<div class="row"><span>Trend</span><span class="value">{state["trend"]}</span></div>
</div>

</div>
</div>

<div class="section card">
<div class="title">POSISJON</div>
<div class="row"><span>Status</span><span class="value">ETH</span></div>
<div class="row"><span>Bot-posisjon</span><span class="value">{'JA' if state["position"] else 'NEI'}</span></div>
<div class="row"><span>Inngangspris</span><span class="value">{fmt(state["entry_price"])} kr</span></div>
<div class="row"><span>Take profit</span><span class="value">{fmt(state["take_profit"])} kr</span></div>
<div class="row"><span>Stop loss</span><span class="value">{fmt(state["stop_loss"])} kr</span></div>
</div>

<div class="section">
<div class="grid">
<div class="card">
<div class="title">SYSTEMSTATUS</div>
<div class="row"><span>Binance market data</span><span>{health(state["market_data_ok"])}</span></div>
<div class="row"><span>Firi</span><span>{health(state["firi_ok"])}</span></div>
<div class="row"><span>Strategy</span><span>{health(state["strategy_ok"])}</span></div>
<div class="row"><span>DRY RUN</span><span class="value">{state["dry_run"]}</span></div>
<div class="row"><span>Handler i dag</span><span class="value">{state["daily_trades"]} / {state["max_daily_trades"]}</span></div>
</div>

<div class="card">
<div class="title">SALDO</div>
<div class="row"><span>NOK</span><span class="value">{fmt(state["nok"])} kr</span></div>
<div class="row"><span>ETH</span><span class="value">{fmt(state["eth"],8)}</span></div>
<div class="row"><span>Sist oppdatert</span><span class="value">{state["last_update"]}</span></div>
</div>
</div>
</div>

<div class="section error">
<div class="title">SISTE FEIL</div>
{state["last_error"]}
</div>

<div class="section card">
<div class="title">LOGG</div>
<div class="logs">{logs or "Ingen logger ennå."}</div>
</div>

</div>
</body>
</html>
"""


def start_dashboard():
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        log_level="warning",
    )
