from dataclasses import dataclass
from typing import List, Optional
import math

EMA_FAST = 9
EMA_SLOW = 21
EMA_TREND = 50
MOMENTUM_PERIOD = 5
MIN_HISTORY = EMA_TREND + 5
MIN_ENTRY_MOVE_PERCENT = 0.45

BUY_FEE_PERCENT = 0.70
SELL_FEE_PERCENT = 0.70
PROFIT_SAFETY_MARGIN_PERCENT = 0.15

TAKE_PROFIT_PERCENT = 1.80
STOP_LOSS_PERCENT = 0.90

RSI_BUY_MIN = 45.0
RSI_BUY_MAX = 72.0
RSI_SELL = 38.0


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
        ema = ((price - ema) * multiplier) + ema
    return ema


def calculate_momentum(prices: List[float], periods=MOMENTUM_PERIOD) -> float:
    if len(prices) <= periods:
        return 0.0
    old = prices[-periods - 1]
    return ((prices[-1] - old) / old) * 100.0 if old > 0 else 0.0


def calculate_volatility(prices: List[float], periods=20) -> float:
    recent = prices[-periods:]
    if len(recent) < 3:
        return 0.0
    returns = [((b-a)/a)*100 for a,b in zip(recent,recent[1:]) if a > 0]
    if not returns:
        return 0.0
    avg = sum(returns)/len(returns)
    return math.sqrt(sum((x-avg)**2 for x in returns)/len(returns))


def calculate_rsi(prices: List[float], period=14) -> float:
    if len(prices) <= period:
        return 50.0
    changes = [prices[i]-prices[i-1] for i in range(len(prices)-period, len(prices))]
    gains = [max(x,0) for x in changes]
    losses = [max(-x,0) for x in changes]
    avg_gain = sum(gains)/period
    avg_loss = sum(losses)/period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain/avg_loss
    return 100.0 - 100.0/(1.0+rs)


def calculate_round_trip_cost_percent(spread_percent: float) -> float:
    return BUY_FEE_PERCENT + SELL_FEE_PERCENT + max(0.0, spread_percent)*100.0


def analyze_market(prices, spread_percent=0.0, has_position=False, entry_price=0.0):
    if len(prices) < MIN_HISTORY:
        return Signal("HOLD", f"Venter på historikk ({len(prices)}/{MIN_HISTORY})")

    current = prices[-1]
    ema_fast = calculate_ema(prices, EMA_FAST) or current
    ema_slow = calculate_ema(prices, EMA_SLOW) or current
    ema_trend = calculate_ema(prices, EMA_TREND) or current
    momentum = calculate_momentum(prices)
    volatility = calculate_volatility(prices)
    rsi = calculate_rsi(prices)

    cost = calculate_round_trip_cost_percent(spread_percent)
    required = max(MIN_ENTRY_MOVE_PERCENT, cost + PROFIT_SAFETY_MARGIN_PERCENT)

    if current > ema_slow > ema_trend:
        trend = "BULLISH"
    elif current < ema_slow < ema_trend:
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    common = dict(ema_fast=ema_fast, ema_slow=ema_slow, ema_trend=ema_trend,
                  momentum=momentum, volatility=volatility, rsi=rsi,
                  estimated_cost_percent=cost, required_move_percent=required,
                  trend=trend)

    if spread_percent > 0.005:
        return Signal("HOLD", f"Spread for høy ({spread_percent*100:.2f}%)", **common)

    if has_position and entry_price > 0:
        pnl = (current-entry_price)/entry_price*100
        if pnl >= TAKE_PROFIT_PERCENT:
            return Signal("SELL", f"Take-profit: +{pnl:.2f}%", 3, sell_score=3, **common)
        if pnl <= -STOP_LOSS_PERCENT:
            return Signal("SELL", f"Stop-loss: {pnl:.2f}%", 3, sell_score=3, **common)
        if ema_fast < ema_slow and momentum < -0.15:
            return Signal("SELL", f"Trend snur ned | MOM {momentum:+.2f}%", 2, sell_score=2, **common)
        if rsi <= RSI_SELL and momentum < 0:
            return Signal("SELL", f"Svakhet | RSI {rsi:.1f}", 2, sell_score=2, **common)
        return Signal("HOLD", f"Holder | P/L {pnl:+.2f}% | RSI {rsi:.1f}", **common)

    score = sum([
        ema_fast > ema_slow,
        current > ema_fast,
        current > ema_trend,
        momentum >= MIN_ENTRY_MOVE_PERCENT,
        RSI_BUY_MIN <= rsi <= RSI_BUY_MAX
    ])

    if score >= 4 and ema_fast > ema_slow and current > ema_trend and momentum >= MIN_ENTRY_MOVE_PERCENT and RSI_BUY_MIN <= rsi <= RSI_BUY_MAX:
        return Signal("BUY",
                      f"Daytrade BUY | score {score}/5 | MOM {momentum:+.2f}% | RSI {rsi:.1f}",
                      score=score, buy_score=score, **common)

    return Signal("HOLD",
                  f"Ingen entry | score {score}/5 | {trend} | MOM {momentum:+.2f}% | RSI {rsi:.1f}",
                  buy_score=score, **common)
