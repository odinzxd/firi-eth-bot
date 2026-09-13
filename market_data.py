import time
from typing import List, Dict, Any

import requests


BINANCE_URLS = [
    "https://api.binance.com/api/v3/klines",
    "https://api.binance.us/api/v3/klines",
]
SYMBOL = "ETHUSDT"
INTERVAL = "5m"
LIMIT = 288


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

    last_error = None

    for base_url in BINANCE_URLS:
        try:
            response = requests.get(
                base_url,
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list):
                raise MarketDataError(
                    f"Uventet Binance-respons: {type(data).__name__}"
                )

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

        except Exception as exc:  # pragma: no cover - defensive fallback
            last_error = exc
            continue

    raise MarketDataError(
        f"Kunne ikke hente Binance-data fra noen endepunkter. Siste feil: {last_error}"
    )


def get_close_prices(candles: List[Dict[str, Any]]) -> List[float]:
    return [float(candle["close"]) for candle in candles]


def get_latest_binance_price() -> float:
    last_error = None

    for base_url in [
        "https://api.binance.com/api/v3/ticker/price",
        "https://api.binance.us/api/v3/ticker/price",
    ]:
        try:
            response = requests.get(
                base_url,
                params={"symbol": SYMBOL},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return float(data["price"])
        except Exception as exc:
            last_error = exc

    raise MarketDataError(
        f"Kunne ikke hente siste Binance-pris. Siste feil: {last_error}"
    )


if __name__ == "__main__":
    candles = get_binance_candles()
    print(f"Hentet {len(candles)} candles.")
    print(f"Siste ETHUSDT: {candles[-1]['close']}")
