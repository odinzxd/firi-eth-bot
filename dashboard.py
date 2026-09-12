from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

state = {
    "status": "STARTING",
    "price": 0,
    "nok": 0,
    "eth": 0,
    "signal": "HOLD",
    "reason": "Starter...",
    "last_update": "-",
    "logs": [],
}


def add_log(message: str):
    state["logs"].append(message)

    # Hold maks 100 linjer i dashboardet
    state["logs"] = state["logs"][-100:]


@app.get("/", response_class=HTMLResponse)
async def dashboard():

    logs = "<br>".join(
        log.replace("&", "&amp;").replace("<", "&lt;")
        for log in reversed(state["logs"])
    )

    html = f"""
    <!DOCTYPE html>
    <html lang="no">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="10">

        <title>Firi ETH Bot</title>

        <style>
            body {{
                background: #111318;
                color: #eeeeee;
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 30px;
            }}

            .header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 25px;
            }}

            .online {{
                color: #45d483;
            }}

            .cards {{
                display: grid;
                grid-template-columns:
                    repeat(4, 1fr);
                gap: 15px;
                margin-bottom: 20px;
            }}

            .card {{
                background: #1b1e25;
                border-radius: 10px;
                padding: 20px;
            }}

            .label {{
                color: #8f96a3;
                font-size: 13px;
                margin-bottom: 8px;
            }}

            .value {{
                font-size: 25px;
                font-weight: bold;
            }}

            .signal {{
                background: #1b1e25;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
            }}

            .hold {{
                color: #f0c75e;
            }}

            .console {{
                background: #080a0e;
                border-radius: 10px;
                padding: 20px;
                font-family: Consolas, monospace;
                font-size: 13px;
                line-height: 1.6;
                height: 400px;
                overflow-y: auto;
            }}
        </style>
    </head>

    <body>

        <div class="header">
            <h1>Firi ETH Trading Bot</h1>
            <div class="online">● {state["status"]}</div>
        </div>

        <div class="cards">

            <div class="card">
                <div class="label">ETH/NOK</div>
                <div class="value">
                    {state["price"]:,.2f} kr
                </div>
            </div>

            <div class="card">
                <div class="label">NOK BALANSE</div>
                <div class="value">
                    {state["nok"]:,.2f} kr
                </div>
            </div>

            <div class="card">
                <div class="label">ETH BALANSE</div>
                <div class="value">
                    {state["eth"]:.8f}
                </div>
            </div>

            <div class="card">
                <div class="label">SIGNAL</div>
                <div class="value hold">
                    {state["signal"]}
                </div>
            </div>

        </div>

        <div class="signal">
            <div class="label">SISTE VURDERING</div>
            <div>
                {state["reason"]}
            </div>

            <br>

            <div class="label">SISTE OPPDATERING</div>
            <div>
                {state["last_update"]}
            </div>
        </div>

        <h2>Console</h2>

        <div class="console">
            {logs}
        </div>

    </body>
    </html>
    """

    return html