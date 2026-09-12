from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, PlainTextResponse
import os
import secrets
from html import escape
from typing import List
from dotenv import load_dotenv

load_dotenv()

TEST_TRADING_ENABLED = (
    os.getenv("TEST_TRADING_ENABLED", "false").lower() == "true"
)
TEST_TRADE_PASSWORD = os.getenv("TEST_TRADE_PASSWORD", "")


def positive_env_float(name: str, default: float) -> float:

    try:

        value = float(os.getenv(name, str(default)))

        return value if value > 0 else default

    except ValueError:

        return default


TEST_BUY_NOK = positive_env_float("TEST_BUY_NOK", 1.0)
TEST_SELL_NOK = positive_env_float("TEST_SELL_NOK", 10.0)

app = FastAPI()


# ============================================================
# GLOBAL STATE
# ============================================================

state = {

    "status": "STARTING",

    "trading": False,

    # Pris
    "price": 0.0,
    "bid": 0.0,
    "ask": 0.0,
    "spread": 0.0,

    # Saldo
    "nok": 0.0,
    "eth": 0.0,

    # Portefølje
    "eth_value": 0.0,
    "portfolio_value": 0.0,

    # Resultat
    "profit_nok": 0.0,
    "profit_percent": 0.0,

    # Strategi
    "signal": "HOLD",
    "reason": "Starter...",

    "rsi": 50.0,

    "ema_fast": 0.0,
    "ema_slow": 0.0,

    "momentum": 0.0,
    "volatility": 0.0,

    "trend": "UNKNOWN",

    "buy_score": 0,
    "sell_score": 0,

    # Kostnader
    "expected_profit_percent": 0.0,
    "estimated_cost_percent": 0.0,
    "net_expected_percent": 0.0,

    # Historikk
    "history_points": 0,

    # Feilsøking
    "last_ticker_ok": False,
    "last_balance_ok": False,
    "last_history_ok": False,
    "last_strategy_ok": False,

    "error_count": 0,
    "last_error": "Ingen feil",

    # Tid
    "last_update": "-",

    # Console
    "logs": [],

    # Manuelle testordrer. Selve ordreutførelsen skjer i bot.py.
    "test_order_request": None,
    "test_order_pending": False,
    "test_order_status": "Testhandel er deaktivert.",
    "test_order_result": "",
}


# ============================================================
# LOGGING
# ============================================================

def add_log(message):

    state["logs"].append(
        message
    )

    if len(
        state["logs"]
    ) > 300:

        state["logs"] = (
            state["logs"][-300:]
        )


