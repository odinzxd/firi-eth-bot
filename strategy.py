from dataclasses import dataclass
from typing import List, Optional


# ============================================================
# ENKEL, AKTIV STRATEGI
# ============================================================

# Korte perioder gir hyppige signaler.
EMA_FAST = 5
EMA_SLOW = 15
MOMENTUM_PERIOD = 3
MOMENTUM_THRESHOLD = 0.05  # prosent over de siste tre 1-minutts-candlene
MIN_HISTORY = EMA_SLOW + 1
MAX_SPREAD_PERCENT = 0.005

# Firi Avansert handel: 0,7 % for kjøp + 0,7 % for salg.
BUY_FEE_PERCENT = 0.7
SELL_FEE_PERCENT = 0.7
PROFIT_SAFETY_MARGIN_PERCENT = 0.20


@dataclass
class Signal:
    action: str
    reason: str
    score: int = 0
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    momentum: float = 0.0
    volatility: float = 0.0
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


def calculate_momentum(
    prices: List[float],
    periods: int = MOMENTUM_PERIOD
) -> float:
    if len(prices) <= periods:
        return 0.0

    old_price = prices[-periods - 1]

    if old_price <= 0:
        return 0.0

    return ((prices[-1] - old_price) / old_price) * 100.0


def calculate_volatility(prices: List[float], periods: int = 10) -> float:
    recent = prices[-periods:]

    if len(recent) < 2:
        return 0.0

    returns = [
        ((current - previous) / previous) * 100.0
        for previous, current in zip(recent, recent[1:])
        if previous > 0
    ]

    if not returns:
        return 0.0

    average = sum(returns) / len(returns)
    variance = sum((value - average) ** 2 for value in returns) / len(returns)

    return variance ** 0.5


def calculate_round_trip_cost_percent(spread_percent: float) -> float:
    """Anslått kostnad for kjøp og senere salg med dagens spread."""
    return (
        BUY_FEE_PERCENT
        + SELL_FEE_PERCENT
        + max(0.0, spread_percent) * 100.0
    )


def analyze_market(
    prices: List[float],
    spread_percent: float = 0.0
) -> Signal:
    if len(prices) < MIN_HISTORY:
        return Signal(
            action="HOLD",
            reason=f"Venter på historikk ({len(prices)}/{MIN_HISTORY})"
        )

    current_price = prices[-1]
    ema_fast = calculate_ema(prices, EMA_FAST) or current_price
    ema_slow = calculate_ema(prices, EMA_SLOW) or current_price
    momentum = calculate_momentum(prices)
    volatility = calculate_volatility(prices)
    estimated_cost = calculate_round_trip_cost_percent(spread_percent)
    required_move = max(
        MOMENTUM_THRESHOLD,
        estimated_cost + PROFIT_SAFETY_MARGIN_PERCENT
    )

    if ema_fast > ema_slow:
        trend = "BULLISH"
    elif ema_fast < ema_slow:
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    if spread_percent > MAX_SPREAD_PERCENT:
        return Signal(
            action="HOLD",
            reason=f"Spread for høy ({spread_percent * 100:.2f}%)",
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            momentum=momentum,
            volatility=volatility,
            estimated_cost_percent=estimated_cost,
            required_move_percent=required_move,
            trend=trend
        )

    # Aktiv logikk: kort bevegelse i samme retning som rask EMA gir signal.
    if momentum >= required_move and current_price >= ema_fast:
        return Signal(
            action="BUY",
            reason=(
                f"Kort momentum opp {momentum:+.2f}% "
                f"over EMA{EMA_FAST}"
            ),
            score=1,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            momentum=momentum,
            volatility=volatility,
            estimated_cost_percent=estimated_cost,
            required_move_percent=required_move,
            trend=trend,
            buy_score=1
        )

    if momentum <= -required_move and current_price <= ema_fast:
        return Signal(
            action="SELL",
            reason=(
                f"Kort momentum ned {momentum:+.2f}% "
                f"under EMA{EMA_FAST}"
            ),
            score=1,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            momentum=momentum,
            volatility=volatility,
            estimated_cost_percent=estimated_cost,
            required_move_percent=required_move,
            trend=trend,
            sell_score=1
        )

    return Signal(
        action="HOLD",
        reason=(
            f"Bevegelse {momentum:+.2f}% dekker ikke anslått "
            f"kostnad + margin ({required_move:.2f}%)"
        ),
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        momentum=momentum,
        volatility=volatility,
        estimated_cost_percent=estimated_cost,
        required_move_percent=required_move,
        trend=trend
    )
