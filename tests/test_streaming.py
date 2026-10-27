"""PRICE stream state and read-only probe. No network: Lightstreamer and IG are simulated."""

from __future__ import annotations

import io
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from typing import Any

import httpx
import pytest

from forex_bot import diagnostic, price_probe
from forex_bot.config import Settings
from forex_bot.instruments import TRADEABLE
from forex_bot.price_probe import StreamListener
from forex_bot.streaming import (
    PRICE_ADAPTER,
    PRICE_FIELDS,
    ConnectionState,
    PriceTracker,
    UpdateOutcome,
    connection_state_from_lightstreamer,
    parse_ig_timestamp,
    price_item,
)

NOW = datetime(2026, 10, 27, 12, 0, 0, tzinfo=UTC)


def ms(moment: datetime) -> str:
    return str(int(moment.timestamp() * 1000))


def full(
    at: datetime, bid: str = "1.11498", ask: str = "1.11508", flag: str = "DEAL", delay: str = "0"
) -> dict[str, str]:
    return {"BIDPRICE1": bid, "ASKPRICE1": ask, "TIMESTAMP": ms(at), "DLG_FLAG": flag, "DELAY": delay}


def connected() -> PriceTracker:
    tracker = PriceTracker()
    tracker.on_connection(ConnectionState.CONNECTED)
    return tracker


def test_timestamp_is_utc_milliseconds() -> None:
    assert parse_ig_timestamp("1792929600123") == datetime(2026, 10, 25, 12, 0, 0, 123000, tzinfo=UTC)
    assert parse_ig_timestamp("12:00:01") is None
    assert parse_ig_timestamp(None) is None


def test_full_update_gives_fresh_tradeable_quote() -> None:
    tracker = connected()
    assert tracker.on_update(full(NOW - timedelta(seconds=1)), NOW) is UpdateOutcome.ACCEPTED
    quote = tracker.quote()
    assert quote is not None
    assert (quote.bid, quote.offer, quote.market_status, quote.delayed) == (
        D("1.11498"),
        D("1.11508"),
        TRADEABLE,
        False,
    )
    assert quote.quote_time_utc == NOW - timedelta(seconds=1)  # IG time
    assert quote.received_at_utc == NOW  # local time, kept separately
    assert tracker.blockers(NOW) == []


def test_partial_messages_are_merged_and_incomplete_state_blocks() -> None:
    tracker = connected()
    tracker.on_update({"BIDPRICE1": "1.11498", "TIMESTAMP": ms(NOW)}, NOW)
    assert tracker.quote() is None
    assert tracker.blockers(NOW) == ["cotation PRICE incomplète (ASKPRICE1, DLG_FLAG)"]
    tracker.on_update({"ASKPRICE1": "1.11508", "DLG_FLAG": "DEAL", "DELAY": "0"}, NOW)
    assert tracker.blockers(NOW) == []
    # a partial update changes only the fields it carries
    tracker.on_update({"BIDPRICE1": "1.11500", "TIMESTAMP": ms(NOW + timedelta(milliseconds=500))}, NOW)
    quote = tracker.quote()
    assert quote is not None and (quote.bid, quote.offer) == (D("1.11500"), D("1.11508"))


def test_out_of_order_update_is_dropped() -> None:
    tracker = connected()
    tracker.on_update(full(NOW, bid="1.11500"), NOW)
    late = full(NOW - timedelta(seconds=3), bid="1.11400")
    assert tracker.on_update(late, NOW + timedelta(seconds=1)) is UpdateOutcome.OUT_OF_ORDER
    quote = tracker.quote()
    assert quote is not None and quote.bid == D("1.11500") and quote.quote_time_utc == NOW
    assert tracker.dropped_out_of_order == 1


def test_reconnection_does_not_refresh_an_old_quote() -> None:
    tracker = connected()
    old = NOW - timedelta(seconds=40)
    tracker.on_update(full(old), old)
    tracker.on_connection(ConnectionState.DISCONNECTED)
    assert tracker.blockers(NOW) == ["flux PRICE non connecté (DISCONNECTED)"]
    assert tracker.quote() is None  # nothing merged across the gap
    tracker.on_connection(ConnectionState.CONNECTED)
    # snapshot re-sent on reconnection, received now, still carrying the old IG time
    assert tracker.on_update(full(old), NOW) is UpdateOutcome.ACCEPTED
    assert "cotation périmée (40 s > 10 s)" in tracker.blockers(NOW)
    # an even older snapshot is refused
    assert tracker.on_update(full(old - timedelta(seconds=1)), NOW) is UpdateOutcome.OUT_OF_ORDER


