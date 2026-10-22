from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from time import monotonic
from typing import Any


class ProviderError(RuntimeError):
    pass


@dataclass(slots=True)
class RateLimit:
    limit: int | None = None
    remaining: int | None = None
    reset_at: float | None = None


@dataclass(slots=True)
class ServicePolicy:
    timeout: float = 15.0
    cache_ttl: float = 0.0
    rate_limit: RateLimit = field(default_factory=RateLimit)


class ApiClient:
    """Offline-ready transport boundary. It never performs a request by itself."""

    def __init__(self, transport: Any = None, policies: dict[str, ServicePolicy] | None = None) -> None:
        self.transport = transport
        self.policies = policies or {}
        self._cache: dict[str, tuple[float, Any]] = {}

    async def request(self, service_key: str, method: str, url: str, **kwargs: Any) -> Any:
        policy = self.policies.get(service_key, ServicePolicy())
        cached = self._cache.get(url)
        now = monotonic()
        if cached and policy.cache_ttl > 0 and cached[0] > now:
            return cached[1]
        if self.transport is None:
            raise ProviderError("live transport is disabled in Phase 2A")
        try:
            result = await asyncio.wait_for(self.transport(method, url, **kwargs), policy.timeout)
        except TimeoutError as err:
            raise ProviderError(f"timeout calling {service_key}") from err
        except Exception as err:
            raise ProviderError(f"provider request failed for {service_key}") from err
        if policy.cache_ttl > 0:
            self._cache[url] = (now + policy.cache_ttl, result)
        return result
