"""Request windows of the JForex IHistory adapter (tools/jforex-ticks, Java). No network access here:
this module is the tested reference of the rule the Java adapter applies.

Documented (JForex Javadoc, IHistory.getTicks / readTicks): the `to` bound is inclusive
("If there is tick with time equals to the time in `to` parameter then it will be loaded as well").
The wiki says "Both from and to times are inclusive"; the Javadoc does not state it for `from`.

Rule, valid whether `from` is inclusive or exclusive: to cover the half-open period
[start, end) in milliseconds, request [start - 1, end - 1] and keep only ticks with
start <= time < end. Ticks are filtered by TIME only, never de-duplicated by value:
distinct ticks sharing a timestamp are all kept, and consecutive windows never share
a millisecond, so no tick at a boundary is duplicated or lost.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TickWindow:
    start_ms: int  # inclusive bound of the period we want
    end_ms: int  # exclusive bound of the period we want
    request_from_ms: int  # value passed as `from`
    request_to_ms: int  # value passed as `to` (inclusive per Javadoc)

    def keep(self, tick_time_ms: int) -> bool:
        return self.start_ms <= tick_time_ms < self.end_ms


def tick_windows(start_ms: int, end_ms: int, chunk_ms: int = 3_600_000) -> list[TickWindow]:
    """Consecutive, non-overlapping windows covering [start_ms, end_ms) by chunks (default one hour)."""
    if end_ms <= start_ms or chunk_ms <= 0:
        raise ValueError("période vide ou découpage invalide")
    windows = []
    cursor = start_ms
    while cursor < end_ms:
        stop = min(cursor + chunk_ms, end_ms)
        windows.append(TickWindow(cursor, stop, cursor - 1, stop - 1))
        cursor = stop
    return windows
