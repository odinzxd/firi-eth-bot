import json
import os
from typing import Any, Dict, Optional


class ClaudeDecisionError(RuntimeError):
    pass


class ClaudeClient:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        self.client = None

    def _get_sdk(self):
        if self.dry_run:
            return None

        if not self.api_key:
            raise ClaudeDecisionError("ANTHROPIC_API_KEY is not set")

        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - runtime dependency guard
            raise ClaudeDecisionError(
                "Anthropic SDK is not installed. Add anthropic to requirements."
            ) from exc

        if self.client is None:
            self.client = anthropic.Anthropic(api_key=self.api_key)

        return self.client

    @staticmethod
    def _normalise_decision(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ClaudeDecisionError("Claude response is not a JSON object")

        action = str(payload.get("action", "HOLD")).upper()
        if action not in {"BUY", "SELL", "HOLD"}:
            raise ClaudeDecisionError(f"Invalid Claude action: {action}")

        confidence = float(payload.get("confidence", 0.0) or 0.0)
        confidence = max(0.0, min(1.0, confidence))

        market_condition = str(payload.get("market_condition", "UNCERTAIN")).upper()
        if market_condition not in {"BULLISH", "BEARISH", "SIDEWAYS", "UNCERTAIN"}:
            market_condition = "UNCERTAIN"

        reason = str(payload.get("reason", "Claude returned no explanation.") or "Claude returned no explanation.")

        return {
            "action": action,
            "confidence": confidence,
            "reason": reason,
            "market_condition": market_condition,
        }

    def _build_prompt(self, market_data: Dict[str, Any]) -> str:
        candles = market_data.get("candles", [])
        latest = candles[-1] if candles else {}
        recent = candles[-30:] if candles else []

        return f"""
You are a disciplined crypto trading analyst.

Return only valid JSON with this exact schema:
{
  "action": "BUY|SELL|HOLD",
  "confidence": 0.0-1.0,
  "reason": "short explanation",
  "market_condition": "BULLISH|BEARISH|SIDEWAYS|UNCERTAIN"
}

Rules:
- Do not claim future certainty.
- Prefer HOLD if the market is unclear.
- Consider cost, spread, trend, momentum, RSI, and volatility.
- Do not choose BUY or SELL just because of one weak signal.
- The Python layer decides whether an order is allowed.

Market data:
Firi ETHNOK:
- bid: {market_data.get('firi_bid', 0.0)}
- ask: {market_data.get('firi_ask', 0.0)}
- spread: {market_data.get('firi_spread', 0.0)}
- current_price: {market_data.get('firi_price', 0.0)}

Binance ETHUSDT:
- latest_price: {market_data.get('binance_price', 0.0)}
- ema9: {market_data.get('ema9', 0.0)}
- ema21: {market_data.get('ema21', 0.0)}
- rsi14: {market_data.get('rsi14', 0.0)}
- change_5m: {market_data.get('change_5m', 0.0)}
- change_15m: {market_data.get('change_15m', 0.0)}
- change_30m: {market_data.get('change_30m', 0.0)}
- volume: {market_data.get('volume', 0.0)}

Recent candles:
{json.dumps(recent, ensure_ascii=False)[:4000]}

Account:
- NOK_balance: {market_data.get('nok_balance', 0.0)}
- ETH_balance: {market_data.get('eth_balance', 0.0)}
- active_position: {str(market_data.get('active_position', False)).lower()}
- entry_price: {market_data.get('entry_price', 0.0)}
- position_age_seconds: {market_data.get('position_age_seconds', 0.0)}

Cost context:
- estimated_round_trip_cost: {market_data.get('estimated_round_trip_cost', 0.0)}
- take_profit_percent: {market_data.get('take_profit_percent', 1.0)}
- stop_loss_percent: {market_data.get('stop_loss_percent', 0.6)}

Return only JSON.
"""

    def get_decision(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.dry_run:
            return {
                "action": "HOLD",
                "confidence": 0.0,
                "reason": "DRY RUN: Claude analysis skipped.",
                "market_condition": "UNCERTAIN",
            }

        try:
            client = self._get_sdk()
            if client is None:
                return {
                    "action": "HOLD",
                    "confidence": 0.0,
                    "reason": "Claude unavailable in dry-run mode.",
                    "market_condition": "UNCERTAIN",
                }

            response = client.messages.create(
                model=self.model,
                max_tokens=400,
                temperature=0.2,
                system=(
                    "You are a conservative crypto analyst. Return only valid JSON. "
                    "Do not explain outside the JSON."
                ),
                messages=[
                    {"role": "user", "content": self._build_prompt(market_data)}
                ],
            )

            text = ""
            for block in getattr(response, "content", []) or []:
                if getattr(block, "type", None) == "text":
                    text += getattr(block, "text", "")

            if not text:
                raise ClaudeDecisionError("Claude response was empty")

            raw = text.strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.lower().startswith("json"):
                    raw = raw[4:].strip()

            payload = json.loads(raw)
            return self._normalise_decision(payload)
        except Exception as exc:  # pragma: no cover - defensive, should not crash bot
            return {
                "action": "HOLD",
                "confidence": 0.0,
                "reason": f"CLAUDE API ERROR: {type(exc).__name__}: {exc}",
                "market_condition": "UNCERTAIN",
            }
