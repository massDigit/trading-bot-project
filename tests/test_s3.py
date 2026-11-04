"""Synthetic tests of the offline S3 engine (docs/strategies/S3_SQUEEZE.md). No real data.

The scenario of the sheet example (§7) is built with the approved parameters, winter 2019: H4 at
22, 02, 06, 10, 14 and 18 UTC. Each H4 is made of 48 ticks every 5 minutes: the first at the
open, the second at the given level, the third at the given low, all the others at the close (as
in test_backtest.py). Before the box:
- a volatile history (more than 300 H4) gives the reference of the band widths;
- one degraded H4 restarts the ATR and the bands, so that A is exactly 12 pips at F;
- 19 quiet H4 with a 12-pip true range each, then the 6 H4 of the box (1.1322 - 1.1350).
D1 context candles are written by hand: middle of the 55-day channel 1.1290, close 1.1340.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal as D
from typing import Any

import pytest
from test_backtest import SPREAD, STEP, candles, utc

from forex_bot.backtest.bar_state import BarState
from forex_bot.backtest.engine import EntryAction, PositionAction, ResearchConfig, ScenarioPolicy
from forex_bot.backtest.explore import RESEARCH_COSTS
from forex_bot.backtest.feed import Tick, TickFeed
from forex_bot.backtest.s3 import Box, ReturnKind, S3Params, bands, h4_ordinals, nearest_rank, return_kind
from forex_bot.backtest.s3_engine import S3Backtest, S3Result
from forex_bot.history.calendar import MarketState, Timeframe, candle_end, candle_start, market_state, trading_day
from forex_bot.risk import Side

Spec = tuple[D, D, D, D]  # bid ticks: open, second tick, third tick, close
MIRROR = D("2.2672")  # p -> 2.2672 - p keeps the box 1.1322 - 1.1350 and turns a buy into a sale
X = utc(2019, 2, 11, 22)  # first H4 of the box (Tuesday's trading day starts Monday 22:00 UTC)
HISTORY_START = utc(2018, 11, 11, 22)


def d(text: str) -> D:
    return D(text)


def spec(o: str, a: str, b: str, c: str) -> Spec:
    return d(o), d(a), d(b), d(c)


def slots(first: datetime, until: datetime) -> list[datetime]:
    """Expected H4 starts in [first, until)."""
    out, moment = [], first
    while moment < until:
        if candle_start(moment, Timeframe.H4) == moment and market_state(moment) is MarketState.OPEN:
            out.append(moment)
        moment += timedelta(hours=1)
    return out


def volatile(count: int) -> list[Spec]:
    """Closes alternating around 1.1320 with amplitudes of 15 to 25 pips."""
    out, previous = [], D("1.1320")
    for k in range(count):
        close = D("1.1320") + D(15 + k % 11) * D("0.0001") * (1 if k % 2 else -1)
        out.append((previous, max(previous, close) + D("0.0002"), min(previous, close) - D("0.0002"), close))
        previous = close
    return out


QUIET_CLOSES = ["1.1340", "1.1335", "1.1339", "1.1334", "1.1338", "1.1336"]


def quiet(first_open: D) -> list[Spec]:
    """19 H4 with a true range of exactly 12 pips (centred on the previous close), last close 1.1336."""
    closes = [d(QUIET_CLOSES[k % 6]) for k in range(19)]
    closes[-1] = d("1.1336")
    out, previous = [], first_open
    for close in closes:
        out.append((previous, previous + D("0.0006"), previous - D("0.0006"), close))
        previous = close
    return out


BOX = [  # previous close inside each 12-pip range: TR = 12 pips; max high 1.1350, min low 1.1322
    spec("1.1336", "1.1342", "1.1330", "1.1340"),
    spec("1.1340", "1.1350", "1.1338", "1.1344"),
    spec("1.1344", "1.1346", "1.1334", "1.1336"),
    spec("1.1336", "1.1340", "1.1328", "1.1330"),
    spec("1.1330", "1.1334", "1.1322", "1.1328"),
    spec("1.1328", "1.1338", "1.1326", "1.1336"),
]
WICK = spec("1.1336", "1.1356", "1.1335", "1.1347")  # Wed 22-02: high above BH, close inside
INSIDE = spec("1.1347", "1.1350", "1.1340", "1.1345")  # Wed 02-06
BREAK = spec("1.1345", "1.1368", "1.1344", "1.1366")  # Wed 06-10: first close above BH, D = 10:00
SUITE_1 = [
    spec("1.1367", "1.1367", "1.1345", "1.1349"),  # 10-14: executed at ask 1.1368; reintegration, above M
    spec("1.1349", "1.1350", "1.1332", "1.1333"),  # 14-18: close under M: trailing exit decided at 18:00
    spec("1.1332", "1.1332", "1.1330", "1.1331"),  # 18-22: exit at the bid of the tick after 18:00
]


def rising(count: int) -> list[Spec]:
    """Closes 10 pips higher each H4 from 1.1372, never back in the box."""
    out, previous = [], d("1.1367")
    for k in range(count):
        close = d("1.1372") + D(10 * k) * D("0.0001")
        out.append((previous, previous if k == 0 else close, min(previous, close) - D("0.0003"), close))
        previous = close
    return out


SUITE_2 = [  # up 10 pips per H4, then a close under M but above the entry: the trailing exit keeps a gain
    *rising(14),
    spec("1.1502", "1.1500", "1.1388", "1.1390"),
    *[spec("1.1390", "1.1391", "1.1389", "1.1390")] * 2,
]


def scenario(after: Sequence[Spec | None]) -> tuple[list[Spec | None], list[datetime]]:
    """History, degraded H4, quiet H4, box, wick, inside, breakout, then `after`."""
    starts = slots(HISTORY_START, X + timedelta(days=40))
    x = starts.index(X)
    history = volatile(x - 20)
    last = history[-1][3]
    degraded = (last, max(last, d("1.1336")), min(last, d("1.1336")), d("1.1336"))
    body: list[Spec | None] = [*history, degraded, *quiet(d("1.1336")), *BOX, WICK, INSIDE, BREAK, *after]
    return body, starts[: len(body)]


def ticks_for(specs: Sequence[Spec | None], starts: Sequence[datetime], mirror: bool = False) -> list[Tick]:
    ticks = []
    for start, s in zip(starts, specs, strict=True):
        if s is None:
            continue
        o, a, b, c = (MIRROR - v for v in s) if mirror else s
        for j in range(48):
            bid = o if j == 0 else a if j == 1 else b if j == 2 else c
            ticks.append(Tick(start + j * STEP, bid, bid + SPREAD))
    return ticks


def d1_context(mirror: bool = False) -> list[dict[str, Any]]:
    """Trading days to mid-February: channel 1.1190 - 1.1390 (middle 1.1290), close 1.1340 on 12 February."""
    bars, moment = [], utc(2018, 10, 1, 12)
    while moment < utc(2019, 2, 16):
        day = trading_day(moment)
        if moment.weekday() < 5 and market_state(moment) is MarketState.OPEN:
            high = d("1.1390") if day.isoformat() == "2019-01-10" else d("1.1380")
            low = d("1.1190") if day.isoformat() == "2019-01-11" else d("1.1200")
            close = d("1.1340") if day.isoformat() == "2019-02-12" else d("1.1300")
            o, h, low_, c = (
                (MIRROR - close, MIRROR - low, MIRROR - high, MIRROR - close)
                if mirror
                else (
                    close,
                    high,
                    low,
                    close,
                )
            )
            start = candle_start(moment, Timeframe.D1)
            bars.append(
                {
                    "start_utc": start,
                    "end_utc": candle_end(start, Timeframe.D1),
                    **{f"bid_{k}": v for k, v in zip(("open", "high", "low", "close"), (o, h, low_, c), strict=True)},
                    **{
                        f"ask_{k}": v + SPREAD
                        for k, v in zip(("open", "high", "low", "close"), (o, h, low_, c), strict=True)
                    },
                    "complete_at_close": True,
                    "flags_at_close": [],
                }
            )
        moment += timedelta(days=1)
    return bars


def engine(
    after: Sequence[Spec | None],
    *,
    mirror: bool = False,
    degrade: Sequence[int] = (),
    drop: tuple[int, int, int] | None = None,
    params: S3Params | None = None,
    d1: list[dict[str, Any]] | None = None,
    end: datetime | None = None,
    **config: Any,
) -> S3Backtest:
    """`degrade`: offsets from X whose H4 is flagged; `drop`: (offset, first, last) ticks removed from an H4."""
    specs, starts = scenario(after)
    ticks = ticks_for(specs, starts, mirror)
    if drop is not None:
        offset, first, last = drop
        start = starts[starts.index(X) + offset]
        ticks = [t for t in ticks if not start + first * STEP <= t.ts_utc <= start + last * STEP]
    h4 = candles(ticks, Timeframe.H4)
    x = next(i for i, b in enumerate(h4) if b["start_utc"] == X)
    for i in [x - 20, *(x + k for k in degrade)]:
        h4[i] = {**h4[i], "complete_at_close": False, "flags_at_close": ["trou de cotation"]}
    feed = TickFeed(ticks)
    return S3Backtest(
        h4,
        d1 if d1 is not None else d1_context(mirror),
        feed,
        feed.gaps(timedelta(minutes=10)),
        params or S3Params(),
        ResearchConfig(**({"costs": RESEARCH_COSTS} | config)),
        start_utc=X - timedelta(days=4),  # decisions from the quiet H4 on; the history only feeds the bands
        end_utc=end,
    )


ALL_SLOTS = slots(HISTORY_START, X + timedelta(days=40))


def at(offset: int) -> datetime:
    """Availability (end) of the H4 `offset` expected slots after X (negative: before X)."""
    return candle_end(ALL_SLOTS[ALL_SLOTS.index(X) + offset], Timeframe.H4)


def line(result: S3Result, offset: int) -> Any:
    return next(r for r in result.decisions if r.decision_utc == at(offset))


def kinds(result: S3Result, kind: str) -> list[str]:
    return [e.detail for e in result.journal if e.kind == kind]


# ---------------------------------------------------------------- rules on numbers


def test_bands_use_the_population_standard_deviation() -> None:
    b = bands([D(1), D(2), D(3), D(4)], D(2))
    sigma = D("1.25").sqrt()
    assert b.middle == D("2.5") and b.upper == D("2.5") + 2 * sigma and b.lower == D("2.5") - 2 * sigma
    assert b.width == 4 * sigma / D("2.5")


def test_nearest_rank_percentile() -> None:
    assert nearest_rank([D(5), D(1), D(4), D(2), D(3)], D("0.20")) == D(1)  # ceil(1.0) = 1st
    assert nearest_rank([D(k) for k in range(10, 0, -1)], D("0.20")) == D(2)  # ceil(2.0) = 2nd
    assert nearest_rank([D(k) for k in range(1, 12)], D("0.20")) == D(3)  # ceil(2.2) = 3rd


def test_ordinals_skip_the_weekend_but_not_an_absent_expected_h4() -> None:
    starts = slots(utc(2019, 2, 7, 22), utc(2019, 2, 12, 2))  # Friday's trading day to Monday 22:00
    present = [s for k, s in enumerate(starts) if k != 2]  # one expected H4 absent on Friday
    bars = [{"start_utc": s, "end_utc": candle_end(s, Timeframe.H4)} for s in present]
    ordinals = h4_ordinals(bars)
    assert ordinals[2] - ordinals[1] == 2  # the absent slot breaks the continuity
    friday_last = next(k for k, s in enumerate(present) if s == utc(2019, 2, 8, 18))
    assert ordinals[friday_last + 1] - ordinals[friday_last] == 1  # the weekend does not


@pytest.mark.parametrize(
    ("side", "close", "expected"),
    [
        (Side.LONG, "1.1351", None),
        (Side.LONG, "1.1350", ReturnKind.REINTEGRATION),  # bounds included
        (Side.LONG, "1.1322", ReturnKind.REINTEGRATION),
        (Side.LONG, "1.1321", ReturnKind.CROSSING),
        (Side.SHORT, "1.1321", None),
        (Side.SHORT, "1.1322", ReturnKind.REINTEGRATION),
        (Side.SHORT, "1.1350", ReturnKind.REINTEGRATION),
        (Side.SHORT, "1.1351", ReturnKind.CROSSING),
    ],
)
def test_first_close_back_is_a_reintegration_bounds_included_or_a_crossing(
    side: Side, close: str, expected: ReturnKind | None
) -> None:
    assert return_kind(side, d(close), d("1.1322"), d("1.1350")) is expected


# ---------------------------------------------------------------- the sheet example (§7)


def test_compression_box_frozen_at_f_and_atr_of_twelve_pips() -> None:
    result = engine(SUITE_1).run()
    (box, *_) = result.boxes
    assert box.formed_utc == at(5) == utc(2019, 2, 12, 22)  # F: availability of the 6th compressed H4
    assert (box.high, box.low, box.atr) == (d("1.1350"), d("1.1322"), d("0.0012"))
    assert box.ask_high == d("1.1351")
    assert line(result, 5).reasons == ["boîte reconnue et figée"]
    # The first H4 with computable bands after the degraded one is X: nothing compressed before.
    assert line(result, -1).entry_action is EntryAction.NOT_COMPUTABLE
    assert all(line(result, k).known["compression"]["compressed"] is True for k in range(6))
    # The wick above BH is not a breakout and does not move the frozen bounds.
    wick = line(result, 6)
    assert wick.signal is None and wick.reasons == ["clôture dans la boîte"] and box.high == d("1.1350")


def test_breakout_with_expansion_and_d1_context_decides_the_entry_of_the_example() -> None:
    result = engine(SUITE_1).run()
    decision = line(result, 8)
    assert decision.decision_utc == utc(2019, 2, 13, 10)
    assert decision.entry_action is EntryAction.ENTRY_DECIDED
    signal, order = decision.signal, decision.order
    assert signal is not None and order is not None
    assert signal["close"] > signal["upper"] and signal["width"] > signal["previous_width"]
    assert signal["stop"] == d("1.1319")  # 1.1322 - 0.25 x 0.0012
    assert order["size"] == d("0.1")
    assert round(order["estimated_stop_loss"] / order["size"], 2) == d("44.83")  # EUR per contract
    trade = result.trades[0]
    assert trade.entry_price == d("1.1368") and trade.entry_utc == utc(2019, 2, 13, 10, 5)
    assert result.boxes[0].end_reason == "consommée par la cassure LONG"


def test_suite_1_reintegration_is_journaled_without_exit_then_the_mean_exits() -> None:
    result = engine(SUITE_1).run()
    first = line(result, 9)  # 10-14 closes at 1.1349, inside the box, above M
    assert first.position_action is PositionAction.HELD
    bands_now = first.known["bands"]
    assert bands_now["middle"] < d("1.1349")
    (event,) = result.returns
    assert event.kind is ReturnKind.REINTEGRATION and event.utc == utc(2019, 2, 13, 14)
    assert event.h4_since_entry == 1 and event.close == d("1.1349") and not event.exit_decided
    assert len(kinds(result, "RÉINTÉGRATION")) == 1
    exit_line = line(result, 10)  # 14-18 closes at 1.1333, under M
    assert exit_line.position_action is PositionAction.EXIT_DECIDED
    assert exit_line.known["bands"]["middle"] > d("1.1333")
    (trade,) = result.trades
    assert trade.exit_reason == "SORTIE_SUIVEUSE" and trade.exit_price == d("1.1332")
    assert trade.exit_utc == utc(2019, 2, 13, 18, 5)
    assert trade.exit_price - trade.entry_price == d("-0.0036")  # about -36 pips, against -49 at the stop


def test_suite_2_no_return_is_journaled_and_the_mean_follows_the_move() -> None:
    result = engine(SUITE_2).run()
    assert result.returns == [] and not kinds(result, "RÉINTÉGRATION") and not kinds(result, "TRAVERSÉE")
    (trade,) = result.trades
    assert trade.exit_reason == "SORTIE_SUIVEUSE"
    exit_line = next(r for r in result.decisions if r.position_action is PositionAction.EXIT_DECIDED)
    held = [r for r in result.decisions if r.position_action is PositionAction.HELD]
    assert any(r.known["bands"]["middle"] > d("1.1350") for r in held)  # M rose above BH
    assert exit_line.known["h4"]["bid_close"] < exit_line.known["bands"]["middle"]
    assert trade.exit_price is not None and trade.exit_price > trade.entry_price


def test_the_breakout_candle_cannot_trigger_the_trailing_exit() -> None:
    result = engine(SUITE_1).run()
    breakout = line(result, 8)
    assert breakout.position_action is PositionAction.FLAT  # the position is opened after D
    assert breakout.signal is not None and breakout.signal["close"] > breakout.known["bands"]["middle"]


def test_a_crossing_is_journaled_as_such_and_kept_with_the_exit_decided_on_the_same_close() -> None:
    crossing = [spec("1.1367", "1.1367", "1.1325", "1.1320"), *SUITE_1[1:]]  # straight under BL, above the stop
    result = engine(crossing).run()
    (event,) = result.returns
    assert event.kind is ReturnKind.CROSSING and event.close == d("1.1320") and event.exit_decided
    decision = line(result, 9)
    assert decision.position_action is PositionAction.EXIT_DECIDED
    assert any(r.startswith("TRAVERSÉE") for r in decision.reasons)  # the observation and the decision
    assert any("sous la moyenne" in r for r in decision.reasons)
    assert not kinds(result, "RÉINTÉGRATION")


def test_sale_is_symmetric() -> None:
    result = engine(SUITE_1, mirror=True).run()
    decision = line(result, 8)
    assert decision.entry_action is EntryAction.ENTRY_DECIDED and decision.signal is not None
    assert decision.signal["side"] == "SHORT"
    (box, *_) = result.boxes
    assert (box.high, box.low) == (d("1.1350"), d("1.1322"))  # the mirror keeps the box
    assert decision.signal["stop"] == box.ask_high + d("0.0003")
    (event,) = result.returns
    assert event.kind is ReturnKind.REINTEGRATION and event.close == d("1.1323")
    (trade,) = result.trades
    assert trade.side is Side.SHORT and trade.exit_reason == "SORTIE_SUIVEUSE"
    assert trade.entry_price == MIRROR - d("1.1367")  # sold at the bid


# ---------------------------------------------------------------- box life and refusals


def test_one_breakout_per_box_even_after_a_refusal() -> None:
    against = d1_context(mirror=True)  # bearish context: the long breakout is refused
    result = engine([*SUITE_1, spec("1.1331", "1.1360", "1.1330", "1.1358")], d1=against).run()
    decision = line(result, 8)
    assert decision.entry_action is EntryAction.SIGNAL_REFUSED
    assert decision.reasons == ["cassure haussière contre le contexte D1"]
    assert result.boxes[0].end_reason == "consommée par la cassure LONG"
    later = [r for r in result.decisions if r.decision_utc > at(8) and r.signal is not None]
    assert later == [] and len(result.boxes) == 1 and result.trades == []


def test_a_breakout_without_expansion_is_refused_and_consumes_the_box() -> None:
    params = S3Params(bb_width=D(6))  # bands too wide for the breakout close
    result = engine(SUITE_1, params=params).run()
    decision = line(result, 8)
    assert decision.entry_action is EntryAction.SIGNAL_REFUSED
    assert decision.reasons[-1].startswith("pas d'expansion")
    assert result.boxes[0].ended_utc == at(8) and result.trades == []


def test_an_unusable_h4_after_f_abandons_the_box() -> None:
    result = engine(SUITE_1, degrade=[7]).run()
    assert result.boxes[0].end_reason is not None and result.boxes[0].end_reason.startswith("DONNÉES_BOÎTE")
    assert line(result, 7).entry_action is EntryAction.NOT_COMPUTABLE
    assert line(result, 8).signal is None and result.trades == []


def test_the_box_expires_at_the_thirtieth_h4_and_a_new_box_needs_new_candles() -> None:
    inside = [spec("1.1345", "1.1346", "1.1344", "1.1345")] * 40
    specs, _ = scenario([])
    body = [*specs[:-3], *inside]  # no wick, no breakout: closes stay in the box
    ticks = ticks_for(body, slots(HISTORY_START, X + timedelta(days=40))[: len(body)])
    h4 = candles(ticks, Timeframe.H4)
    x = next(i for i, b in enumerate(h4) if b["start_utc"] == X)
    h4[x - 20] = {**h4[x - 20], "complete_at_close": False, "flags_at_close": ["trou de cotation"]}
    feed = TickFeed(ticks)
    result = S3Backtest(
        h4,
        d1_context(),
        feed,
        feed.gaps(timedelta(minutes=10)),
        S3Params(),
        ResearchConfig(costs=RESEARCH_COSTS),
        start_utc=X - timedelta(days=4),
    ).run()
    first = result.boxes[0]
    assert first.end_reason == "expirée après 30 H4" and first.ended_utc == at(35)
    assert line(result, 35).reasons == [
        "boîte expirée sans cassure",
        "pas de boîte : bougies déjà utilisées par la boîte précédente",
    ]
    # A new box needs 6 compressed H4 that all start after the end of the previous one.
    assert result.boxes[1].formed_utc == at(41)


class InjectedBox(S3Backtest):
    """Puts an active box under the price at one decision, to meet a breakout while a position is open."""

    def _decide(self, t: int, decision: datetime) -> None:
        if decision == at(12):
            self.box = Box(t - 1, at(11), d("1.1300"), d("1.1290"), d("1.1301"), d("0.0012"))
            self.boxes.append(self.box)
        super()._decide(t, decision)


def test_a_breakout_during_an_open_position_is_not_evaluated_and_consumes_the_box() -> None:
    base = engine(SUITE_2)
    injected = InjectedBox(
        base.h4, base.d1, ticks_for(*scenario(SUITE_2)), [], S3Params(), base.config, start_utc=base.start_utc
    )
    result = injected.run()
    decision = line(result, 12)
    assert decision.signal is not None and decision.signal["side"] == "LONG"
    assert decision.entry_action is EntryAction.NOT_EVALUATED
    assert decision.reasons[-1] == "cassure pendant une position ouverte : boîte consommée"
    assert result.boxes[-1].end_reason == "consommée par la cassure LONG" and len(result.trades) == 1


def test_exit_not_computable_keeps_the_position_and_still_journals_the_reintegration() -> None:
    after = [
        SUITE_1[0],
        spec("1.1349", "1.1350", "1.1345", "1.1348"),
        *[spec("1.1348", "1.1349", "1.1347", "1.1348")] * 3,
    ]
    result = engine(after, degrade=[9]).run()
    degraded = line(result, 9)
    assert degraded.position_action is PositionAction.HELD_EXIT_NOT_COMPUTABLE
    assert degraded.reasons == ["bougie de décision INTERRUPTION_INEXPLIQUÉE"]
    following = line(result, 10)  # usable, inside the box, but M includes the degraded H4
    assert following.position_action is PositionAction.HELD_EXIT_NOT_COMPUTABLE
    assert "moyenne de 20 H4 non calculable" in following.reasons  # exit; then the entry side's own reason
    assert following.reasons[-1] == "compression non calculable"
    (event,) = result.returns
    assert event.kind is ReturnKind.REINTEGRATION and event.utc == at(10) and event.middle is None
    assert result.trades == [] and result.open_trade is not None


def test_a_position_open_at_the_end_is_valued_without_a_fictitious_close() -> None:
    result = engine(SUITE_2, end=at(14)).run()
    assert result.trades == [] and result.open_trade is not None and result.open_trade.exit_utc is None
    assert result.equity_curve[-1].unrealized > 0


# ---------------------------------------------------------------- execution, scenarios


def test_unexplained_interruption_in_position_scenarios_a_and_b() -> None:
    drop = (10, 6, 12)  # 30 minutes without quotes inside the second H4 after the entry
    a = engine(SUITE_2, drop=drop).run()
    b = engine(SUITE_2, drop=drop, policy=ScenarioPolicy.ALL_TRIGGERED).run()
    trade_a = a.trades[0] if a.trades else a.open_trade
    assert trade_a is not None and trade_a.indeterminate and trade_a.exit_reason != "STOP_SCÉNARIO_H1"
    (trade_b,) = b.trades
    assert trade_b.exit_reason == "STOP_SCÉNARIO_H1" and trade_b.exit_price == trade_b.stop
    assert line(a, 10).known["h4"]["state"] == BarState.UNEXPLAINED_INTERRUPTION.value


def test_a_stop_reached_before_a_pending_trailing_exit_closes_once_and_abandons_the_trailing_exit() -> None:
    stop_first = [*SUITE_1[:2], spec("1.1332", "1.1318", "1.1316", "1.1317")]  # 18:05 bid under the stop 1.1319
    result = engine(stop_first).run()
    assert line(result, 10).position_action is PositionAction.EXIT_DECIDED  # trailing exit pending from 18:00
    (trade,) = result.trades
    assert trade.exit_reason == "STOP_OBSERVÉ" and trade.exit_price == d("1.1319")
    assert trade.exit_utc == utc(2019, 2, 13, 18, 5)
    assert result.open_trade is None and len(kinds(result, "SORTIE")) == 1
    (abandoned,) = kinds(result, "SORTIE_SUIVEUSE_ABANDONNÉE")
    assert abandoned.startswith("STOP_OBSERVÉ") and "sortie suiveuse" in abandoned
    assert not kinds(result, "SORTIE_CANAL_ABANDONNÉE")
    assert not any("canal" in e.detail or "CANAL" in e.kind for e in result.journal)


def test_first_price_beyond_the_stop_is_filled_then_liquidated() -> None:
    gap_down = [spec("1.1318", "1.1317", "1.1316", "1.1317"), *SUITE_1[1:]]  # opens under the stop 1.1319
    result = engine(gap_down).run()
    (trade,) = result.trades
    assert trade.exit_reason == "STOP_FRANCHI_À_L'EXÉCUTION"
    assert kinds(result, "STOP_DÉPASSÉ_À_L'EXÉCUTION")
