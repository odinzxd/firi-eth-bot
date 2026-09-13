import os

from bot import calculate_trade_costs
from firi_client import FiriClient
from strategy import analyze_market


def test_firi_client_allows_missing_credentials_in_dry_run(monkeypatch):
    monkeypatch.delenv("FIRI_API_KEY", raising=False)
    monkeypatch.delenv("FIRI_CLIENT_ID", raising=False)
    monkeypatch.delenv("FIRI_SECRET_KEY", raising=False)
    monkeypatch.setenv("DRY_RUN", "true")

    client = FiriClient()

    assert client is not None


def test_calculate_trade_costs_includes_spread_and_fees():
    estimate = calculate_trade_costs(1000.0, 970.0)

    assert estimate["spread_percent"] == 3.0
    assert estimate["round_trip_cost_percent"] == 3.2
    assert estimate["break_even_percent"] == 3.2
    assert estimate["take_profit_percent"] == 3.7


def test_bot_reads_test_trade_environment_variables(monkeypatch):
    import importlib

    monkeypatch.setenv("TEST_BUY_NOK", "450")
    monkeypatch.setenv("TEST_SELL_NOK", "300")
    monkeypatch.setenv("TEST_TRADING_ENABLED", "true")
    monkeypatch.setenv("TEST_TRADE_PASSWORD", "secretpw")

    import bot

    importlib.reload(bot)

    assert bot.TEST_BUY_NOK == 450.0
    assert bot.TEST_SELL_NOK == 300.0
    assert bot.TEST_TRADING_ENABLED is True
    assert bot.TEST_TRADE_PASSWORD == "secretpw"


def test_analyze_market_does_not_sell_on_single_bearish_ema():
    prices = [1000.0] * 30 + [995.0] * 10

    signal = analyze_market(
        prices,
        current_position=True,
        entry_price=1000.0,
        take_profit_percent=1.0,
        stop_loss_percent=0.6,
    )

    assert signal.action == "HOLD"
    assert "Trend" in signal.reason or "Holder" in signal.reason


def test_analyze_market_requires_two_bearish_checks_before_trend_exit():
    prices = [1000.0] * 40 + [990.0] * 10

    signal = analyze_market(
        prices,
        current_position=True,
        entry_price=1000.0,
        take_profit_percent=1.0,
        stop_loss_percent=0.6,
        bearish_trend_exit_streak=2,
    )

    assert signal.action == "SELL"
    assert "Trend" in signal.reason or "EMA9" in signal.reason