# ============================================================
# HTML
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse
)
async def dashboard():

    profit = (
        state["profit_nok"]
    )


    # --------------------------------------------------------
    # PROFIT
    # --------------------------------------------------------

    if profit > 0:

        profit_class = "profit"
        profit_sign = "+"

    elif profit < 0:

        profit_class = "loss"
        profit_sign = ""

    else:

        profit_class = "neutral"
        profit_sign = ""


    # --------------------------------------------------------
    # TRADING
    # --------------------------------------------------------

    if state["trading"]:

        trading_text = "ON (LIVE)"
        trading_class = "trading-on"

    else:

        trading_text = "OFF (DRY RUN)"
        trading_class = "trading-off"


    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    signal = state["signal"]

    if signal.startswith("BUY"):

        signal_class = "signal-buy"

    elif signal.startswith("SELL"):

        signal_class = "signal-sell"

    else:

        signal_class = "signal-hold"


    # --------------------------------------------------------
    # HELSE
    # --------------------------------------------------------

    def health(ok):

        if ok:

            return (
                '<span class="ok">'
                '● OK'
                '</span>'
            )

        return (
            '<span class="error">'
            '● FEIL'
            '</span>'
        )


    # --------------------------------------------------------
    # LOGS
    # --------------------------------------------------------

    logs_html = ""

    for log_message in reversed(
        state["logs"]
    ):

        logs_html += (
            '<div class="log">'
            f'{log_message}'
            '</div>'
        )


    if not logs_html:

        logs_html = (
            '<div class="empty">'
            'Ingen logger ennå...'
            '</div>'
        )


    # ========================================================
    # HTML
    # ========================================================

    return f"""
<!DOCTYPE html>

<html lang="no">

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1.0">

<meta http-equiv="refresh" content="2">

<title>Firi ETH Bot</title>


<style>

* {{
    box-sizing: border-box;
}}


body {{

    margin: 0;

    background: #0e1014;

    color: #f5f5f5;

    font-family:
        Arial,
        Helvetica,
        sans-serif;

}}


.container {{

    max-width: 1700px;

    margin: auto;

    padding: 20px;

}}


.header {{

    display: flex;

    justify-content:
        space-between;

    align-items:
        center;

    margin-bottom: 20px;

}}


h1 {{

    margin: 0;

    font-size: 28px;

}}


.card {{

    background: #191c22;

    border: 1px solid #292e37;

    border-radius: 12px;

    padding: 20px;

}}


.grid {{

    display: grid;

    grid-template-columns:
        repeat(
            4,
            minmax(0, 1fr)
        );

    gap: 14px;

    margin-top: 14px;

}}


.title {{

    color: #8e98a8;

    font-size: 12px;

    font-weight: bold;

    margin-bottom: 10px;

    text-transform:
        uppercase;

}}


.value {{

    font-size: 25px;

    font-weight: bold;

}}


.small {{

    margin-top: 7px;

    color: #8993a3;

    font-size: 13px;

}}


.profit,
.ok,
.trading-on {{

    color: #3ddc84;

}}


.loss,
.error,
.trading-off {{

    color: #ff5c5c;

}}


.neutral,
.signal-hold {{

    color: #f0c75e;

}}


.signal-buy {{

    color: #3ddc84;

}}


.signal-sell {{

    color: #ff5c5c;

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


.indicator {{

    display: flex;

    justify-content:
        space-between;

    padding: 10px 0;

    border-bottom:
        1px solid #292e37;

}}


.indicator:last-child {{

    border-bottom: none;

}}


.indicator-name {{

    color: #929baa;

}}


.indicator-value {{

    font-weight: bold;

}}


.logs {{

    background: #050609;

    border: 1px solid #292e37;

    border-radius: 10px;

    height: 450px;

    overflow-y: auto;

    padding: 15px;

    font-family:
        Consolas,
        monospace;

    font-size: 12px;

    line-height: 1.6;

}}


.log {{

    border-bottom:
        1px solid #111419;

    padding: 3px 0;

    white-space:
        pre-wrap;

}}


.empty {{

    color: #657080;

}}


.health-grid {{

    display: grid;

    grid-template-columns:
        repeat(
            4,
            minmax(0, 1fr)
        );

    gap: 10px;

}}


.health-item {{

    background: #101217;

    border-radius: 8px;

    padding: 12px;

}}


.alert {{

    border: 1px solid #5b2020;

    background: #241315;

    border-radius: 10px;

    padding: 15px;

    margin-top: 14px;

}}


.reason {{

    background: #101217;

    border-radius: 8px;

    padding: 15px;

    color: #d7dce4;

}}


.test-button {{

    border: 0;

    border-radius: 8px;

    color: #ffffff;

    cursor: pointer;

    font-weight: bold;

    margin: 8px 8px 0 0;

    padding: 10px 14px;

}}


.test-buy {{

    background: #197b45;

}}


.test-sell {{

    background: #a93e3e;

}}


@media (max-width: 1100px) {{

    .grid,
    .health-grid {{

        grid-template-columns:
            repeat(
                2,
                minmax(0, 1fr)
            );

    }}

}}


@media (max-width: 600px) {{

    .container {{

        padding: 10px;

    }}

    .header {{

        display: block;

    }}

    .grid,
    .health-grid {{

        grid-template-columns:
            1fr;

    }}

}}

</style>

</head>


<body>


<div class="container">


<!-- ===================================================== -->
<!-- HEADER -->
<!-- ===================================================== -->

<div class="header">

    <h1>
        Firi ETH Trading Bot
    </h1>

    <div>
        <span class="ok">
            ● {state["status"]}
        </span>
    </div>

</div>


<!-- ===================================================== -->
<!-- TRADING STATUS -->
<!-- ===================================================== -->

<div class="card">

    <div class="title">
        Trading
    </div>

    <div class="value {trading_class}">
        ● {trading_text}
    </div>

    <div class="small">
        DRY_RUN =
        {str(not state["trading"]).lower()}
    </div>

</div>


<!-- ===================================================== -->
<!-- MANUELL TESTHANDEL -->
<!-- ===================================================== -->

<div class="section">

    <div class="section-title">
        Manuell testhandel
    </div>

    <div class="card">

        <div class="small">
            Testmodus: {"AKTIVERT" if TEST_TRADING_ENABLED else "AV"}
            | Kjøp: {TEST_BUY_NOK:.2f} kr | Salg: {TEST_SELL_NOK:.2f} kr
        </div>

        <button class="test-button test-buy" onclick="requestTestOrder('buy')">
            Testkjøp {TEST_BUY_NOK:.2f} kr
        </button>

        <button class="test-button test-sell" onclick="requestTestOrder('sell')">
            Testselg ca. {TEST_SELL_NOK:.2f} kr
        </button>

        <div class="small">
            {escape(str(state["test_order_status"]))}
        </div>

        <div class="small">
            {escape(str(state["test_order_result"]))}
        </div>

    </div>

</div>


<!-- ===================================================== -->
<!-- PRIS / SALDO -->
<!-- ===================================================== -->

<div class="grid">


    <div class="card">

        <div class="title">
            ETH/NOK
        </div>

        <div class="value">
            {state["price"]:,.2f} kr
        </div>

        <div class="small">
            Bid:
            {state["bid"]:,.2f}
        </div>

        <div class="small">
            Ask:
            {state["ask"]:,.2f}
        </div>

    </div>


    <div class="card">

        <div class="title">
            ETH BEHOLDNING
        </div>

        <div class="value">
            {state["eth"]:.8f}
        </div>

        <div class="small">
            ETH
            |
            Verdi:
            {state["eth_value"]:,.2f} kr
        </div>

    </div>


    <div class="card">

        <div class="title">
            NOK
        </div>

        <div class="value">
            {state["nok"]:,.2f} kr
        </div>

    </div>


    <div class="card">

        <div class="title">
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


<!-- ===================================================== -->
<!-- PROFIT -->
<!-- ===================================================== -->

<div class="grid">


    <div class="card">

        <div class="title">
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

        <div class="title">
            AVKASTNING
        </div>

        <div class="value {profit_class}">
            {profit_sign}
            {state["profit_percent"]:.2f}%
        </div>

    </div>


    <div class="card">

        <div class="title">
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

        <div class="title">
            SIGNAL
        </div>

        <div class="signal {signal_class}">
            {signal}
        </div>

        <div class="small">
            BUY:
            {state["buy_score"]}/12
            |
            SELL:
            {state["sell_score"]}/12
        </div>

    </div>


</div>


<!-- ===================================================== -->
<!-- INDIKATORER -->
<!-- ===================================================== -->

<div class="section">

    <div class="section-title">
        Markedsindikatorer
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
                Trend
            </span>

            <span class="indicator-value">
                {state["trend"]}
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


        <div class="indicator">

            <span class="indicator-name">
                Historikk
            </span>

            <span class="indicator-value">
                {state["history_points"]}
                datapunkter
            </span>

        </div>


    </div>

</div>


<!-- ===================================================== -->
<!-- SIGNAL -->
<!-- ===================================================== -->

<div class="section">

    <div class="section-title">
        Strategiforklaring
    </div>

    <div class="reason">

        {state["reason"]}

    </div>

</div>


<!-- ===================================================== -->
<!-- SYSTEMHELSEN -->
<!-- ===================================================== -->

<div class="section">

    <div class="section-title">
        Systemstatus
    </div>


    <div class="health-grid">


        <div class="health-item">

            <div class="title">
                Firi Ticker
            </div>

            {health(
                state["last_ticker_ok"]
            )}

        </div>


        <div class="health-item">

            <div class="title">
                Firi Balance
            </div>

            {health(
                state["last_balance_ok"]
            )}

        </div>


        <div class="health-item">

            <div class="title">
                Market History
            </div>

            {health(
                state["last_history_ok"]
            )}

        </div>


        <div class="health-item">

            <div class="title">
                Strategy
            </div>

            {health(
                state["last_strategy_ok"]
            )}

        </div>


    </div>

</div>


<!-- ===================================================== -->
<!-- FEIL -->
<!-- ===================================================== -->

<div class="section">

    <div class="section-title">
        Feilsøking
    </div>


    <div class="alert">

        <div class="title">
            Antall feil
        </div>

        <div class="value">
            {state["error_count"]}
        </div>

        <div class="small">
            Siste feil:
            {state["last_error"]}
        </div>

    </div>

</div>


<!-- ===================================================== -->
<!-- OPPDATERING -->
<!-- ===================================================== -->

<div class="section">

    <div class="card">

        <div class="title">
            Sist oppdatert
        </div>

        <div>
            {state["last_update"]}
        </div>

    </div>

</div>


<!-- ===================================================== -->
<!-- CONSOLE -->
<!-- ===================================================== -->

<div class="section">

    <div class="section-title">
        Console
    </div>

    <div class="logs">

        {logs_html}

    </div>

</div>


</div>


<script>

async function requestTestOrder(action) {{

    const password = window.prompt(
        'Skriv testpassordet for å sende en ekte ' + action + '-ordre.'
    );

    if (password === null) {{

        return;

    }}

    const response = await fetch('/test-order', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{action: action, password: password}})
    }});

    const result = await response.json();

    window.alert(
        result.message || result.detail || 'Ukjent svar fra testhandel.'
    );

    window.location.reload();

}}

</script>

</body>

</html>
"""


