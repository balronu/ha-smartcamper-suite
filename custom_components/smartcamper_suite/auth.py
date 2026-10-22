from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CredentialState(StrEnum):
    NOT_CONFIGURED = "not_configured"
    VALID = "valid"
    EXPIRED = "expired"
    MISSING_PERMISSION = "missing_permission"


@dataclass(slots=True)
class CredentialRecord:
    credential_id: str
    provider: str
    kind: str
    state: CredentialState = CredentialState.NOT_CONFIGURED
    scopes: frozenset[str] = frozenset()
    expires_at: str | None = None
    _secret: str | None = field(default=None, repr=False)

    def public_status(self) -> dict[str, Any]:
        return {"credential_id": self.credential_id, "provider": self.provider,
                "kind": self.kind, "state": self.state.value,
                "scopes": sorted(self.scopes), "expires_at": self.expires_at}


class CredentialStore:
    """In-memory testable credential layer; HA Secret storage is the adapter boundary."""

    def __init__(self) -> None:
        self._records: dict[str, CredentialRecord] = {}
        self._refresh_locks: dict[str, Any] = {}

    def put_api_key(self, credential_id: str, provider: str, api_key: str) -> None:
        if not api_key.strip():
            raise ValueError("api key must not be empty")
        self._records[credential_id] = CredentialRecord(credential_id, provider, "api_key", CredentialState.VALID, _secret=api_key)

    def put_oauth(self, credential_id: str, provider: str, access_token: str, scopes: set[str], expires_at: str | None = None) -> None:
        if not access_token.strip():
            raise ValueError("access token must not be empty")
        self._records[credential_id] = CredentialRecord(credential_id, provider, "oauth2", CredentialState.VALID, frozenset(scopes), expires_at, access_token)

    def get_secret(self, credential_id: str) -> str | None:
        record = self._records.get(credential_id)
        return record._secret if record else None

    def status(self, credential_id: str) -> dict[str, Any]:
        return self._records[credential_id].public_status()

    def remove(self, credential_id: str) -> None:
        self._records.pop(credential_id, None)

    def replace_api_key(self, credential_id: str, provider: str, api_key: str) -> None:
        """Rotate one shared provider key without changing its identity."""
        self.put_api_key(credential_id, provider, api_key)

    def records(self) -> list[dict[str, Any]]:
        """Return secret-free credential status records."""
        return [record.public_status() for record in self._records.values()]

    def load_api_keys(self, records: object) -> None:
        """Restore config-entry credentials without exposing them to diagnostics."""
        if not isinstance(records, dict):
            return
        for credential_id, value in records.items():
            if not isinstance(value, dict):
                continue
            provider = value.get("provider")
            api_key = value.get("api_key")
            if isinstance(credential_id, str) and isinstance(provider, str) and isinstance(api_key, str):
                self.put_api_key(credential_id, provider, api_key)

    def export_api_keys(self) -> dict[str, dict[str, str]]:
        """Return config-entry storage data; callers must never log this value."""
        return {
            record.credential_id: {"provider": record.provider, "api_key": record._secret or ""}
            for record in self._records.values()
            if record.kind == "api_key" and record._secret
        }

    async def async_refresh_oauth(
        self,
        credential_id: str,
        refresh: Callable[[str], Awaitable[tuple[str, str | None]]],
    ) -> str:
        """Refresh once for concurrent callers and never expose the token."""
        record = self._records.get(credential_id)
        if record is None or record.kind != "oauth2" or not record._secret:
            raise ValueError("OAuth credential is not configured")
        previous_token = record._secret
        lock = self._refresh_locks.setdefault(credential_id, asyncio.Lock())
        async with lock:
            current = self._records.get(credential_id)
            if current is None or not current._secret:
                raise ValueError("OAuth credential is not configured")
            if current._secret != previous_token and current.expires_at:
                return current._secret
            token, expires_at = await refresh(current._secret)
            self._records[credential_id] = CredentialRecord(
                credential_id, current.provider, "oauth2", CredentialState.VALID,
                current.scopes, expires_at, token,
            )
            return token
