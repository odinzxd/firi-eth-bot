import json
import os
import threading
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


app = FastAPI(title="Firi Simple ETH Bot")


@app.on_event("startup")
async def startup_event():
    if not os.getenv("BOT_RUNNING_IN_BACKGROUND", "false").lower() == "true":
        thread = threading.Thread(
            target=_run_bot_in_background,
            daemon=True,
        )
        thread.start()
        os.environ["BOT_RUNNING_IN_BACKGROUND"] = "true"


def _run_bot_in_background():
    import asyncio

    from bot import main as bot_main

    asyncio.run(bot_main())


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
    "trade_status": "WAITING",
    "trade_reason": "",
    "chart_candles": [],
    "chart_history": [],
    "position": False,
    "entry_price": 0.0,
    "take_profit": 0.0,
    "stop_loss": 0.0,
    "take_profit_percent": 0.0,
    "stop_loss_percent": 0.6,
    "estimated_round_trip_cost": 0.0,
    "break_even_percent": 0.0,
    "nok": 0.0,
    "eth": 0.0,
    "eth_value_nok": 0.0,
    "total_portfolio_nok": 0.0,
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

    eth_value_nok = state["eth"] * state["price"] if state["price"] else 0.0
    total_portfolio_nok = state["nok"] + eth_value_nok
    state["eth_value_nok"] = eth_value_nok
    state["total_portfolio_nok"] = total_portfolio_nok

    trade_status = state.get("trade_status", "WAITING")
    trade_reason = state.get("trade_reason", "")
    chart_candles_json = json.dumps(state.get("chart_candles", []))
    chart_history_json = json.dumps(state.get("chart_history", []))

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
<div>TRADE STATUS: {trade_status}</div>
<div>REASON: {trade_reason or state["reason"]}</div>
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
<div class="title">BEHOLDNING</div>
<div class="row"><span>NOK-beholdning</span><span class="value">{fmt(state["nok"])} NOK</span></div>
<div class="row"><span>ETH-beholdning</span><span class="value">{fmt(state["eth"],8)} ETH</span></div>
<div class="row"><span>ETH-verdi</span><span class="value">{fmt(eth_value_nok)} NOK</span></div>
<div class="row"><span>Total beholdning</span><span class="value">{fmt(total_portfolio_nok)} NOK</span></div>
</div>

<div class="section card">
<div class="title">POSISJON</div>
<div class="row"><span>Status</span><span class="value">ETH</span></div>
<div class="row"><span>Bot-posisjon</span><span class="value">{'JA' if state["position"] else 'NEI'}</span></div>
<div class="row"><span>Inngangspris</span><span class="value">{fmt(state["entry_price"])} kr</span></div>
<div class="row"><span>Take profit</span><span class="value">{fmt(state["take_profit"])} kr</span></div>
<div class="row"><span>Stop loss</span><span class="value">{fmt(state["stop_loss"])} kr</span></div>
<div class="row"><span>Estimert round-trip-kostnad</span><span class="value">{fmt(state["estimated_round_trip_cost"], 2)} %</span></div>
<div class="row"><span>Break-even %</span><span class="value">{fmt(state["break_even_percent"], 2)} %</span></div>
<div class="row"><span>Take-profit %</span><span class="value">{fmt(state["take_profit_percent"], 2)} %</span></div>
<div class="row"><span>Stop-loss %</span><span class="value">{fmt(state["stop_loss_percent"], 2)} %</span></div>
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

<div class="section card">
<div class="title">TRADING GRAF (ETHUSDT / 24H)</div>
<canvas id="tradeChart" height="120"></canvas>
</div>

<div class="section error">
<div class="title">SISTE FEIL</div>
{state["last_error"]}
</div>

<div class="section card">
<div class="title">LOGG</div>
<div class="logs">{logs or "Ingen logger ennå."}</div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
<script>
const candles = {chart_candles_json};
const events = {chart_history_json};

const closeValues = candles.map(c => Number(c.close));
const timestamps = candles.map(c => Number(c.timestamp));

function computeEma(values, period) {{
  const result = [];
  let prev = null;
  const multiplier = 2 / (period + 1);

  values.forEach((value, index) => {{
    if (index === 0) {{
      prev = value;
      result.push(null);
      return;
    }}

    if (index < period) {{
      prev = ((value - prev) * multiplier) + prev;
      result.push(null);
      return;
    }}

    prev = ((value - prev) * multiplier) + prev;
    result.push(prev);
  }});

  return result;
}}

const ema9 = computeEma(closeValues, 9);
const ema21 = computeEma(closeValues, 21);

const chartDatasets = [
  {{
    label: 'ETHUSDT pris',
    data: candles.map(c => ({{x: Number(c.timestamp), y: Number(c.close)}})),
    borderColor: '#67b7ff',
    backgroundColor: 'rgba(103,183,255,0.12)',
    borderWidth: 2,
    pointRadius: 0,
    fill: false,
    tension: 0.15,
  }},
  {{
    label: 'EMA9',
    data: candles.map((c, index) => ({{x: Number(c.timestamp), y: ema9[index]}})).filter(item => item.y !== null),
    borderColor: '#66d9b5',
    borderWidth: 2,
    pointRadius: 0,
    tension: 0.15,
    fill: false,
  }},
  {{
    label: 'EMA21',
    data: candles.map((c, index) => ({{x: Number(c.timestamp), y: ema21[index]}})).filter(item => item.y !== null),
    borderColor: '#f7b267',
    borderWidth: 2,
    pointRadius: 0,
    tension: 0.15,
    fill: false,
  }},
];