@app.post("/test-order")
async def queue_test_order(request: Request) -> JSONResponse:

    if not TEST_TRADING_ENABLED:

        raise HTTPException(
            status_code=403,
            detail="Testhandel er deaktivert. Sett TEST_TRADING_ENABLED=true."
        )

    if not TEST_TRADE_PASSWORD:

        raise HTTPException(
            status_code=503,
            detail="TEST_TRADE_PASSWORD mangler."
        )

    try:

        payload = await request.json()

    except ValueError:

        raise HTTPException(status_code=400, detail="Ugyldig forespørsel.")

    action = str(payload.get("action", "")).lower()
    password = str(payload.get("password", ""))

    if action not in {"buy", "sell"}:

        raise HTTPException(status_code=400, detail="Ugyldig testhandling.")

    if not secrets.compare_digest(password, TEST_TRADE_PASSWORD):

        raise HTTPException(status_code=401, detail="Feil testpassord.")

    if state["test_order_pending"]:

        raise HTTPException(status_code=409, detail="En testordre behandles allerede.")

    state["test_order_request"] = action
    state["test_order_pending"] = True
    state["test_order_status"] = f"Test-{action} ligger i kø."
    state["test_order_result"] = "Venter på at botten sender ordren til Firi."

    add_log(f"Manuell test-{action} lagt i kø.")

    return JSONResponse(content={"message": "Testordre lagt i kø."})



