"""OIDC implicit flow authentication for the Rain Bird IQ4 cloud API.

Direct port of auth.go from https://github.com/nickustinov/rainbird-iq4-cli.
"""

from __future__ import annotations

import re
import secrets
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin

import aiohttp

from .exceptions import RainbirdAuthError, RainbirdConnectionError

_AUTH_BASE = "https://iq4server.rainbird.com/coreidentityserver"
_CLIENT_ID = "C5A6F324-3CD3-4B22-9F78-B4835BA55D25"
_REDIRECT_URI = "https://iq4.rainbird.com/auth.html"
_SCOPES = "coreAPI.read coreAPI.write openid profile"
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

_TOKEN_RE = re.compile(r"[#&]access_token=([^&\s]+)")


class _AntiforgeryParser(HTMLParser):
    """Extracts __RequestVerificationToken from hidden input fields."""

    def __init__(self) -> None:
        super().__init__()
        self.token: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "input":
            return
        attr_dict = dict(attrs)
        if attr_dict.get("name") == "__RequestVerificationToken":
            self.token = attr_dict.get("value")


async def authenticate(
    session: aiohttp.ClientSession,
    username: str,
    password: str,
) -> str:
    """Perform OIDC implicit flow and return the JWT access token.

    Flow (mirrors auth.go):
    1. GET the login page; extract ``__RequestVerificationToken`` via html.parser.
    2. POST credentials + token; follow redirects.
    3. Extract ``access_token`` from the ``Location`` header of the last
       redirect before it is followed (the fragment is browser-only, but
       ``aiohttp`` exposes the raw ``Location`` header via ``resp.history``).

    Args:
        session: Caller-managed ``aiohttp.ClientSession``.
        username: Rain Bird account username.
        password: Rain Bird account password.

    Returns:
        JWT access token string (~2 hour lifetime).

    Raises:
        RainbirdAuthError: Bad credentials, AWS WAF 202 block, or token not found.
        RainbirdConnectionError: Network-level failure.
    """
    state = secrets.token_hex(8)
    nonce = secrets.token_hex(8)

    return_url = "/coreidentityserver/connect/authorize/callback?" + urlencode(
        {
            "client_id": _CLIENT_ID,
            "redirect_uri": _REDIRECT_URI,
            "response_type": "id_token token",
            "scope": _SCOPES,
            "state": state,
            "nonce": nonce,
        }
    )
    login_url = f"{_AUTH_BASE}/Account/Login?" + urlencode({"ReturnUrl": return_url})
    headers = {"User-Agent": _USER_AGENT}

    # Step 1: GET login page, extract antiforgery token.
    try:
        async with session.get(login_url, headers=headers) as resp:
            if resp.status == 202:
                raise RainbirdAuthError(
                    "AWS WAF challenge received (HTTP 202). Try again later.",
                    status_code=202,
                )
            if resp.status != 200:
                raise RainbirdAuthError(
                    f"Login page returned unexpected status {resp.status}.",
                    status_code=resp.status,
                )
            html = await resp.text()
    except aiohttp.ClientError as exc:
        raise RainbirdConnectionError(f"Network error fetching login page: {exc}") from exc

    parser = _AntiforgeryParser()
    parser.feed(html)
    if not parser.token:
        raise RainbirdAuthError("Could not find __RequestVerificationToken in login page HTML.")

    # Step 2: POST credentials.
    # We disable automatic redirect-following so we can inspect the Location
    # header ourselves — the access_token lives in the URL fragment, which
    # aiohttp would strip when constructing resp.url after following the redirect.
    form_data = {
        "Username": username,
        "Password": password,
        "ReturnUrl": return_url,
        "__RequestVerificationToken": parser.token,
    }
    try:
        async with session.post(
            login_url,
            data=form_data,
            headers=headers,
            allow_redirects=False,
        ) as resp:
            location = resp.headers.get("Location", "")

        if not location:
            # Some WAF or error responses don't redirect at all.
            raise RainbirdAuthError(
                f"No Location header after login POST (status {resp.status}). "
                "Credentials may be incorrect.",
                status_code=resp.status,
            )

        # Follow redirects manually until we see access_token in a Location.
        # We can't use allow_redirects=True because aiohttp strips the URL
        # fragment (#access_token=...) when building resp.url after following.
        _origin = "https://iq4server.rainbird.com"
        token = _extract_token(location)
        redirect_limit = 10
        while not token and redirect_limit > 0:
            redirect_limit -= 1
            next_url = urljoin(_origin, location)
            async with session.get(next_url, headers=headers, allow_redirects=False) as r:
                location = r.headers.get("Location", "")
                token = _extract_token(location)
                if not location:
                    break

    except aiohttp.ClientError as exc:
        raise RainbirdConnectionError(f"Network error during login: {exc}") from exc

    if not token:
        raise RainbirdAuthError(
            "Could not extract access_token from redirect chain. "
            "Credentials may be incorrect or the account may be locked."
        )

    return token


def _extract_token(s: str) -> str | None:
    """Return the access_token value from a URL string, or None."""
    m = _TOKEN_RE.search(s)
    return m.group(1) if m else None
