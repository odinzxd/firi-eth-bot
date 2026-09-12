from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

state = {
    "status": "STARTING",
    "trading": False,

    "price": 0.0,
    "bid": 0.0,
    "ask": 0.0,
    "spread": 0.0,

    "nok": 0.0,
    "eth": 0.0,

    "eth_value": 0.0,
    "portfolio_value": 0.0,

    "profit_nok": 0.0,
    "profit_percent": 0.0,

    "signal": "HOLD",
    "reason": "Starter...",

    "last_update": "-",

    "logs": [],
}


def add_log(message):
    state["logs"].append(message)

    if len(state["logs"]) > 100:
        state["logs"] = state["logs"][-100:]


@app.get("/", response_class=HTMLResponse)
async def dashboard():

    profit = state["profit_nok"]

    if profit > 0:
        profit_class = "profit"
        profit_sign = "+"
    elif profit < 0:
        profit_class = "loss"
        profit_sign = ""
    else:
        profit_class = "neutral"
        profit_sign = ""

    # Trading-status
    if state["trading"]:
        trading_text = "ON (LIVE)"
        trading_class = "trading-on"
    else:
        trading_text = "OFF (DRY RUN)"
        trading_class = "trading-off"

    return f"""
<!DOCTYPE html>
<html lang="no">

<head>

<meta charset="UTF-8">

<meta name="viewport" content="width=device-width, initial-scale=1.0">

<meta http-equiv="refresh" content="10">

<title>Firi ETH Trading Bot</title>

<style>

body {{
    margin: 0;
    padding: 0;
    background: #101114;
    color: #f5f5f5;
    font-family: Arial, sans-serif;
}}

.container {{
    padding: 20px;
}}

h1 {{
    margin-top: 0;
}}

.status {{
    float: right;
    color: #3ddc84;
    font-size: 16px;
}}

.grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-top: 20px;
}}

.card {{
    background: #1b1e24;
    border-radius: 10px;
    padding: 20px;
}}

.card-title {{
    color: #8f9aaa;
    font-size: 13px;
    text-transform: uppercase;
    margin-bottom: 10px;
}}

.value {{
    font-size: 24px;
    font-weight: bold;
}}

.small {{
    font-size: 14px;
    color: #9da5b1;
    margin-top: 7px;
}}

.profit {{
    color: #3ddc84;
}}

.loss {{
    color: #ff5c5c;
}}

.neutral {{
    color: #f0c75e;
}}

.trading-on {{
    color: #3ddc84;
}}

.trading-off {{
    color: #ff5c5c;
}}

.signal {{
    font-size: 24px;
    font-weight: bold;
    color: #f0c75e;
}}

.section {{
    margin-top: 20px;
}}

.logs {{
    background: #050609;
    border-radius: 8px;
    padding: 15px;
    height: 400px;
    overflow-y: auto;
    font-family: Consolas, monospace;
    font-size: 12px;
    line-height: 1.5;
}}

.log {{
    margin-bottom: 3px;
}}

.info {{
    background: #1b1e24;
    border-radius: 10px;
    padding: 20px;
}}

@media (max-width: 1000px) {{
    .grid {{
        grid-template-columns: repeat(2, 1fr);
    }}
}}

@media (max-width: 600px) {{
    .grid {{
        grid-template-columns: 1fr;
    }}
}}

</style>

</head>

<body>

<div class="container">

<h1>
    Firi ETH Trading Bot

    <span class="status">
        ● {state["status"]}
    </span>
</h1>


<!-- TRADING STATUS -->

<div class="card" style="margin-top: 20px;">

    <div class="card-title">
        TRADING STATUS
    </div>

    <div class="value {trading_class}">
        ● {trading_text}
    </div>

    <div class="small">
        DRY_RUN = {str(not state["trading"]).lower()}
    </div>

</div>


<!-- MARKEDATA -->

<div class="grid">

    <div class="card">

        <div class="card-title">
            ETH/NOK
        </div>

        <div class="value">
            {state["price"]:,.2f} kr
        </div>

        <div class="small">
            Bid: {state["bid"]:,.2f} kr
        </div>

        <div class="small">
            Ask: {state["ask"]:,.2f} kr
        </div>

    </div>


    <div class="card">

        <div class="card-title">
            ETH BEHOLDNING
        </div>

        <div class="value">
            {state["eth"]:.8f} ETH
        </div>

        <div class="small">
            Verdi: {state["eth_value"]:,.2f} kr
        </div>

    </div>


    <div class="card">

        <div class="card-title">
            NOK SALDO
        </div>

        <div class="value">
            {state["nok"]:,.2f} kr
        </div>

        <div class="small">
            Tilgjengelig for handel
        </div>

    </div>


    <div class="card">

        <div class="card-title">
            TOTAL PORTEFØLJE
        </div>

        <div class="value">
            {state["portfolio_value"]:,.2f} kr
        </div>

        <div class="small">
            ETH + NOK
        </div>

    </div>

</div>


<!-- GEVINST / TAP -->

<div class="grid">

    <div class="card">

        <div class="card-title">
            GEVINST / TAP
        </div>

        <div class="value {profit_class}">
            {profit_sign}{profit:,.2f} kr
        </div>

        <div class="small">
            Siden start: 1 800 kr
        </div>

    </div>


    <div class="card">

        <div class="card-title">
            AVKASTNING
        </div>

        <div class="value {profit_class}">
            {profit_sign}{state["profit_percent"]:.2f} %
        </div>

        <div class="small">
            Samlet portefølje
        </div>

    </div>


    <div class="card">

        <div class="card-title">
            SPREAD
        </div>

        <div class="value">
            {state["spread"]:,.2f} kr
        </div>

        <div class="small">
            Bid → Ask
        </div>

    </div>


    <div class="card">

        <div class="card-title">
            SIGNAL
        </div>

        <div class="signal">
            {state["signal"]}
        </div>

        <div class="small">
            {state["reason"]}
        </div>

    </div>

</div>


<!-- SISTE OPPDATERING -->

<div class="section">

    <div class="info">

        <div class="card-title">
            SISTE OPPDATERING
        </div>

        <div>
            {state["last_update"]}
        </div>

    </div>

</div>


<!-- CONSOLE -->

<div class="section">

    <h2>Console</h2>

    <div class="logs">

"""

    logs_html = ""

    for log in reversed(state["logs"]):
        logs_html += f'<div class="log">{log}</div>'

    return f"""
        {logs_html}

    </div>

</div>

</div>

</body>

</html>
"""