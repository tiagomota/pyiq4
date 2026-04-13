from __future__ import annotations


class RainbirdError(Exception):
    """Base exception for all pyiq4 errors."""


class RainbirdConnectionError(RainbirdError):
    """Network/transport level failure (DNS, timeout, SSL)."""


class RainbirdAuthError(RainbirdError):
    """Authentication failed: bad credentials, WAF block, or token expired.

    Attributes:
        status_code: HTTP status code that triggered the error, if any.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class RainbirdAPIError(RainbirdError):
    """API returned an unexpected non-2xx response.

    Attributes:
        status_code: HTTP status code.
        response_body: Raw response text, if available.
    """

    def __init__(self, message: str, status_code: int, response_body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
