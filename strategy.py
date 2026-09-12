from dataclasses import dataclass
from typing import List, Optional


# ============================================================
# STRATEGI-INNSTILLINGER
# ============================================================

# Firi handelsgebyr
BUY_FEE = 0.007
SELL_FEE = 0.007

# Ekstra sikkerhetsmargin over gebyrer/spread
MIN_PROFIT_MARGIN = 0.008

# RSI
RSI_PERIOD = 14

RSI_OVERSOLD = 30
RSI_BUY_ZONE = 40
RSI_OVERBOUGHT = 70

# EMA
EMA_FAST = 20
EMA_SLOW = 50

# Hvor mye historikk vi ønsker
MIN_HISTORY = 60

# Scoregrenser
BUY_SCORE = 6
STRONG_BUY_SCORE = 9

SELL_SCORE = 6
STRONG_SELL_SCORE = 9


# ============================================================
# SIGNAL
# ============================================================

@dataclass
class Signal:

    action: str
    reason: str

    score: int = 0

    rsi: float = 0.0

    ema_fast: float = 0.0
    ema_slow: float = 0.0

    momentum: float = 0.0

    expected_profit_percent: float = 0.0

    estimated_cost_percent: float = 0.0

    net_expected_percent: float = 0.0


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

        change = recent[i] - recent[i - 1]

        if change > 0:
            gains.append(change)
            losses.append(0)

        else:
            gains.append(0)
            losses.append(abs(change))

    average_gain = sum(gains) / period
    average_loss = sum(losses) / period

    if average_loss == 0:

        return 100.0

    relative_strength = (
        average_gain /
        average_loss
    )

    rsi = (
        100 -
        (100 / (1 + relative_strength))
    )

    return rsi


# ============================================================
# EMA
# ============================================================

def calculate_ema(
    prices: List[float],
    period: int
) -> Optional[float]:

    if len(prices) < period:
        return None

    multiplier = 2 / (period + 1)

    ema = sum(
        prices[:period]
    ) / period

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

    if old_price == 0:
        return 0.0

    return (
        (current_price - old_price)
        / old_price
    ) * 100


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

        if previous == 0:
            continue

        change = (
            (current - previous)
            / previous
        ) * 100

        returns.append(change)

    if not returns:
        return 0.0

    average = (
        sum(returns)
        / len(returns)
    )

    variance = sum(
        (x - average) ** 2
        for x in returns
    ) / len(returns)

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
        + spread_percent
        + MIN_PROFIT_MARGIN
    ) * 100


# ============================================================
# FORVENTET GEVINST
# ============================================================

def estimate_expected_profit(
    price: float,
    rsi: float,
    momentum: float,
    volatility: float
) -> float:

    """
    Forsiktig estimat på mulig bevegelse.

    Dette er ikke en garanti eller prediksjon.
    Det brukes kun som filter for om en handel
    er interessant nok etter kostnader.
    """

    if price <= 0:
        return 0.0

    base_move = abs(momentum)

    volatility_component = (
        volatility * 1.5
    )

    rsi_component = 0.0

    if rsi < 35:
        rsi_component += 0.5

    elif rsi > 65:
        rsi_component += 0.5

    expected = (
        base_move
        + volatility_component
        + rsi_component
    )

    # Begrens estimatet
    expected = max(
        0.0,
        min(expected, 15.0)
    )

    return expected


