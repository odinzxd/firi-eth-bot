import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from gemini_client import GeminiClient
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

# Safety: this bot is intended to stay in dry-run mode unless explicitly changed.
os.environ["DRY_RUN"] = "true"
DRY_RUN = True
MARKET = os.getenv("MARKET", "ETHNOK")
MAX_TRADE_NOK = float(os.getenv("MAX_TRADE_NOK", "200"))
TEST_BUY_NOK = float(os.getenv("TEST_BUY_NOK", str(MAX_TRADE_NOK)))
TEST_SELL_NOK = float(os.getenv("TEST_SELL_NOK", str(MAX_TRADE_NOK)))
TEST_TRADE_PASSWORD = os.getenv("TEST_TRADE_PASSWORD", "")
TEST_TRADING_ENABLED = os.getenv("TEST_TRADING_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
FIRI_TRADE_FEE_PERCENT = 0.10
MAX_DAILY_TRADES = 20
COOLDOWN_SECONDS = 600
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


def log_sell_decision(position, current_bid, pnl_percent, ema9, ema21, rsi, sell_reason):
    log("SELL DECISION")
    log(f"ENTRY PRICE {position['entry_price']:.2f}")
    log(f"CURRENT BID {current_bid:.2f}")
    log(f"P/L % {pnl_percent:+.2f}%")
    log(f"EMA9 {ema9:.2f}")
    log(f"EMA21 {ema21:.2f}")
    log(f"RSI {rsi:.1f}")
    log(f"SELL REASON {sell_reason}")

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
    pending_buy_order = None
    pending_sell_order = None
    gemini_client = GeminiClient()

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
                state["last_error"] = f"BINANCE: {type(exc).__name__}: {exc}"
                log(state["last_error"])
                await asyncio.sleep(LOOP_SECONDS)
                continue

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
                state["last_error"] = f"FIRI: {type(exc).__name__}: {exc}"
                log(state["last_error"])
                await asyncio.sleep(LOOP_SECONDS)
                continue

            if pending_buy_order is not None and not position["position"]:
                current_eth = balances["ETH"]
                if current_eth >= pending_buy_order["previous_eth"] + pending_buy_order["amount"] * 0.95:
                    position = {
                        "position": True,
                        "entry_price": pending_buy_order["entry_price"],
                        "amount": pending_buy_order["amount"],
                        "entry_time": time.time(),
                    }
                    save_position(position)
                    pending_buy_order = None
                    state["pending_buy_order"] = None
                    log(
                        f"BUY CONFIRMED: {pending_buy_order['amount']:.8f} ETH @ {pending_buy_order['entry_price']:.2f}"
                    )
                    if not DRY_RUN:
                        daily["trades"] += 1
                        daily["last_trade"] = time.time()
                elif time.time() - pending_buy_order["submitted_at"] > 120:
                    log("BUY order not confirmed within timeout; leaving position inactive.")
                    pending_buy_order = None
                    state["pending_buy_order"] = None

            if pending_sell_order is not None and position["position"]:
                current_eth = balances["ETH"]
                if current_eth <= pending_sell_order["previous_eth"] - pending_sell_order["amount"] * 0.95:
                    clear_position()
                    position = {
                        "position": False,
                        "entry_price": 0.0,
                        "amount": 0.0,
                        "entry_time": 0.0,
                    }
                    pending_sell_order = None
                    state["pending_sell_order"] = None
                    log(
                        f"SELL CONFIRMED: ETH reduced by {pending_sell_order['amount']:.8f}"
                    )
                    if not DRY_RUN:
                        daily["trades"] += 1
                        daily["last_trade"] = time.time()
                elif time.time() - pending_sell_order["submitted_at"] > 120:
                    log("SELL order not confirmed within timeout; keeping position open.")
                    pending_sell_order = None
                    state["pending_sell_order"] = None

            trade_costs = calculate_trade_costs(
                ask_price=state["ask"],
                bid_price=state["bid"],
            )
            state["estimated_round_trip_cost"] = trade_costs["round_trip_cost_percent"]
            state["break_even_percent"] = trade_costs["break_even_percent"]
            state["take_profit_percent"] = trade_costs["take_profit_percent"]
            state["stop_loss_percent"] = trade_costs["stop_loss_percent"]

            if position["position"] and position["entry_price"] > 0:
                state["take_profit"] = position["entry_price"] * (
                    1.0 + get_take_profit_percent(trade_costs["round_trip_cost_percent"]) / 100.0
                )
                state["stop_loss"] = position["entry_price"] * (
                    1.0 - STOP_LOSS_PERCENT / 100.0
                )
                state["pnl_percent"] = (
                    (state["bid"] - position["entry_price"]) / position["entry_price"]
                ) * 100.0
            else:
                state["take_profit"] = 0.0
                state["stop_loss"] = 0.0
                state["pnl_percent"] = 0.0

            state["position"] = position["position"]
            state["entry_price"] = position["entry_price"]
            state["daily_trades"] = daily["trades"]

            signal = None
            bearish_trend_exit_streak = int(state.get("bearish_trend_exit_streak", 0))
            previous_ema9 = state.get("ema9")
            previous_ema21 = state.get("ema21")
            if previous_ema9 is not None and previous_ema21 is not None:
                if previous_ema9 < previous_ema21:
                    bearish_trend_exit_streak += 1
                else:
                    bearish_trend_exit_streak = 0
            else:
                bearish_trend_exit_streak = 0

            try:
                signal = analyze_market(
                    prices,
                    current_position=position["position"],
                    entry_price=position["entry_price"],
                    current_price=state["bid"],
                    bearish_trend_exit_streak=bearish_trend_exit_streak,
                )
            except Exception as exc:
                state["strategy_ok"] = False
                state["last_error"] = f"STRATEGY: {type(exc).__name__}: {exc}"
                log(state["last_error"])
                await asyncio.sleep(LOOP_SECONDS)
                continue

            if signal.action == "SELL" and position["position"]:
                pnl_percent = ((state["bid"] - position["entry_price"]) / position["entry_price"]) * 100.0
                log_sell_decision(
                    position,
                    state["bid"],
                    pnl_percent,
                    signal.ema9 or 0.0,
                    signal.ema21 or 0.0,
                    signal.rsi14 if signal.rsi14 is not None else 0.0,
                    signal.reason,
                )

            state["strategy_ok"] = True
            state["signal"] = signal.action
            state["reason"] = signal.reason
            state["ema9"] = signal.ema9
            state["ema21"] = signal.ema21
            state["rsi14"] = signal.rsi14
            state["trend"] = signal.trend
            state["bearish_trend_exit_streak"] = bearish_trend_exit_streak
            state["sell_reason"] = signal.reason if signal.action == "SELL" else ""

            market_payload = {
                "firi_bid": state["bid"],
                "firi_ask": state["ask"],
                "firi_spread": state["spread_percent"],
                "firi_price": state["price"],
                "binance_price": state["binance_price"],
                "ema9": signal.ema9,
                "ema21": signal.ema21,
                "rsi14": signal.rsi14,
                "change_5m": ((state["binance_price"] - prices[-6]) / prices[-6]) * 100.0 if len(prices) >= 6 else 0.0,
                "change_15m": ((state["binance_price"] - prices[-15]) / prices[-15]) * 100.0 if len(prices) >= 15 else 0.0,
                "change_30m": ((state["binance_price"] - prices[-30]) / prices[-30]) * 100.0 if len(prices) >= 30 else 0.0,
                "volume": float(candles[-1].get("volume", 0.0)) if candles else 0.0,
                "nok_balance": state["nok"],
                "eth_balance": state["eth"],
                "active_position": position["position"],
                "entry_price": position["entry_price"],
                "position_age_seconds": (time.time() - position["entry_time"]) if position["position"] and position["entry_time"] else 0.0,
                "estimated_round_trip_cost": trade_costs["round_trip_cost_percent"],
                "take_profit_percent": trade_costs["take_profit_percent"],
                "stop_loss_percent": STOP_LOSS_PERCENT,
                "candles": candles[-50:],
            }

            gemini_decision = gemini_client.get_decision(market_payload)
            state["claude_signal"] = gemini_decision["action"]
            state["claude_confidence"] = gemini_decision["confidence"]
            state["claude_reason"] = gemini_decision["reason"]
            state["market_condition"] = gemini_decision["market_condition"]
            state["gemini_signal"] = gemini_decision["action"]
            state["gemini_confidence"] = gemini_decision["confidence"]
            state["gemini_reason"] = gemini_decision["reason"]

            log("GEMINI ANALYSIS")
            log(f"PRICE: {state['binance_price']:.2f}")
            log(f"EMA9: {signal.ema9 if signal.ema9 is not None else 0.0:.2f}")
            log(f"EMA21: {signal.ema21 if signal.ema21 is not None else 0.0:.2f}")
            log(f"RSI: {signal.rsi14 if signal.rsi14 is not None else 0.0:.1f}")
            log(f"SPREAD: {state['spread_percent']:.2f}%")
            log(f"POSITION: {'ACTIVE' if position['position'] else 'NONE'}")
            log(f"GEMINI ACTION: {gemini_decision['action']}")
            log(f"CONFIDENCE: {gemini_decision['confidence']:.2f}")
            log(f"REASON: {gemini_decision['reason']}")

            cooldown_active = time.time() - daily["last_trade"] < COOLDOWN_SECONDS
            max_trades_reached = daily["trades"] >= MAX_DAILY_TRADES
            action = gemini_decision["action"]
            state["trade_status"] = "READY"
            state["trade_reason"] = ""

            if gemini_decision["action"] == "HOLD":
                action = "HOLD"

            python_reason = ""
            if cooldown_active:
                action = "HOLD"
                python_reason = "Cooldown active"
            if max_trades_reached:
                action = "HOLD"
                python_reason = "Daily trade limit reached"
            if action == "BUY" and position["position"]:
                action = "HOLD"
                python_reason = "Bot already has an active position"
            if action == "SELL" and not position["position"]:
                action = "HOLD"
                python_reason = "No active bot position to sell"
            if action == "BUY" and trade_costs["round_trip_cost_percent"] >= 100.0:
                action = "HOLD"
                python_reason = f"Estimated round-trip cost too high: {trade_costs['round_trip_cost_percent']:.2f}%"
            if action == "BUY" and state["nok"] < MAX_TRADE_NOK:
                action = "HOLD"
                python_reason = f"Insufficient NOK balance: {state['nok']:.2f} < {MAX_TRADE_NOK:.2f}"
            if action == "SELL" and not position["position"]:
                action = "HOLD"
                python_reason = "No active bot position to sell"

            if action == "HOLD" and python_reason:
                state["trade_status"] = "BLOCKED"
                state["trade_reason"] = python_reason
                state["reason"] = python_reason
                log("PYTHON RISK CHECK: BLOCKED")
                log(f"REASON: {python_reason}")
            elif action in {"BUY", "SELL"}:
                state["trade_status"] = "READY"
                state["trade_reason"] = ""
                state["reason"] = gemini_decision["reason"]
                log("PYTHON RISK CHECK: APPROVED")
            else:
                state["trade_status"] = "READY"
                state["trade_reason"] = ""
                state["reason"] = "HOLD"

            if action == "BUY" and not position["position"] and not pending_buy_order:
                trade_nok = min(MAX_TRADE_NOK, state["nok"])
                if trade_nok <= 0:
                    state["trade_status"] = "BLOCKED"
                    state["trade_reason"] = "Trade amount is zero or negative"
                    state["reason"] = state["trade_reason"]
                    action = "HOLD"
                else:
                    price = state["ask"]
                    amount = trade_nok / price
                    log_buy_signal(signal, trade_costs, "DRY RUN")
                    if DRY_RUN:
                        log(f"DRY RUN BUY: {trade_nok:.2f} NOK | {amount:.8f} ETH @ {price:.2f} | {gemini_decision['reason']}")
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
                        state["trade_status"] = "DRY RUN"
                        daily["trades"] += 1
                        daily["last_trade"] = time.time()
                        log("ORDER: BUY")
                        log(f"AMOUNT: {amount:.8f}")
                        log(f"PRICE: {price:.2f}")
                        log("STATUS: DRY RUN")
                    else:
                        response = await firi.place_order("buy", price, amount)
                        log(f"ORDER: BUY | AMOUNT: {amount:.8f} | PRICE: {price:.2f} | STATUS: SUBMITTED")
                        log(f"Firi response: {str(response)[:500]}")
                        pending_buy_order = {
                            "submitted_at": time.time(),
                            "amount": amount,
                            "entry_price": price,
                            "previous_eth": balances["ETH"],
                        }
                        state["pending_buy_order"] = pending_buy_order

            elif action == "SELL" and position["position"] and not pending_sell_order:
                price = state["bid"]
                amount = position["amount"]
                if amount <= 0:
                    state["trade_status"] = "BLOCKED"
                    state["trade_reason"] = "Position size is zero"
                    state["reason"] = state["trade_reason"]
                    action = "HOLD"
                else:
                    pnl_percent = ((price - position["entry_price"]) / position["entry_price"]) * 100.0
                    log_sell_decision(position, price, pnl_percent, signal.ema9 or 0.0, signal.ema21 or 0.0, signal.rsi14 if signal.rsi14 is not None else 0.0, gemini_decision["reason"])
                    if DRY_RUN:
                        log(f"DRY RUN SELL: {amount:.8f} ETH @ {price:.2f} | {gemini_decision['reason']}")
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
                        state["trade_status"] = "DRY RUN"
                        daily["trades"] += 1
                        daily["last_trade"] = time.time()
                        log("ORDER: SELL")
                        log(f"AMOUNT: {amount:.8f}")
                        log(f"PRICE: {price:.2f}")
                        log("STATUS: DRY RUN")
                    else:
                        response = await firi.place_order("sell", price, amount)
                        log(f"ORDER: SELL | AMOUNT: {amount:.8f} | PRICE: {price:.2f} | STATUS: SUBMITTED")
                        log(f"Firi response: {str(response)[:500]}")
                        pending_sell_order = {
                            "submitted_at": time.time(),
                            "amount": amount,
                            "entry_price": position["entry_price"],
                            "previous_eth": balances["ETH"],
                        }
                        state["pending_sell_order"] = pending_sell_order

            state["signal"] = action
            state["reason"] = state.get("reason", "")
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

            if cooldown_active:
                action = "HOLD"
                state["trade_status"] = "BLOCKED"
                state["trade_reason"] = "Cooldown active"
                state["reason"] = state["trade_reason"]

            if max_trades_reached:
                action = "HOLD"
                state["trade_status"] = "BLOCKED"
                state["trade_reason"] = "Daily trade limit reached"
                state["reason"] = state["trade_reason"]

            if action == "BUY" and not position["position"] and not pending_buy_order:
                trade_nok = min(TEST_BUY_NOK, MAX_TRADE_NOK)
                if daily["trades"] >= MAX_DAILY_TRADES:
                    state["trade_status"] = "BLOCKED"
                    state["trade_reason"] = "Daily trade limit reached"
                    state["reason"] = state["trade_reason"]
                elif trade_nok <= 0:
                    state["trade_status"] = "BLOCKED"
                    state["trade_reason"] = "Trade amount is zero or negative"
                    state["reason"] = state["trade_reason"]
                elif state["nok"] < trade_nok:
                    state["trade_status"] = "BLOCKED"
                    state["trade_reason"] = f"Insufficient NOK balance: {state['nok']:.2f} < {trade_nok:.2f}"
                    state["reason"] = state["trade_reason"]
                elif trade_costs["round_trip_cost_percent"] >= 100.0:
                    state["trade_status"] = "BLOCKED"
                    state["trade_reason"] = f"Expected cost too high: {trade_costs['round_trip_cost_percent']:.2f}%"
                    state["reason"] = state["trade_reason"]
                else:
                    price = state["ask"]
                    amount = trade_nok / price
                    log_buy_signal(signal, trade_costs, "READY")
                    if DRY_RUN:
                        log(f"DRY RUN BUY | {trade_nok:.2f} NOK | {amount:.8f} ETH @ {price:.2f} | {signal.reason}")
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
                        daily["trades"] += 1
                        daily["last_trade"] = time.time()
                    else:
                        response = await firi.place_order("buy", price, amount)
                        log(f"LIVE BUY sendt | {amount:.8f} ETH @ {price:.2f}")
                        log(f"Firi response: {str(response)[:500]}")
                        log("BUY order accepted by Firi; waiting for actual ETH balance confirmation before activating position.")
                        pending_buy_order = {
                            "submitted_at": time.time(),
                            "amount": amount,
                            "entry_price": price,
                            "previous_eth": balances["ETH"],
                        }
                        state["pending_buy_order"] = pending_buy_order
                        record_trade_event(
                            signal="BUY",
                            event_type="SUBMITTED",
                            price=binance_price,
                            timestamp=candles[-1]["timestamp"],
                            entry_price=price,
                            take_profit=price * (1.0 + trade_costs["take_profit_percent"] / 100.0),
                            stop_loss=price * (1.0 - STOP_LOSS_PERCENT / 100.0),
                        )
                    state["trade_status"] = "READY"
                    state["trade_reason"] = ""

            elif action == "SELL" and position["position"] and not pending_sell_order:
                price = state["bid"]
                amount = position["amount"]

                if amount <= 0:
                    log("SELL blokkert: posisjonsmengde er 0.")
                else:
                    pnl_percent = ((price - position["entry_price"]) / position["entry_price"]) * 100.0
                    log_sell_decision(
                        position,
                        price,
                        pnl_percent,
                        signal.ema9 or 0.0,
                        signal.ema21 or 0.0,
                        signal.rsi14 if signal.rsi14 is not None else 0.0,
                        signal.reason,
                    )
                    if DRY_RUN:
                        log(f"DRY RUN SELL | {amount:.8f} ETH @ {price:.2f} | {signal.reason}")
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
                        response = await firi.place_order("sell", price, amount)
                        log(f"LIVE SELL sendt | {amount:.8f} ETH @ {price:.2f}")
                        log(f"Firi response: {str(response)[:500]}")
                        log("SELL order accepted by Firi; waiting for actual ETH balance reduction before clearing position.")
                        pending_sell_order = {
                            "submitted_at": time.time(),
                            "amount": amount,
                            "entry_price": position["entry_price"],
                            "previous_eth": balances["ETH"],
                        }
                        state["pending_sell_order"] = pending_sell_order
                        record_trade_event(
                            signal="SELL",
                            event_type="SUBMITTED",
                            price=binance_price,
                            timestamp=candles[-1]["timestamp"],
                            entry_price=position["entry_price"],
                            take_profit=state.get("take_profit", 0.0),
                            stop_loss=state.get("stop_loss", 0.0),
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


if __name__ == "__main__":
    asyncio.run(main())
