import asyncio
import os
import threading
import time
import traceback
from datetime import datetime

import uvicorn
from dotenv import load_dotenv
from firipy import FiriAPI
import aiohttp

from dashboard import app, state, add_log
from strategy import analyze_market


# ============================================================
# MILJØ
# ============================================================

load_dotenv()


# ============================================================
# API-INNSTILLINGER
# ============================================================

API_KEY = os.getenv(
    "FIRI_API_KEY"
)

CLIENT_ID = os.getenv(
    "FIRI_CLIENT_ID"
)

SECRET_KEY = os.getenv(
    "FIRI_SECRET_KEY"
)


# ============================================================
# TRADING-INNSTILLINGER
# ============================================================

MARKET = os.getenv(
    "MARKET",
    "ETHNOK"
)

DRY_RUN = (
    os.getenv(
        "DRY_RUN",
        "true"
    ).lower()
    == "true"
)

MAX_TRADE_NOK = float(
    os.getenv(
        "MAX_TRADE_NOK",
        "200"
    )
)

STARTING_CAPITAL_NOK = 1800.0


# ============================================================
# TIDSINTERVALLER
# ============================================================

TICKER_INTERVAL = 5

BALANCE_INTERVAL = 30

HISTORY_INTERVAL = 60

HISTORY_COUNT = 500

MAX_PRICE_HISTORY = 500


# ============================================================
# RISIKO
# ============================================================

MAX_SPREAD_PERCENT = 0.005


# ============================================================
# FALLBACK / CONFIG
# ============================================================

FALLBACK_SOURCES = os.getenv(
    "FALLBACK_SOURCES",
    "coingecko"
).lower().split(",")

FALLBACK_DAYS = int(
    os.getenv(
        "FALLBACK_DAYS",
        "2"
    )
)


# ============================================================
# DIAGNOSTIKK
# ============================================================

DEBUG_MODE = True

last_ticker_ok = False
last_balance_ok = False
last_history_ok = False
last_strategy_ok = False

last_error = "Ingen feil"

error_count = 0


# ============================================================
# LOGGING
# ============================================================

def log(message):

    timestamp = (
        datetime.now()
        .strftime("%H:%M:%S")
    )

    text = (
        f"[{timestamp}] "
        f"{message}"
    )

    print(
        text,
        flush=True
    )

    add_log(text)


def debug(message):

    if DEBUG_MODE:

        log(
            f"DEBUG: {message}"
        )


def log_error(
    location,
    error
):

    global error_count
    global last_error

    error_count += 1

    last_error = (
        f"{location}: "
        f"{type(error).__name__}: "
        f"{error}"
    )

    log(
        f"FEIL [{location}]: "
        f"{type(error).__name__}: "
        f"{error}"
    )

    if DEBUG_MODE:

        traceback_text = (
            traceback.format_exc()
        )

        log(
            f"TRACEBACK:\n"
            f"{traceback_text}"
        )


# ============================================================
# SALDO
# ============================================================

def find_balance(
    balances,
    currency
):

    if isinstance(
        balances,
        dict
    ):

        if currency in balances:

            value = balances[currency]

            if isinstance(
                value,
                dict
            ):

                for key in [
                    "available",
                    "balance",
                    "amount",
                    "free"
                ]:

                    if key in value:

                        try:

                            return float(
                                value[key]
                            )

                        except (
                            ValueError,
                            TypeError
                        ):

                            pass

            try:

                return float(
                    value
                )

            except (
                ValueError,
                TypeError
            ):

                pass

        for key in [
            "balances",
            "data",
            "result"
        ]:

            if key in balances:

                result = find_balance(
                    balances[key],
                    currency
                )

                if result is not None:

                    return result


    elif isinstance(
        balances,
        list
    ):

        for item in balances:

            if not isinstance(
                item,
                dict
            ):

                continue

            symbol = (
                item.get("symbol")
                or item.get("currency")
                or item.get("asset")
                or item.get("code")
            )

            if (
                str(symbol).upper()
                != currency.upper()
            ):

                continue

            for key in [
                "available",
                "balance",
                "amount",
                "free",
                "available_balance"
            ]:

                if key in item:

                    try:

                        return float(
                            item[key]
                        )

                    except (
                        ValueError,
                        TypeError
                    ):

                        pass

    return 0.0


# ============================================================
# HISTORY -> PRIS
# ============================================================

