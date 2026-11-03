"""Quality state of a candle as knowable at a decision instant (S1 sheet §10.1).

Starts from the decision-time status written at the candle's close (`complete_at_close`,
`flags_at_close`), then adds what became knowable since, up to the decision instant only: a gap
that started before the close and has since exceeded the threshold. The retrospective audit
(`complete`, `flags`) is never read.
"""

from __future__ import annotations

import bisect
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any

from forex_bot.history.bars import Gap, overlaps_gap
from forex_bot.history.calendar import trading_day


class BarState(StrEnum):
    OK = "OK"
    DOCUMENTED_CLOSURE = "FERMETURE_DOCUMENTÉE"
    PARTIAL_COVERAGE = "COUVERTURE_PARTIELLE"
    UNEXPLAINED_INTERRUPTION = "INTERRUPTION_INEXPLIQUÉE"

    @property
    def usable(self) -> bool:
        return self in (BarState.OK, BarState.DOCUMENTED_CLOSURE)


# Flags a documented special closure may explain on its own (no gap, no invalid tick).
CLOSURE_ONLY_FLAGS = ("jour férié probable", "H1 incomplète dans la bougie")


class GapIndex:
    """Gaps sorted by start, to find those that touch a candle without scanning them all."""

    def __init__(self, gaps: Sequence[Gap]) -> None:
        self._gaps = sorted(gaps, key=lambda g: g.start_utc)
        self._starts = [g.start_utc for g in self._gaps]

    def touching(self, start: datetime, end: datetime) -> list[Gap]:
        """Gaps that started before `end` and end after `start`."""
        upper = bisect.bisect_left(self._starts, end)
        return [g for g in self._gaps[:upper] if g.end_utc > start]


def bar_state(
    bar: dict[str, Any],
    decision_utc: datetime,
    gaps: GapIndex,
    threshold: timedelta,
    documented_closures: frozenset[date] = frozenset(),
) -> BarState:
    """State of `bar` with the information available at `decision_utc` (never later)."""
    start, end = bar["start_utc"], bar["end_utc"]
    if decision_utc < end:
        raise ValueError("bougie non clôturée à l'instant de décision")
    flags = list(bar["flags_at_close"])
    nearby = [g for g in gaps.touching(start, end) if g.start_utc < decision_utc]
    if overlaps_gap(start, end, nearby, threshold, known_until=decision_utc) and not any(
        f.startswith("trou de cotation") for f in flags
    ):
        flags.append("trou de cotation connu à l'instant de décision")
    if not flags and bar["complete_at_close"]:
        return BarState.OK
    if any(f.startswith("hors couverture") for f in flags):
        return BarState.PARTIAL_COVERAGE
    if trading_day(start) in documented_closures and all(f.startswith(CLOSURE_ONLY_FLAGS) for f in flags):
        return BarState.DOCUMENTED_CLOSURE
    return BarState.UNEXPLAINED_INTERRUPTION
