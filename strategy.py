from dataclasses import dataclass
from typing import List, Optional


# ============================================================
# STRATEGI-INNSTILLINGER
# ============================================================

BUY_FEE = 0.007
SELL_FEE = 0.007

RSI_PERIOD = 14

RSI_OVERSOLD = 30
RSI_BUY_ZONE = 40

RSI_OVERBOUGHT = 70
RSI_SELL_ZONE = 60

EMA_FAST = 20
EMA_SLOW = 50

MIN_HISTORY = 60

BUY_SCORE = 6
STRONG_BUY_SCORE = 9

SELL_SCORE = 6
STRONG_SELL_SCORE = 9

# Ekstra margin over forventede kostnader
SAFETY_MARGIN = 0.008


# ============================================================
# SIGNAL
# ============================================================

@dataclass
class Signal:

    action: str
    reason: str

    score: int = 0

    rsi: float = 50.0

    ema_fast: float = 0.0
    ema_slow: float = 0.0

    momentum: float = 0.0
    volatility: float = 0.0

    expected_profit_percent: float = 0.0
    estimated_cost_percent: float = 0.0
    net_expected_percent: float = 0.0

    trend: str = "UNKNOWN"

    buy_score: int = 0
    sell_score: int = 0


# ============================================================
# RSI
# ============================================================

def calculate_rsi(
    prices: List[float],
    period: int = RSI_PERIOD
) -> Optional[float]:

    if len(prices) < period + 1:
        return None

    recent = prices[-(period + 1):]

    gains = []
    losses = []

    for i in range(1, len(recent)):

        change = (
            recent[i]
            - recent[i - 1]
        )

        if change > 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))

    average_gain = (
        sum(gains) / period
    )

    average_loss = (
        sum(losses) / period
    )

    if average_loss == 0:
        return 100.0

    rs = (
        average_gain
        / average_loss
    )

    return 100.0 - (
        100.0
        / (1.0 + rs)
    )


# ============================================================
# EMA
# ============================================================

def calculate_ema(
    prices: List[float],
    period: int
) -> Optional[float]:

    if len(prices) < period:
        return None

    ema = (
        sum(prices[:period])
        / period
    )

    multiplier = (
        2.0
        / (period + 1)
    )

    for price in prices[period:]:

        ema = (
            (price - ema)
            * multiplier
            + ema
        )

    return ema


# ============================================================
# MOMENTUM
# ============================================================

def calculate_momentum(
    prices: List[float],
    periods: int = 10
) -> float:

    if len(prices) <= periods:
        return 0.0

    old_price = prices[-periods - 1]
    current_price = prices[-1]

    if old_price <= 0:
        return 0.0

    return (
        (
            current_price
            - old_price
        )
        / old_price
    ) * 100.0


# ============================================================
# VOLATILITET
# ============================================================

def calculate_volatility(
    prices: List[float],
    periods: int = 20
) -> float:

    if len(prices) < periods + 1:
        return 0.0

    recent = prices[-periods:]

    returns = []

    for i in range(1, len(recent)):

        previous = recent[i - 1]
        current = recent[i]

        if previous <= 0:
            continue

        change = (
            (
                current
                - previous
            )
            / previous
        ) * 100.0

        returns.append(change)

    if not returns:
        return 0.0

    average = (
        sum(returns)
        / len(returns)
    )

    variance = (
        sum(
            (x - average) ** 2
            for x in returns
        )
        / len(returns)
    )

    return variance ** 0.5


# ============================================================
# KOSTNADER
# ============================================================

def calculate_trading_cost(
    spread_percent: float
) -> float:

    return (
        BUY_FEE
        + SELL_FEE
        + max(
            0.0,
            spread_percent
        )
        + SAFETY_MARGIN
    ) * 100.0


# ============================================================
# FORVENTET BEVEGELSE
# ============================================================

def estimate_expected_move(
    rsi: float,
    momentum: float,
    volatility: float,
    trend_strength: float
) -> float:

    momentum_component = (
        abs(momentum)
        * 0.8
    )

    volatility_component = (
        volatility
        * 1.2
    )

    trend_component = (
        trend_strength
        * 0.5
    )

    rsi_component = 0.0

    if rsi <= 35:
        rsi_component = 0.8

    elif rsi >= 65:
        rsi_component = 0.8

    expected = (
        momentum_component
        + volatility_component
        + trend_component
        + rsi_component
    )

    return max(
        0.0,
        min(
            expected,
            12.0
        )
    )


