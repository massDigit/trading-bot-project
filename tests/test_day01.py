"""DAY_01 engine on synthetic sessions (docs/strategies/DAY_01_LONDON_RANGE.md, ADR-021, ADR-022).

Ticks are written in London wall-clock time and converted through the session date. M5 and M15
come from the same ticks through the real builder, under the DAY_01 convention (silence > 5 min,
empty sub-slot not OK), so that candles and ticks agree. The H4 for the ATR are synthetic: every
true range is 0.00200, hence A = 0.00200 (20 pips) as in the sheet §7. Spread 0.2 pip everywhere.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal as D
from pathlib import Path
from typing import Any

import pytest

from forex_bot.backtest.day01 import (
    ATR_UNAVAILABLE,
    BREAKOUT_DATA,
    CANCELLED_INTERRUPTION,
    DELAYED_LIQUIDATION,
    EXECUTED,
    EXPIRED,
    INVALIDATED,
    LIQUIDATION,
    NO_BREAKOUT,
    NO_SESSION,
    POSITION_OPEN,
    RANGE_INCOMPLETE,
    RANGE_WIDTH,
    RETEST_DATA,
    RETEST_TIMEOUT,
    SIZE_REFUSED,
    UNPLANNED_NIGHT,
    Day01Params,
    london,
)
from forex_bot.backtest.day01_engine import Day01Backtest, Day01Result
from forex_bot.backtest.engine import ResearchConfig
from forex_bot.backtest.explore import RESEARCH_COSTS
from forex_bot.backtest.feed import Tick
from forex_bot.backtest.s2 import GapScenario
from forex_bot.history.calendar import MarketState, Timeframe, candle_end, candle_start, market_state
from forex_bot.history.intraday import DAY01_5MIN, Grid, build_intraday
from forex_bot.history.store import HistoryStore, IngestRequest
from forex_bot.risk import Side

WINTER = date(2019, 2, 12)  # Tuesday, GMT: London = UTC (sheet §7)
SUMMER = date(2019, 7, 9)  # Tuesday, BST: London = UTC + 1
SPREAD = D("0.00002")
C = D("1.13150")  # middle of the range


def at(day: date, hh: int, mm: int, ss: int = 0, ms: int = 0) -> datetime:
    return london(day, time(hh, mm, ss, ms * 1000))


def tick(moment: datetime, bid: str | D) -> Tick:
    b = D(bid)
    return Tick(moment, b, b + SPREAD)


def fill(start: datetime, end: datetime, bid: str | D, step: timedelta = timedelta(seconds=30)) -> list[Tick]:
    out, cursor = [], start
    while cursor < end:
        out.append(tick(cursor, bid))
        cursor += step
    return out


# ---------------------------------------------------------------- sessions of the sheet §7


def range_and_breakout(day: date, breakout_at: tuple[int, int] = (8, 15)) -> list[Tick]:
    """Range RH 1.13250 / RL 1.13050 on [01:00, 08:00); M15 [08:00, 08:15) closes at 1.13262 (no
    breakout); the M15 starting at `breakout_at` closes at 1.13291 > RH + 0.1 A (breakout)."""
    ticks = [tick(at(day, 1, 0), "1.13150"), tick(at(day, 1, 0, 30), "1.13250"), tick(at(day, 1, 1), "1.13050")]
    ticks += fill(at(day, 1, 1, 30), at(day, 8, 0), C)
    ticks += [*fill(at(day, 8, 0), at(day, 8, 14, 59), "1.13200"), tick(at(day, 8, 14, 59), "1.13262")]
    bh, bm = breakout_at
    if (bh, bm) != (8, 15):
        ticks += fill(at(day, 8, 15), at(day, bh, bm), "1.13200")
    end = at(day, bh, bm) + timedelta(minutes=15)
    ticks += [
        *fill(at(day, bh, bm), end - timedelta(seconds=1), "1.13220"),
        tick(end - timedelta(seconds=1), "1.13291"),
    ]
    return ticks


def m5_bar(day: date, hh: int, mm: int, prices: list[str], last_ms: int = 0) -> list[Tick]:
    """One M5 as ticks one minute apart from its start; the last one at mm + 4 min 59 s (+ ms)."""
    out = [tick(at(day, hh, mm + i), p) for i, p in enumerate(prices[:-1])]
    return [*out, tick(at(day, hh, mm + 4, 59, last_ms), prices[-1])]


def example_a(day: date, after: list[Tick] | None = None) -> list[Tick]:
    """Example A: no contact at 08:35, contact at 08:40, confirmation at 08:45 (next M5)."""
    ticks = range_and_breakout(day)
    ticks += m5_bar(day, 8, 30, ["1.13291", "1.13296", "1.13275", "1.13280", "1.13285", "1.13281"])
    ticks += m5_bar(day, 8, 35, ["1.13281", "1.13284", "1.13239", "1.13245", "1.13250", "1.13248"])
    ticks += m5_bar(day, 8, 40, ["1.13248", "1.13266", "1.13241", "1.13255", "1.13257", "1.13259"], last_ms=870)
    if after is None:
        after = [tick(at(day, 8, 45), "1.13258"), tick(at(day, 8, 45, 0, 140), "1.13260")]
        after += fill(at(day, 8, 45, 30), at(day, 10, 12, 31), "1.13300")
        after += [tick(at(day, 10, 12, 31, 405), "1.13370"), *fill(at(day, 10, 13), at(day, 16, 30), "1.13300")]
    return ticks + after


def example_b(day: date, after: list[Tick] | None = None) -> list[Tick]:
    """Example B: contact and confirmation on the same M5 [08:35, 08:40); no target before 16:00."""
    ticks = range_and_breakout(day)
    ticks += m5_bar(day, 8, 30, ["1.13291", "1.13296", "1.13275", "1.13280", "1.13285", "1.13281"])
    ticks += m5_bar(day, 8, 35, ["1.13281", "1.13284", "1.13244", "1.13250", "1.13255", "1.13258"], last_ms=910)
    if after is None:
        after = [tick(at(day, 8, 40, 0, 200), "1.13259"), *fill(at(day, 8, 40, 30), at(day, 16, 0), "1.13300")]
        after += [tick(at(day, 16, 0), "1.13301"), tick(at(day, 16, 0, 30), "1.13305")]
        after += fill(at(day, 16, 1), at(day, 16, 30), "1.13300")
    return ticks + after


def example_c(day: date, after: list[Tick]) -> list[Tick]:
    """Example C: breakout at K = 11:00, confirmation on M5 [11:55, 12:00), last tick 11:59:58.300."""
    ticks = range_and_breakout(day, breakout_at=(10, 45))
    ticks += fill(at(day, 11, 0), at(day, 11, 55), "1.13291")  # above the zone: no contact
    ticks += [tick(at(day, 11, 55 + i), p) for i, p in enumerate(["1.13281", "1.13284", "1.13244", "1.13250"])]
    ticks += [tick(at(day, 11, 59, 58, 300), "1.13258")]
    return ticks + after


# ---------------------------------------------------------------- inputs of the engine


def h4_bars(until: datetime, days: int = 12) -> list[dict[str, Any]]:
    """Expected-open H4 ending by `until`, each with a true range of 0.00200 around C."""
    bars, cursor = [], candle_start(until - timedelta(days=days), Timeframe.H4)
    while (end := candle_end(cursor, Timeframe.H4)) <= until:
        if market_state(cursor) is MarketState.OPEN:
            bars.append(
                {
                    "start_utc": cursor,
                    "end_utc": end,
                    "bid_high": C + D("0.001"),
                    "bid_low": C - D("0.001"),
                    "bid_close": C,
                    "complete_at_close": True,
                    "flags_at_close": [],
                }
            )
        cursor = end
    return bars


def candles(tmp_path: Path, ticks: list[Tick]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """M5 and M15 built from `ticks` by the real builder, one file per UTC day, DAY_01 convention."""
    by_day: dict[date, list[Tick]] = defaultdict(list)
    for t in ticks:
        by_day[t.ts_utc.date()].append(t)
    tmp_path.mkdir(parents=True, exist_ok=True)
    store = HistoryStore(tmp_path / "data")
    for day, rows in sorted(by_day.items()):
        path = tmp_path / f"{day}.csv"
        lines = ["Gmt time,Ask,Bid,AskVolume,BidVolume\n"]
        lines += [
            f"{t.ts_utc:%d.%m.%Y %H:%M:%S}.{t.ts_utc.microsecond // 1000:03d},{t.ask},{t.bid},1,1\n"
            for t in sorted(rows, key=lambda t: t.ts_utc)
        ]
        path.write_text("".join(lines), encoding="utf-8")
        start = datetime.combine(day, time(), tzinfo=UTC)
        store.ingest(
            IngestRequest(
                path, "dukascopy", "EURUSD", "dukascopy-ticks-csv-v1", start, start + timedelta(days=1), start
            )
        )
    built = build_intraday(store, "dukascopy", "EURUSD", convention=DAY01_5MIN)
    return built.bars[Grid.M5], built.bars[Grid.M15]


CONFIG = ResearchConfig(costs=RESEARCH_COSTS)


def run(
    tmp_path: Path,
    ticks: list[Tick],
    day: date,
    *,
    days: int = 1,
    scenario: GapScenario = GapScenario.OBSERVED_ONLY,
    feed: list[Tick] | None = None,
    config: ResearchConfig = CONFIG,
    h4: list[dict[str, Any]] | None = None,
    end_utc: datetime | bool | None = True,
) -> Day01Result:
    m5, m15 = candles(tmp_path, ticks)
    start = london(day, time(0))
    end = london(day + timedelta(days=days), time(0)) if end_utc is True else end_utc
    engine = Day01Backtest(
        m5,
        m15,
        h4_bars(london(day + timedelta(days=days), time(0))) if h4 is None else h4,
        sorted(feed if feed is not None else ticks, key=lambda t: t.ts_utc),
        [],
        Day01Params(),
        config,
        scenario=scenario,
        start_utc=start,
        end_utc=end if isinstance(end, datetime) else None,
    )
    return engine.run()


def kinds(result: Day01Result) -> list[str]:
    return [j.kind for j in result.journal]


# ---------------------------------------------------------------- examples of the sheet §7


@pytest.mark.parametrize("day", [WINTER, SUMMER], ids=["GMT", "BST"])
def test_example_a_is_reproduced_in_london_time_in_winter_and_summer(tmp_path: Path, day: date) -> None:
    result = run(tmp_path, example_a(day), day)
    (session,) = result.sessions
    assert session.abstention is None and session.entry_outcome == EXECUTED
    assert (session.range["rh"], session.range["rl"], session.range["atr"]) == (D("1.13250"), D("1.13050"), D("0.002"))
    assert session.range["frozen_utc"] == at(day, 8, 0)
    assert session.breakout == {"side": "LONG", "k_utc": at(day, 8, 30), "bid_close": D("1.13291")}
    assert session.retest["contact_utc"] == at(day, 8, 35) and session.retest["confirmation_utc"] == at(day, 8, 45)
    decision = session.decision
    assert (decision["p_d"], decision["stop"], decision["target"]) == (D("1.13261"), D("1.13189"), D("1.13369"))
    assert decision["size"] == D("0.6") and decision["deadline_utc"] == at(day, 8, 50)
    (trade,) = result.trades
    # The tick stamped exactly at D (08:45:00.000) never executes: entry at 08:45:00.140, ask 1.13262.
    assert (trade.entry_utc, trade.entry_price) == (at(day, 8, 45, 0, 140), D("1.13262"))
    assert (trade.exit_utc, trade.exit_price, trade.exit_reason) == (at(day, 10, 12, 31, 405), D("1.13370"), "CIBLE")
    # 10.8 pips x 0.6 contract - 0.5 pip slippage, converted at 1/ask and less 0.5 % conversion fee.
    expected = (D("10.8") - D("0.5")) * D("0.6") / D("1.13372") * D("0.995")
    assert abs(trade.net_account - expected) < D("0.000001")
    assert not trade.indeterminate and "financement overnight" not in trade.costs_quote
    if day == SUMMER:  # sheet §7: in BST the freeze is at 07:00 UTC and the liquidation at 15:00 UTC
        assert session.range["frozen_utc"] == datetime(2019, 7, 9, 7, tzinfo=UTC)


def test_example_b_confirms_on_the_contact_candle_and_liquidates_after_16h(tmp_path: Path) -> None:
    result = run(tmp_path, example_b(WINTER), WINTER)
    (session,) = result.sessions
    assert session.retest["contact_utc"] == session.retest["confirmation_utc"] - timedelta(minutes=5)
    assert session.retest["confirmation_utc"] == at(WINTER, 8, 40)
    decision = session.decision
    assert (decision["p_d"], decision["stop"], decision["target"]) == (D("1.13260"), D("1.13194"), D("1.13359"))
    (trade,) = result.trades
    assert (trade.entry_utc, trade.entry_price) == (at(WINTER, 8, 40, 0, 200), D("1.13261"))
    # A tick exactly at 16:00:00.000 does not liquidate: the first one strictly after it does.
    assert (trade.exit_utc, trade.exit_price, trade.exit_reason) == (at(WINTER, 16, 0, 30), D("1.13305"), LIQUIDATION)
    (liquidation,) = result.liquidations
    assert liquidation["delay"] == timedelta(seconds=30) and not liquidation["delayed"]
    assert not liquidation["unplanned_night"] and DELAYED_LIQUIDATION not in kinds(result)


def test_short_side_is_the_mirror_of_example_a(tmp_path: Path) -> None:
    """Prices reflected around 1.13150: bid' = 2 C - ask, ask' = 2 C - bid (the spread is kept)."""
    mirrored = [Tick(t.ts_utc, 2 * C - t.ask, 2 * C - t.bid) for t in example_a(WINTER)]
    result = run(tmp_path, mirrored, WINTER)
    (session,) = result.sessions
    assert session.breakout["side"] == "SHORT" and session.range["rl"] == D("1.13048")
    assert session.retest["contact_utc"] == at(WINTER, 8, 35)
    decision = session.decision
    # Stop above the highest ask of the retest (2 C - 1.13239 = 1.13061) plus 0.25 A; P_D = last bid.
    assert (decision["stop"], decision["p_d"], decision["target"]) == (D("1.13111"), D("1.13039"), D("1.12931"))
    (trade,) = result.trades
    assert (trade.side, trade.entry_price) == (Side.SHORT, D("1.13038"))
    assert (trade.exit_price, trade.exit_reason) == (D("1.12930"), "CIBLE")  # first ask <= target


# ---------------------------------------------------------------- pending entry: expiry and interruption


def test_pending_entry_is_cancelled_when_the_next_tick_reveals_an_interruption(tmp_path: Path) -> None:
    """Last quote 08:44:59.870; the next tick at 08:50:00.000 closes a 5 min 0.13 s silence."""
    after = [tick(at(WINTER, 8, 50), "1.13260"), *fill(at(WINTER, 8, 50, 30), at(WINTER, 16, 30), "1.13300")]
    result = run(tmp_path, example_a(WINTER, after), WINTER)
    (session,) = result.sessions
    assert session.entry_outcome == CANCELLED_INTERRUPTION and result.trades == []
    cancel = next(j for j in result.journal if j.kind == CANCELLED_INTERRUPTION)
    assert cancel.utc == at(WINTER, 8, 50) and "révélé" in cancel.detail
    assert "tentative consommée" in cancel.detail


def test_pending_entry_is_cancelled_before_the_deadline_without_any_tick(tmp_path: Path) -> None:
    after = fill(at(WINTER, 8, 51), at(WINTER, 16, 30), "1.13300")
    result = run(tmp_path, example_a(WINTER, after), WINTER)
    assert result.sessions[0].entry_outcome == CANCELLED_INTERRUPTION and result.trades == []
    cancel = next(j for j in result.journal if j.kind == CANCELLED_INTERRUPTION)
    assert cancel.utc == at(WINTER, 8, 49, 59, 870)  # last quote + 5 min, before the 08:50 deadline


@pytest.mark.parametrize(
    ("next_tick", "outcome"),
    [((8, 50, 0, 0), EXECUTED), ((8, 50, 0, 1), EXPIRED)],
    ids=["tick-at-deadline-executes", "deadline-passes"],
)
def test_quote_exactly_at_d_and_the_deadline(tmp_path: Path, next_tick: tuple[int, ...], outcome: str) -> None:
    """A tick at exactly D counts for the silence; the next one at D + 5 min (exactly 5 min of silence,
    not above the threshold) still executes, one millisecond later the entry has expired."""
    hh, mm, ss, ms = next_tick
    after = [tick(at(WINTER, 8, 45), "1.13258"), tick(at(WINTER, hh, mm, ss, ms), "1.13260")]
    after += fill(at(WINTER, 8, 51), at(WINTER, 16, 30), "1.13300")
    result = run(tmp_path, example_a(WINTER, after), WINTER)
    session = result.sessions[0]
    assert session.entry_outcome == outcome
    if outcome == EXECUTED:
        assert result.trades[0].entry_utc == at(WINTER, 8, 50)
    else:
        assert result.trades == [] and CANCELLED_INTERRUPTION not in kinds(result)
        assert next(j for j in result.journal if j.kind == EXPIRED).utc == at(WINTER, 8, 50)


@pytest.mark.parametrize(
    ("after", "outcome"),
    [
        ([(12, 0, 0, 0), (12, 3, 10, 0)], EXECUTED),
        ([(12, 4, 59, 0)], CANCELLED_INTERRUPTION),
        ([(12, 0, 0, 0), (12, 5, 0, 1)], EXPIRED),
    ],
    ids=["case-1-entry", "case-2-interruption", "case-3-expiry"],
)
def test_example_c_confirmation_at_noon(tmp_path: Path, after: list[tuple[int, ...]], outcome: str) -> None:
    rest = [tick(at(WINTER, *t), "1.13259") for t in after] + fill(at(WINTER, 12, 6), at(WINTER, 16, 30), "1.13300")
    result = run(tmp_path, example_c(WINTER, rest), WINTER)
    (session,) = result.sessions
    assert session.breakout["k_utc"] == at(WINTER, 11, 0)
    assert session.decision["d_utc"] == at(WINTER, 12, 0) and session.decision["deadline_utc"] == at(WINTER, 12, 5)
    assert session.entry_outcome == outcome
    if outcome == EXECUTED:
        assert result.trades[0].entry_utc == at(WINTER, 12, 3, 10)  # the tick at 12:00:00.000 did not execute
    else:
        assert result.trades == []


# ---------------------------------------------------------------- interruptions of an open position


def _gap_after_entry(silence_end: datetime) -> list[Tick]:
    after = [tick(at(WINTER, 8, 45, 0, 140), "1.13260"), *fill(at(WINTER, 8, 45, 30), at(WINTER, 9, 0, 30), "1.13300")]
    after += [
        tick(silence_end, "1.13300"),
        *fill(silence_end + timedelta(seconds=30), at(WINTER, 10, 12, 31), "1.13300"),
    ]
    return [
        *after,
        tick(at(WINTER, 10, 12, 31, 405), "1.13370"),
        *fill(at(WINTER, 10, 13), at(WINTER, 16, 30), "1.13300"),
    ]


@pytest.mark.parametrize(
    ("scenario", "reason", "price", "exit_at"),
    [
        (GapScenario.OBSERVED_ONLY, "CIBLE", D("1.13370"), (10, 12, 31, 405)),
        (GapScenario.STOP_FIRST, "STOP_SCÉNARIO_B", D("1.13189"), (9, 6, 0, 0)),
        (GapScenario.TARGET_FIRST, "CIBLE_SCÉNARIO_C", D("1.13369"), (9, 6, 0, 0)),
    ],
    ids=["A", "B", "C"],
)
def test_interruption_of_an_open_position_keeps_the_trade_under_each_scenario(
    tmp_path: Path, scenario: GapScenario, reason: str, price: D, exit_at: tuple[int, ...]
) -> None:
    """Silence 09:00:00 -> 09:06:00 (6 min > 5): the trade is kept, indeterminate, never removed."""
    result = run(tmp_path, example_a(WINTER, _gap_after_entry(at(WINTER, 9, 6))), WINTER, scenario=scenario)
    (trade,) = result.trades
    assert trade.unobservable_crossings == [f"{at(WINTER, 9, 0).isoformat()} → {at(WINTER, 9, 6).isoformat()}"]
    assert (trade.exit_reason, trade.exit_price, trade.exit_utc) == (reason, price, at(WINTER, *exit_at))
    assert "INTERRUPTION_POSITION" in kinds(result)
    assert result.sessions[0].entry_outcome == EXECUTED  # never cancelled retroactively


def test_a_silence_of_exactly_five_minutes_is_not_an_interruption_of_the_position(tmp_path: Path) -> None:
    result = run(
        tmp_path, example_a(WINTER, _gap_after_entry(at(WINTER, 9, 5))), WINTER, scenario=GapScenario.STOP_FIRST
    )
    (trade,) = result.trades
    assert not trade.indeterminate and trade.exit_reason == "CIBLE"
    assert "INTERRUPTION_POSITION" not in kinds(result)


# ---------------------------------------------------------------- liquidation


def test_liquidation_closing_an_interruption_is_delayed_and_reported(tmp_path: Path) -> None:
    after = [
        tick(at(WINTER, 8, 40, 0, 200), "1.13259"),
        *fill(at(WINTER, 8, 40, 30), at(WINTER, 15, 58, 30), "1.13300"),
    ]
    after += fill(at(WINTER, 16, 7), at(WINTER, 16, 30), "1.13300")  # silence 15:58:00 -> 16:07:00
    result = run(tmp_path, example_b(WINTER, after), WINTER)
    (trade,) = result.trades
    assert (trade.exit_reason, trade.exit_utc) == (LIQUIDATION, at(WINTER, 16, 7))
    assert trade.indeterminate  # scenario A: the first quote after the gap is between stop and target
    (liquidation,) = result.liquidations
    assert liquidation["delayed"] and liquidation["delay"] == timedelta(minutes=7)
    assert DELAYED_LIQUIDATION in kinds(result) and UNPLANNED_NIGHT not in kinds(result)


def test_no_quote_until_the_next_trading_day_is_an_unplanned_night(tmp_path: Path) -> None:
    after = [
        tick(at(WINTER, 8, 40, 0, 200), "1.13259"),
        *fill(at(WINTER, 8, 40, 30), at(WINTER, 15, 58, 30), "1.13300"),
    ]
    nxt = WINTER + timedelta(days=1)
    after += fill(at(nxt, 0, 30), at(nxt, 0, 40), "1.13300")  # after 22:00 London: next trading day
    result = run(tmp_path, example_b(WINTER, after), WINTER, days=2)
    (trade,) = result.trades
    assert (trade.exit_reason, trade.exit_utc) == (LIQUIDATION, at(nxt, 0, 30))
    assert result.liquidations[0]["unplanned_night"] and UNPLANNED_NIGHT in kinds(result)
    assert "financement overnight" in trade.costs_quote  # one night booked
    assert result.sessions[1].abstention == RANGE_INCOMPLETE  # the next session has no range


def test_a_position_from_the_previous_day_blocks_the_next_entry_without_catch_up(tmp_path: Path) -> None:
    """Deliberately incomplete feed: no tick between 15:58 on day 1 and 08:45:00.140 on day 2, while
    the candles of day 2 come from complete ticks. The day-1 liquidation is still pending at D."""
    day1, day2 = WINTER, WINTER + timedelta(days=1)
    first = example_b(
        day1, [tick(at(day1, 8, 40, 0, 200), "1.13259"), *fill(at(day1, 8, 40, 30), at(day1, 15, 58, 30), "1.13300")]
    )
    second = example_a(day2)
    feed = first + [t for t in second if t.ts_utc >= at(day2, 8, 45, 0, 140)]
    result = run(tmp_path, first + second, day1, days=2, feed=feed)
    s1, s2 = result.sessions
    assert s1.entry_outcome == EXECUTED
    assert s2.previous_position and s2.range is not None and s2.breakout is not None  # still evaluated
    assert s2.abstention == POSITION_OPEN and s2.entry_outcome is None
    (trade,) = result.trades  # no second trade, no catch-up after the old position closed
    assert trade.exit_reason == LIQUIDATION and trade.exit_utc == at(day2, 8, 45, 0, 140)
    assert result.liquidations[0]["unplanned_night"]


def test_position_still_open_at_the_end_of_the_study_is_valued_without_invented_exit(tmp_path: Path) -> None:
    ticks = example_a(
        WINTER, [tick(at(WINTER, 8, 45, 0, 140), "1.13260"), *fill(at(WINTER, 8, 45, 30), at(WINTER, 10, 0), "1.13300")]
    )
    result = run(tmp_path, ticks, WINTER, end_utc=None)
    assert result.trades == [] and result.open_trade is not None
    assert result.open_trade.exit_utc is None and result.unrealized != 0


# ---------------------------------------------------------------- abstentions (sheet §8)


def _flat_session(day: date, holes: list[tuple[datetime, datetime]] | None = None, low: str = "1.13050") -> list[Tick]:
    ticks = [tick(at(day, 1, 0), "1.13150"), tick(at(day, 1, 0, 30), "1.13250"), tick(at(day, 1, 1), low)]
    ticks += fill(at(day, 1, 1, 30), at(day, 16, 30), C)
    return [t for t in ticks if not any(a <= t.ts_utc < b for a, b in holes or [])]


def test_abstention_reasons_in_the_order_of_the_sheet(tmp_path: Path) -> None:
    cases = {
        RANGE_INCOMPLETE: _flat_session(WINTER, [(at(WINTER, 3, 0), at(WINTER, 3, 6))]),
        RANGE_WIDTH: _flat_session(WINTER, low="1.12700"),  # H = 55 pips > 2 A
        NO_BREAKOUT: _flat_session(WINTER),
        BREAKOUT_DATA: _flat_session(WINTER, [(at(WINTER, 9, 0), at(WINTER, 9, 6))]),
    }
    for i, (reason, ticks) in enumerate(cases.items()):
        result = run(tmp_path / str(i), ticks, WINTER)
        assert result.sessions[0].abstention == reason, reason
        assert result.trades == [] and result.decisions == []


def test_retest_abstentions(tmp_path: Path) -> None:
    base = range_and_breakout(WINTER)
    invalid = base + m5_bar(WINTER, 8, 30, ["1.13250", "1.13240", "1.13230", "1.13225", "1.13220", "1.13221"])
    invalid += fill(at(WINTER, 8, 35), at(WINTER, 16, 30), "1.13300")
    timeout = base + fill(at(WINTER, 8, 30), at(WINTER, 16, 30), "1.13300")  # never back to the zone
    silent = (
        base
        + fill(at(WINTER, 8, 30), at(WINTER, 8, 40), "1.13300")
        + fill(at(WINTER, 8, 46), at(WINTER, 16, 30), "1.13300")
    )
    for i, (ticks, reason) in enumerate([(invalid, INVALIDATED), (timeout, RETEST_TIMEOUT), (silent, RETEST_DATA)]):
        result = run(tmp_path / str(i), ticks, WINTER)
        assert result.sessions[0].abstention == reason, reason


def test_atr_unavailable_and_size_refused(tmp_path: Path) -> None:
    assert run(tmp_path / "a", example_a(WINTER), WINTER, h4=[]).sessions[0].abstention == ATR_UNAVAILABLE
    poor = ResearchConfig(costs=RESEARCH_COSTS, initial_equity=D("100"))  # budget 0.25 EUR < 0.1 contract
    result = run(tmp_path / "b", example_a(WINTER), WINTER, config=poor)
    assert result.sessions[0].abstention == SIZE_REFUSED and result.trades == []


def test_no_session_on_a_probable_holiday(tmp_path: Path) -> None:
    day = date(2019, 12, 25)  # Wednesday
    result = run(tmp_path, _flat_session(date(2019, 12, 24)), day, h4=[])
    assert result.sessions[0].abstention == NO_SESSION


# ---------------------------------------------------------------- chronology


def test_decision_uses_only_what_is_known_before_d(tmp_path: Path) -> None:
    """Changing only the ticks after D never changes the decision (quote, stop, target, size)."""
    other = [tick(at(WINTER, 8, 45, 0, 140), "1.13260"), *fill(at(WINTER, 8, 45, 30), at(WINTER, 16, 30), "1.13210")]
    a = run(tmp_path / "a", example_a(WINTER), WINTER)
    b = run(tmp_path / "b", example_a(WINTER, other), WINTER)
    keys = ("d_utc", "p_d", "stop", "target", "size", "deadline_utc")
    assert {k: a.sessions[0].decision[k] for k in keys} == {k: b.sessions[0].decision[k] for k in keys}
    assert a.decisions[0].known == b.decisions[0].known
    assert a.trades[0].exit_reason == "CIBLE" and b.trades[0].exit_reason == LIQUIDATION


def test_quote_and_stop_checks_at_d_on_a_deliberately_inconsistent_feed(tmp_path: Path) -> None:
    """With ticks and candles that agree, an OK confirming M5 always holds a quote and a stop below the
    bid. Feeds that differ from the candles exercise the two checks anyway."""
    from forex_bot.backtest.day01 import NO_QUOTE, STOP_INADMISSIBLE

    ticks = example_a(WINTER)
    no_quote = [t for t in ticks if not at(WINTER, 8, 40) <= t.ts_utc < at(WINTER, 8, 45)]
    assert run(tmp_path / "q", ticks, WINTER, feed=no_quote).sessions[0].abstention == NO_QUOTE
    low = [tick(t.ts_utc, "1.13180") if t.ts_utc == at(WINTER, 8, 44, 59, 870) else t for t in ticks]
    result = run(tmp_path / "s", ticks, WINTER, feed=low)
    assert result.sessions[0].abstention == STOP_INADMISSIBLE and result.trades == []
