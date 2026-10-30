"""Declared formats of raw files. A file that does not match its declared format is rejected.

`DUKASCOPY_TICKS_CSV` describes a tick CSV exported MANUALLY from the Dukascopy
"Historical Data Export" web tool. Dukascopy publishes no specification of this
CSV: header, date format, time zone and volume unit below are UNCONFIRMED and
must be checked against the first real export (see docs/DATA.md). The time
convention is DECLARED (column name "Gmt time"), not documented by Dukascopy;
the quality report only checks its consistency with the weekly schedule.

`JFOREX_SDK_TICKS_CSV` is written by tools/jforex-ticks (JForex SDK, demo server):
one row per `ITick`, `time_ms` = `ITick.getTime()` unchanged. The SDK documents no unit
or zone for it; milliseconds since 1970-01-01 UTC is the reading the quality report
checks against the weekly schedule (consistency, not proof).
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path


class FormatError(Exception):
    """The raw file does not match its declared format. Message includes the line number."""


@dataclass(frozen=True)
class TickCsvFormat:
    name: str
    header: tuple[str, ...]
    time_column: str
    time_format: str  # strptime format, or EPOCH_MS for integer milliseconds since 1970-01-01 UTC
    time_zone: str  # declared zone of the timestamps; only "UTC" is accepted
    bid_column: str
    ask_column: str
    bid_volume_column: str
    ask_volume_column: str
    price_decimals: int  # maximum decimals accepted for prices
    volume_note: str


DUKASCOPY_TICKS_CSV = TickCsvFormat(
    name="dukascopy-ticks-csv-v1",
    header=("Gmt time", "Ask", "Bid", "AskVolume", "BidVolume"),  # UNCONFIRMED
    time_column="Gmt time",
    time_format="%d.%m.%Y %H:%M:%S.%f",  # UNCONFIRMED (e.g. 07.03.2019 00:00:00.123)
    time_zone="UTC",  # declared by the column name and the "GMT" export option; not documented
    bid_column="Bid",
    ask_column="Ask",
    bid_volume_column="BidVolume",
    ask_volume_column="AskVolume",
    price_decimals=5,
    volume_note="volume du fournisseur, unité non confirmée ; ce n'est pas un volume de marché",
)

EPOCH_MS = "epoch-ms"

JFOREX_SDK_TICKS_CSV = TickCsvFormat(
    name="jforex-sdk-ticks-csv-v1",
    header=("time_ms", "ask", "bid", "ask_volume", "bid_volume"),
    time_column="time_ms",
    time_format=EPOCH_MS,
    time_zone="UTC",  # reading of ITick.getTime(); not documented by the SDK
    bid_column="bid",
    ask_column="ask",
    bid_volume_column="bid_volume",
    ask_volume_column="ask_volume",
    price_decimals=5,
    volume_note="volume du fournisseur (ITick.getBidVolume/getAskVolume), unité non documentée ; "
    "ce n'est pas un volume de marché",
)

FORMATS = {fmt.name: fmt for fmt in (DUKASCOPY_TICKS_CSV, JFOREX_SDK_TICKS_CSV)}


@dataclass(frozen=True)
class RawTick:
    row: int  # 1-based line number in the raw file (header = line 1)
    ts_utc: datetime
    bid: Decimal
    ask: Decimal
    bid_volume: float | None
    ask_volume: float | None


def _price(text: str, decimals: int, line: int, column: str) -> Decimal:
    try:
        value = Decimal(text.strip())
    except InvalidOperation as exc:
        raise FormatError(f"ligne {line} : {column} illisible ({text!r})") from exc
    if not value.is_finite():
        raise FormatError(f"ligne {line} : {column} non fini ({text!r})")
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > decimals:
        raise FormatError(f"ligne {line} : {column} a plus de {decimals} décimales ({text!r})")
    return value


def _volume(text: str, line: int, column: str) -> float | None:
    if text.strip() == "":
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise FormatError(f"ligne {line} : {column} illisible ({text!r})") from exc


def _timestamp(text: str, time_format: str, line: int) -> datetime:
    try:
        if time_format == EPOCH_MS:
            if not text.strip().isdigit():
                raise ValueError(text)
            millis = int(text)
            return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=millis)
        return datetime.strptime(text.strip(), time_format).replace(tzinfo=UTC)
    except (ValueError, OverflowError) as exc:
        raise FormatError(f"ligne {line} : horodatage illisible ({text!r})") from exc


def read_ticks(path: Path, fmt: TickCsvFormat) -> Iterator[RawTick]:
    """Parse every row. Prices are NOT validated here (non-positive or crossed quotes are kept and
    flagged later by the quality report): only the format is checked."""
    if fmt.time_zone != "UTC":
        raise FormatError(f"fuseau déclaré {fmt.time_zone} non pris en charge : UTC attendu")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None or tuple(h.strip() for h in header) != fmt.header:
            raise FormatError(f"ligne 1 : en-tête {header!r} différent du format déclaré {list(fmt.header)}")
        index = {name: i for i, name in enumerate(fmt.header)}
        for line, row in enumerate(reader, start=2):
            if len(row) != len(fmt.header):
                raise FormatError(f"ligne {line} : {len(row)} colonnes, {len(fmt.header)} attendues")
            ts = _timestamp(row[index[fmt.time_column]], fmt.time_format, line)
            yield RawTick(
                row=line,
                ts_utc=ts,
                bid=_price(row[index[fmt.bid_column]], fmt.price_decimals, line, fmt.bid_column),
                ask=_price(row[index[fmt.ask_column]], fmt.price_decimals, line, fmt.ask_column),
                bid_volume=_volume(row[index[fmt.bid_volume_column]], line, fmt.bid_volume_column),
                ask_volume=_volume(row[index[fmt.ask_volume_column]], line, fmt.ask_volume_column),
            )