# ============================================================
# ANALYSE
# ============================================================

def analyze_market(
    prices: List[float],
    spread_percent: float = 0.0
) -> Signal:

    if len(prices) < MIN_HISTORY:

        return Signal(
            action="HOLD",
            reason=(
                f"Venter på historikk "
                f"({len(prices)}/{MIN_HISTORY})"
            )
        )

    current_price = prices[-1]

    rsi = calculate_rsi(
        prices
    )

    ema_fast = calculate_ema(
        prices,
        EMA_FAST
    )

    ema_slow = calculate_ema(
        prices,
        EMA_SLOW
    )

    momentum = calculate_momentum(
        prices
    )

    volatility = calculate_volatility(
        prices
    )

    if rsi is None:
        rsi = 50.0

    if ema_fast is None:
        ema_fast = current_price

    if ema_slow is None:
        ema_slow = current_price

    # --------------------------------------------------------
    # TREND
    # --------------------------------------------------------

    if ema_slow != 0:

        trend_strength = (
            abs(
                ema_fast
                - ema_slow
            )
            / ema_slow
        ) * 100.0

    else:

        trend_strength = 0.0

    if ema_fast > ema_slow:
        trend = "BULLISH"

    elif ema_fast < ema_slow:
        trend = "BEARISH"

    else:
        trend = "NEUTRAL"

    # --------------------------------------------------------
    # KOSTNADER
    # --------------------------------------------------------

    estimated_cost = (
        calculate_trading_cost(
            spread_percent
        )
    )

    expected_move = (
        estimate_expected_move(
            rsi,
            momentum,
            volatility,
            trend_strength
        )
    )

    net_expected = (
        expected_move
        - estimated_cost
    )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    buy_score = 0
    sell_score = 0

    buy_reasons = []
    sell_reasons = []

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    if rsi <= RSI_OVERSOLD:

        buy_score += 3

        buy_reasons.append(
            f"RSI oversolgt ({rsi:.1f})"
        )

    elif rsi <= RSI_BUY_ZONE:

        buy_score += 2

        buy_reasons.append(
            f"RSI kjøpsområde ({rsi:.1f})"
        )

    elif rsi >= RSI_OVERBOUGHT:

        sell_score += 3

        sell_reasons.append(
            f"RSI overkjøpt ({rsi:.1f})"
        )

    elif rsi >= RSI_SELL_ZONE:

        sell_score += 1

        sell_reasons.append(
            f"RSI høy ({rsi:.1f})"
        )

    # --------------------------------------------------------
    # EMA
    # --------------------------------------------------------

    if ema_fast > ema_slow:

        buy_score += 2

        buy_reasons.append(
            "EMA20 over EMA50"
        )

    elif ema_fast < ema_slow:

        sell_score += 2

        sell_reasons.append(
            "EMA20 under EMA50"
        )

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    if momentum > 1.0:

        buy_score += 2

        buy_reasons.append(
            f"Positivt momentum ({momentum:.2f}%)"
        )

    elif momentum > 0:

        buy_score += 1

        buy_reasons.append(
            f"Svakt positivt momentum ({momentum:.2f}%)"
        )

    if momentum < -1.0:

        sell_score += 2

        sell_reasons.append(
            f"Negativt momentum ({momentum:.2f}%)"
        )

    elif momentum < 0:

        sell_score += 1

        sell_reasons.append(
            f"Svakt negativt momentum ({momentum:.2f}%)"
        )

    # --------------------------------------------------------
    # BULLISH PULLBACK
    # --------------------------------------------------------

    if (
        rsi < 40
        and ema_fast > ema_slow
        and momentum > -1.0
    ):

        buy_score += 2

        buy_reasons.append(
            "Bullish pullback"
        )

    # --------------------------------------------------------
    # BEARISH RALLY
    # --------------------------------------------------------

    if (
        rsi > 60
        and ema_fast < ema_slow
        and momentum < 1.0
    ):

        sell_score += 2

        sell_reasons.append(
            "Bearish rally"
        )

    # --------------------------------------------------------
    # SPREAD-FILTER
    # --------------------------------------------------------

    if spread_percent > 0.005:

        return Signal(
            action="HOLD",
            reason=(
                f"Spread for høy "
                f"({spread_percent * 100:.2f}%)"
            ),
            rsi=rsi,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            momentum=momentum,
            volatility=volatility,
            estimated_cost_percent=estimated_cost,
            expected_profit_percent=expected_move,
            net_expected_percent=net_expected,
            trend=trend,
            buy_score=buy_score,
            sell_score=sell_score
        )

    # --------------------------------------------------------
    # LØNNSOMHETS-FILTER
    # --------------------------------------------------------

    if net_expected <= 0:

        return Signal(
            action="HOLD",
            reason=(
                f"Ikke lønnsomt etter kostnader: "
                f"{expected_move:.2f}% mulig "
                f"mot {estimated_cost:.2f}% kostnad"
            ),
            score=max(
                buy_score,
                sell_score
            ),
            rsi=rsi,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            momentum=momentum,
            volatility=volatility,
            estimated_cost_percent=estimated_cost,
            expected_profit_percent=expected_move,
            net_expected_percent=net_expected,
            trend=trend,
            buy_score=buy_score,
            sell_score=sell_score
        )

    # --------------------------------------------------------
    # BUY STRONG
    # --------------------------------------------------------

    if buy_score >= STRONG_BUY_SCORE:

        return Signal(
            action="BUY STRONG",
            reason=(
                " | ".join(
                    buy_reasons
                )
                + f" | Netto "
                f"{net_expected:.2f}%"
            ),
            score=buy_score,
            rsi=rsi,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            momentum=momentum,
            volatility=volatility,
            estimated_cost_percent=estimated_cost,
            expected_profit_percent=expected_move,
            net_expected_percent=net_expected,
            trend=trend,
            buy_score=buy_score,
            sell_score=sell_score
        )

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    if buy_score >= BUY_SCORE:

        return Signal(
            action="BUY",
            reason=(
                " | ".join(
                    buy_reasons
                )
                + f" | Netto "
                f"{net_expected:.2f}%"
            ),
            score=buy_score,
            rsi=rsi,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            momentum=momentum,
            volatility=volatility,
            estimated_cost_percent=estimated_cost,
            expected_profit_percent=expected_move,
            net_expected_percent=net_expected,
            trend=trend,
            buy_score=buy_score,
            sell_score=sell_score
        )

    # --------------------------------------------------------
    # SELL STRONG
    # --------------------------------------------------------

    if sell_score >= STRONG_SELL_SCORE:

        return Signal(
            action="SELL STRONG",
            reason=(
                " | ".join(
                    sell_reasons
                )
                + f" | Netto "
                f"{net_expected:.2f}%"
            ),
            score=sell_score,
            rsi=rsi,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            momentum=momentum,
            volatility=volatility,
            estimated_cost_percent=estimated_cost,
            expected_profit_percent=expected_move,
            net_expected_percent=net_expected,
            trend=trend,
            buy_score=buy_score,
            sell_score=sell_score
        )

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    if sell_score >= SELL_SCORE:

        return Signal(
            action="SELL",
            reason=(
                " | ".join(
                    sell_reasons
                )
                + f" | Netto "
                f"{net_expected:.2f}%"
            ),
            score=sell_score,
            rsi=rsi,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            momentum=momentum,
            volatility=volatility,
            estimated_cost_percent=estimated_cost,
            expected_profit_percent=expected_move,
            net_expected_percent=net_expected,
            trend=trend,
            buy_score=buy_score,
            sell_score=sell_score
        )

    # --------------------------------------------------------
    # HOLD
    # --------------------------------------------------------

    return Signal(
        action="HOLD",
        reason=(
            f"Ingen tydelig fordel "
            f"(BUY {buy_score}/12 | "
            f"SELL {sell_score}/12)"
        ),
        score=max(
            buy_score,
            sell_score
        ),
        rsi=rsi,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        momentum=momentum,
        volatility=volatility,
        estimated_cost_percent=estimated_cost,
        expected_profit_percent=expected_move,
        net_expected_percent=net_expected,
        trend=trend,
        buy_score=buy_score,
        sell_score=sell_score
    )