# ============================================================
# HOVEDSTRATEGI
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


    # --------------------------------------------------------
    # INDIKATORER
    # --------------------------------------------------------

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
    # KOSTNADER
    # --------------------------------------------------------

    estimated_cost = calculate_trading_cost(
        spread_percent
    )


    expected_profit = estimate_expected_profit(
        current_price,
        rsi,
        momentum,
        volatility
    )


    net_expected = (
        expected_profit
        - estimated_cost
    )


    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    buy_score = 0
    sell_score = 0

    buy_reasons = []
    sell_reasons = []


    # ========================================================
    # RSI
    # ========================================================

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

    elif rsi >= 60:

        sell_score += 1

        sell_reasons.append(
            f"RSI høy ({rsi:.1f})"
        )


    # ========================================================
    # EMA TREND
    # ========================================================

    if ema_fast > ema_slow:

        buy_score += 2

        buy_reasons.append(
            "EMA20 over EMA50"
        )

    else:

        sell_score += 2

        sell_reasons.append(
            "EMA20 under EMA50"
        )


    # ========================================================
    # MOMENTUM
    # ========================================================

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


    # ========================================================
    # RSI + TREND FILTER
    # ========================================================

    # Oversolgt i bullish trend er interessant
    if (
        rsi < 40
        and ema_fast > ema_slow
    ):

        buy_score += 2

        buy_reasons.append(
            "Oversolgt pullback i bullish trend"
        )


    # Overkjøpt i bearish trend
    if (
        rsi > 60
        and ema_fast < ema_slow
    ):

        sell_score += 2

        sell_reasons.append(
            "Overkjøpt rally i bearish trend"
        )


    # ========================================================
    # SPREAD FILTER
    # ========================================================

    if spread_percent > 0.005:

        return Signal(
            action="HOLD",
            reason=(
                f"Spread for høy "
                f"({spread_percent * 100:.2f}%)"
            ),
            score=0,
            rsi=rsi,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            momentum=momentum,
            expected_profit_percent=expected_profit,
            estimated_cost_percent=estimated_cost,
            net_expected_percent=net_expected,
        )


    # ========================================================
    # LØNNSOMHETS-FILTER
    # ========================================================

    if net_expected <= 0:

        return Signal(
            action="HOLD",
            reason=(
                f"Ingen handel: "
                f"forventet {expected_profit:.2f}% "
                f"vs kostnad {estimated_cost:.2f}%"
            ),
            score=max(
                buy_score,
                sell_score
            ),
            rsi=rsi,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            momentum=momentum,
            expected_profit_percent=expected_profit,
            estimated_cost_percent=estimated_cost,
            net_expected_percent=net_expected,
        )


    # ========================================================
    # BUY
    # ========================================================

    if buy_score >= STRONG_BUY_SCORE:

        return Signal(
            action="BUY STRONG",
            reason=(
                " + ".join(
                    buy_reasons
                )
                + f" | Netto potensial "
                f"{net_expected:.2f}%"
            ),
            score=buy_score,
            rsi=rsi,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            momentum=momentum,
            expected_profit_percent=expected_profit,
            estimated_cost_percent=estimated_cost,
            net_expected_percent=net_expected,
        )


    if buy_score >= BUY_SCORE:

        return Signal(
            action="BUY",
            reason=(
                " + ".join(
                    buy_reasons
                )
                + f" | Netto potensial "
                f"{net_expected:.2f}%"
            ),
            score=buy_score,
            rsi=rsi,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            momentum=momentum,
            expected_profit_percent=expected_profit,
            estimated_cost_percent=estimated_cost,
            net_expected_percent=net_expected,
        )


    # ========================================================
    # SELL
    # ========================================================

    if sell_score >= STRONG_SELL_SCORE:

        return Signal(
            action="SELL STRONG",
            reason=(
                " + ".join(
                    sell_reasons
                )
                + f" | Netto potensial "
                f"{net_expected:.2f}%"
            ),
            score=sell_score,
            rsi=rsi,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            momentum=momentum,
            expected_profit_percent=expected_profit,
            estimated_cost_percent=estimated_cost,
            net_expected_percent=net_expected,
        )


    if sell_score >= SELL_SCORE:

        return Signal(
            action="SELL",
            reason=(
                " + ".join(
                    sell_reasons
                )
                + f" | Netto potensial "
                f"{net_expected:.2f}%"
            ),
            score=sell_score,
            rsi=rsi,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            momentum=momentum,
            expected_profit_percent=expected_profit,
            estimated_cost_percent=estimated_cost,
            net_expected_percent=net_expected,
        )


    # ========================================================
    # HOLD
    # ========================================================

    return Signal(
        action="HOLD",
        reason=(
            f"Ingen tydelig fordel "
            f"(BUY {buy_score}/12, "
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
        expected_profit_percent=expected_profit,
        estimated_cost_percent=estimated_cost,
        net_expected_percent=net_expected,
    )


# ============================================================
# KOMPATIBILITET MED GAMMEL BOT
# ============================================================

def get_signal(
    price: float
) -> Signal:

    return Signal(
        action="HOLD",
        reason=(
            "Venter på historiske prisdata "
            "for RSI/EMA-strategien."
        )
    )