import time
from typing import List, Dict, Any

import requests


BINANCE_URL = "https://api.binance.com/api/v3/klines"
SYMBOL = "ETHUSDT"
INTERVAL = "5m"
LIMIT = 200


class MarketDataError(Exception):
    pass


def get_binance_candles(
    symbol: str = SYMBOL,
    interval: str = INTERVAL,
    limit: int = LIMIT,
) -> List[Dict[str, Any]]:
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }

    response = requests.get(
        BINANCE_URL,
        params=params,
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise MarketDataError(f"Uventet Binance-respons: {type(data).__name__}")

    candles = []

    for row in data:
        if not isinstance(row, list) or len(row) < 6:
            continue

        candles.append(
            {
                "timestamp": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
        )

    if len(candles) < 25:
        raise MarketDataError(
            f"For få candles fra Binance: {len(candles)}"
        )

    return candles


def get_close_prices(candles: List[Dict[str, Any]]) -> List[float]:
    return [float(candle["close"]) for candle in candles]


def get_latest_binance_price() -> float:
    response = requests.get(
        "https://api.binance.com/api/v3/ticker/price",
        params={"symbol": SYMBOL},
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()
    return float(data["price"])


if __name__ == "__main__":
    candles = get_binance_candles()
    print(f"Hentet {len(candles)} candles.")
    print(f"Siste ETHUSDT: {candles[-1]['close']}")
