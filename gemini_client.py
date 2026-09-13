import json
import os
from typing import Any, Dict, Optional


class GeminiDecisionError(RuntimeError):
    pass


class GeminiClient:
    def __init__(self):
        self.api_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_KEY")
        )
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        self.client = None

    def _get_sdk(self):
        if self.dry_run:
            return None

        if not self.api_key:
            raise GeminiDecisionError(
                "Missing Gemini API key. Set GEMINI_API_KEY or GOOGLE_API_KEY in the environment."
            )

        try:
            from google import genai as google_genai
            if self.client is None:
                self.client = google_genai.Client(api_key=self.api_key)
            return self.client
        except Exception:
            try:
                import google.generativeai as generative_ai
                if self.client is None:
                    generative_ai.configure(api_key=self.api_key)
                    self.client = generative_ai
                return self.client
            except Exception as exc:  # pragma: no cover - runtime dependency guard
                raise GeminiDecisionError(
                    "Gemini SDK is not installed. Install google-generativeai or google-genai."
                ) from exc

    @staticmethod
    def _normalise_decision(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise GeminiDecisionError("Gemini response is not a JSON object")

        action = str(payload.get("action", "HOLD")).upper()
        if action not in {"BUY", "SELL", "HOLD"}:
            raise GeminiDecisionError(f"Invalid Gemini action: {action}")

        confidence = float(payload.get("confidence", 0.0) or 0.0)
        confidence = max(0.0, min(1.0, confidence))

        market_condition = str(payload.get("market_condition", "UNCERTAIN")).upper()
        if market_condition not in {"BULLISH", "BEARISH", "SIDEWAYS", "UNCERTAIN"}:
            market_condition = "UNCERTAIN"

        reason = str(
            payload.get("reason", "Gemini returned no explanation.")
            or "Gemini returned no explanation."
        )

        return {
            "action": action,
            "confidence": confidence,
            "reason": reason,
            "market_condition": market_condition,
        }

    def _build_prompt(self, market_data: Dict[str, Any]) -> str:
        candles = market_data.get("candles", [])
        recent = candles[-30:] if candles else []

        return f"""
You are a conservative crypto trading analyst.

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
- Consider trend, momentum, RSI, EMA9 vs EMA21, Firi spread, and cost.
- Do not force BUY or SELL if the setup is weak or mixed.
- The Python layer decides whether an order is allowed.

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

Recent candles:
{json.dumps(recent, ensure_ascii=False)[:4000]}

Return only JSON.
"""

    def get_decision(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.dry_run:
            return {
                "action": "HOLD",
                "confidence": 0.0,
                "reason": "DRY RUN: Gemini analysis skipped.",
                "market_condition": "UNCERTAIN",
            }

        try:
            sdk = self._get_sdk()
            if sdk is None:
                return {
                    "action": "HOLD",
                    "confidence": 0.0,
                    "reason": "Gemini unavailable in dry-run mode.",
                    "market_condition": "UNCERTAIN",
                }

            try:
                response = sdk.models.generate_content(
                    model=self.model,
                    contents=self._build_prompt(market_data),
                )
                text = getattr(response, "text", None) or ""
            except AttributeError:
                response = sdk.GenerativeModel(self.model).generate_content(
                    self._build_prompt(market_data)
                )
                text = getattr(response, "text", "")

            if not text:
                raise GeminiDecisionError("Gemini response was empty")

            raw = str(text).strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.lower().startswith("json"):
                    raw = raw[4:].strip()

            payload = json.loads(raw)
            return self._normalise_decision(payload)
        except Exception as exc:  # pragma: no cover - defensive
            return {
                "action": "HOLD",
                "confidence": 0.0,
                "reason": f"GEMINI API ERROR: {type(exc).__name__}: {exc}",
                "market_condition": "UNCERTAIN",
            }
