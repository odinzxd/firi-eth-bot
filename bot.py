import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from dashboard import start_dashboard, state, add_log
from firi_client import FiriClient
from market_data import get_binance_candles, get_close_prices, get_latest_binance_price
from strategy import (
    analyze_market,
    TAKE_PROFIT_PERCENT,
    STOP_LOSS_PERCENT,
)


load_dotenv()


DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
MARKET = os.getenv("MARKET", "ETHNOK")
MAX_TRADE_NOK = float(os.getenv("MAX_TRADE_NOK", "200"))
TEST_BUY_NOK = float(os.getenv("TEST_BUY_NOK", str(MAX_TRADE_NOK)))
MAX_DAILY_TRADES = 10
COOLDOWN_SECONDS = 600
LOOP_SECONDS = 30

POSITION_FILE = Path("position.json")


def log(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    text = f"[{timestamp}] {message}"
    print(text, flush=True)
    add_log(text)


def load_position():
    if not POSITION_FILE.exists():
        return {
            "position": False,
            "entry_price": 0.0,
            "amount": 0.0,
            "entry_time": 0.0,
        }

    try:
        data = json.loads(POSITION_FILE.read_text(encoding="utf-8"))
        return {
            "position": bool(data.get("position", False)),
            "entry_price": float(data.get("entry_price", 0.0)),
            "amount": float(data.get("amount", 0.0)),
            "entry_time": float(data.get("entry_time", 0.0)),
        }
    except Exception as exc:
        log(f"POSITION FILE ERROR: {type(exc).__name__}: {exc}")
        return {
            "position": False,
            "entry_price": 0.0,
            "amount": 0.0,
            "entry_time": 0.0,
        }


def save_position(position):
    POSITION_FILE.write_text(
        json.dumps(position, indent=2),
        encoding="utf-8",
    )


def clear_position():
    if POSITION_FILE.exists():
        POSITION_FILE.unlink()


def reset_daily_counter_if_needed(state_data):
    today = datetime.now().date().isoformat()

    if state_data.get("day") != today:
        state_data["day"] = today
        state_data["trades"] = 0


async def main():
    state["dry_run"] = DRY_RUN
    state["max_daily_trades"] = MAX_DAILY_TRADES

    log("======================================")
    log("FIRI SIMPLE ETH DAYTRADING BOT")
    log(f"Market: {MARKET}")
    log(f"DRY_RUN: {DRY_RUN}")
    log("Analyse: Binance ETHUSDT 5m")
    log("Strategi: EMA9 / EMA21 / RSI14")
    log("TP: +1.0% | SL: -0.6%")
    log("======================================")

    daily = {
        "day": datetime.now().date().isoformat(),
        "trades": 0,
        "last_trade": 0.0,
    }

    position = load_position()

    state["position"] = position["position"]
    state["entry_price"] = position["entry_price"]

    firi = FiriClient()

    try:
        await firi.connect()
        state["firi_ok"] = True
        log("Firi API tilkoblet.")
    except Exception as exc:
        state["firi_ok"] = False
        state["status"] = "ERROR"
        state["last_error"] = f"FIRI CONNECT: {type(exc).__name__}: {exc}"
        log(state["last_error"])
        return

    try:
        while True:
            reset_daily_counter_if_needed(daily)

            # -------------------------------
            # Binance market data
            # -------------------------------
            try:
                candles = get_binance_candles()
                prices = get_close_prices(candles)
                binance_price = prices[-1]

                state["binance_price"] = binance_price
                state["market_data_ok"] = True

            except Exception as exc:
                state["market_data_ok"] = False
                state["strategy_ok"] = False
                state["last_error"] = (
                    f"BINANCE: {type(exc).__name__}: {exc}"
                )
                log(state["last_error"])
                await asyncio.sleep(LOOP_SECONDS)
                continue

            # -------------------------------
            # Firi ticker + balance
            # -------------------------------
            try:
                ticker = await firi.get_ticker()

                state["price"] = ticker["price"]
                state["bid"] = ticker["bid"]
                state["ask"] = ticker["ask"]
                state["spread_percent"] = ticker["spread_percent"]

                balances = await firi.get_balances()

                state["nok"] = balances["NOK"]
                state["eth"] = balances["ETH"]
                state["firi_ok"] = True

            except Exception as exc:
                state["firi_ok"] = False
                state["last_error"] = (
                    f"FIRI: {type(exc).__name__}: {exc}"
                )
                log(state["last_error"])
                await asyncio.sleep(LOOP_SECONDS)
                continue

            # -------------------------------
            # Strategy
            # -------------------------------
            try:
                signal = analyze_market(
                    prices,
                    current_position=position["position"],
                    entry_price=position["entry_price"],
                )

                state["strategy_ok"] = True
                state["signal"] = signal.action
                state["reason"] = signal.reason
                state["ema9"] = signal.ema9
                state["ema21"] = signal.ema21
                state["rsi14"] = signal.rsi14
                state["trend"] = signal.trend

            except Exception as exc:
                state["strategy_ok"] = False
                state["last_error"] = (
                    f"STRATEGY: {type(exc).__name__}: {exc}"
                )
                log(state["last_error"])
                await asyncio.sleep(LOOP_SECONDS)
                continue

            # -------------------------------
            # Position targets
            # -------------------------------
            if position["position"] and position["entry_price"] > 0:
                state["take_profit"] = (
                    position["entry_price"]
                    * (1.0 + TAKE_PROFIT_PERCENT / 100.0)
                )
                state["stop_loss"] = (
                    position["entry_price"]
                    * (1.0 - STOP_LOSS_PERCENT / 100.0)
                )
            else:
                state["take_profit"] = 0.0
                state["stop_loss"] = 0.0

            state["position"] = position["position"]
            state["entry_price"] = position["entry_price"]
            state["daily_trades"] = daily["trades"]

            # -------------------------------
            # Safety filters
            # -------------------------------
            spread_too_high = state["spread_percent"] > 0.50
            cooldown_active = (
                time.time() - daily["last_trade"] < COOLDOWN_SECONDS
            )
            max_trades_reached = daily["trades"] >= MAX_DAILY_TRADES

            action = signal.action

            if spread_too_high:
                log(
                    f"HOLD | Firi spread {state['spread_percent']:.2f}% er for høy."
                )
                action = "HOLD"

            if cooldown_active:
                action = "HOLD"

            if max_trades_reached:
                action = "HOLD"

            # -------------------------------
            # BUY
            # -------------------------------
            if action == "BUY" and not position["position"]:
                if daily["trades"] >= MAX_DAILY_TRADES:
                    action = "HOLD"
                else:
                    trade_nok = min(TEST_BUY_NOK, MAX_TRADE_NOK)

                    if trade_nok <= 0:
                        log("BUY blokkert: trade-beløp <= 0.")
                    elif state["nok"] < trade_nok:
                        log(
                            f"BUY blokkert: NOK-saldo {state['nok']:.2f} "
                            f"< {trade_nok:.2f}."
                        )
                    else:
                        price = state["ask"]
                        amount = trade_nok / price

                        if DRY_RUN:
                            log(
                                f"DRY RUN BUY | {trade_nok:.2f} NOK | "
                                f"{amount:.8f} ETH @ {price:.2f} | "
                                f"{signal.reason}"
                            )

                            position = {
                                "position": True,
                                "entry_price": price,
                                "amount": amount,
                                "entry_time": time.time(),
                            }
                            save_position(position)

                        else:
                            try:
                                response = await firi.place_order(
                                    "buy",
                                    price,
                                    amount,
                                )

                                log(
                                    f"LIVE BUY sendt | "
                                    f"{amount:.8f} ETH @ {price:.2f}"
                                )
                                log(f"Firi response: {str(response)[:500]}")

                                position = {
                                    "position": True,
                                    "entry_price": price,
                                    "amount": amount,
                                    "entry_time": time.time(),
                                }
                                save_position(position)

                            except Exception as exc:
                                log(
                                    f"ORDER BUY ERROR: "
                                    f"{type(exc).__name__}: {exc}"
                                )
                                position = load_position()

                        daily["trades"] += 1
                        daily["last_trade"] = time.time()

            # -------------------------------
            # SELL
            # -------------------------------
            elif action == "SELL" and position["position"]:
                price = state["bid"]
                amount = position["amount"]

                if amount <= 0:
                    log("SELL blokkert: posisjonsmengde er 0.")
                elif DRY_RUN:
                    log(
                        f"DRY RUN SELL | {amount:.8f} ETH @ {price:.2f} | "
                        f"{signal.reason}"
                    )

                    clear_position()
                    position = {
                        "position": False,
                        "entry_price": 0.0,
                        "amount": 0.0,
                        "entry_time": 0.0,
                    }

                    daily["trades"] += 1
                    daily["last_trade"] = time.time()

                else:
                    try:
                        response = await firi.place_order(
                            "sell",
                            price,
                            amount,
                        )

                        log(
                            f"LIVE SELL sendt | "
                            f"{amount:.8f} ETH @ {price:.2f}"
                        )
                        log(f"Firi response: {str(response)[:500]}")

                        clear_position()
                        position = {
                            "position": False,
                            "entry_price": 0.0,
                            "amount": 0.0,
                            "entry_time": 0.0,
                        }

                        daily["trades"] += 1
                        daily["last_trade"] = time.time()

                    except Exception as exc:
                        log(
                            f"ORDER SELL ERROR: "
                            f"{type(exc).__name__}: {exc}"
                        )

            state["daily_trades"] = daily["trades"]
            state["last_update"] = datetime.now().strftime("%H:%M:%S")
            state["status"] = "RUNNING"
            state["last_error"] = "Ingen feil"

            log(
                f"MARKET | Firi {state['price']:.2f} NOK | "
                f"Binance {state['binance_price']:.2f} | "
                f"EMA9 {state['ema9'] or 0:.2f} | "
                f"EMA21 {state['ema21'] or 0:.2f} | "
                f"RSI {state['rsi14'] if state['rsi14'] is not None else 0:.1f} | "
                f"SIGNAL {state['signal']}"
            )

            await asyncio.sleep(LOOP_SECONDS)

    finally:
        await firi.close()


if __name__ == "__main__":
    asyncio.run(main())
