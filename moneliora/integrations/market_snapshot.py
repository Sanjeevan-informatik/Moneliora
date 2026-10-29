"""An opt-in, market-linked educational paper trading snapshot.

Quotes and FX are fetched from Twelve Data server-side. Prices may be delayed.
The separate fictional trading account is deliberately not rewritten.
"""
from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from moneliora.integrations.market_data import (
    SYMBOLS, QUOTE_TTL, _cached, _provider_call, _valid_price,
    _as_of, latest,
)

import moneliora.integrations.market_data as provider

router = APIRouter(prefix="/api/quotes", tags=["market data"])
SUPPORTED = tuple(SYMBOLS)
FX_PAIR = "USD/EUR"


def fx_quote():
    if not provider.API_KEY:
        raise HTTPException(503, "Market data not configured.")

    def fetch():
        data = _provider_call("/exchange_rate", {"symbol": FX_PAIR})
        try:
            if str(data.get("symbol", "")).upper() != FX_PAIR:
                raise ValueError("FX pair mismatch")
            value = _valid_price(data["rate"])
            if not 0.01 < value < 10:
                raise ValueError("Unreasonable FX value")
            ts = _as_of(data)
            return {
                "pair": FX_PAIR,
                "rate": value,
                "as_of": ts,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "provider": "Twelve Data",
            }
        except (ValueError, TypeError, KeyError, AttributeError):
            raise HTTPException(502, "Invalid USD/EUR rate from provider.") from None

    return _cached("fx:" + FX_PAIR, QUOTE_TTL, fetch)


@router.get("/snapshot")
def snapshot():
    """All-or-nothing quote+FX snapshot, never silently substitute demo prices."""
    if not provider.API_KEY:
        raise HTTPException(503, "Configure a licensed Twelve Data API key to enable live-linked values.")
    # _cached is RLock-protected in a single process; reuses per-symbol cache.
    def gather():
        fx = fx_quote()
        quotes = []
        for ticker in SUPPORTED:
            q = latest(ticker)
            if q["currency"] != "USD":
                raise HTTPException(502, "Only USD-quoted instruments can be converted.")
            # Latest provider quote is not necessarily the exchange's current price.
            quotes.append({
                "symbol": ticker,
                "name": SYMBOLS[ticker],
                "usd": q["price"],
                "eur": round(q["price"] * fx["rate"], 6),
                "percent_change": q["percent_change"],
                "as_of": q["as_of"],
                "exchange": q["exchange"],
                "market_open": q["market_open"],
                "fetched_at": q["fetched_at"],
            })
        return {
            "currency": "EUR",
            "quote_currency": "USD",
            "fx": fx,
            "quotes": quotes,
            "source": "Twelve Data",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "refresh_seconds": QUOTE_TTL,
            "disclaimer": "Provider quotes and FX may be delayed. Not connected to real-money orders.",
        }
    return _cached("portfolio:snapshot:v1", QUOTE_TTL, gather)