def test_late_delivery_is_judged_on_ig_time() -> None:
    tracker = connected()
    tracker.on_update(full(NOW - timedelta(seconds=30)), NOW)  # received now, quoted 30 s ago
    assert "cotation périmée (30 s > 10 s)" in tracker.blockers(NOW)


def test_price_change_without_new_timestamp_keeps_previous_ig_time() -> None:
    tracker = connected()
    tracker.on_update(full(NOW - timedelta(seconds=20)), NOW - timedelta(seconds=20))
    tracker.on_update({"BIDPRICE1": "1.11490"}, NOW)
    quote = tracker.quote()
    assert quote is not None and quote.quote_time_utc == NOW - timedelta(seconds=20)
    assert "cotation périmée (20 s > 10 s)" in tracker.blockers(NOW)


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"DLG_FLAG": "EDIT"}, "marché non négociable (DLG_FLAG=EDIT)"),
        ({"DLG_FLAG": "CLOSED"}, "marché non négociable (DLG_FLAG=CLOSED)"),
        ({"DELAY": "1"}, "cotation différée (DELAY=1)"),
        ({"DELAY": "2"}, "indicateur de cotation différée inconnu"),
    ],
)
def test_dealing_flag_and_delay_block(changes: dict[str, str], reason: str) -> None:
    tracker = connected()
    tracker.on_update({**full(NOW), **changes}, NOW)
    assert reason in tracker.blockers(NOW)


def test_dealing_flag_padding_is_ignored() -> None:
    # observed on the demo on 2026-10-27: "DEAL" followed by spaces
    tracker = connected()
    tracker.on_update(full(NOW, flag="DEAL         "), NOW)
    quote = tracker.quote()
    assert quote is not None and quote.market_status == TRADEABLE


def test_missing_delay_keeps_quote_visible_but_blocks() -> None:
    # observed on the demo on 2026-10-27: DELAY never delivered with a value
    tracker = connected()
    tracker.on_update({k: v for k, v in full(NOW).items() if k != "DELAY"}, NOW)
    quote = tracker.quote()
    assert quote is not None and quote.delayed is None
    assert tracker.blockers(NOW) == ["indicateur de cotation différée inconnu"]


def test_malformed_values_are_dropped() -> None:
    tracker = connected()
    tracker.on_update(full(NOW), NOW)
    assert tracker.on_update({"TIMESTAMP": "12:00:01"}, NOW) is UpdateOutcome.MALFORMED
    assert tracker.on_update({"BIDPRICE1": "abc", "TIMESTAMP": ms(NOW)}, NOW) is UpdateOutcome.MALFORMED
    assert tracker.dropped_malformed == 2
    assert tracker.blockers(NOW) == []


def test_lost_updates_block_until_newer_quote() -> None:
    tracker = connected()
    tracker.on_update(full(NOW - timedelta(seconds=2)), NOW)
    tracker.on_lost_updates()
    assert "mises à jour PRICE perdues, en attente d'une cotation plus récente" in tracker.blockers(NOW)
    tracker.on_update({"TIMESTAMP": ms(NOW - timedelta(seconds=1))}, NOW)
    assert tracker.blockers(NOW) == []


def test_update_while_disconnected_is_ignored() -> None:
    tracker = PriceTracker()
    assert tracker.on_update(full(NOW), NOW) is UpdateOutcome.NOT_CONNECTED
    with pytest.raises(ValueError):
        connected().on_update(full(NOW), datetime(2026, 10, 27, 12, 0))


@pytest.mark.parametrize(
    ("status", "state"),
    [
        ("CONNECTED:WS-STREAMING", ConnectionState.CONNECTED),
        ("CONNECTED:HTTP-POLLING", ConnectionState.CONNECTED),
        ("CONNECTED:STREAM-SENSING", ConnectionState.CONNECTING),
        ("CONNECTING", ConnectionState.CONNECTING),
        ("STALLED", ConnectionState.STALLED),
        ("DISCONNECTED:WILL-RETRY", ConnectionState.DISCONNECTED),
        ("DISCONNECTED", ConnectionState.DISCONNECTED),
    ],
)
def test_lightstreamer_status_mapping(status: str, state: ConnectionState) -> None:
    assert connection_state_from_lightstreamer(status) is state


# ---------------------------------------------------------------- probe

