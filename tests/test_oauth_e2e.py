import asyncio
import base64
import hashlib
import json
from urllib.parse import parse_qs, urlencode, urlparse

import aiohttp
from aiohttp import web

from custom_components.smartcamper_suite.auth import CredentialStore
from custom_components.smartcamper_suite.oauth2 import NakordoniOAuth2Implementation


def test_synthetic_oauth_pkce_refresh_revoke_and_restart():
    async def run():
        codes: dict[str, str] = {}
        refresh_tokens = {"synthetic-refresh"}
        refresh_calls = 0

        async def authorize(request):
            query = request.query
            assert query["code_challenge_method"] == "S256"
            code = "synthetic-code"
            codes[code] = query["code_challenge"]
            location = f"{query['redirect_uri']}?{urlencode({'code': code, 'state': query['state']})}"
            raise web.HTTPFound(location=location)

        async def token(request):
            nonlocal refresh_calls
            data = await request.post()
            if data.get("grant_type") == "authorization_code":
                verifier = data["code_verifier"]
                challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
                if codes.get(data.get("code")) != challenge:
                    return web.json_response({"error": "invalid_grant"}, status=400)
                return web.json_response({"access_token": "synthetic-access", "refresh_token": "synthetic-refresh", "expires_in": 60})
            refresh_calls += 1
            if data.get("refresh_token") not in refresh_tokens:
                return web.json_response({"error": "invalid_grant"}, status=400)
            return web.json_response({"access_token": f"synthetic-refresh-{refresh_calls}", "refresh_token": data["refresh_token"], "expires_in": 60})

        app = web.Application()
        app.router.add_get("/authorize", authorize)
        app.router.add_post("/token", token)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            verifier = NakordoniOAuth2Implementation.generate_code_verifier()
            challenge = NakordoniOAuth2Implementation.compute_code_challenge(verifier)
            redirect_uri = "http://127.0.0.1/callback"
            async with aiohttp.ClientSession() as session:
                auth_url = f"http://127.0.0.1:{port}/authorize?{urlencode({'response_type': 'code', 'client_id': 'public-client', 'redirect_uri': redirect_uri, 'state': 'synthetic-state', 'code_challenge': challenge, 'code_challenge_method': 'S256'})}"
                auth_response = await session.get(auth_url, allow_redirects=False)
                callback = parse_qs(urlparse(auth_response.headers["Location"]).query)
                token_response = await session.post(f"http://127.0.0.1:{port}/token", data={"grant_type": "authorization_code", "code": callback["code"][0], "code_verifier": verifier, "redirect_uri": redirect_uri})
                token = await token_response.json()
                assert token["access_token"] == "synthetic-access"

                store = CredentialStore()
                store.put_oauth("nkd", "nakordoni", token["access_token"], set(), "expired", token["refresh_token"])

                async def refresh(old_token):
                    response = await session.post(f"http://127.0.0.1:{port}/token", data={"grant_type": "refresh_token", "refresh_token": old_token})
                    payload = await response.json()
                    if response.status != 200:
                        raise ValueError(payload["error"])
                    return payload["access_token"], "future"

                refreshed = await asyncio.gather(
                    store.async_refresh_oauth("nkd", refresh),
                    store.async_refresh_oauth("nkd", refresh),
                )
                assert refreshed == ["synthetic-refresh-1", "synthetic-refresh-1"]
                assert refresh_calls == 1

                restarted = CredentialStore()
                restarted.put_oauth("nkd", "nakordoni", refreshed[0], set(), "future", "synthetic-refresh")
                assert restarted.get_secret("nkd") == "synthetic-refresh-1"
                refresh_tokens.clear()
                with_error = False
                try:
                    await restarted.async_refresh_oauth("nkd", refresh)
                except ValueError as err:
                    with_error = str(err) == "invalid_grant"
                assert with_error is True
                assert restarted.get_secret("nkd") == "synthetic-refresh-1"
                assert "synthetic-refresh-1" not in json.dumps(restarted.status("nkd"))
        finally:
            await runner.cleanup()

    asyncio.run(run())
