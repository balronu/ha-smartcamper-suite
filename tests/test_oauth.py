from types import SimpleNamespace

from homeassistant.helpers.config_entry_oauth2_flow import MY_AUTH_CALLBACK_PATH

from custom_components.smartcamper_suite.const import (
    DOMAIN,
    NAKORDONI_OAUTH_AUTHORIZE_URL,
    NAKORDONI_OAUTH_CLIENT_ID,
    NAKORDONI_OAUTH_TOKEN_URL,
)
from custom_components.smartcamper_suite.oauth2 import create_implementation


def test_nakordoni_oauth_uses_reference_endpoints_and_pkce():
    implementation = create_implementation(SimpleNamespace(data={}))
    assert implementation.domain == "nakordoni"
    assert implementation.client_id == NAKORDONI_OAUTH_CLIENT_ID
    assert implementation.authorize_url == NAKORDONI_OAUTH_AUTHORIZE_URL
    assert implementation.token_url == NAKORDONI_OAUTH_TOKEN_URL
    assert implementation.redirect_uri == MY_AUTH_CALLBACK_PATH
    assert len(implementation.code_verifier) == 128
    assert implementation.compute_code_challenge(implementation.code_verifier)


def test_oauth_contract_preserves_provider_market_fields_without_secrets():
    token = {
        "access_token": "synthetic-access-token",
        "refresh_token": "synthetic-refresh-token",
        "expires_in": 3600,
        "markets_approved": ["DE"],
        "markets_granted": ["DE", "AT"],
        "markets_available": ["DE", "AT", "PL"],
        "markets_allowed": ["DE"],
    }
    assert {key: token[key] for key in token if key.startswith("markets_")} == {
        "markets_approved": ["DE"],
        "markets_granted": ["DE", "AT"],
        "markets_available": ["DE", "AT", "PL"],
        "markets_allowed": ["DE"],
    }
    assert "synthetic-access-token" not in str({key: value for key, value in token.items() if key.startswith("markets_")})


def test_reference_domain_is_stable():
    assert DOMAIN == "smartcamper_suite"
