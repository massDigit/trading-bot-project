"""Time conventions: candle anchoring, weekly market closure and evaluation partitions.

Working configuration (proposals, see docs/DATA.md and ASSUMP-015 / ASSUMP-016)
-------------------------------------------------------------------------------
- Storage and computation are in UTC.
- H1 candles start on every UTC hour. New York's offset to UTC is a whole
  number of hours, so H1 boundaries are the same in UTC and New York time.
- H4 and D1 candles are anchored on the "New York close": the trading day
  runs from 17:00 to 17:00 America/New_York; H4 candles start at 17:00,
  21:00, 01:00, 05:00, 09:00 and 13:00 New York time. In UTC these
  boundaries move by one hour when US daylight saving time changes.
- Weekly closure (schedule used to tell normal closures from missing data):
  Friday 17:00 to Sunday 17:00 America/New_York. US clock changes happen on
  Sunday at 02:00 local time, inside this closure, so no H4 or D1 candle
  straddles a clock change. Sunday evening quotes belong to Monday's
  trading day: there is no Sunday D1 candle.
- 25 December and 1 January are flagged as probable holidays, never
  silently treated as normal closures.
These choices are a working configuration, not an IG or Dukascopy convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
TRADING_DAY_START = time(17, 0)  # New York local time
H4_SLOTS_PER_DAY = 6
ONE_HOUR = timedelta(hours=1)


class Timeframe(StrEnum):
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


def require_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("date sans fuseau : UTC attendu")
    return moment.astimezone(UTC)


def floor_hour(moment: datetime) -> datetime:
    return require_utc(moment).replace(minute=0, second=0, microsecond=0)


def trading_day(moment: datetime) -> date:
    """New York trading day containing `moment` (a day starts at 17:00 New York the evening before)."""
    local = require_utc(moment).astimezone(NEW_YORK)
    return (local + timedelta(hours=24 - TRADING_DAY_START.hour)).date()


def trading_day_start_utc(day: date) -> datetime:
    """UTC instant at which trading day `day` starts (17:00 New York on the previous calendar day)."""
    local = datetime.combine(day - timedelta(days=1), TRADING_DAY_START, tzinfo=NEW_YORK)
    return local.astimezone(UTC)


def candle_start(moment: datetime, timeframe: Timeframe) -> datetime:
    """UTC start of the candle of `timeframe` containing `moment`."""
    moment = require_utc(moment)
    if timeframe is Timeframe.H1:
        return floor_hour(moment)
    day = trading_day(moment)
    start = trading_day_start_utc(day)
    if timeframe is Timeframe.D1:
        return start
    hours = int((floor_hour(moment) - start) / ONE_HOUR)
    return start + timedelta(hours=4 * (hours // 4))


def candle_end(start: datetime, timeframe: Timeframe) -> datetime:
    """UTC end (exclusive) of the candle starting at `start`."""
    start = require_utc(start)
    if timeframe is Timeframe.H1:
        return start + ONE_HOUR
    if timeframe is Timeframe.H4:
        return start + 4 * ONE_HOUR
    return trading_day_start_utc(trading_day(start) + timedelta(days=1))


class MarketState(StrEnum):
    OPEN = "OPEN"
    WEEKLY_CLOSURE = "WEEKLY_CLOSURE"
    PROBABLE_HOLIDAY = "PROBABLE_HOLIDAY"


def market_state(moment: datetime) -> MarketState:
    """Expected state of the EUR/USD market under the working schedule."""
    day = trading_day(moment)
    if day.weekday() >= 5:  # trading days Saturday and Sunday do not exist: Fri 17:00 -> Sun 17:00 NY
        return MarketState.WEEKLY_CLOSURE
    if (day.month, day.day) in {(12, 25), (1, 1)}:
        return MarketState.PROBABLE_HOLIDAY
    return MarketState.OPEN


def expected_open_hours(start: datetime, end: datetime) -> list[datetime]:
    """UTC hour starts in [start, end) during which the market is expected to be open."""
    hour = floor_hour(start)
    if hour < require_utc(start):
        hour += ONE_HOUR
    hours = []
    while hour < require_utc(end):
        if market_state(hour) is MarketState.OPEN:
            hours.append(hour)
        hour += ONE_HOUR
    return hours


# ----------------------------------------------------------------- evaluation partitions


class Partition(StrEnum):
    DEVELOPMENT = "DEVELOPMENT"  # 2015-2021: development and training
    VALIDATION = "VALIDATION"  # 2022-2023: validation of candidates and selector
    FINAL_TEST = "FINAL_TEST"  # 2024-2025: reserved, opened only after the system is frozen
    OUTSIDE = "OUTSIDE"


@dataclass(frozen=True)
class PartitionRange:
    partition: Partition
    start: datetime
    end: datetime  # exclusive


# Cahier des charges §9 "Découpage proposé" (conditioned on data coverage).
PARTITIONS = (
    PartitionRange(Partition.DEVELOPMENT, datetime(2015, 1, 1, tzinfo=UTC), datetime(2022, 1, 1, tzinfo=UTC)),
    PartitionRange(Partition.VALIDATION, datetime(2022, 1, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)),
    PartitionRange(Partition.FINAL_TEST, datetime(2024, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)),
)


def partitions_touched(start: datetime, end: datetime) -> set[Partition]:
    start, end = require_utc(start), require_utc(end)
    if end <= start:
        raise ValueError("période vide ou inversée")
    touched = {p.partition for p in PARTITIONS if start < p.end and p.start < end}
    covered = sum(
        ((min(end, p.end) - max(start, p.start)) for p in PARTITIONS if start < p.end and p.start < end),
        timedelta(0),
    )
    if covered < end - start:
        touched.add(Partition.OUTSIDE)
    return touched
