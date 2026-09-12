import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv
from firipy import FiriAPI

from strategy import get_signal
import dashboard


load_dotenv()


API_KEY = os.getenv("FIRI_API_KEY")
CLIENT_ID = os.getenv("FIRI_CLIENT_ID")
SECRET_KEY = os.getenv("FIRI_SECRET_KEY")

MARKET = os.getenv("MARKET", "ETHNOK")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
MAX_TRADE_NOK = float(os.getenv("MAX_TRADE_NOK", "200"))


def log(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")

    line = f"[{timestamp}] {message}"

    print(line, flush=True)

    dashboard.add_log(line)


def find_balance(balances, currency):
    """
    Firi kan returnere saldoene som en liste.
    Denne funksjonen forsøker å finne riktig valuta.
    """

    if isinstance(balances, dict):

        # Enkel variant:
        if currency in balances:
            value = balances[currency]

            if isinstance(value, dict):
                return float(
                    value.get("available", value.get("balance", 0))
                )

            return float(value)

    if isinstance(balances, list):

        for item in balances:

            if not isinstance(item, dict):
                continue

            symbol = (
                item.get("symbol")
                or item.get("currency")
                or item.get("asset")
            )

            if symbol == currency:

                return float(
                    item.get("available")
                    or item.get("balance")
                    or item.get("amount")
                    or 0
                )

    return 0.0


async def main():

    if not API_KEY:
        log("FEIL: FIRI_API_KEY mangler.")
        return

    dashboard.state["status"] = "ONLINE"

    log("===================================")
    log("Firi ETH-bot starter")
    log(f"Marked: {MARKET}")
    log(f"Dry run: {DRY_RUN}")
    log(f"Maks handel: {MAX_TRADE_NOK:.2f} NOK")
    log("===================================")

    client_args = {
        "api_key": API_KEY,
        "rate_limit": 1,
    }

    if CLIENT_ID and SECRET_KEY:
        client_args["client_id"] = CLIENT_ID
        client_args["secret_key"] = SECRET_KEY

    async with FiriAPI(**client_args) as client:

        while True:

            try:

                ticker = await client.markets_market_ticker(MARKET)
                balances = await client.balances()

                log(f"Ticker: {ticker}")

                # Firi ticker returneres normalt som et objekt med "last".
                price = float(ticker["last"])

                nok_balance = find_balance(
                    balances,
                    "NOK"
                )

                eth_balance = find_balance(
                    balances,
                    "ETH"
                )

                signal = get_signal(price)

                dashboard.state["price"] = price
                dashboard.state["nok"] = nok_balance
                dashboard.state["eth"] = eth_balance
                dashboard.state["signal"] = signal.action
                dashboard.state["reason"] = signal.reason
                dashboard.state["last_update"] = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                log(f"ETH/NOK: {price:,.2f}")
                log(f"NOK saldo: {nok_balance:,.2f}")
                log(f"ETH saldo: {eth_balance:.8f}")
                log(f"Signal: {signal.action}")

                if signal.action != "HOLD":

                    log(
                        f"SIGNAL: {signal.action} - "
                        f"{signal.reason}"
                    )

                    if DRY_RUN:

                        log(
                            "DRY RUN: Ingen ordre blir sendt."
                        )

                    else:

                        log(
                            "LIVE TRADING ER IKKE IMPLEMENTERT ENNÅ."
                        )

                await asyncio.sleep(30)

            except Exception as error:

                dashboard.state["status"] = "ERROR"

                log(
                    f"FEIL: {type(error).__name__}: {error}"
                )

                await asyncio.sleep(30)


if __name__ == "__main__":

    import threading
    import uvicorn

    def start_dashboard():
        uvicorn.run(
            "dashboard:app",
            host="0.0.0.0",
            port=int(os.getenv("PORT", "8000")),
        )

    web_thread = threading.Thread(
        target=start_dashboard,
        daemon=True,
    )

    web_thread.start()

    asyncio.run(main())