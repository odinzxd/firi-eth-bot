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
    get_take_profit_percent,
)


load_dotenv()


DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
MARKET = os.getenv("MARKET", "ETHNOK")
MAX_TRADE_NOK = float(os.getenv("MAX_TRADE_NOK", "200"))
TEST_BUY_NOK = float(os.getenv("TEST_BUY_NOK", str(MAX_TRADE_NOK)))
FIRI_TRADE_FEE_PERCENT = 0.10
MAX_DAILY_TRADES = 20
COOLDOWN_SECONDS = 30
LOOP_SECONDS = 30


def calculate_trade_costs(
    ask_price: float,
    bid_price: float,
    fee_percent: float = FIRI_TRADE_FEE_PERCENT,
):
    if ask_price <= 0 or bid_price <= 0:
        return {
            "spread_percent": 0.0,
            "fee_percent": fee_percent,
            "round_trip_cost_percent": 0.0,
            "break_even_percent": 0.0,
            "take_profit_percent": 0.0,
            "stop_loss_percent": STOP_LOSS_PERCENT,
        }

    spread_percent = ((ask_price - bid_price) / ask_price) * 100.0
    round_trip_fee_percent = fee_percent * 2.0
    round_trip_cost_percent = spread_percent + round_trip_fee_percent
    break_even_percent = round_trip_cost_percent
    take_profit_percent = max(
        round_trip_cost_percent + 0.5,
        TAKE_PROFIT_PERCENT,
    )

    return {
        "spread_percent": spread_percent,
        "fee_percent": fee_percent,
        "round_trip_cost_percent": round_trip_cost_percent,
        "break_even_percent": break_even_percent,
        "take_profit_percent": take_profit_percent,
        "stop_loss_percent": STOP_LOSS_PERCENT,
    }


def log_buy_signal(signal, trade_costs, status: str, reason: str = ""):
    spread = trade_costs["spread_percent"]
    estimated_cost = trade_costs["round_trip_cost_percent"]
    break_even = trade_costs["break_even_percent"]
    take_profit = trade_costs["take_profit_percent"]

    log("BUY SIGNAL")
    log(f"EMA9 > EMA21")
    log(f"RSI {signal.rsi14:.1f}")
    log(f"Spread {spread:.2f}%")
    log(f"Estimated round-trip cost: {estimated_cost:.2f}%")
    log(f"Break-even: {break_even:.2f}%")
    log(f"Take profit: {take_profit:.2f}%")
    log(f"TRADE STATUS: {status}")
    if reason:
        log(f"Reason: {reason}")

POSITION_FILE = Path("position.json")
HISTORY_FILE = Path("trade_history.json")


def load_trade_history():
    if not HISTORY_FILE.exists():
        return []

    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data[-500:]
    except Exception:
        return []

    return []


def save_trade_history(events):
    HISTORY_FILE.write_text(json.dumps(events, indent=2), encoding="utf-8")


