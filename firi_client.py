import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from firipy import FiriAPI


load_dotenv()


class FiriClient:
    def __init__(self):
        self.api_key = os.getenv("FIRI_API_KEY")
        self.client_id = os.getenv("FIRI_CLIENT_ID")
        self.secret_key = os.getenv("FIRI_SECRET_KEY")
        self.market = os.getenv("MARKET", "ETHNOK")

        missing = []
        if not self.api_key:
            missing.append("FIRI_API_KEY")
        if not self.client_id:
            missing.append("FIRI_CLIENT_ID")
        if not self.secret_key:
            missing.append("FIRI_SECRET_KEY")

        if missing:
            raise RuntimeError(
                "Mangler Firi-miljøvariabler: " + ", ".join(missing)
            )

        self.client = None

    async def connect(self):
        self.client = FiriAPI(
            api_key=self.api_key,
            secret_key=self.secret_key,
            client_id=self.client_id,
        )
        await self.client.__aenter__()
        return self

    async def close(self):
        if self.client is not None:
            await self.client.__aexit__(None, None, None)
            self.client = None

    async def get_ticker(self) -> Dict[str, float]:
        if self.client is None:
            raise RuntimeError("FiriClient er ikke tilkoblet.")

        ticker = await self.client.markets_market_ticker(self.market)

        bid = float(ticker["bid"])
        ask = float(ticker["ask"])
        spread = float(ticker.get("spread", ask - bid))

        mid = (bid + ask) / 2.0
        spread_percent = (spread / mid * 100.0) if mid > 0 else 0.0

        return {
            "bid": bid,
            "ask": ask,
            "price": mid,
            "spread": spread,
            "spread_percent": spread_percent,
        }

    async def get_balances(self) -> Dict[str, float]:
        if self.client is None:
            raise RuntimeError("FiriClient er ikke tilkoblet.")

        raw = await self.client.balances()

        return {
            "NOK": find_balance(raw, "NOK"),
            "ETH": find_balance(raw, "ETH"),
        }

    async def place_order(
        self,
        action: str,
        price: float,
        amount: float,
    ) -> Any:
        if self.client is None:
            raise RuntimeError("FiriClient er ikke tilkoblet.")

        order_type = "bid" if action == "buy" else "ask"

        return await self.client.post_orders(
            self.market,
            order_type,
            f"{price:.2f}",
            f"{amount:.12f}",
        )


def find_balance(value: Any, currency: str) -> float:
    if isinstance(value, dict):
        if currency in value:
            item = value[currency]

            if isinstance(item, dict):
                for key in ("available", "balance", "amount", "free"):
                    if key in item:
                        try:
                            return float(item[key])
                        except (TypeError, ValueError):
                            pass

            try:
                return float(item)
            except (TypeError, ValueError):
                pass

        for key in ("balances", "data", "result"):
            if key in value:
                result = find_balance(value[key], currency)
                if result is not None:
                    return result

    elif isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue

            symbol = item.get("symbol") or item.get("currency")
            if str(symbol).upper() == currency.upper():
                for key in ("available", "balance", "amount", "free"):
                    if key in item:
                        try:
                            return float(item[key])
                        except (TypeError, ValueError):
                            pass

    return 0.0
