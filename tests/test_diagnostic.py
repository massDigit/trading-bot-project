"""Offline tests: IG is simulated with httpx.MockTransport, no network access."""

from __future__ import annotations

import copy
import io
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from ig_fixtures import MARKET_DETAILS

from forex_bot import diagnostic
from forex_bot.config import IG_DEMO_BASE_URL, ConfigError, Settings, load_settings
from forex_bot.ig_client import IGDemoReadOnlyClient, ReadOnlyViolation, is_allowed
from forex_bot.redaction import Redactor

API_KEY = "fake-api-key-0123456789"
USERNAME = "fakeuser"
PASSWORD = "fake-password-xyz"
CST = "fake-cst-token-aaaaaaaa"
XST = "fake-security-token-bbbbbbbb"
XST_ROTATED = "fake-security-token-rotated-cccc"
ACCOUNT_A = "ZZ9AA"
ACCOUNT_B = "ZZ9BB"
CLIENT_ID = "123456789"
ALL_SECRETS = (API_KEY, USERNAME, PASSWORD, CST, XST, XST_ROTATED, ACCOUNT_A, ACCOUNT_B, CLIENT_ID)


def settings(account_id: str | None = None) -> Settings:
    return Settings(
        api_key=API_KEY,
        username=USERNAME,
        password=PASSWORD,
        account_id=account_id,
        search_term="EUR/USD",
    )


def search_result(epic: str, name: str, status: str = "TRADEABLE") -> dict[str, Any]:
    return {"epic": epic, "instrumentName": name, "instrumentType": "CURRENCIES", "expiry": "-", "marketStatus": status}


SEARCH_RESULTS = [
    search_result("CS.D.EURUSD.CEF.IP", "EUR/USD"),
    search_result("CS.D.EURUSD.CEFM.IP", "EUR/USD Mini"),
    search_result("IX.D.SUNEURUSD.CEF.IP", "Weekend EUR/USD", "EDITS_ONLY"),
]


class FakeIG:
    """Records requests and answers like the documented IG endpoints."""

    def __init__(
        self,
        login_status: int = 200,
        login_error: str | None = None,
        market_details: dict[str, Any] | None = None,
    ) -> None:
        self.requests: list[httpx.Request] = []
        self.market_details = market_details if market_details is not None else MARKET_DETAILS
        self.login_status = login_status
        self.login_error = login_error

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert request.url.host == "demo-api.ig.com"
        path = request.url.path.removeprefix("/gateway/deal")
        method = request.method

        if method == "POST" and path == "/session":
            if self.login_status != 200:
                return httpx.Response(self.login_status, json={"errorCode": self.login_error})
            body = json.loads(request.content)
            assert body == {"identifier": USERNAME, "password": PASSWORD, "encryptedPassword": False}
            return httpx.Response(
                200,
                headers={"CST": CST, "X-SECURITY-TOKEN": XST},
                json={
                    "currentAccountId": ACCOUNT_A,
                    "clientId": CLIENT_ID,
                    "currencyIsoCode": "EUR",
                    "dealingEnabled": True,
                    "accounts": [{"accountId": ACCOUNT_A}, {"accountId": ACCOUNT_B}],
                },
            )

        assert request.headers["CST"] == CST
        assert request.headers["X-SECURITY-TOKEN"] in (XST, XST_ROTATED)
        if method == "PUT" and path == "/session":
            assert json.loads(request.content) == {"accountId": ACCOUNT_B}
            return httpx.Response(200, headers={"X-SECURITY-TOKEN": XST_ROTATED}, json={})
        if method == "DELETE" and path == "/session":
            return httpx.Response(204)
        if method == "GET" and path == "/accounts":
            return httpx.Response(
                200,
                json={
                    "accounts": [
                        {
                            "accountId": ACCOUNT_A,
                            "accountName": f"Demo CFD {ACCOUNT_A}",
                            "accountType": "CFD",
                            "currency": "EUR",
                            "status": "ENABLED",
                            "preferred": True,
                            "balance": {
                                "balance": 10000.0,
                                "available": 10000.0,
                                "deposit": 0.0,
                                "profitLoss": 0.0,
                            },
                        },
                        {
                            "accountId": ACCOUNT_B,
                            "accountName": "Demo spread bet",
                            "accountType": "SPREADBET",
                            "currency": "EUR",
                            "status": "ENABLED",
                            "preferred": False,
                            "balance": {
                                "balance": 10000.0,
                                "available": 9000.0,
                                "deposit": 1000.0,
                                "profitLoss": -5.0,
                            },
                        },
                    ]
                },
            )
        if method == "GET" and path == "/markets" and "searchTerm" in request.url.params:
            return httpx.Response(200, json={"markets": SEARCH_RESULTS})
        if method == "GET" and path.startswith("/markets/"):
            assert request.headers["Version"] == "3"
            epic = path.removeprefix("/markets/")
            if epic == "CS.D.EURUSD.CEFM.IP":
                return httpx.Response(200, json=self.market_details)
        return httpx.Response(404, json={"errorCode": "invalid.url"})


