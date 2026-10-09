"""Exchange rates from open.er-api.com (free, no API key), cached in memory.

All rates are relative to USD; converting A -> B is amount / rate[A] * rate[B].
If a refresh fails and an older table exists, the old table is used and the
result is marked `stale` so the user can be told.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from bot.config import RATES_API_URL

log = logging.getLogger(__name__)


class RatesUnavailableError(Exception):
    """Raised when no exchange rates could be obtained at all."""


class UnknownCurrencyError(Exception):
    """Raised when a currency code is not supported by the rates provider."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Conversion:
    """Result of a conversion, including the rate used and its freshness."""

    amount: float
    source: str
    target: str
    result: float
    rate: float  # 1 source = rate target
    updated_at: datetime
    stale: bool


class RatesClient:
    """Fetches and caches the USD-based rate table."""

    def __init__(self, ttl_seconds: int, http: httpx.AsyncClient | None = None):
        self._ttl = ttl_seconds
        self._http = http or httpx.AsyncClient(timeout=15)
        self._rates: dict[str, float] = {}
        self._updated_at: datetime | None = None
        self._fetched_monotonic = 0.0

    async def _fetch(self) -> None:
        resp = await self._http.get(RATES_API_URL)
        resp.raise_for_status()
        data = resp.json()
        if data.get("result") != "success":
            raise RatesUnavailableError(f"Rates API error: {data.get('error-type')}")
        self._rates = {k.upper(): float(v) for k, v in data["rates"].items()}
        self._updated_at = datetime.fromtimestamp(data["time_last_update_unix"], tz=UTC)
        self._fetched_monotonic = time.monotonic()
        log.info("Fetched %d exchange rates (updated %s)", len(self._rates), self._updated_at)

    async def _ensure_fresh(self) -> bool:
        """Refresh if the cache expired. Returns True if the data in use is stale."""
        if self._rates and time.monotonic() - self._fetched_monotonic < self._ttl:
            return False
        try:
            await self._fetch()
            return False
        except (httpx.HTTPError, RatesUnavailableError, KeyError, ValueError) as e:
            if self._rates:
                log.warning("Rates refresh failed, using cached table: %s", e)
                return True
            raise RatesUnavailableError(str(e)) from e

    async def supported(self) -> set[str]:
        """Return the set of supported ISO currency codes."""
        await self._ensure_fresh()
        return set(self._rates)

    async def convert(self, amount: float, source: str, target: str) -> Conversion:
        """Convert `amount` from `source` to `target` currency.

        Raises:
            UnknownCurrencyError: if either code is not supported.
            RatesUnavailableError: if no rates could be fetched.
        """
        stale = await self._ensure_fresh()
        for code in (source, target):
            if code not in self._rates:
                raise UnknownCurrencyError(code)
        rate = self._rates[target] / self._rates[source]
        assert self._updated_at is not None
        return Conversion(
            amount=amount,
            source=source,
            target=target,
            result=amount * rate,
            rate=rate,
            updated_at=self._updated_at,
            stale=stale,
        )

    async def aclose(self) -> None:
        await self._http.aclose()