def extract_trades(
    data
):

    trades = []

    def walk(value):

        if isinstance(
            value,
            dict
        ):

            price = None
            timestamp = None

            for key in [
                "price",
                "rate"
            ]:

                if key in value:

                    try:

                        candidate = float(
                            value[key]
                        )

                        if candidate > 0:

                            price = candidate
                            break

                    except (
                        ValueError,
                        TypeError
                    ):

                        pass

            for key in [
                "timestamp",
                "time",
                "ts",
                "date"
            ]:

                if key in value:

                    candidate = value[key]

                    try:

                        timestamp = float(
                            candidate
                        )

                        break

                    except (
                        ValueError,
                        TypeError
                    ):

                        pass

            if (
                price is not None
                and timestamp is not None
            ):

                if timestamp > 10_000_000_000:

                    timestamp /= 1000.0

                trades.append(
                    (
                        timestamp,
                        price
                    )
                )

            for child in value.values():

                if isinstance(
                    child,
                    (dict, list)
                ):

                    walk(child)

        elif isinstance(
            value,
            list
        ):

            for item in value:

                walk(item)

    walk(data)

    trades.sort(
        key=lambda x: x[0]
    )

    return trades


def build_minute_prices(
    history
):

    trades = extract_trades(
        history
    )

    if not trades:

        debug(
            "History inneholdt "
            "ingen gjenkjennelige trades."
        )

        return []

    buckets = {}

    for timestamp, price in trades:

        minute = int(
            timestamp // 60
        )

        buckets[minute] = price

    prices = [
        buckets[key]
        for key in sorted(
            buckets.keys()
        )
    ]

    return prices[
        -MAX_PRICE_HISTORY:
    ]


# ============================================================
# DASHBOARD
# ============================================================

def start_dashboard():

    try:

        log(
            "Starter dashboard..."
        )

        uvicorn.run(
            app,
            host="0.0.0.0",
            port=int(
                os.getenv(
                    "PORT",
                    "8080"
                )
            ),
            log_level="warning"
        )

    except Exception as e:

        log_error(
            "DASHBOARD",
            e
        )


# ============================================================
# HOVEDPROGRAM
# ============================================================