const markerColors = {{
  SIGNAL: '#f7c948',
  EXECUTED: '#2ec27e',
  BLOCKED: '#ff5d73',
}};

const eventPoints = events
  .filter(item => item && Number(item.timestamp) > 0)
  .map(item => ({{
    x: Number(item.timestamp),
    y: Number(item.price || 0),
    label: `${{item.signal}} ${{item.event_type === 'SIGNAL' ? 'SIGNAL' : item.event_type === 'EXECUTED' ? 'EXECUTED' : 'BLOCKED'}}`,
    signal: item.signal,
    eventType: item.event_type,
    entryPrice: Number(item.entry_price || 0),
    takeProfit: Number(item.take_profit || 0),
    stopLoss: Number(item.stop_loss || 0),
  }}));

const eventDatasets = [
  {{
    label: 'BUY SIGNAL',
    type: 'scatter',
    data: eventPoints.filter(item => item.signal === 'BUY' && item.eventType === 'SIGNAL'),
    pointBackgroundColor: markerColors.SIGNAL,
    pointRadius: 5,
    pointStyle: 'triangle',
    showLine: false,
  }},
  {{
    label: 'SELL SIGNAL',
    type: 'scatter',
    data: eventPoints.filter(item => item.signal === 'SELL' && item.eventType === 'SIGNAL'),
    pointBackgroundColor: markerColors.SIGNAL,
    pointRadius: 5,
    pointStyle: 'triangle',
    showLine: false,
  }},
  {{
    label: 'BUY EXECUTED',
    type: 'scatter',
    data: eventPoints.filter(item => item.signal === 'BUY' && item.eventType === 'EXECUTED'),
    pointBackgroundColor: markerColors.EXECUTED,
    pointRadius: 6,
    pointStyle: 'circle',
    showLine: false,
  }},
  {{
    label: 'SELL EXECUTED',
    type: 'scatter',
    data: eventPoints.filter(item => item.signal === 'SELL' && item.eventType === 'EXECUTED'),
    pointBackgroundColor: markerColors.EXECUTED,
    pointRadius: 6,
    pointStyle: 'circle',
    showLine: false,
  }},
  {{
    label: 'BUY SIGNAL - BLOCKED',
    type: 'scatter',
    data: eventPoints.filter(item => item.signal === 'BUY' && item.eventType === 'BLOCKED'),
    pointBackgroundColor: markerColors.BLOCKED,
    pointRadius: 7,
    pointStyle: 'rectRot',
    showLine: false,
  }},
  {{
    label: 'SELL SIGNAL - BLOCKED',
    type: 'scatter',
    data: eventPoints.filter(item => item.signal === 'SELL' && item.eventType === 'BLOCKED'),
    pointBackgroundColor: markerColors.BLOCKED,
    pointRadius: 7,
    pointStyle: 'rectRot',
    showLine: false,
  }},
];

new Chart(document.getElementById('tradeChart'), {{
  type: 'line',
  data: {{
    datasets: [...chartDatasets, ...eventDatasets],
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    interaction: {{ mode: 'nearest', intersect: false }},
    scales: {{
      x: {{
        type: 'time',
        time: {{
          unit: 'hour',
          tooltipFormat: 'yyyy-MM-dd HH:mm',
        }},
        ticks: {{
          color: '#dfe7f3',
        }},
        title: {{
          display: true,
          text: 'Tid',
          color: '#dfe7f3',
        }},
      }},
      y: {{
        ticks: {{
          color: '#dfe7f3',
        }},
        title: {{
          display: true,
          text: 'ETHUSDT',
          color: '#dfe7f3',
        }},
      }},
    }},
    plugins: {{
      legend: {{
        labels: {{
          color: '#e8eaf0',
        }},
      }},
      tooltip: {{
        callbacks: {{
          title(context) {{
            if (!context || !context[0]) return 'Signal';
            const value = context[0].parsed.x;
            return new Date(value).toLocaleString('no-NO', {{dateStyle:'medium', timeStyle:'short'}});
          }},
          label(context) {{
            const point = context.raw;
            if (point && point.signal && point.eventType) {{
              const eventLabel = `${{point.signal}} ${{point.eventType}}`;
              const price = point.y ? Number(point.y).toFixed(2) : 'N/A';
              const entry = point.entryPrice ? ` | Entry: ${{Number(point.entryPrice).toFixed(2)}}` : '';
              const tp = point.takeProfit ? ` | TP: ${{Number(point.takeProfit).toFixed(2)}}` : '';
              const sl = point.stopLoss ? ` | SL: ${{Number(point.stopLoss).toFixed(2)}}` : '';
              return `${{eventLabel}} | Price: ${{price}}${{entry}}${{tp}}${{sl}}`;
            }}
            return `${{context.dataset.label}}: ${{Number(context.parsed.y).toFixed(2)}}`;
          }},
        }},
      }},
    }},
  }},
}});
</script>

</div>
</body>
</html>
"""


def start_dashboard():
    import uvicorn

    uvicorn.run(
        "dashboard:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        log_level="warning",
    )
