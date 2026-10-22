from __future__ import annotations

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
