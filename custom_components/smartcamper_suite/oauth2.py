"""Nakordoni OAuth2-PKCE integration using Home Assistant's helpers."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    MY_AUTH_CALLBACK_PATH,
    LocalOAuth2ImplementationWithPkce,
    async_get_config_entry_implementation,
    async_register_implementation,
)

from .const import (
    DOMAIN,
    NAKORDONI_OAUTH_AUTHORIZE_URL,
    NAKORDONI_OAUTH_CLIENT_ID,
    NAKORDONI_OAUTH_IMPLEMENTATION,
    NAKORDONI_OAUTH_TOKEN_URL,
)


class NakordoniOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """Use the exact public Nakordoni client from the Stable reference."""

    @property
    def redirect_uri(self) -> str:
        return MY_AUTH_CALLBACK_PATH


def create_implementation(hass: HomeAssistant) -> NakordoniOAuth2Implementation:
    return NakordoniOAuth2Implementation(
        hass,
        NAKORDONI_OAUTH_IMPLEMENTATION,
        NAKORDONI_OAUTH_CLIENT_ID,
        NAKORDONI_OAUTH_AUTHORIZE_URL,
        NAKORDONI_OAUTH_TOKEN_URL,
        client_secret="",
    )


def async_register(hass: HomeAssistant) -> None:
    """Register Nakordoni; HA owns authorization-code and refresh storage."""
    async_register_implementation(hass, DOMAIN, create_implementation(hass))


__all__ = [
    "NakordoniOAuth2Implementation",
    "async_get_config_entry_implementation",
    "async_register",
    "create_implementation",
]
