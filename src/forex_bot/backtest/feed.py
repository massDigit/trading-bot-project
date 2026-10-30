"""Tick feed used for execution and stop monitoring, and the classification of quote silences.

The engine only reads ticks in chronological order, never ahead of the instant it simulates:
`first_after` serves executions decided at an instant, `ticks_until` advances the simulation.
"""

from __future__ import annotations

import bisect
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from forex_bot.history.bars import Gap
from forex_bot.history.calendar import (
    ONE_HOUR,
    MarketState,
    expected_open_minutes,
    floor_hour,
    market_state,
    require_utc,
    trading_day,
)


@dataclass(frozen=True)
class Tick:
    ts_utc: datetime
    bid: Decimal
    ask: Decimal


class TickFeed:
    """Ticks sorted by time (ties keep their input order)."""

    def __init__(self, ticks: Sequence[Tick]) -> None:
        self._ticks = sorted(ticks, key=lambda t: t.ts_utc)
        self._times = [t.ts_utc for t in self._ticks]

    def __len__(self) -> int:
        return len(self._ticks)

    def __getitem__(self, index: int) -> Tick:
        return self._ticks[index]

    def index_after(self, instant: datetime) -> int:
        """Index of the first tick strictly after `instant` (len(self) if none)."""
        return bisect.bisect_right(self._times, require_utc(instant))

    def last_before(self, instant: datetime) -> Tick | None:
        """Last tick strictly before `instant`: a tick stamped exactly at it opens the next candle."""
        index = bisect.bisect_left(self._times, require_utc(instant))
        return self._ticks[index - 1] if index else None

    def ticks_between(self, start_index: int, until: datetime) -> Iterator[tuple[int, Tick]]:
        """Ticks from `start_index` with ts <= `until`."""
        index = start_index
        while index < len(self._ticks) and self._ticks[index].ts_utc <= until:
            yield index, self._ticks[index]
            index += 1

    def gaps(self, threshold: timedelta) -> list[Gap]:
        """Silences longer than `threshold` between consecutive ticks (same definition as the quality report)."""
        return [
            Gap(a.ts_utc, b.ts_utc, expected_open_minutes(a.ts_utc, b.ts_utc))
            for a, b in zip(self._ticks, self._ticks[1:], strict=False)
            if b.ts_utc - a.ts_utc > threshold
        ]


class Silence(StrEnum):
    NONE = "NONE"  # no silence longer than the threshold
    KNOWN_CLOSURE = "KNOWN_CLOSURE"  # weekly closure or documented special closure, little open time
    UNEXPLAINED = "UNEXPLAINED"  # open time without quotes, or an undocumented probable holiday


def classify_silence(
    start: datetime, end: datetime, threshold: timedelta, documented_closures: frozenset[date] = frozenset()
) -> Silence:
    """Class of the silence between two consecutive ticks (docs/strategies/S1_DONCHIAN.md §10.5).

    A probable holiday counts as a known closure only if its trading day is in
    `documented_closures` (closure established by a cited source); otherwise it is unexplained.
    """
    if end - start <= threshold:
        return Silence.NONE
    if expected_open_minutes(start, end) * 60 > threshold.total_seconds():
        return Silence.UNEXPLAINED
    hour = floor_hour(start)
    while hour < end:
        moment = max(hour, start)
        if market_state(moment) is MarketState.PROBABLE_HOLIDAY and trading_day(moment) not in documented_closures:
            return Silence.UNEXPLAINED
        hour += ONE_HOUR
    return Silence.KNOWN_CLOSURE
