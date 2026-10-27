"""Read-only client for the IG REST API, demo environment only.

Endpoints, versions and fields follow the official IG Labs reference
(https://labs.ig.com/rest-trading-api-reference.html):

- POST   /session            v2  login, returns CST and X-SECURITY-TOKEN headers
- PUT    /session            v1  switch active account (no trading effect)
- DELETE /session            v1  logout
- GET    /accounts           v1  list accounts and balances
- GET    /markets?searchTerm v1  market search
- GET    /markets/{epic}     v3  market details and dealing rules

Every other method/path is refused before any network call: no order,
position or working-order endpoint can be reached through this client.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from forex_bot.config import IG_DEMO_BASE_URL
from forex_bot.redaction import Redactor

_EPIC_PATTERN = r"[A-Za-z0-9._-]+"
_ALLOWED: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("POST", re.compile(r"/session")),
    ("PUT", re.compile(r"/session")),
    ("DELETE", re.compile(r"/session")),
    ("GET", re.compile(r"/accounts")),
    ("GET", re.compile(r"/markets")),
    ("GET", re.compile(rf"/markets/{_EPIC_PATTERN}")),
)

DEFAULT_TIMEOUT_SECONDS = 15.0


class ReadOnlyViolation(Exception):
    """Raised when code tries to call an endpoint outside the read-only allowlist."""


class IGApiError(Exception):
    """HTTP error returned by IG, with the documented `errorCode` when available."""

    def __init__(self, status_code: int, error_code: str | None, method: str, path: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.method = method
        self.path = path
        super().__init__(f"{method} {path} -> HTTP {status_code} ({error_code or 'sans errorCode'})")


def is_allowed(method: str, path: str) -> bool:
    return any(method == m and pattern.fullmatch(path) for m, pattern in _ALLOWED)


class IGDemoReadOnlyClient:
    """Minimal session-aware client. Use as a context manager to guarantee logout."""

    def __init__(
        self,
        api_key: str,
        redactor: Redactor,
        base_url: str = IG_DEMO_BASE_URL,
        transport: httpx.BaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if base_url != IG_DEMO_BASE_URL:
            raise ReadOnlyViolation("Seul l'environnement démo IG est autorisé en V1.")
        self._api_key = api_key
        self._redactor = redactor
        self._cst: str | None = None
        self._security_token: str | None = None
        self.logout_error: Exception | None = None
        self._http = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            follow_redirects=False,  # never forward auth headers to another host
        )

    @property
    def has_session(self) -> bool:
        return self._cst is not None

    # -- context management -------------------------------------------------

    def __enter__(self) -> IGDemoReadOnlyClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        """Log out if needed, then release the connection pool.

        A logout failure is kept in `logout_error` rather than raised, so that it
        never hides the original error of the diagnostic.
        """
        try:
            if self._cst is not None:
                self.logout()
        except (IGApiError, httpx.HTTPError) as exc:
            self.logout_error = exc
        finally:
            self._http.close()

    # -- low level ----------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        version: int,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        if not is_allowed(method, path):
            raise ReadOnlyViolation(f"Appel refusé (hors liste lecture seule) : {method} {path}")

        headers = {
            "X-IG-API-KEY": self._api_key,
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json; charset=UTF-8",
            "Version": str(version),
        }
        if authenticated:
            if self._cst is None or self._security_token is None:
                raise RuntimeError("Session IG non ouverte.")
            headers["CST"] = self._cst
            headers["X-SECURITY-TOKEN"] = self._security_token

        response = self._http.request(method, path, params=params, json=json, headers=headers)

        if response.url.host != "demo-api.ig.com":  # defensive, redirects are disabled
            raise ReadOnlyViolation("Réponse reçue d'un hôte inattendu.")
        if response.is_error:
            raise IGApiError(response.status_code, _error_code(response), method, path)

        # IG may rotate the account token (e.g. after an account switch).
        new_token = response.headers.get("X-SECURITY-TOKEN")
        if new_token and authenticated:
            self._set_security_token(new_token)
        return response

    def _set_security_token(self, token: str) -> None:
        self._security_token = token
        self._redactor.register("X-SECURITY-TOKEN", token)

    # -- endpoints ----------------------------------------------------------

    def login(self, identifier: str, password: str) -> dict[str, Any]:
        """POST /session v2. Stores CST / X-SECURITY-TOKEN; returns the response body."""
        response = self._request(
            "POST",
            "/session",
            2,
            json={"identifier": identifier, "password": password, "encryptedPassword": False},
            authenticated=False,
        )
        cst = response.headers.get("CST")
        token = response.headers.get("X-SECURITY-TOKEN")
        if not cst or not token:
            raise IGApiError(response.status_code, "missing-session-headers", "POST", "/session")
        self._cst = cst
        self._redactor.register("CST", cst)
        self._set_security_token(token)
        body: dict[str, Any] = response.json()
        return body

    def lightstreamer_password(self) -> str:
        """Streaming password documented by IG: "CST-<CST>|XST-<X-SECURITY-TOKEN>" (masked in outputs)."""
        if self._cst is None or self._security_token is None:
            raise RuntimeError("Session IG non ouverte.")
        password = f"CST-{self._cst}|XST-{self._security_token}"
        self._redactor.register("mot de passe Lightstreamer", password)
        return password

    def switch_account(self, account_id: str) -> dict[str, Any]:
        """PUT /session v1 without `defaultAccount`: the default account is left unchanged."""
        body: dict[str, Any] = self._request("PUT", "/session", 1, json={"accountId": account_id}).json()
        return body

    def logout(self) -> None:
        """DELETE /session v1. Tokens are forgotten even if the call fails."""
        try:
            self._request("DELETE", "/session", 1)
        finally:
            self._cst = None
            self._security_token = None

    def get_accounts(self) -> list[dict[str, Any]]:
        """GET /accounts v1."""
        accounts: list[dict[str, Any]] = self._request("GET", "/accounts", 1).json().get("accounts", [])
        return accounts

    def search_markets(self, search_term: str) -> list[dict[str, Any]]:
        """GET /markets?searchTerm= v1."""
        markets: list[dict[str, Any]] = (
            self._request("GET", "/markets", 1, params={"searchTerm": search_term}).json().get("markets", [])
        )
        return markets

    def get_market(self, epic: str) -> dict[str, Any]:
        """GET /markets/{epic} v3 (includes dealingRules, instrument and snapshot)."""
        if not re.fullmatch(_EPIC_PATTERN, epic):
            raise ValueError("Epic invalide.")
        body: dict[str, Any] = self._request("GET", f"/markets/{epic}", 3).json()
        return body


def _error_code(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if isinstance(payload, dict):
        code = payload.get("errorCode")
        return str(code) if code is not None else None
    return None