def run_diag(fake: FakeIG, cfg: Settings) -> tuple[int, str]:
    stream = io.StringIO()
    code = diagnostic.run(lambda: cfg, transport=httpx.MockTransport(fake), stream=stream)
    return code, stream.getvalue()


def test_full_diagnostic_success_and_no_secret_leak() -> None:
    fake = FakeIG()
    code, output = run_diag(fake, settings())

    assert code == diagnostic.EXIT_OK, output
    assert "balance    : 10000.0" in output
    assert "0.1 POINTS" in output and "minDealSize" in output
    assert "2.0 POINTS" in output
    for secret in ALL_SECRETS:
        assert secret not in output
    methods = [(r.method, r.url.path.removeprefix("/gateway/deal")) for r in fake.requests]
    assert methods[0] == ("POST", "/session")
    assert methods[-1] == ("DELETE", "/session")
    # only the explicitly selected contract is queried; Weekend is excluded
    market_calls = [p for m, p in methods if p.startswith("/markets/")]
    assert market_calls == ["/markets/CS.D.EURUSD.CEFM.IP"]
    assert "IX.D.SUNEURUSD.CEF.IP | Weekend EUR/USD" in output and "[EXCLU]" in output
    # reference allocation, independent from the 10 000 EUR demo balance
    assert "Allocation initiale : 2000 EUR" in output
    assert "Budget indicatif sur l'allocation initiale : 5.00 EUR (information seulement)" in output
    assert "[BLOQUÉ] Entrée / dimensionnement exécutable" in output
    assert "- horodatage de la cotation inconnu" in output
    assert "- fonds propres actualisés du portefeuille du robot indisponibles" in output
    assert "- coût inconnu : commission" in output
    assert "[OK] Vérification du contrat EUR/USD Mini" in output


def test_contract_drift_is_a_failure() -> None:
    drifted = copy.deepcopy(MARKET_DETAILS)
    drifted["instrument"]["contractSize"] = "100000"
    code, output = run_diag(FakeIG(market_details=drifted), settings())
    assert code == diagnostic.EXIT_PARTIAL
    assert "contractSize : attendu 10000, observé 100000" in output
    assert "[ÉCHEC] Vérification du contrat EUR/USD Mini" in output


def test_closed_market_is_a_warning() -> None:
    closed = copy.deepcopy(MARKET_DETAILS)
    closed["snapshot"]["marketStatus"] = "CLOSED"
    code, output = run_diag(FakeIG(market_details=closed), settings())
    assert code == diagnostic.EXIT_PARTIAL
    assert "[AVERTISSEMENT] Vérification du contrat EUR/USD Mini" in output


def test_account_switch_uses_rotated_token() -> None:
    fake = FakeIG()
    code, output = run_diag(fake, settings(account_id=ACCOUNT_B))

    assert code == diagnostic.EXIT_OK, output
    assert "Compte #2 (SPREADBET)" in output
    put = [r for r in fake.requests if r.method == "PUT"]
    assert len(put) == 1
    after_switch = fake.requests[fake.requests.index(put[0]) + 1]
    assert after_switch.headers["X-SECURITY-TOKEN"] == XST_ROTATED
    for secret in ALL_SECRETS:
        assert secret not in output