async def main():

    global last_ticker_ok
    global last_balance_ok
    global last_history_ok
    global last_strategy_ok

    log(
        "========================================"
    )

    log(
        "FIRI ETH TRADING BOT"
    )

    log(
        "========================================"
    )

    log(
        f"Market: {MARKET}"
    )

    log(
        f"DRY_RUN: {DRY_RUN}"
    )

    log(
        f"Maks handel: "
        f"{MAX_TRADE_NOK:.2f} kr"
    )


    # ========================================================
    # TRADING STATUS
    # ========================================================

    state["trading"] = not DRY_RUN

    if DRY_RUN:

        log(
            "TRADING: OFF - DRY RUN"
        )

    else:

        log(
            "TRADING: ON - LIVE"
        )

        log(
            "VIKTIG: Ekte ordrelogikk "
            "er fortsatt deaktivert."
        )


    # ========================================================
    # API-NØKLER
    # ========================================================

    if not API_KEY:

        log(
            "KRITISK: FIRI_API_KEY mangler."
        )

        state["status"] = "ERROR"

        return

    if not CLIENT_ID:

        log(
            "KRITISK: FIRI_CLIENT_ID mangler."
        )

        state["status"] = "ERROR"

        return

    if not SECRET_KEY:

        log(
            "KRITISK: FIRI_SECRET_KEY mangler."
        )

        state["status"] = "ERROR"

        return


    # ========================================================
    # DASHBOARD
    # ========================================================

    dashboard_thread = threading.Thread(
        target=start_dashboard,
        daemon=True
    )

    dashboard_thread.start()

    await asyncio.sleep(2)


    # ========================================================
    # FIRI
    # ========================================================

    try:

        async with FiriAPI(
            api_key=API_KEY,
            secret_key=SECRET_KEY,
            client_id=CLIENT_ID,
        ) as client:

            log(
                "Firi API tilkoblet."
            )


            # =================================================
            # API TIME
            # =================================================

            try:

                api_time = (
                    await client.time()
                )

                debug(
                    f"API time OK: "
                    f"{api_time}"
                )

            except Exception as e:

                log_error(
                    "API TIME",
                    e
                )


            # =================================================
            # VARIABLER
            # =================================================

            price_history = []

            last_history_update = 0

            last_balance_update = 0

            nok = 0.0

            eth = 0.0

            last_price = 0.0


            # =================================================
            # HOVEDLOOP
            # =================================================

            while True:

                loop_start = (
                    time.time()
                )


                # =================================================
                # TICKER
                # =================================================

                try:

                    ticker = (
                        await client
                        .markets_market_ticker(
                            MARKET
                        )
                    )

                    bid = float(
                        ticker["bid"]
                    )

                    ask = float(
                        ticker["ask"]
                    )

                    spread = float(
                        ticker["spread"]
                    )

                    price = (
                        bid + ask
                    ) / 2.0

                    spread_percent = (
                        spread / price
                        if price > 0
                        else 0.0
                    )

                    last_price = price

                    last_ticker_ok = True

                    log(
                        f"ETH "
                        f"{price:,.2f} kr | "
                        f"Spread "
                        f"{spread_percent * 100:.2f}%"
                    )

                except Exception as e:

                    last_ticker_ok = False

                    log_error(
                        "TICKER",
                        e
                    )

                    await asyncio.sleep(
                        TICKER_INTERVAL
                    )

                    continue


                # =================================================
                # HISTORY
                # =================================================

                now = time.time()

                if (
                    now
                    - last_history_update
                    >= HISTORY_INTERVAL
                ):

                    try:

                        debug(
                            "Henter markedshistorikk..."
                        )

                        history = (
                            await client
                            .markets_market_history(
                                MARKET,
                                count=HISTORY_COUNT
                            )
                        )

                        debug(
                            f"History type: "
                            f"{type(history).__name__}"
                        )

                        # Ekstra debug: vis et kort sammendrag av rå history-responsen
                        try:
                            if isinstance(history, dict):
                                debug(
                                    f"History dict keys: {list(history.keys())}"
                                )
                                # Vis eksempel på første nøkkelverdi
                                first_key = next(iter(history), None)
                                if first_key is not None:
                                    sample = history[first_key]
                                    debug(
                                        f"Sample for key {first_key}: {type(sample).__name__}"
                                    )

                            elif isinstance(history, list):
                                debug(
                                    f"History list length: {len(history)}"
                                )
                                try:
                                    debug(
                                        f"History first items: {history[:5]}"
                                    )
                                except Exception:
                                    debug("History sample: (could not stringify items)")

                            else:
                                debug(
                                    f"History raw repr (truncated): {str(history)[:1000]}"
                                )

                        except Exception as e:
                            debug(f"Could not introspect history: {e}")

                        price_history = (
                            build_minute_prices(
                                history
                            )
                        )

                        # Hvis Firi ikke ga brukbare priser, prøv fallback-kilder basert på konfigurasjon
                        if not price_history:

                            debug(
                                "Firi history tom — prøver konfigurerte fallback-kilder."
                            )

                            try:

                                async def fetch_coingecko_history(vs_currency: str = "nok", days: int = 2):

                                    url = (
                                        f"https://api.coingecko.com/api/v3/coins/ethereum/market_chart?vs_currency={vs_currency}&days={days}"
                                    )

                                    async with aiohttp.ClientSession() as session:

                                        async with session.get(url, timeout=10) as resp:

                                            if resp.status != 200:

                                                debug(
                                                    f"CoinGecko returned status {resp.status}"
                                                )

                                                return []

                                            data = await resp.json()

                                    prices = data.get("prices", [])

                                    if not prices:

                                        return []

                                    buckets = {}

                                    for ts_ms, price in prices:

                                        ts = ts_ms / 1000.0

                                        minute = int(ts // 60)

                                        buckets[minute] = float(price)

                                    result = [
                                        buckets[k]
                                        for k in sorted(buckets.keys())
                                    ]

                                    return result[-MAX_PRICE_HISTORY:]

                                # Bestem valuta for CoinGecko basert på MARKET (f.eks. ETHNOK -> nok)
                                vs_currency = (
                                    "nok"
                                    if (
                                        "NOK" in MARKET.upper()
                                    )
                                    else "usd"
                                )

                                if "coingecko" in FALLBACK_SOURCES:

                                    cg_prices = await fetch_coingecko_history(vs_currency, FALLBACK_DAYS)

                                    if cg_prices:

                                        price_history = cg_prices

                                        debug(
                                            f"CoinGecko fallback OK: {len(price_history)} priser."
                                        )

                                    else:

                                        debug(
                                            "CoinGecko fallback ga ingen priser."
                                        )

                            except Exception as e:

                                debug(
                                    f"Fallback feil: {e}"
                                )

                        if len(
                            price_history
                        ) >= 60:

                            last_history_ok = True

                            log(
                                f"History OK: "
                                f"{len(price_history)} "
                                f"minuttpriser."
                            )

                        else:

                            last_history_ok = False

                            log(
                                f"History: "
                                f"bare "
                                f"{len(price_history)} "
                                f"brukbare priser."
                            )

                        last_history_update = now

                    except Exception as e:

                        last_history_ok = False

                        log_error(
                            "HISTORY",
                            e
                        )


                # =================================================
                # BALANSER
                # =================================================

                now = time.time()

                if (
                    now
                    - last_balance_update
                    >= BALANCE_INTERVAL
                ):

                    try:

                        balances = (
                            await client.balances()
                        )

                        nok = find_balance(
                            balances,
                            "NOK"
                        )

                        eth = find_balance(
                            balances,
                            "ETH"
                        )

                        last_balance_ok = True

                        log(
                            f"Saldo: "
                            f"{nok:,.2f} NOK | "
                            f"{eth:.8f} ETH"
                        )

                        last_balance_update = now

                    except Exception as e:

                        last_balance_ok = False

                        log_error(
                            "BALANCE",
                            e
                        )


                # =================================================
                # STRATEGI
                # =================================================

                try:

                    signal = analyze_market(
                        price_history,
                        spread_percent
                    )

                    last_strategy_ok = True

                except Exception as e:

                    last_strategy_ok = False

                    log_error(
                        "STRATEGY",
                        e
                    )

                    continue


                # =================================================
                # PORTEFØLJE
                # =================================================

                eth_value = (
                    eth * price
                )

                portfolio_value = (
                    nok
                    + eth_value
                )

                profit_nok = (
                    portfolio_value
                    - STARTING_CAPITAL_NOK
                )

                profit_percent = (
                    (
                        profit_nok
                        / STARTING_CAPITAL_NOK
                    )
                    * 100.0
                )


                # =================================================
                # DASHBOARD DATA
                # =================================================

                state["price"] = price

                state["bid"] = bid

                state["ask"] = ask

                state["spread"] = spread

                state["nok"] = nok

                state["eth"] = eth

                state["eth_value"] = (
                    eth_value
                )

                state["portfolio_value"] = (
                    portfolio_value
                )

                state["profit_nok"] = (
                    profit_nok
                )

                state["profit_percent"] = (
                    profit_percent
                )

                state["signal"] = (
                    signal.action
                )

                state["reason"] = (
                    signal.reason
                )

                state["rsi"] = (
                    signal.rsi
                )

                state["ema_fast"] = (
                    signal.ema_fast
                )

                state["ema_slow"] = (
                    signal.ema_slow
                )

                state["momentum"] = (
                    signal.momentum
                )

                state["volatility"] = (
                    signal.volatility
                )

                state[
                    "expected_profit_percent"
                ] = (
                    signal.expected_profit_percent
                )

                state[
                    "estimated_cost_percent"
                ] = (
                    signal.estimated_cost_percent
                )

                state[
                    "net_expected_percent"
                ] = (
                    signal.net_expected_percent
                )

                state["trend"] = (
                    signal.trend
                )

                state["buy_score"] = (
                    signal.buy_score
                )

                state["sell_score"] = (
                    signal.sell_score
                )

                state["history_points"] = (
                    len(price_history)
                )

                state["last_ticker_ok"] = (
                    last_ticker_ok
                )

                state["last_balance_ok"] = (
                    last_balance_ok
                )

                state["last_history_ok"] = (
                    last_history_ok
                )

                state["last_strategy_ok"] = (
                    last_strategy_ok
                )

                state["error_count"] = (
                    error_count
                )

                state["last_error"] = (
                    last_error
                )

                state["last_update"] = (
                    datetime.now()
                    .strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )

                state["status"] = (
                    "RUNNING"
                )


                # =================================================
                # STRATEGI-LOGG
                # =================================================

                log(
                    f"INDIKATORER | "
                    f"RSI {signal.rsi:.1f} | "
                    f"EMA20 {signal.ema_fast:,.0f} | "
                    f"EMA50 {signal.ema_slow:,.0f} | "
                    f"MOM {signal.momentum:+.2f}% | "
                    f"TREND {signal.trend}"
                )


                log(
                    f"SCORE | "
                    f"BUY {signal.buy_score} | "
                    f"SELL {signal.sell_score} | "
                    f"Signal {signal.action}"
                )


                log(
                    f"KOSTNAD | "
                    f"{signal.estimated_cost_percent:.2f}% | "
                    f"Potensiell netto "
                    f"{signal.net_expected_percent:+.2f}%"
                )


                # =================================================
                # HANDELSFILTER
                # =================================================

                if (
                    spread_percent
                    > MAX_SPREAD_PERCENT
                ):

                    log(
                        "HANDELSSTOPP: "
                        "Spread for høy."
                    )

                elif signal.action == "HOLD":

                    debug(
                        f"HOLD: "
                        f"{signal.reason}"
                    )

                elif DRY_RUN:

                    log(
                        f"DRY RUN: "
                        f"Signal "
                        f"{signal.action}"
                    )

                else:

                    log(
                        "LIVE MODE: "
                        "Ordreutførelse "
                        "ikke aktivert."
                    )


                # =================================================
                # VENT
                # =================================================

                elapsed = (
                    time.time()
                    - loop_start
                )

                sleep_time = max(
                    0.5,
                    TICKER_INTERVAL
                    - elapsed
                )

                await asyncio.sleep(
                    sleep_time
                )


    except Exception as e:

        log_error(
            "FIRI CONNECTION",
            e
        )

        state["status"] = (
            "ERROR"
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        log(
            "Bot stoppet."
        )

    except Exception as e:

        log_error(
            "MAIN",
            e
        )