API_KEY, USERNAME, PASSWORD = "fake-api-key-0123456789", "fakeuser", "fake-password-xyz"
CST, XST, ACCOUNT, CLIENT_ID = "fake-cst-aaaaaaaa", "fake-xst-bbbbbbbb", "ZZ9AA", "123456789"
ENDPOINT = "https://demo-apd.marketdatasystems.com"


def fake_settings() -> Settings:
    return Settings(api_key=API_KEY, username=USERNAME, password=PASSWORD, account_id=None, search_term="EUR/USD")


def rest(environment: str | None, endpoint: str = ENDPOINT) -> tuple[list[str], httpx.MockTransport]:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/gateway/deal")
        calls.append(f"{request.method} {path}")
        if request.method == "POST" and path == "/session":
            assert json.loads(request.content)["identifier"] == USERNAME
            body = {
                "currentAccountId": ACCOUNT,
                "clientId": CLIENT_ID,
                "lightstreamerEndpoint": endpoint,
                "reroutingEnvironment": environment,
            }
            return httpx.Response(200, headers={"CST": CST, "X-SECURITY-TOKEN": XST}, json=body)
        if request.method == "DELETE" and path == "/session":
            return httpx.Response(204)
        return httpx.Response(404)

    return calls, httpx.MockTransport(handler)


class FakeStreamer:
    def __init__(self, updates: list[tuple[Mapping[str, str | None], bool]]) -> None:
        self.updates = updates
        self.started: dict[str, Any] | None = None
        self.stopped = False

    def start(self, endpoint: str, user: str, password: str, item: str, listener: StreamListener) -> None:
        self.started = {"endpoint": endpoint, "user": user, "password": password, "item": item}
        listener.on_status("CONNECTING")
        listener.on_status("CONNECTED:WS-STREAMING")
        for changed, snapshot in self.updates:
            listener.on_update(changed, snapshot)

    def stop(self) -> None:
        self.stopped = True


def probe(environment: str | None, streamer: FakeStreamer, endpoint: str = ENDPOINT) -> tuple[int, str, list[str]]:
    calls, transport = rest(environment, endpoint)
    output = io.StringIO()
    code = price_probe.run(
        settings_loader=fake_settings,
        streamer=streamer,
        transport=transport,
        stream=output,
        seconds=0,
        clock=lambda: NOW,
        sleep=lambda _: None,
    )
    return code, output.getvalue(), calls


def test_probe_reports_timestamp_and_masks_secrets() -> None:
    streamer = FakeStreamer([(full(NOW - timedelta(seconds=1)), True), ({"BIDPRICE1": "1.11499"}, False)])
    code, text, calls = probe(None, streamer)  # reroutingEnvironment observed empty on the demo
    assert code == diagnostic.EXIT_OK
    assert streamer.started == {
        "endpoint": ENDPOINT,
        "user": ACCOUNT,
        "password": f"CST-{CST}|XST-{XST}",
        "item": price_item(ACCOUNT, "CS.D.EURUSD.CEFM.IP"),
    }
    assert streamer.stopped
    assert calls == ["POST /session", "DELETE /session"]
    assert "TIMESTAMP reçu" in text
    assert "heure IG (TIMESTAMP, UTC)   : 2026-10-27T11:59:59.000+00:00" in text
    assert f"adaptateur {PRICE_ADAPTER}" in text and ", ".join(PRICE_FIELDS) in text
    assert "MARKET:" not in text
    for secret in (API_KEY, USERNAME, PASSWORD, CST, XST, ACCOUNT, CLIENT_ID):
        assert secret not in text


@pytest.mark.parametrize(
    ("environment", "endpoint"),
    [("LIVE", ENDPOINT), (None, "https://apd.marketdatasystems.com"), (None, "http://demo-apd.marketdatasystems.com")],
)
def test_probe_refuses_non_demo_session(environment: str | None, endpoint: str) -> None:
    streamer = FakeStreamer([])
    code, text, calls = probe(environment, streamer, endpoint)
    assert code == diagnostic.EXIT_BLOCKING
    assert streamer.started is None
    assert "ARRÊT" in text
    assert calls == ["POST /session", "DELETE /session"]


def test_probe_without_timestamp_is_partial() -> None:
    code, text, _ = probe("DEMO", FakeStreamer([({"BIDPRICE1": "1.1", "ASKPRICE1": "1.2"}, True)]))
    assert code == diagnostic.EXIT_PARTIAL
    assert "aucun TIMESTAMP reçu" in text
