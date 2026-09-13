"""Indicator calculations and the ETH/NOK day-trading decision rules."""

from dataclasses import dataclass
import math
from typing import List, Optional

EMA_FAST, EMA_SLOW, EMA_TREND = 9, 21, 50
RSI_PERIOD, MOMENTUM_PERIOD, MIN_HISTORY = 14, 5, EMA_TREND + 5
MIN_ENTRY_MOVE_PERCENT = 0.45
BUY_FEE_PERCENT, SELL_FEE_PERCENT, PROFIT_SAFETY_MARGIN_PERCENT = 0.70, 0.70, 0.15
TAKE_PROFIT_PERCENT, STOP_LOSS_PERCENT = 1.80, 0.90
RSI_BUY_MIN, RSI_BUY_MAX, RSI_SELL = 45.0, 72.0, 38.0
MAX_SPREAD_PERCENT = 0.005


@dataclass
class Signal:
    action: str
    reason: str
    score: int = 0
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    ema_trend: float = 0.0
    momentum: float = 0.0
    volatility: float = 0.0
    rsi: float = 50.0
    estimated_cost_percent: float = 0.0
    required_move_percent: float = 0.0
    trend: str = "UNKNOWN"
    buy_score: int = 0
    sell_score: int = 0


def calculate_ema(prices: List[float], period: int) -> Optional[float]:
    if len(prices) < period:
        return None
    ema = sum(prices[:period]) / period
    multiplier = 2.0 / (period + 1)
    for price in prices[period:]:
        ema += (price - ema) * multiplier
    return ema


def calculate_momentum(prices: List[float], periods: int = MOMENTUM_PERIOD) -> float:
    if len(prices) <= periods or prices[-periods - 1] <= 0:
        return 0.0
    return (prices[-1] / prices[-periods - 1] - 1.0) * 100.0


def calculate_volatility(prices: List[float], periods: int = 20) -> float:
    returns = [((new - old) / old) * 100.0 for old, new in zip(prices[-periods:], prices[-periods + 1:]) if old > 0]
    if len(returns) < 2:
        return 0.0
    average = sum(returns) / len(returns)
    return math.sqrt(sum((value - average) ** 2 for value in returns) / len(returns))


def calculate_rsi(prices: List[float], period: int = RSI_PERIOD) -> float:
    if len(prices) <= period:
        return 50.0
    changes = [prices[index] - prices[index - 1] for index in range(len(prices) - period, len(prices))]
    gain = sum(max(change, 0.0) for change in changes) / period
    loss = sum(max(-change, 0.0) for change in changes) / period
    if loss == 0:
        return 100.0 if gain > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + gain / loss)


def calculate_round_trip_cost_percent(spread_percent: float) -> float:
    return BUY_FEE_PERCENT + SELL_FEE_PERCENT + max(0.0, spread_percent) * 100.0


def analyze_market(prices: List[float], spread_percent: float = 0.0,
                   has_position: bool = False, entry_price: float = 0.0) -> Signal:
    """Return BUY, SELL, or HOLD without placing an order."""
    if len(prices) < MIN_HISTORY:
        return Signal("HOLD", f"Varmer opp historikk: {len(prices)}/{MIN_HISTORY} datapunkter.")

    current = prices[-1]
    ema_fast = calculate_ema(prices, EMA_FAST) or current
    ema_slow = calculate_ema(prices, EMA_SLOW) or current
    ema_trend = calculate_ema(prices, EMA_TREND) or current
    momentum, volatility, rsi = calculate_momentum(prices), calculate_volatility(prices), calculate_rsi(prices)
    cost = calculate_round_trip_cost_percent(spread_percent)
    required_move = max(MIN_ENTRY_MOVE_PERCENT, cost + PROFIT_SAFETY_MARGIN_PERCENT)
    trend = "BULLISH" if current > ema_slow > ema_trend else "BEARISH" if current < ema_slow < ema_trend else "NEUTRAL"
    common = dict(ema_fast=ema_fast, ema_slow=ema_slow, ema_trend=ema_trend, momentum=momentum,
                  volatility=volatility, rsi=rsi, estimated_cost_percent=cost,
                  required_move_percent=required_move, trend=trend)

    if has_position and entry_price > 0:
        pnl = (current / entry_price - 1.0) * 100.0
        exits = [pnl >= TAKE_PROFIT_PERCENT, pnl <= -STOP_LOSS_PERCENT,
                 ema_fast < ema_slow and momentum < 0, rsi <= RSI_SELL and momentum < 0]
        sell_score = sum(exits)
        reasons = [f"Take profit nådd: {pnl:+.2f}%", f"Stop loss nådd: {pnl:+.2f}%",
                   f"Trend-exit: EMA 9 < EMA 21 og momentum {momentum:+.2f}%",
                   f"RSI-exit: RSI {rsi:.1f} og negativt momentum"]
        for triggered, reason in zip(exits, reasons):
            if triggered:
                return Signal("SELL", reason, sell_score=sell_score, **common)
        return Signal("HOLD", f"Posisjon holdes: P/L {pnl:+.2f}%", **common)

    criteria = [ema_fast > ema_slow, current > ema_fast, current > ema_trend,
                momentum >= MIN_ENTRY_MOVE_PERCENT, RSI_BUY_MIN <= rsi <= RSI_BUY_MAX]
    buy_score = sum(criteria)
    if spread_percent > MAX_SPREAD_PERCENT:
        return Signal("HOLD", f"Spread for høy: {spread_percent * 100:.2f}%", buy_score=buy_score, **common)
    if required_move > TAKE_PROFIT_PERCENT:
        return Signal("HOLD", f"Kostnad {cost:.2f}% gjør take-profit utilstrekkelig", buy_score=buy_score, **common)
    if buy_score >= 4 and trend == "BULLISH" and momentum > 0 and rsi < RSI_BUY_MAX:
        return Signal("BUY", f"Score {buy_score}/5 – bullish trend, positivt momentum og RSI innenfor kjøpsområdet.",
                      score=buy_score, buy_score=buy_score, **common)
    return Signal("HOLD", f"BUY score {buy_score}/5 – ikke nok bekreftelse for BUY.", buy_score=buy_score, **common)
