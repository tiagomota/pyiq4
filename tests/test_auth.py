"""Tests for pyiq4.auth — OIDC implicit flow."""

import re
from pathlib import Path

import aiohttp
import pytest
from aioresponses import aioresponses

from pyiq4.auth import _extract_token, authenticate
from pyiq4.exceptions import RainbirdAuthError, RainbirdConnectionError

_FIXTURES = Path(__file__).parent / "fixtures"
# Use a regex so the random state/nonce query params don't break URL matching.
_LOGIN_URL_RE = re.compile(
    r"https://iq4server\.rainbird\.com/coreidentityserver/Account/Login.*"
)
_AUTH_REDIRECT = "https://iq4.rainbird.com/auth.html#access_token=MY_JWT_TOKEN&token_type=Bearer"


def _login_html() -> str:
    return (_FIXTURES / "login_page.html").read_text()


class TestExtractToken:
    def test_extracts_from_fragment(self):
        url = "https://iq4.rainbird.com/auth.html#access_token=ABC123&state=xyz"
        assert _extract_token(url) == "ABC123"

    def test_does_not_extract_from_query_string(self):
        url = "https://example.com/?access_token=XYZ&other=1"
        assert _extract_token(url) is None  # fragment only, no leading #

    def test_returns_none_when_absent(self):
        assert _extract_token("https://example.com/") is None

    def test_handles_encoded_token(self):
        url = "https://iq4.rainbird.com/auth.html#access_token=ey.abc.def"
        assert _extract_token(url) == "ey.abc.def"


class TestAuthenticate:
    async def test_happy_path(self):
        with aioresponses() as m:
            # Step 1: GET login page
            m.get(_LOGIN_URL_RE, status=200, body=_login_html())
            # Step 2: POST credentials → redirect with token in Location
            m.post(
                _LOGIN_URL_RE,
                status=302,
                headers={"Location": _AUTH_REDIRECT},
            )

            async with aiohttp.ClientSession() as session:
                token = await authenticate(session, "user@example.com", "password123")

        assert token == "MY_JWT_TOKEN"

    async def test_waf_block_on_get(self):
        with aioresponses() as m:
            m.get(_LOGIN_URL_RE, status=202, body="")

            async with aiohttp.ClientSession() as session:
                with pytest.raises(RainbirdAuthError) as exc_info:
                    await authenticate(session, "user@example.com", "pass")

        assert exc_info.value.status_code == 202
        assert "WAF" in str(exc_info.value)

    async def test_missing_antiforgery_token(self):
        with aioresponses() as m:
            m.get(_LOGIN_URL_RE, status=200, body="<html><body>No token here</body></html>")

            async with aiohttp.ClientSession() as session:
                with pytest.raises(RainbirdAuthError) as exc_info:
                    await authenticate(session, "user@example.com", "pass")

        assert "RequestVerificationToken" in str(exc_info.value)

    async def test_no_location_header_after_post(self):
        with aioresponses() as m:
            m.get(_LOGIN_URL_RE, status=200, body=_login_html())
            # Bad credentials — no redirect
            m.post(_LOGIN_URL_RE, status=200, body=_login_html())

            async with aiohttp.ClientSession() as session:
                with pytest.raises(RainbirdAuthError) as exc_info:
                    await authenticate(session, "user@example.com", "wrongpass")

        assert "No Location header" in str(exc_info.value)

    async def test_network_error_on_get(self):
        with aioresponses() as m:
            m.get(_LOGIN_URL_RE, exception=aiohttp.ClientConnectionError("connection refused"))

            async with aiohttp.ClientSession() as session:
                with pytest.raises(RainbirdConnectionError):
                    await authenticate(session, "user@example.com", "pass")
