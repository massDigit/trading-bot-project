"""Read-only probe of the IG demo PRICE stream for CS.D.EURUSD.CEFM.IP.

Logs in on the demo REST API (locked URL), refuses to go further if the
session reports an environment other than DEMO (`reroutingEnvironment`, observed
empty on the demo on 2026-10-27) or a streaming host outside the demo allowlist
(fail closed: a new host requires review), then subscribes to
`PRICE:{account}:{epic}` (MERGE, adapter `Pricing`) for a few seconds and
reports whether TIMESTAMP, DLG_FLAG and DELAY are delivered.

Network exchanges: REST `POST /session` then `DELETE /session` (read-only
allowlist, demo URL locked); towards Lightstreamer, only the control requests
of the client library (session creation, subscription, unsubscription,
disconnection). `sendMessage` is never called, so no order can be sent. The
legacy MARKET subscription is not used. Tokens and account identifiers are masked.

The "receipt - TIMESTAMP" gap it prints is NOT a network latency: it mixes IG
publication delay, transport, client processing and the unmeasured offset
between the local clock and IG's clock.

Usage: uv run ig-price-probe [--seconds 20]
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol, TextIO

import httpx

from forex_bot.config import ConfigError, Settings, load_settings
from forex_bot.diagnostic import EXIT_BLOCKING, EXIT_CONFIG, EXIT_OK, EXIT_PARTIAL, explain
from forex_bot.ig_client import IGApiError, IGDemoReadOnlyClient, ReadOnlyViolation
from forex_bot.instruments import EURUSD_MINI_EPIC
from forex_bot.market import DEFAULT_MAX_QUOTE_AGE
from forex_bot.redaction import Redactor
from forex_bot.streaming import (
    PRICE_ADAPTER,
    PRICE_FIELDS,
    PRICE_MODE,
    PriceTracker,
    UpdateOutcome,
    connection_state_from_lightstreamer,
    parse_ig_timestamp,
    price_item,
)

DEFAULT_SECONDS = 20
# `lightstreamerEndpoint` host returned by the demo POST /session, observed on 2026-10-27.
DEMO_STREAMING_HOSTS = frozenset({"demo-apd.marketdatasystems.com"})


class StreamListener(Protocol):
    def on_status(self, status: str) -> None: ...
    def on_update(self, changed: Mapping[str, str | None], is_snapshot: bool) -> None: ...
    def on_lost_updates(self, count: int) -> None: ...
    def on_error(self, origin: str, code: int, message: str) -> None: ...


class PriceStreamer(Protocol):
    def start(self, endpoint: str, user: str, password: str, item: str, listener: StreamListener) -> None: ...
    def stop(self) -> None: ...


class LightstreamerPriceStreamer:
    """Wrapper around the official Lightstreamer client: connect, subscribe, unsubscribe, disconnect; no sendMessage."""

    def __init__(self) -> None:
        self._client: Any = None
        self._subscription: Any = None

    def start(self, endpoint: str, user: str, password: str, item: str, listener: StreamListener) -> None:
        from lightstreamer.client import LightstreamerClient, Subscription

        client = LightstreamerClient(endpoint, None)
        client.connectionDetails.setUser(user)
        client.connectionDetails.setPassword(password)
        client.addListener(_ClientListener(listener))
        subscription = Subscription(PRICE_MODE, [item], list(PRICE_FIELDS))
        subscription.setDataAdapter(PRICE_ADAPTER)
        subscription.setRequestedSnapshot("yes")
        subscription.addListener(_SubscriptionListener(listener))
        self._client, self._subscription = client, subscription
        client.subscribe(subscription)
        client.connect()

    def stop(self) -> None:
        if self._client is not None:
            if self._subscription is not None:
                self._client.unsubscribe(self._subscription)
            self._client.disconnect()


class _ClientListener:
    def __init__(self, listener: StreamListener) -> None:
        self._listener = listener

    def onStatusChange(self, status: str) -> None:  # Lightstreamer callback names
        self._listener.on_status(status)

    def onServerError(self, code: int, message: str) -> None:
        self._listener.on_error("serveur", code, message)


class _SubscriptionListener:
    def __init__(self, listener: StreamListener) -> None:
        self._listener = listener

    def onItemUpdate(self, update: Any) -> None:
        self._listener.on_update(dict(update.getChangedFields()), bool(update.isSnapshot()))

    def onItemLostUpdates(self, item_name: str, item_pos: int, lost_updates: int) -> None:
        self._listener.on_lost_updates(lost_updates)

    def onSubscriptionError(self, code: int, message: str) -> None:
        self._listener.on_error("abonnement", code, message)


class ProbeListener:
    """Feeds a PriceTracker from Lightstreamer callbacks (other threads) and keeps statistics."""

    def __init__(self, clock: Callable[[], datetime]) -> None:
        self.tracker = PriceTracker()
        self.lock = threading.Lock()
        self._clock = clock
        self.statuses: list[str] = []
        self.outcomes: Counter[str] = Counter()
        self.snapshots = 0
        self.fields_seen: set[str] = set()
        self.timestamps_seen = 0
        self.lags: list[float] = []  # local receipt - IG TIMESTAMP, seconds
        self.lost_updates = 0
        self.errors: list[str] = []

    def on_status(self, status: str) -> None:
        with self.lock:
            self.statuses.append(status)
            self.tracker.on_connection(connection_state_from_lightstreamer(status))

    def on_update(self, changed: Mapping[str, str | None], is_snapshot: bool) -> None:
        with self.lock:
            received_at = self._clock()
            self.snapshots += is_snapshot
            self.fields_seen.update(name for name, value in changed.items() if value not in (None, ""))
            if ig_time := parse_ig_timestamp(changed.get("TIMESTAMP")):
                self.timestamps_seen += 1
                self.lags.append((received_at - ig_time).total_seconds())
            outcome = self.tracker.on_update(changed, received_at)
            self.outcomes[outcome] += 1

    def on_lost_updates(self, count: int) -> None:
        with self.lock:
            self.lost_updates += count
            self.tracker.on_lost_updates()

    def on_error(self, origin: str, code: int, message: str) -> None:
        with self.lock:
            self.errors.append(f"erreur {origin} {code} : {message}")


def run(
    settings_loader: Callable[[], Settings] = load_settings,
    streamer: PriceStreamer | None = None,
    transport: httpx.BaseTransport | None = None,
    stream: TextIO = sys.stdout,
    seconds: float = DEFAULT_SECONDS,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    redactor = Redactor()

    def out(line: str = "") -> None:
        print(redactor.mask(line), file=stream)

    out("=== Sonde du flux PRICE IG démo — lecture seule, aucun ordre ===")
    try:
        settings = settings_loader()
    except ConfigError as exc:
        out(f"Configuration : {exc}")
        return EXIT_CONFIG
    redactor.register_many(settings.secrets())

    streamer = streamer or LightstreamerPriceStreamer()
    listener = ProbeListener(clock)
    try:
        with IGDemoReadOnlyClient(settings.api_key, redactor, transport=transport) as client:
            session = client.login(settings.username, settings.password)
            account_id = str(session.get("currentAccountId") or "")
            redactor.register("compte", account_id)
            redactor.register("client", str(session.get("clientId") or ""))
            environment = session.get("reroutingEnvironment")
            endpoint = str(session.get("lightstreamerEndpoint") or "")
            host = httpx.URL(endpoint).host if endpoint else ""
            out(f"Environnement de session : {environment if environment is not None else 'non renseigné'}")
            out(f"Point d'accès Lightstreamer : {host or 'absent'}")
            if environment not in (None, "DEMO"):
                out("ARRÊT : la session indique un environnement autre que DEMO, aucun abonnement n'est ouvert.")
                return EXIT_BLOCKING
            if not endpoint.startswith("https://") or host not in DEMO_STREAMING_HOSTS or not account_id:
                out("ARRÊT : point d'accès Lightstreamer hors liste démo ou non HTTPS, ou compte courant inconnu.")
                return EXIT_BLOCKING
            item = price_item(account_id, EURUSD_MINI_EPIC)
            out(f"Abonnement : {item} ; mode {PRICE_MODE} ; adaptateur {PRICE_ADAPTER}")
            out(f"Champs demandés : {', '.join(PRICE_FIELDS)}")
            out(f"Écoute pendant {seconds:.0f} s…")
            streamer.start(endpoint, account_id, client.lightstreamer_password(), item, listener)
            try:
                sleep(seconds)
                with listener.lock:  # evaluated while still connected
                    lines = _quote_lines(listener.tracker, clock())
            finally:
                streamer.stop()
    except (IGApiError, httpx.HTTPError, ReadOnlyViolation) as exc:
        out(f"ÉCHEC : {explain(exc)}")
        return EXIT_BLOCKING
    except Exception as exc:  # report masked, never the raw traceback
        out(f"ÉCHEC inattendu : {type(exc).__name__} : {exc}")
        return EXIT_BLOCKING

    with listener.lock:
        return _report(listener, lines, out)


def _quote_lines(tracker: PriceTracker, now: datetime) -> list[str]:
    lines = []
    quote = tracker.quote()
    if quote is not None and quote.quote_time_utc is not None:
        lines.append(f"Dernière cotation : bid {quote.bid} / offer {quote.offer}")
        lines.append(f"  heure IG (TIMESTAMP, UTC)   : {quote.quote_time_utc.isoformat(timespec='milliseconds')}")
        if quote.received_at_utc is not None:
            lines.append(f"  réception locale (UTC)      : {quote.received_at_utc.isoformat(timespec='milliseconds')}")
        lines.append(
            f"  DLG_FLAG {tracker.dealing_flag} ; DELAY {quote.delayed if quote.delayed is not None else 'absent'}"
        )
    lines.append(
        f"Conditions d'entrée sur ce flux (seuil expérimental {DEFAULT_MAX_QUOTE_AGE.total_seconds():.0f} s), "
        f"évaluées avant déconnexion à {now.isoformat(timespec='milliseconds')} :"
    )
    lines += [f"  - {reason}" for reason in tracker.blockers(now) or ["aucun blocage lié à la cotation"]]
    return lines


def _report(listener: ProbeListener, lines: list[str], out: Callable[[str], None]) -> int:
    out("")
    out(f"États de connexion observés : {' -> '.join(listener.statuses) or 'aucun'}")
    total = sum(listener.outcomes.values())
    out(
        f"Mises à jour : {total} (instantanés {listener.snapshots}) ; acceptées "
        f"{listener.outcomes[UpdateOutcome.ACCEPTED]}, hors ordre {listener.outcomes[UpdateOutcome.OUT_OF_ORDER]}, "
        f"malformées {listener.outcomes[UpdateOutcome.MALFORMED]}, "
        f"hors plage {listener.outcomes[UpdateOutcome.OUT_OF_RANGE]}, hors connexion "
        f"{listener.outcomes[UpdateOutcome.NOT_CONNECTED]}, pertes signalées {listener.lost_updates}"
    )
    out(f"Champs reçus avec une valeur : {', '.join(sorted(listener.fields_seen)) or 'aucun'}")
    for error in listener.errors:
        out(f"  ! {error}")
    if listener.lags:
        lags = sorted(listener.lags)
        out(
            f"Écart apparent réception locale - TIMESTAMP IG : min {lags[0]:+.3f} s, "
            f"médiane {lags[len(lags) // 2]:+.3f} s, max {lags[-1]:+.3f} s"
        )
        out("  (pas une latence : inclut le décalage, non mesuré, entre l'horloge locale et celle d'IG)")
    for line in lines:
        out(line)
    out("")
    if listener.errors and not total:
        out("RÉSULTAT : abonnement PRICE refusé ou en erreur.")
        return EXIT_BLOCKING
    if listener.timestamps_seen:
        out(f"RÉSULTAT : TIMESTAMP reçu ({listener.timestamps_seen} mise(s) à jour).")
        return EXIT_OK
    out("RÉSULTAT : aucun TIMESTAMP reçu (marché fermé, droits insuffisants ou durée trop courte).")
    return EXIT_PARTIAL


def main() -> None:
    parser = argparse.ArgumentParser(description="Sonde du flux PRICE IG démo (lecture seule).")
    parser.add_argument("--seconds", type=float, default=DEFAULT_SECONDS)
    args = parser.parse_args()
    sys.exit(run(seconds=max(1.0, min(args.seconds, 120.0))))


if __name__ == "__main__":
    main()
