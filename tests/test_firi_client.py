import os

from bot import calculate_trade_costs
from firi_client import FiriClient


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
