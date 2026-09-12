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

    "rsi": 50.0,
    "ema_fast": 0.0,
    "ema_slow": 0.0,
    "momentum": 0.0,
    "volatility": 0.0,

    "expected_profit_percent": 0.0,
    "estimated_cost_percent": 0.0,
    "net_expected_percent": 0.0,

    "history_points": 0,

    "last_update": "-",

    "logs": [],
}


def add_log(message):

    state["logs"].append(
        message
    )

    if len(state["logs"]) > 300:

        state["logs"] = (
            state["logs"][-300:]
        )


@app.get(
    "/",
    response_class=HTMLResponse
)
async def dashboard():

    profit = (
        state["profit_nok"]
    )

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


    signal = state["signal"]

    if signal.startswith("BUY"):

        signal_class = "signal-buy"

    elif signal.startswith("SELL"):

        signal_class = "signal-sell"

    else:

        signal_class = "signal-hold"


    logs_html = ""

    for log_message in reversed(
        state["logs"]
    ):

        logs_html += (
            f'<div class="log">'
            f'{log_message}'
            f'</div>'
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
    color: #3ddc84;
    font-size: 14px;
    font-weight: bold;
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

.signal-buy {{
    color: #3ddc84;
}}

.signal-sell {{
    color: #ff5c5c;
}}

.signal-hold {{
    color: #f0c75e;
}}

.signal {{
    font-size: 25px;
    font-weight: bold;
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
}}

.log {{
    padding: 3px 0;

    border-bottom:
        1px solid #111318;
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

.indicator {{
    display: flex;

    justify-content: space-between;

    align-items: center;

    padding: 8px 0;

    border-bottom:
        1px solid #292d35;
}}

.indicator:last-child {{
    border-bottom: none;
}}

.indicator-name {{
    color: #9da5b1;
}}

.indicator-value {{
    font-weight: bold;
}}

.good {{
    color: #3ddc84;
}}

.bad {{
    color: #ff5c5c;
}}

.warning {{
    color: #f0c75e;
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


<!-- TRADING -->

<div class="card">

    <div class="card-title">
        TRADING STATUS
    </div>

    <div class="value {trading_class}">
        ● {trading_text}
    </div>

    <div class="small">
        DRY_RUN =
        {str(not state["trading"]).lower()}
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


<!-- GEVINST -->

<div class="grid">


    <div class="card">

        <div class="card-title">
            GEVINST / TAP
        </div>

        <div class="value {profit_class}">
            {profit_sign}
            {profit:,.2f} kr
        </div>

        <div class="small">
            Startkapital:
            1 800 kr
        </div>

    </div>


    <div class="card">

        <div class="card-title">
            AVKASTNING
        </div>

        <div class="value {profit_class}">
            {profit_sign}
            {state["profit_percent"]:.2f}%
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

        <div class="signal {signal_class}">
            {signal}
        </div>

        <div class="small">
            Score:
            {state["history_points"]} datapunkter
        </div>

    </div>


</div>


<!-- INDIKATORER -->

<div class="section">

    <div class="section-title">
        Strategi
    </div>

    <div class="card">


        <div class="indicator">

            <span class="indicator-name">
                RSI 14
            </span>

            <span class="indicator-value">
                {state["rsi"]:.2f}
            </span>

        </div>


        <div class="indicator">

            <span class="indicator-name">
                EMA 20
            </span>

            <span class="indicator-value">
                {state["ema_fast"]:,.2f} kr
            </span>

        </div>


        <div class="indicator">

            <span class="indicator-name">
                EMA 50
            </span>

            <span class="indicator-value">
                {state["ema_slow"]:,.2f} kr
            </span>

        </div>


        <div class="indicator">

            <span class="indicator-name">
                Momentum
            </span>

            <span class="indicator-value">
                {state["momentum"]:+.2f}%
            </span>

        </div>


        <div class="indicator">

            <span class="indicator-name">
                Volatilitet
            </span>

            <span class="indicator-value">
                {state["volatility"]:.2f}%
            </span>

        </div>


        <div class="indicator">

            <span class="indicator-name">
                Forventet bevegelse
            </span>

            <span class="indicator-value">
                {state["expected_profit_percent"]:.2f}%
            </span>

        </div>


        <div class="indicator">

            <span class="indicator-name">
                Estimert kostnad
            </span>

            <span class="indicator-value">
                {state["estimated_cost_percent"]:.2f}%
            </span>

        </div>


        <div class="indicator">

            <span class="indicator-name">
                Forventet netto
            </span>

            <span class="indicator-value">
                {state["net_expected_percent"]:+.2f}%
            </span>

        </div>


    </div>

</div>


<!-- SIGNALGRUNN -->

<div class="section">

    <div class="section-title">
        Hvorfor?
    </div>

    <div class="info">

        {state["reason"]}

    </div>

</div>


<!-- OPPDATERING -->

<div class="section">

    <div class="info">

        <div class="card-title">
            SISTE OPPDATERING
        </div>

        <div>
            {state["last_update"]}
        </div>

        <div class="small">
            Bot: 5 sekunder
            |
            Dashboard: live refresh
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