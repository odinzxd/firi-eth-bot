import os

from firi_client import FiriClient


def test_firi_client_allows_missing_credentials_in_dry_run(monkeypatch):
    monkeypatch.delenv("FIRI_API_KEY", raising=False)
    monkeypatch.delenv("FIRI_CLIENT_ID", raising=False)
    monkeypatch.delenv("FIRI_SECRET_KEY", raising=False)
    monkeypatch.setenv("DRY_RUN", "true")

    client = FiriClient()

    assert client is not None