@app.get("/debug/files")
async def list_debug_files() -> JSONResponse:

    debug_dir = os.path.join(os.getcwd(), "debug")

    if not os.path.isdir(debug_dir):

        return JSONResponse(200, [])

    files: List[str] = []

    for name in sorted(os.listdir(debug_dir), reverse=True):

        path = os.path.join(debug_dir, name)

        if os.path.isfile(path):

            files.append(name)

    return JSONResponse(content=files)


@app.get("/debug/file/{fname}")
async def get_debug_file(fname: str):

    # Prevent directory traversal
    if ".." in fname or fname.startswith("/"):

        raise HTTPException(status_code=400, detail="Invalid filename")

    debug_dir = os.path.join(os.getcwd(), "debug")

    path = os.path.join(debug_dir, fname)

    if not os.path.isfile(path):

        raise HTTPException(status_code=404, detail="File not found")

    try:

        return FileResponse(path, media_type="application/json", filename=fname)

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))


@app.get("/debug/latest")
async def get_latest_debug_file():

    debug_dir = os.path.join(os.getcwd(), "debug")

    if not os.path.isdir(debug_dir):

        raise HTTPException(status_code=404, detail="No debug directory")

    files = [
        f for f in os.listdir(debug_dir)
        if os.path.isfile(os.path.join(debug_dir, f)) and not f.startswith(".")
    ]

    if not files:

        raise HTTPException(status_code=404, detail="No debug files")

    files.sort(reverse=True)

    latest = files[0]

    path = os.path.join(debug_dir, latest)

    return FileResponse(path, media_type="application/json", filename=latest)


@app.get("/debug/peek/{fname}")
async def peek_debug_file(fname: str, lines: int = 50):

    if ".." in fname or fname.startswith("/"):

        raise HTTPException(status_code=400, detail="Invalid filename")

    debug_dir = os.path.join(os.getcwd(), "debug")

    path = os.path.join(debug_dir, fname)

    if not os.path.isfile(path):

        raise HTTPException(status_code=404, detail="File not found")

    try:

        with open(path, "r", encoding="utf-8", errors="replace") as fh:

            content = []

            for _ in range(lines):

                line = fh.readline()

                if not line:

                    break

                content.append(line.rstrip("\n"))

        return JSONResponse(content={"file": fname, "lines": content})

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))



@app.get("/console")
async def console():

    # Samle feillogger og relevante tracebacks fra state
    header = []

    header.append(f"Error count: {state.get('error_count', 0)}")
    header.append(f"Last error: {state.get('last_error', 'Ingen feil')}")
    header.append("")

    error_patterns = [
        "FEIL",
        "ERROR",
        "TRACEBACK",
        "Exception",
        "Traceback",
    ]

    found = []

    for entry in reversed(state.get("logs", [])):

        for pat in error_patterns:

            if pat in entry:

                found.append(entry)

                break

    if not found:

        found = ["Ingen feillogg funnet."]

    text = "\n".join(header + found)

    return PlainTextResponse(text)
