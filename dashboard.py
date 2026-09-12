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

    # Behold de siste 200 loggene
    if len(state["logs"]) > 200:
        state["logs"] = state["logs"][-200:]


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

    if state["trading"]:
        trading_text = "ON (LIVE)"
        trading_class = "trading-on"
    else:
        trading_text = "OFF (DRY RUN)"
        trading_class = "trading-off"

    # Lag console-innhold
    logs_html = ""

    for log_message in reversed(state["logs"]):
        logs_html += (
            f'<div class="log">{log_message}</div>'
        )

    if not logs_html:
        logs_html = (
            '<div class="empty-log">'
            'Ingen logger ennå...'
            '</div>'
        )

    return f"""
<!DOCTYPE html>

<html lang="no">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Firi ETH Trading Bot</title>

<meta http-equiv="refresh" content="2">

<style>

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    padding: 0;

    background: #0f1115;
    color: #f5f5f5;

    font-family:
        Arial,
        Helvetica,
        sans-serif;
}}

.container {{
    max-width: 1600px;

    margin: auto;

    padding: 20px;
}}

.header {{
    display: flex;

    justify-content: space-between;

    align-items: center;

    margin-bottom: 20px;
}}

h1 {{
    margin: 0;

    font-size: 28px;
}}

.bot-status {{
    font-size: 14px;

    font-weight: bold;

    color: #3ddc84;
}}

.grid {{
    display: grid;

    grid-template-columns:
        repeat(4, minmax(0, 1fr));

    gap: 14px;

    margin-top: 14px;
}}

.card {{
    background: #1a1d23;

    border: 1px solid #292d35;

    border-radius: 12px;

    padding: 20px;

    min-width: 0;
}}

.card-title {{
    color: #8f98a8;

    font-size: 12px;

    font-weight: bold;

    letter-spacing: 0.5px;

    margin-bottom: 10px;
}}

.value {{
    font-size: 25px;

    font-weight: bold;

    word-break: break-word;
}}

.small {{
    color: #8f98a8;

    font-size: 13px;

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
    font-size: 25px;

    font-weight: bold;

    color: #f0c75e;
}}

.trading-card {{
    margin-bottom: 14px;
}}

.update {{
    color: #8f98a8;

    font-size: 13px;

    margin-top: 8px;
}}

.section {{
    margin-top: 20px;
}}

.section-title {{
    font-size: 20px;

    font-weight: bold;

    margin-bottom: 10px;
}}

.logs {{
    background: #050609;

    border: 1px solid #292d35;

    border-radius: 10px;

    padding: 15px;

    height: 450px;

    overflow-y: auto;

    font-family:
        Consolas,
        "Courier New",
        monospace;

    font-size: 12px;

    line-height: 1.6;

    white-space: normal;
}}

.log {{
    padding: 2px 0;

    border-bottom: 1px solid #111318;

    color: #d7dbe2;
}}

.empty-log {{
    color: #6f7785;
}}

.info {{
    background: #1a1d23;

    border: 1px solid #292d35;

    border-radius: 10px;

    padding: 15px;
}}

@media (max-width: 1100px) {{

    .grid {{
        grid-template-columns:
            repeat(2, minmax(0, 1fr));
    }}

}}

@media (max-width: 600px) {{

    .container {{
        padding: 10px;
    }}

    .header {{
        display: block;
    }}

    .bot-status {{
        margin-top: 8px;
    }}

    .grid {{
        grid-template-columns: 1fr;
    }}

    .logs {{
        height: 350px;
    }}

}}

</style>

</head>


<body>

<div class="container">


<div class="header">

    <h1>
        Firi ETH Trading Bot
    </h1>

    <div class="bot-status">
        ● {state["status"]}
    </div>

</div>


<!-- TRADING STATUS -->

<div class="card trading-card">

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
            Bid:
            {state["bid"]:,.2f} kr
        </div>

        <div class="small">
            Ask:
            {state["ask"]:,.2f} kr
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
            Verdi:
            {state["eth_value"]:,.2f} kr
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
            Siden start:
            1 800 kr
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

        <div class="update">
            Dashboard oppdateres hvert 2. sekund
        </div>

    </div>

</div>


<!-- CONSOLE -->

<div class="section">

    <div class="section-title">
        Console
    </div>

    <div class="logs">

        {logs_html}

    </div>

</div>


</div>

</body>

</html>
"""