def record_trade_event(
    signal: str,
    event_type: str,
    price: float,
    timestamp: float,
    entry_price: float = 0.0,
    take_profit: float = 0.0,
    stop_loss: float = 0.0,
):
    history = load_trade_history()
    event = {
        "timestamp": int(timestamp),
        "price": float(price),
        "signal": str(signal).upper(),
        "event_type": str(event_type).upper(),
        "entry_price": float(entry_price),
        "take_profit": float(take_profit),
        "stop_loss": float(stop_loss),
    }

    last_event = history[-1] if history else None
    if last_event == event:
        return history

    history.append(event)
    history = history[-500:]
    save_trade_history(history)
    state["chart_history"] = history
    return history


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
    state["chart_history"] = load_trade_history()

    log("======================================")
    log("FIRI SIMPLE ETH DAYTRADING BOT")
    log(f"Market: {MARKET}")
    log(f"DRY_RUN: {DRY_RUN}")
    log("Analyse: Binance ETHUSDT 5m")
    log("Strategi: EMA9 / EMA21 / RSI14")
    log("TP: dynamic cost-aware | SL: -0.6%")
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
                candles = get_binance_candles(limit=288)
                prices = get_close_prices(candles)
                binance_price = prices[-1]

                state["chart_candles"] = candles
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

                if signal.action in {"BUY", "SELL"}:
                    signal_timestamp = candles[-1]["timestamp"]
                    record_trade_event(
                        signal=signal.action,
                        event_type="SIGNAL",
                        price=binance_price,
                        timestamp=signal_timestamp,
                        entry_price=state.get("entry_price", 0.0),
                        take_profit=state.get("take_profit", 0.0),
                        stop_loss=state.get("stop_loss", 0.0),
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
            trade_costs = calculate_trade_costs(
                ask_price=state["ask"],
                bid_price=state["bid"],
            )
            state["estimated_round_trip_cost"] = trade_costs[
                "round_trip_cost_percent"
            ]
            state["break_even_percent"] = trade_costs["break_even_percent"]
            state["take_profit_percent"] = trade_costs["take_profit_percent"]
            state["stop_loss_percent"] = trade_costs["stop_loss_percent"]

            if position["position"] and position["entry_price"] > 0:
                target_take_profit = get_take_profit_percent(
                    trade_costs["round_trip_cost_percent"]
                )
                state["take_profit"] = (
                    position["entry_price"]
                    * (1.0 + target_take_profit / 100.0)
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
            cooldown_active = (
                time.time() - daily["last_trade"] < COOLDOWN_SECONDS
            )
            max_trades_reached = daily["trades"] >= MAX_DAILY_TRADES

            action = signal.action
            state["trade_status"] = "READY"
            state["trade_reason"] = ""
            buy_block_reason = ""

            if cooldown_active:
                state["trade_status"] = "BLOCKED"
                state["trade_reason"] = "Cooldown active"
                state["reason"] = state["trade_reason"]
                buy_block_reason = state["trade_reason"]
                action = "HOLD"

            if max_trades_reached:
                state["trade_status"] = "BLOCKED"
                state["trade_reason"] = "Daily trade limit reached"
                state["reason"] = state["trade_reason"]
                buy_block_reason = state["trade_reason"]
                action = "HOLD"

            # -------------------------------
            # BUY
            # -------------------------------
            if action == "BUY" and not position["position"]:
                trade_nok = min(TEST_BUY_NOK, MAX_TRADE_NOK)
                trade_status = "READY"
                reason = ""

                if daily["trades"] >= MAX_DAILY_TRADES:
                    trade_status = "BLOCKED"
                    reason = "Daily trade limit reached"
                    action = "HOLD"
                elif trade_nok <= 0:
                    trade_status = "BLOCKED"
                    reason = "Trade amount is zero or negative"
                    action = "HOLD"
                elif state["nok"] < trade_nok:
                    trade_status = "BLOCKED"
                    reason = (
                        f"Insufficient NOK balance: {state['nok']:.2f} < "
                        f"{trade_nok:.2f}"
                    )
                    action = "HOLD"
                elif trade_costs["round_trip_cost_percent"] >= 100.0:
                    trade_status = "BLOCKED"
                    reason = (
                        f"Expected cost too high: "
                        f"{trade_costs['round_trip_cost_percent']:.2f}%"
                    )
                    action = "HOLD"
                else:
                    price = state["ask"]
                    amount = trade_nok / price
                    state["take_profit_percent"] = trade_costs[
                        "take_profit_percent"
                    ]
                    state["stop_loss_percent"] = STOP_LOSS_PERCENT
                    trade_status = "READY"
                    reason = ""

                    if DRY_RUN:
                        log_buy_signal(signal, trade_costs, "READY")
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
                        record_trade_event(
                            signal="BUY",
                            event_type="EXECUTED",
                            price=binance_price,
                            timestamp=candles[-1]["timestamp"],
                            entry_price=price,
                            take_profit=price * (1.0 + trade_costs["take_profit_percent"] / 100.0),
                            stop_loss=price * (1.0 - STOP_LOSS_PERCENT / 100.0),
                        )

                    else:
                        try:
                            response = await firi.place_order(
                                "buy",
                                price,
                                amount,
                            )

                            log_buy_signal(signal, trade_costs, "READY")
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
                            record_trade_event(
                                signal="BUY",
                                event_type="EXECUTED",
                                price=binance_price,
                                timestamp=candles[-1]["timestamp"],
                                entry_price=price,
                                take_profit=price * (1.0 + trade_costs["take_profit_percent"] / 100.0),
                                stop_loss=price * (1.0 - STOP_LOSS_PERCENT / 100.0),
                            )

                        except Exception as exc:
                            log(
                                f"ORDER BUY ERROR: "
                                f"{type(exc).__name__}: {exc}"
                            )
                            position = load_position()

                    daily["trades"] += 1
                    daily["last_trade"] = time.time()

                if trade_status == "BLOCKED":
                    state["trade_status"] = "BLOCKED"
                    state["trade_reason"] = reason
                    state["reason"] = reason
                    log_buy_signal(signal, trade_costs, "BLOCKED", reason)
                    record_trade_event(
                        signal=signal.action,
                        event_type="BLOCKED",
                        price=binance_price,
                        timestamp=candles[-1]["timestamp"],
                        entry_price=state.get("entry_price", 0.0),
                        take_profit=state.get("take_profit", 0.0),
                        stop_loss=state.get("stop_loss", 0.0),
                    )
                    action = "HOLD"
                else:
                    state["trade_status"] = "READY"
                    state["trade_reason"] = ""

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
                    record_trade_event(
                        signal="SELL",
                        event_type="EXECUTED",
                        price=binance_price,
                        timestamp=candles[-1]["timestamp"],
                        entry_price=position["entry_price"],
                        take_profit=state.get("take_profit", 0.0),
                        stop_loss=state.get("stop_loss", 0.0),
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

                        record_trade_event(
                            signal="SELL",
                            event_type="EXECUTED",
                            price=binance_price,
                            timestamp=candles[-1]["timestamp"],
                            entry_price=position["entry_price"],
                            take_profit=state.get("take_profit", 0.0),
                            stop_loss=state.get("stop_loss", 0.0),
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
