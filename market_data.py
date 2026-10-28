"""Server-side Twelve Data adapter for latest quotes and historical charts.

The paper-trading engine intentionally never consumes these prices.
Requires an appropriate market-data DISPLAY/REDISTRIBUTION licence before public use.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
import json
import os
from threading import RLock
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest, urlopen

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/quotes", tags=["market-data"])
API_ROOT = "https://api.twelvedata.com"
API_KEY = os.getenv("MONELIORA_TWELVE_DATA_KEY", "").strip()
# US-listed examples only; quote currencies are the exchange's native currency (USD).
SYMBOLS = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "TSLA": "Tesla",
}
RANGES = {
    "1D": ("5min", 84, 90),
    "5D": ("1h", 70, 300),
    "1M": ("1day", 30, 900),
    "3M": ("1day", 100, 900),
    "1Y": ("1day", 270, 900),
}
QUOTE_TTL = 75
MAX_RESPONSE_BYTES = 175000
CACHE: dict[str, tuple[float, dict]] = {}
LOCK = RLock()


def _required_symbol(symbol: str) -> str:
    ticker = symbol.upper()
    if ticker not in SYMBOLS:
        raise HTTPException(status_code=404, detail="Stock not supported for market data.")
    return ticker


def _require_key() -> None:
    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Live market data not configured. Add a licensed Twelve Data API key on the server.",
        )


def _valid_price(value: object, *, allow_negative: bool = False) -> float:
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("Missing numeric provider price") from exc
    if not isfinite(number) or abs(number) > 1_000_000_000 or (number <= 0 and not allow_negative):
        raise ValueError("Invalid provider price")
    return round(number, 6)


def _provider_call(path: str, parameters: dict[str, str | int]) -> dict:
    _require_key()
    # The only symbols/intervals are server-allowlisted; clients never supply URLs or keys.
    query = urlencode({**parameters, "apikey": API_KEY})
    url = API_ROOT + path + "?" + query
    req = URLRequest(url, headers={"Accept": "application/json", "User-Agent": "Moneliora-market-research/1"})
    try:
        with urlopen(req, timeout=7) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
        if len(content) > MAX_RESPONSE_BYTES:
            raise ValueError("Provider response too large")
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("Unexpected provider response")
        if data.get("status") == "error" or "code" in data and "message" in data:
            # Never forward provider request URL or diagnostic messages (may contain the API key).
            code = data.get("code")
            if code == 429:
                raise HTTPException(status_code=503, detail="Market-data provider rate limit reached. Try later.")
            raise HTTPException(status_code=502, detail="Market-data provider rejected the request.")
        return data
    except HTTPError as exc:
        if exc.code == 429:
            raise HTTPException(status_code=503, detail="Market-data provider rate limit reached. Try later.") from None
        raise HTTPException(status_code=502, detail="Market data could not be loaded.") from None
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Market data temporarily unavailable.") from None


def _cached(key: str, ttl: int, producer):
    now = time.monotonic()
    with LOCK:
        item = CACHE.get(key)
        if item and now - item[0] < ttl:
            return item[1]
        # Lock is also single-process single-flight to conserve API credits under load.
        result = producer()
        if len(CACHE) >= 100:
            CACHE.clear()
        CACHE[key] = (time.monotonic(), result)
        return result


def _as_of(data: dict) -> str | None:
    for field in ("last_quote_at", "timestamp"):
        value = data.get(field)
        try:
            timestamp = int(value)
        except (TypeError, ValueError):
            continue
        if 946684800 <= timestamp <= 4102444800:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    return None


@router.get("/status")
def availability():
    return {
        "configured": bool(API_KEY),
        "provider": "Twelve Data",
        "supported": [{"symbol": s, "name": name} for s, name in SYMBOLS.items()],
        "timeframes": list(RANGES),
        "quote_refresh_seconds": QUOTE_TTL,
        "prices_connected_to_paper_trading": False,
        "note": "Provider prices are not guaranteed to be real-time. Exchange/plan delays and display rights apply.",
    }


@router.get("/latest/{symbol}")
def latest(symbol: str):
    ticker = _required_symbol(symbol)
    _require_key()

    def load():
        data = _provider_call("/quote", {"symbol": ticker})
        try:
            if data.get("symbol", "").upper() != ticker:
                raise ValueError("Quote symbol mismatch")
            currency = str(data["currency"]).upper()
            if currency != "USD":
                raise ValueError("Unexpected instrument currency")
            price = _valid_price(data["close"])
            previous = data.get("previous_close")
            previous_close = _valid_price(previous) if previous not in (None, "") else None
            change = round(price - previous_close, 6) if previous_close is not None else None
            percent = round(change / previous_close * 100, 4) if previous_close else None
            fetched_at = datetime.now(timezone.utc).isoformat()
            as_of = _as_of(data)
            return {
                "symbol": ticker, "name": SYMBOLS[ticker], "provider": "Twelve Data",
                "exchange": str(data.get("exchange", ""))[:80],
                "currency": currency, "price": price, "previous_close": previous_close,
                "change": change, "percent_change": percent,
                "market_open": data.get("is_market_open") if isinstance(data.get("is_market_open"), bool) else None,
                "as_of": as_of, "exchange_datetime": str(data.get("datetime", ""))[:35],
                "fetched_at": fetched_at,
                "refresh_seconds": QUOTE_TTL,
                "label": "Latest provider quote (may be delayed)",
            }
        except (KeyError, TypeError, ValueError, AttributeError):
            raise HTTPException(status_code=502, detail="Invalid quote returned by data provider.") from None

    return _cached("quote:" + ticker, QUOTE_TTL, load)


@router.get("/chart/{symbol}")
def chart(symbol: str, range: str = Query(default="1M", pattern=r"^(1D|5D|1M|3M|1Y)$")):
    ticker = _required_symbol(symbol)
    interval, limit, ttl = RANGES[range]
    _require_key()

    def load():
        data = _provider_call("/time_series", {"symbol": ticker, "interval": interval, "outputsize": limit})
        try:
            meta = data.get("meta", {})
            if not isinstance(meta, dict) or str(meta.get("symbol", "")).upper() != ticker:
                raise ValueError("Chart symbol mismatch")
            currency = str(meta.get("currency", "")).upper()
            if currency != "USD":
                raise ValueError("Unexpected quote currency")
            raw = data.get("values")
            if not isinstance(raw, list) or not raw:
                raise ValueError("No chart points")
            points = []
            for item in raw[:limit]:
                stamp = str(item["datetime"])
                # ISO-like fixed provider dates, no HTML/SQL data ever returned from this field.
                datetime.strptime(stamp[:10], "%Y-%m-%d")
                if len(stamp) > 19 or not all(c in "0123456789- :T" for c in stamp):
                    raise ValueError("Unexpected timestamp format")
                points.append({"time": stamp, "close": _valid_price(item["close"])})
            points.sort(key=lambda x: x["time"])
            return {
                "symbol": ticker, "currency": currency, "provider": "Twelve Data",
                "range": range, "interval": interval, "exchange": str(meta.get("exchange", ""))[:80],
                "timezone": str(meta.get("exchange_timezone", ""))[:60],
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "points": points,
                "note": "Historical closes; may be delayed. Chart data is not used in paper trading.",
            }
        except (TypeError, ValueError, KeyError, AttributeError):
            raise HTTPException(status_code=502, detail="Invalid chart data returned by provider.") from None
    return _cached("chart:" + ticker + ":" + range, ttl, load)
