import asyncio
import os
import threading
from datetime import datetime

import uvicorn
from dotenv import load_dotenv
from firipy import FiriAPI

from dashboard import app, state, add_log
from strategy import get_signal


# --------------------------------------------------
# INNSTILLINGER
# --------------------------------------------------

load_dotenv()

API_KEY = os.getenv("FIRI_API_KEY")
CLIENT_ID = os.getenv("FIRI_CLIENT_ID")
SECRET_KEY = os.getenv("FIRI_SECRET_KEY")

MARKET = os.getenv("MARKET", "ETHNOK")

DRY_RUN = os.getenv(
    "DRY_RUN",
    "true"
).lower() == "true"

MAX_TRADE_NOK = float(
    os.getenv(
        "MAX_TRADE_NOK",
        "200"
    )
)

STARTING_CAPITAL_NOK = 1800.0

MAX_SPREAD_NOK = 100


# --------------------------------------------------
# LOGGING
# --------------------------------------------------

def log(message):

    timestamp = datetime.now().strftime("%H:%M:%S")

    text = f"[{timestamp}] {message}"

    print(text)

    add_log(text)


# --------------------------------------------------
# FINN SALDO
# --------------------------------------------------

def find_balance(balances, currency):

    if isinstance(balances, dict):

        if currency in balances:

            value = balances[currency]

            if isinstance(value, dict):

                for key in [
                    "available",
                    "balance",
                    "amount",
                    "free"
                ]:

                    if key in value:

                        try:
                            return float(value[key])
                        except (
                            ValueError,
                            TypeError
                        ):
                            pass

            try:
                return float(value)

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

    elif isinstance(balances, list):

        for item in balances:

            if not isinstance(item, dict):
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


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

def start_dashboard():

    log(
        "Starter dashboard på port 8080..."
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
        log_level="info",
    )


# --------------------------------------------------
# HOVEDPROGRAM
# --------------------------------------------------

async def main():

    log(
        "===================================="
    )

    log(
        "FIRI ETH BOT STARTER"
    )

    log(
        "===================================="
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


    # --------------------------------------------------
    # TRADING STATUS
    # --------------------------------------------------

    state["trading"] = not DRY_RUN

    if DRY_RUN:

        log(
            "TRADING: OFF - DRY RUN"
        )

    else:

        log(
            "TRADING: ON - LIVE TRADING"
        )


    # --------------------------------------------------
    # SJEKK API-NØKLER
    # --------------------------------------------------

    if not API_KEY:

        log(
            "FEIL: FIRI_API_KEY mangler."
        )

        return

    if not CLIENT_ID:

        log(
            "FEIL: FIRI_CLIENT_ID mangler."
        )

        return

    if not SECRET_KEY:

        log(
            "FEIL: FIRI_SECRET_KEY mangler."
        )

        return


    # --------------------------------------------------
    # START DASHBOARD
    # --------------------------------------------------

    dashboard_thread = threading.Thread(
        target=start_dashboard,
        daemon=True
    )

    dashboard_thread.start()

    await asyncio.sleep(2)


    log(
        "Kobler til Firi API..."
    )


    # --------------------------------------------------
    # FIRI
    # --------------------------------------------------

    try:

        async with FiriAPI(
            api_key=API_KEY,
            secret_key=SECRET_KEY,
            client_id=CLIENT_ID,
        ) as client:

            log(
                "Firi API tilkoblet."
            )


            # --------------------------------------------------
            # TEST API
            # --------------------------------------------------

            try:

                api_time = await client.time()

                log(
                    f"API time OK: {api_time}"
                )

            except Exception as e:

                log(
                    f"Kunne ikke hente API time: {e}"
                )


            # --------------------------------------------------
            # HOVEDLOOP
            # --------------------------------------------------

            while True:

                try:

                    # ------------------------------------------
                    # HENT TICKER
                    # ------------------------------------------

                    ticker = (
                        await client
                        .markets_market_ticker(
                            MARKET
                        )
                    )

                    log(
                        f"Ticker: {ticker}"
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


                    # Midtpris
                    price = (
                        bid + ask
                    ) / 2


                    log(
                        f"Bid: {bid:,.2f} kr | "
                        f"Ask: {ask:,.2f} kr | "
                        f"Mid: {price:,.2f} kr | "
                        f"Spread: {spread:,.2f} kr"
                    )


                    # ------------------------------------------
                    # HENT SALDO
                    # ------------------------------------------

                    balances = (
                        await client.balances()
                    )

                    log(
                        f"Balances: {balances}"
                    )


                    nok = find_balance(
                        balances,
                        "NOK"
                    )

                    eth = find_balance(
                        balances,
                        "ETH"
                    )


                    log(
                        f"NOK saldo: "
                        f"{nok:,.2f} kr"
                    )

                    log(
                        f"ETH saldo: "
                        f"{eth:.8f} ETH"
                    )


                    # ------------------------------------------
                    # STRATEGI
                    # ------------------------------------------

                    signal = get_signal(
                        price
                    )


                    log(
                        f"Signal: "
                        f"{signal.action} - "
                        f"{signal.reason}"
                    )


                    # ------------------------------------------
                    # PORTEFØLJE
                    # ------------------------------------------

                    eth_value = (
                        eth * price
                    )

                    portfolio_value = (
                        nok + eth_value
                    )

                    profit_nok = (
                        portfolio_value
                        - STARTING_CAPITAL_NOK
                    )

                    profit_percent = (
                        (
                            profit_nok
                            / STARTING_CAPITAL_NOK
                        ) * 100
                        if STARTING_CAPITAL_NOK > 0
                        else 0
                    )


                    # ------------------------------------------
                    # OPPDATER DASHBOARD
                    # ------------------------------------------

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

                    state["last_update"] = (
                        datetime.now()
                        .strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    )

                    state["status"] = (
                        "RUNNING"
                    )


                    # ------------------------------------------
                    # SPREAD-SJEKK
                    # ------------------------------------------

                    if spread > MAX_SPREAD_NOK:

                        log(
                            f"ADVARSEL: Spread er "
                            f"{spread:,.2f} kr."
                        )

                        log(
                            "Ingen handel tillatt "
                            "på grunn av høy spread."
                        )


                    # ------------------------------------------
                    # DRY RUN
                    # ------------------------------------------

                    elif DRY_RUN:

                        log(
                            "DRY_RUN=true: "
                            "Ingen ordre blir sendt."
                        )


                    # ------------------------------------------
                    # LIVE
                    # ------------------------------------------

                    else:

                        log(
                            "LIVE MODE: "
                            "Handelslogikk er "
                            "ikke aktivert ennå."
                        )


                    # ------------------------------------------
                    # VENT
                    # ------------------------------------------

                    await asyncio.sleep(
                        30
                    )


                except Exception as e:

                    log(
                        f"FEIL: "
                        f"{type(e).__name__}: {e}"
                    )

                    state["status"] = (
                        "ERROR"
                    )

                    await asyncio.sleep(
                        30
                    )


    except Exception as e:

        log(
            f"KRITISK FEIL VED FIRI API: "
            f"{type(e).__name__}: {e}"
        )

        state["status"] = (
            "ERROR"
        )


# --------------------------------------------------
# START
# --------------------------------------------------

if __name__ == "__main__":

    asyncio.run(
        main()
    )