def test_invalid_credentials_are_explained() -> None:
    fake = FakeIG(login_status=401, login_error="error.security.invalid-details")
    code, output = run_diag(fake, settings())

    assert code == diagnostic.EXIT_BLOCKING
    assert "compte DÉMO" in output
    assert [r.method for r in fake.requests] == ["POST"]  # no logout without session
    for secret in ALL_SECRETS:
        assert secret not in output


def test_unknown_account_id_is_reported() -> None:
    code, output = run_diag(FakeIG(), settings(account_id="NOPE1"))
    assert code == diagnostic.EXIT_PARTIAL
    assert "IG_ACCOUNT_ID ne correspond à aucun compte" in output
    assert "NOPE1" not in output


def test_config_error_sends_nothing() -> None:
    def loader() -> Settings:
        raise ConfigError("Variables manquantes : IG_API_KEY")

    fake = FakeIG()
    stream = io.StringIO()
    code = diagnostic.run(loader, transport=httpx.MockTransport(fake), stream=stream)
    assert code == diagnostic.EXIT_CONFIG
    assert fake.requests == []


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/positions/otc"),
        ("POST", "/workingorders/otc"),
        ("PUT", "/positions/otc/DEAL1"),
        ("DELETE", "/positions/otc"),
        ("GET", "/positions"),
        ("POST", "/markets"),
        ("GET", "/markets/../positions"),
    ],
)
def test_trading_endpoints_are_refused(method: str, path: str) -> None:
    assert not is_allowed(method, path)


def test_client_refuses_non_demo_url_and_forbidden_call() -> None:
    with pytest.raises(ReadOnlyViolation):
        IGDemoReadOnlyClient(API_KEY, Redactor(), base_url="https://api.ig.com/gateway/deal")

    fake = FakeIG()
    client = IGDemoReadOnlyClient(API_KEY, Redactor(), transport=httpx.MockTransport(fake))
    with pytest.raises(ReadOnlyViolation):
        client._request("POST", "/positions/otc", 2, authenticated=False)
    client.close()
    assert fake.requests == []


def test_redactor_masks_registered_and_header_like_values() -> None:
    r = Redactor()
    r.register("IG_API_KEY", API_KEY)
    masked = r.mask(f'key={API_KEY} CST: unknown-token-123 "password": "hunter2"')
    assert API_KEY not in masked
    assert "unknown-token-123" not in masked
    assert "hunter2" not in masked


def test_load_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "IG_API_KEY",
        "IG_USERNAME",
        "IG_PASSWORD",
        "IG_ACCOUNT_ID",
        "IG_BASE_URL",
        "IG_MARKET_SEARCH_TERM",
    ):
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / ".env"

    env.write_text("IG_API_KEY=k\nIG_USERNAME=u\n")
    with pytest.raises(ConfigError, match="IG_PASSWORD"):
        load_settings(env)

    env.write_text("IG_API_KEY=k\nIG_USERNAME=u\nIG_PASSWORD=p\nIG_BASE_URL=https://api.ig.com\n")
    with pytest.raises(ConfigError, match="non autorisées"):
        load_settings(env)

    env.write_text("IG_API_KEY=k\nIG_USERNAME=u\nIG_PASSWORD=p\n")
    s = load_settings(env)
    assert s.base_url == IG_DEMO_BASE_URL
    assert s.search_term == "EUR/USD"
    assert "p" not in repr(s).replace("Settings", "").replace("masqué", "")


def test_default_file_is_env_demo_and_plain_env_is_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("IG_API_KEY", "IG_USERNAME", "IG_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("IG_API_KEY=k\nIG_USERNAME=u\nIG_PASSWORD=p\n")
    with pytest.raises(ConfigError, match=r"\.env\.demo"):
        load_settings()

    (tmp_path / ".env.demo").write_text("IG_API_KEY=k\nIG_USERNAME=u\nIG_PASSWORD=p\n")
    assert load_settings().api_key == "k"
