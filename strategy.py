from dataclasses import dataclass
from typing import List, Optional


EMA_FAST = 9
EMA_SLOW = 21
RSI_PERIOD = 14

TAKE_PROFIT_PERCENT = 1.0
STOP_LOSS_PERCENT = 0.6


def get_take_profit_percent(
    expected_cost_percent: float = 0.0,
    minimum: float = TAKE_PROFIT_PERCENT,
) -> float:
    return max(minimum, expected_cost_percent + 0.5)


@dataclass
class Signal:
    action: str
    reason: str
    ema9: Optional[float] = None
    ema21: Optional[float] = None
    rsi14: Optional[float] = None
    trend: str = "UNKNOWN"


def calculate_ema(prices: List[float], period: int) -> Optional[float]:
    if len(prices) < period:
        return None

    ema = sum(prices[:period]) / period
    multiplier = 2.0 / (period + 1)

    for price in prices[period:]:
        ema = ((price - ema) * multiplier) + ema

    return ema


def calculate_rsi(prices: List[float], period: int = RSI_PERIOD) -> Optional[float]:
    if len(prices) < period + 1:
        return None

    changes = [
        prices[i] - prices[i - 1]
        for i in range(1, len(prices))
    ]

    recent = changes[-period:]
    gains = [change for change in recent if change > 0]
    losses = [-change for change in recent if change < 0]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0

    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def analyze_market(
    prices: List[float],
    current_position: bool = False,
    entry_price: float = 0.0,
    take_profit_percent: float = TAKE_PROFIT_PERCENT,
    stop_loss_percent: float = STOP_LOSS_PERCENT,
    current_price: Optional[float] = None,
    bearish_trend_exit_streak: int = 0,
) -> Signal:
    if len(prices) < EMA_SLOW:
        return Signal(
            action="HOLD",
            reason=f"Venter på markedsdata ({len(prices)}/{EMA_SLOW})",
        )

    ema9 = calculate_ema(prices, EMA_FAST)
    ema21 = calculate_ema(prices, EMA_SLOW)
    rsi = calculate_rsi(prices)

    if ema9 is None or ema21 is None or rsi is None:
        return Signal(
            action="HOLD",
            reason="Venter på nok data for EMA/RSI",
            ema9=ema9,
            ema21=ema21,
            rsi14=rsi,
        )

    if ema9 > ema21:
        trend = "BULLISH"
    elif ema9 < ema21:
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    current = prices[-1] if current_price is None else current_price

    # Exit first when we already own ETH.
    if current_position and entry_price > 0:
        change_percent = ((current - entry_price) / entry_price) * 100.0

        if change_percent >= take_profit_percent:
            return Signal(
                action="SELL",
                reason=f"TAKE PROFIT: {change_percent:+.2f}%",
                ema9=ema9,
                ema21=ema21,
                rsi14=rsi,
                trend=trend,
            )

        if change_percent <= -stop_loss_percent:
            return Signal(
                action="SELL",
                reason=f"STOP LOSS: {change_percent:+.2f}%",
                ema9=ema9,
                ema21=ema21,
                rsi14=rsi,
                trend=trend,
            )

        if ema9 < ema21 and bearish_trend_exit_streak >= 2:
            return Signal(
                action="SELL",
                reason=(
                    f"Trend exit: EMA9 {ema9:.2f} < EMA21 {ema21:.2f} "
                    f"for {bearish_trend_exit_streak} analyser i rad"
                ),
                ema9=ema9,
                ema21=ema21,
                rsi14=rsi,
                trend=trend,
            )

        return Signal(
            action="HOLD",
            reason=f"Holder posisjon. RSI={rsi:.1f}, EMA9 >= EMA21",
            ema9=ema9,
            ema21=ema21,
            rsi14=rsi,
            trend=trend,
        )

    # Simple entry.
    if ema9 > ema21 and 50.0 <= rsi <= 70.0:
        return Signal(
            action="BUY",
            reason=f"EMA9 > EMA21 og RSI={rsi:.1f}",
            ema9=ema9,
            ema21=ema21,
            rsi14=rsi,
            trend=trend,
        )

    return Signal(
        action="HOLD",
        reason=f"Ingen kjøpssignal. Trend={trend}, RSI={rsi:.1f}",
        ema9=ema9,
        ema21=ema21,
        rsi14=rsi,
        trend=trend,
    )
