"""Synthetic tests of the offline S2 engine (docs/strategies/S2_PULLBACK.md). No real data.

H1 candles are built from ticks whose open, high, low and close are set exactly: a tick every
5 minutes, the first at the open, the second at the high, the third at the low, all the others at
the close (as in test_backtest.py). H4 candles are aggregated from the same ticks; D1 context
candles are written by hand before the study (an up trend: two rising highs, two rising lows).
Week of 2019-03-11, US summer time: H4 at 21, 01, 05, 09, 13, 17 UTC.

Small pivot orders (1) and a short ATR (2) keep the paths readable; the rules are the same for
the approved orders, whose confirmation delay is tested on the pivot tracker directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal as D
from typing import Any

from test_backtest import COSTS, SPREAD, STEP, candles, utc

from forex_bot.backtest.bar_state import BarState
from forex_bot.backtest.engine import EntryAction, PositionAction, ResearchConfig
from forex_bot.backtest.explore import RESEARCH_COSTS
from forex_bot.backtest.feed import Tick, TickFeed
from forex_bot.backtest.s1 import WilderAtr
from forex_bot.backtest.s2 import (
    ContinuousWilderAtr,
    GapScenario,
    PivotKind,
    PivotTracker,
    S2Params,
    overlaps,
    pivot_kinds,
)
from forex_bot.backtest.s2_engine import RelativeDrawdown, S2Backtest, S2Result
from forex_bot.history.calendar import MarketState, Timeframe, candle_end, candle_start, market_state
from forex_bot.risk import Side

Spec = tuple[D, D, D, D]  # open, high, low, close of one H1 candle (bid)
START = utc(2019, 3, 10, 21)  # Sunday 17:00 New York: first H1 of Monday's trading day
P = S2Params(pivot_d1=1, pivot_h4=1, pivot_h1=1, atr_period=2)
MIRROR = D("2.2")
FINE: dict[str, Any] = {"min_size": D("0.01"), "size_increment": D("0.01")}  # wide synthetic stops, 5 EUR budget


def d(text: str) -> D:
    return D(text)


def h1(o: str, h: str, low: str, c: str) -> Spec:
    return d(o), d(h), d(low), d(c)


def flat(level: str, count: int = 1) -> list[Spec]:
    return [h1(level, level, level, level)] * count


def block(o: str, h: str, low: str, c: str) -> list[Spec]:
    """Four H1 candles whose H4 is exactly (o, h, low, c)."""
    return [h1(o, h, o, o), h1(o, o, low, o), h1(o, max(o, c), min(o, c), c), h1(c, c, c, c)]


# Before I: ATR warm-up, K (H4 high 1.1040), a dip, E (H4 high 1.1250), then the H4 confirming E.
PRE: list[Spec] = (
    block("1.1000", "1.1005", "1.0995", "1.1000") * 4
    + block("1.1000", "1.1040", "1.0998", "1.1030")  # H4 #4: K
    + block("1.1030", "1.1035", "1.1010", "1.1020")  # H4 #5 confirms K
    + block("1.1020", "1.1250", "1.1015", "1.1240")  # H4 #6: E
    + block("1.1240", "1.1245", "1.1080", "1.1090")  # H4 #7 confirms E: I = its end
)
I_UTC = START + timedelta(hours=len(PRE))  # Tuesday 05:00 UTC
CONTACT = h1("1.1090", "1.1092", "1.1070", "1.1072")  # meets the zone K +/- z A
RECOVERY = h1("1.1072", "1.1095", "1.1068", "1.1075")  # recovery pivot (right after the contact)
CONFIRM = h1("1.1075", "1.1080", "1.1060", "1.1065")  # confirms it: threshold 1.1095 known at its end
BREAK = h1("1.1065", "1.1100", "1.1063", "1.1098")  # first close above 1.1095
TO_TARGET = h1("1.1098", "1.1255", "1.1097", "1.1250")  # the bid reaches E = 1.1250


def mirror(spec: Spec) -> Spec:
    o, h, low, c = spec
    return MIRROR - o, MIRROR - low, MIRROR - h, MIRROR - c


def ticks_for(specs: Sequence[Spec | None]) -> list[Tick]:
    """One H1 per spec from START (None: an hour without any quote)."""
    ticks = []
    for k, spec in enumerate(specs):
        if spec is None:
            continue
        start = START + timedelta(hours=k)
        o, h, low, c = spec
        for j in range(12):
            bid = o if j == 0 else h if j == 1 else low if j == 2 else c
            ticks.append(Tick(start + j * STEP, bid, bid + SPREAD))
    return ticks


def d1_context(down: bool = False) -> list[dict[str, Any]]:
    """Six trading days before the study: highs at days 1 and 3, lows at days 2 and 4, all rising."""
    rows = [
        ("1.0850", "1.0900", "1.0800", "1.0880"),
        ("1.0880", "1.1000", "1.0850", "1.0950"),
        ("1.0950", "1.0950", "1.0830", "1.0900"),
        ("1.0900", "1.1050", "1.0880", "1.1000"),
        ("1.1000", "1.1020", "1.0860", "1.0950"),
        ("1.0950", "1.1040", "1.0900", "1.1000"),
    ]
    days = [utc(2019, 3, day, 12) for day in (1, 4, 5, 6, 7, 8)]
    bars = []
    for moment, (o, h, low, c) in zip(days, rows, strict=True):
        spec = (d(o), d(h), d(low), d(c))
        o_, h_, l_, c_ = mirror(spec) if down else spec
        start = candle_start(moment, Timeframe.D1)
        bars.append(
            {
                "start_utc": start,
                "end_utc": candle_end(start, Timeframe.D1),
                "bid_open": o_,
                "bid_high": h_,
                "bid_low": l_,
                "bid_close": c_,
                "ask_open": o_ + SPREAD,
                "ask_high": h_ + SPREAD,
                "ask_low": l_ + SPREAD,
                "ask_close": c_ + SPREAD,
                "complete_at_close": True,
                "flags_at_close": [],
            }
        )
    return bars


def run(
    specs: Sequence[Spec | None],
    params: S2Params = P,
    scenario: GapScenario = GapScenario.OBSERVED_ONLY,
    down: bool = False,
    **config: Any,
) -> S2Result:
    if down:
        specs = [None if s is None else mirror(s) for s in specs]
    ticks = ticks_for(specs)
    feed = TickFeed(ticks)
    return S2Backtest(
        candles(ticks, Timeframe.H1),
        candles(ticks, Timeframe.H4),
        d1_context(down),
        feed,
        feed.gaps(timedelta(minutes=10)),
        params,
        ResearchConfig(costs=config.pop("costs", COSTS), **{**FINE, **config}),
        scenario=scenario,
    ).run()


def kinds(result: S2Result, kind: str) -> list[str]:
    return [e.detail for e in result.journal if e.kind == kind]


def decided(result: S2Result) -> list[datetime]:
    return [r.decision_utc for r in result.decisions if r.entry_action is EntryAction.ENTRY_DECIDED]


def at(hours_after_i: int) -> datetime:
    return I_UTC + timedelta(hours=hours_after_i)


BASE = [*PRE, CONTACT, RECOVERY, CONFIRM, BREAK, *flat("1.1098"), TO_TARGET, *flat("1.1250", 2)]


# ---------------------------------------------------------------- pivots


def _bars(highs: list[str], lows: list[str] | None = None) -> list[dict[str, Any]]:
    lows = lows or ["1.0"] * len(highs)
    return [
        {
            "start_utc": START + timedelta(hours=k),
            "end_utc": START + timedelta(hours=k + 1),
            "bid_high": d(h),
            "bid_low": d(low),
        }
        for k, (h, low) in enumerate(zip(highs, lows, strict=True))
    ]


def ok(_: int) -> BarState:
    return BarState.OK


def test_pivot_is_known_only_at_the_availability_of_candle_i_plus_p() -> None:
    bars = _bars(["1.1", "1.2", "1.3", "1.9", "1.4", "1.3", "1.2", "1.0"])  # high at index 3
    available = [b["end_utc"] for b in bars]
    tracker = PivotTracker(bars, available, 3)  # approved order for H4
    assert tracker.update(available[5], ok) == []  # i + 2: not yet
    (pivot,) = [p for p in tracker.update(available[6], ok) if p.kind is PivotKind.HIGH]
    assert pivot.index == 3 and pivot.level == d("1.9") and pivot.confirmed_utc == available[6]


def test_equal_highs_make_no_pivot_and_an_unusable_candle_blocks_it() -> None:
    bars = _bars(["1.1", "1.5", "1.5", "1.1"])
    assert PivotKind.HIGH not in pivot_kinds(bars, 1, 1, ok)
    assert PivotKind.HIGH not in pivot_kinds(bars, 2, 1, ok)
    bars = _bars(["1.1", "1.5", "1.2"])
    assert PivotKind.HIGH in pivot_kinds(bars, 1, 1, ok)
    assert pivot_kinds(bars, 1, 1, lambda i: BarState.UNEXPLAINED_INTERRUPTION if i == 2 else BarState.OK) == []


def test_contact_requires_the_candle_range_to_meet_the_zone() -> None:
    below = {"bid_low": d("1.1430"), "bid_high": d("1.1435")}
    assert not overlaps(below, d("1.1440"), d("1.1460"))  # entirely below: not a contact
    assert overlaps({"bid_low": d("1.1430"), "bid_high": d("1.1440")}, d("1.1440"), d("1.1460"))
    assert not overlaps({"bid_low": d("1.1461"), "bid_high": d("1.1470")}, d("1.1440"), d("1.1460"))


# ---------------------------------------------------------------- sequence and time bounds


def test_long_entry_follows_the_full_sequence_and_exits_at_the_first_bid_reaching_e() -> None:
    result = run(BASE)
    (setup_log,) = kinds(result, "CONFIGURATION")
    assert "E 1.1250 K 1.1040" in setup_log
    # Breakout close at the end of BREAK (I + 4 h); threshold confirmed at the end of CONFIRM,
    # i.e. exactly at the start of BREAK (confirmation <= start of the breakout candle).
    assert decided(result) == [at(4)]
    (trade,) = result.trades
    assert trade.side is Side.LONG
    assert trade.entry_utc == at(4) + STEP and trade.entry_price == BREAK[3] + SPREAD  # ask, after D
    (setup,) = result.setups
    assert trade.stop == CONFIRM[2] - P.stop_atr * setup.atr  # PL = lowest bid since E, minus b A
    assert trade.exit_reason == "CIBLE" and trade.exit_price == d("1.1255")  # observed bid, not E


def test_contact_before_identification_does_not_count() -> None:
    # Remove the contact after I: the only candles in the zone are before I (H4 #7) -> no entry.
    no_contact = [*PRE, h1("1.1120", "1.1125", "1.1115", "1.1118"), *flat("1.1118", 6)]
    result = run(no_contact)
    assert decided(result) == []
    assert any("pas de contact" in " ".join(r.reasons) for r in result.decisions if r.decision_utc > I_UTC)


def test_the_contact_candle_cannot_be_the_recovery_pivot_but_the_next_one_can() -> None:
    # The pivot candle is itself the first contact: it can never serve as the threshold.
    on_contact = [
        *PRE,
        h1("1.1120", "1.1125", "1.1116", "1.1118"),  # above the zone: no contact
        h1("1.1118", "1.1135", "1.1100", "1.1105"),  # contact AND pivot high 1.1135
        h1("1.1105", "1.1110", "1.1090", "1.1095"),  # confirms it
        h1("1.1095", "1.1140", "1.1093", "1.1138"),  # closes above 1.1135
        *flat("1.1138", 3),
    ]
    result = run(on_contact)
    assert decided(result) == []
    close_above = next(r for r in result.decisions if r.decision_utc == at(4))  # closes at 1.1138 > 1.1135
    assert close_above.reasons == ["pas de seuil de reprise connu"]
    # BASE: the pivot candle starts exactly at the end of the contact candle -> allowed.
    assert decided(run(BASE)) == [at(4)]


def test_the_threshold_is_known_at_the_start_of_the_breakout_candle() -> None:
    # confirmation(threshold) <= start(breakout candle): BASE sits exactly on the bound. A candle
    # that confirms a pivot cannot close above it (its high is below the pivot), so the breakout is
    # always a later candle.
    result = run(BASE)
    (breakout,) = [r for r in result.decisions if r.signal is not None]
    assert breakout.signal is not None
    assert breakout.signal["threshold"] == RECOVERY[1]
    assert breakout.signal["threshold_confirmed_utc"] == at(3) == breakout.known["trigger_candle"]["start_utc"]


def test_a_breakout_consumes_its_threshold_even_when_the_entry_is_refused() -> None:
    specs = [
        *PRE,
        CONTACT,
        h1("1.1072", "1.1180", "1.1068", "1.1170"),  # recovery pivot 1.1180
        h1("1.1170", "1.1175", "1.1150", "1.1160"),  # confirms it
        h1("1.1160", "1.1195", "1.1158", "1.1190"),  # breakout 1: target too close -> refused
        h1("1.1190", "1.1192", "1.1100", "1.1105"),
        h1("1.1105", "1.1188", "1.1102", "1.1185"),  # closes above the consumed threshold again
        h1("1.1185", "1.1186", "1.1100", "1.1105"),
        h1("1.1105", "1.1106", "1.1060", "1.1065"),
        h1("1.1065", "1.1110", "1.1062", "1.1090"),  # new recovery pivot 1.1110, after the refusal
        h1("1.1090", "1.1095", "1.1075", "1.1080"),  # confirms it
        h1("1.1080", "1.1115", "1.1078", "1.1112"),  # breakout 2
        *flat("1.1112", 2),
    ]
    result = run(specs)
    refusals = kinds(result, "ABSTENTION")
    assert len(refusals) == 1 and "cible trop proche" in refusals[0]
    again = next(r for r in result.decisions if r.decision_utc == at(6))
    assert again.entry_action is EntryAction.NO_SIGNAL and again.signal is None  # not a new breakout
    assert decided(result) == [at(11)]


# ---------------------------------------------------------------- abandonment


def test_a_missing_h1_during_the_pullback_abandons_the_configuration() -> None:
    gap = [*PRE, CONTACT, RECOVERY, None, BREAK, *flat("1.1098", 3)]
    result = run(gap)
    assert any("DONNÉES_REPLI_INCOMPLÈTES" in a for a in kinds(result, "CONFIGURATION_ABANDONNÉE"))
    assert decided(result) == []


def test_an_h4_close_below_the_lower_bound_abandons_but_below_k_does_not() -> None:
    deep = PRE + flat("1.0960", 4) + [CONTACT, RECOVERY, CONFIRM, BREAK, *flat("1.1098", 2)]
    result = run(deep)
    assert any("repli trop profond" in a for a in kinds(result, "CONFIGURATION_ABANDONNÉE"))
    assert decided(result) == []
    below_k = PRE + flat("1.1000", 4) + [CONTACT, RECOVERY, CONFIRM, BREAK, *flat("1.1098", 2)]
    assert decided(run(below_k)) == [at(8)]  # 1.1000 < K = 1.1040, above K - z A


def test_the_configuration_expires_after_t_max_h4() -> None:
    late = PRE + flat("1.1118", 8) + [CONTACT, RECOVERY, CONFIRM, BREAK, *flat("1.1098", 2)]
    assert decided(run(late, S2Params(pivot_d1=1, pivot_h4=1, pivot_h1=1, atr_period=2, max_setup_h4=3))) == []
    assert decided(run(late)) == [at(12)]


# ---------------------------------------------------------------- execution and exits


def test_a_buy_whose_first_price_is_already_beyond_the_target_buys_at_the_ask_and_sells_at_the_bid() -> None:
    jump = [*PRE, CONTACT, RECOVERY, CONFIRM, BREAK, h1("1.1251", "1.1251", "1.1251", "1.1251"), *flat("1.1251", 2)]
    (trade,) = run(jump).trades
    assert trade.exit_reason == "CIBLE_ATTEINTE_À_L'EXÉCUTION"
    assert trade.entry_utc == trade.exit_utc
    assert trade.entry_price == d("1.1252") and trade.exit_price == d("1.1251")  # ask, then bid
    assert trade.net_account is not None and trade.net_account < 0  # "target reached" lost money


def test_time_exit_after_h_max_h4_started_after_the_execution() -> None:
    params = S2Params(pivot_d1=1, pivot_h4=1, pivot_h1=1, atr_period=2, max_hold_h4=2)
    result = run([*PRE, CONTACT, RECOVERY, CONFIRM, BREAK, *flat("1.1100", 14)], params)
    (trade,) = result.trades
    # Execution at I+4h+5min (09:05); first H4 starting after it: 09:00-13:00 does not, 13:00 does.
    # The 2nd such H4 (17:00-21:00) is available at 21:00; exit at the first tick after it.
    assert trade.exit_reason == "SORTIE_TEMPORELLE" and trade.exit_utc == at(16) + STEP
    # A missing H4 during the holding (no quote 13:00-17:00) does not lengthen it.
    holed = [*PRE, CONTACT, RECOVERY, CONFIRM, BREAK, *flat("1.1100", 4), *[None] * 4, *flat("1.1100", 6)]
    (trade,) = run(holed, params).trades
    assert trade.exit_reason == "SORTIE_TEMPORELLE" and trade.exit_utc == at(16) + STEP


def test_sell_mirror_uses_the_ask_for_the_stop_extreme_and_the_target() -> None:
    sell = [*PRE, CONTACT, RECOVERY, CONFIRM, BREAK, h1("1.1098", "1.1250", "1.1097", "1.1240")]
    sell += [h1("1.1240", "1.1251", "1.1239", "1.1245"), *flat("1.1245", 2)]
    result = run(sell, down=True)
    (trade,) = result.trades
    assert trade.side is Side.SHORT
    e = MIRROR - d("1.1250")  # E of the sell, on the bid
    # A bid at E (ask = E + spread) does not reach the target; the next bid E - 1 pip does, at the ask.
    assert trade.exit_reason == "CIBLE" and trade.exit_price == e
    assert trade.exit_utc == at(5) + 2 * STEP  # third tick of that hour: the mirrored high
    h1_bars = candles(ticks_for([mirror(s) for s in sell]), Timeframe.H1)
    pullback = [b for b in h1_bars if b["start_utc"] >= START + timedelta(hours=28) and b["end_utc"] <= at(4)]
    assert trade.stop > max(b["ask_high"] for b in pullback)  # beyond the ask extreme of the pullback


# ---------------------------------------------------------------- quote gaps: scenarios A, B and C


# Long open from I+4h; two hours without quotes (12:00-14:00 UTC), price unchanged on both sides;
# then a second configuration (E' 1.1200 on H4 21-01, I' at 05:00) and its breakout at I+28h,
# all between the first trade's stop and target.
AFTER_GAP: list[Spec | None] = [
    *PRE,
    CONTACT,
    RECOVERY,
    CONFIRM,
    BREAK,
    *flat("1.1100", 3),
    None,
    None,
    *flat("1.1100", 7),  # the H4 holding the gap is unusable: E' needs usable neighbours
    *block("1.1100", "1.1200", "1.1095", "1.1190"),  # E'
    *block("1.1190", "1.1195", "1.1120", "1.1130"),  # confirms E'
    h1("1.1080", "1.1082", "1.1070", "1.1075"),  # contact
    h1("1.1075", "1.1110", "1.1072", "1.1100"),  # recovery pivot 1.1110
    h1("1.1100", "1.1105", "1.1085", "1.1090"),  # confirms it
    h1("1.1090", "1.1115", "1.1088", "1.1112"),  # breakout
    *flat("1.1112", 2),
]


def test_gap_scenarios_a_b_c_lead_to_different_later_decisions() -> None:
    results = {s: run(AFTER_GAP, scenario=s) for s in GapScenario}
    a, b, c = (results[s] for s in GapScenario)
    first_a = a.open_trade if a.open_trade is not None else a.trades[0]
    assert first_a.decided_utc == at(4) and first_a.indeterminate and first_a.exit_utc is None
    assert b.trades[0].exit_reason == "STOP_SCÉNARIO_B" and b.trades[0].exit_price == b.trades[0].stop
    assert c.trades[0].exit_reason == "CIBLE_SCÉNARIO_C" and c.trades[0].exit_price == d("1.1250")
    # Accounted at the first tick that closes the gap, never before; the gap interval is logged apart.
    assert b.trades[0].exit_utc == c.trades[0].exit_utc == at(9)
    assert any("comptabilisé au premier tick" in h for h in c.trades[0].hypotheses)
    assert kinds(c, "SCÉNARIO_C") and kinds(a, "SCÉNARIO_A")
    # First decision after the gap: A still holds the position; B and C are flat, with different equity.
    record = {s: next(r for r in results[s].decisions if r.decision_utc == at(10)) for s in GapScenario}
    assert record[GapScenario.OBSERVED_ONLY].position_action is PositionAction.HELD
    assert record[GapScenario.STOP_FIRST].position_action is PositionAction.FLAT
    assert record[GapScenario.TARGET_FIRST].position_action is PositionAction.FLAT
    equity = {s: record[s].known["account"]["equity"] for s in GapScenario}
    assert equity[GapScenario.STOP_FIRST] < equity[GapScenario.OBSERVED_ONLY] < equity[GapScenario.TARGET_FIRST]
    # The second configuration's breakout: not evaluated under A, an entry under B and C.
    breakout = {s: next(r for r in results[s].decisions if r.decision_utc == at(28)) for s in GapScenario}
    assert breakout[GapScenario.OBSERVED_ONLY].entry_action is EntryAction.NOT_EVALUATED
    assert breakout[GapScenario.STOP_FIRST].entry_action is EntryAction.ENTRY_DECIDED
    assert breakout[GapScenario.TARGET_FIRST].entry_action is EntryAction.ENTRY_DECIDED
    after_stop, after_target = breakout[GapScenario.STOP_FIRST].order, breakout[GapScenario.TARGET_FIRST].order
    assert after_stop is not None and after_target is not None
    assert after_stop["budget"] < after_target["budget"]  # sized on different equity


def test_no_capital_is_released_for_a_decision_inside_the_gap() -> None:
    ticks = ticks_for(AFTER_GAP)
    h1_bars = candles(ticks, Timeframe.H1)
    hole = at(7)  # an H1 candle inside the gap, flagged incomplete: a decision happens at its end
    h1_bars.append(
        {
            **h1_bars[-1],
            "start_utc": hole,
            "end_utc": hole + timedelta(hours=1),
            "complete_at_close": False,
            "flags_at_close": ["trou de cotation"],
        }
    )
    h1_bars.sort(key=lambda b: b["start_utc"])
    feed = TickFeed(ticks)
    result = S2Backtest(
        h1_bars,
        candles(ticks, Timeframe.H4),
        d1_context(),
        feed,
        feed.gaps(timedelta(minutes=10)),
        P,
        ResearchConfig(costs=COSTS, **FINE),
        scenario=GapScenario.TARGET_FIRST,
    ).run()
    inside = next(r for r in result.decisions if r.decision_utc == hole + timedelta(hours=1))
    assert inside.position_action is PositionAction.HELD  # the exit is booked later, at the gap's end
    assert result.trades[0].exit_utc == at(9)


# ---------------------------------------------------------------- comparison: H4 trigger


def test_h4_trigger_applies_the_whole_sequence_to_h4_candles() -> None:
    h4_params = S2Params(pivot_d1=1, pivot_h4=1, pivot_h1=1, atr_period=2, trigger=Timeframe.H4)
    specs = PRE + block("1.1090", "1.1092", "1.1070", "1.1072")  # H4 contact
    specs += block("1.1072", "1.1110", "1.1068", "1.1075")  # H4 recovery pivot 1.1110
    specs += block("1.1075", "1.1080", "1.1060", "1.1065")  # confirms it
    specs += block("1.1065", "1.1115", "1.1063", "1.1112")  # first H4 close above 1.1110
    specs += flat("1.1112", 4)
    result = run(specs, h4_params)
    assert decided(result) == [at(16)]
    assert all(r.known["trigger_candle"]["timeframe"] == "4h" for r in result.decisions)
    # The same path read with the H1 trigger is a different sequence (another decision instant).
    assert decided(run(specs)) != [at(16)]


# ---------------------------------------------------------------- reading: relative drawdown


def test_relative_drawdown_is_the_true_maximum_and_the_first_review_crossing_is_reported() -> None:
    dd = RelativeDrawdown(d("2000"))
    for k, equity in enumerate(["2000", "1870", "2600", "2450", "2700"]):
        dd.observe(START + timedelta(hours=k), d(equity), None)
    # Deepest fall in EUR: 2600 -> 2450 (150 EUR, 5.77 %); deepest in %: 2000 -> 1870 (130 EUR, 6.5 %).
    assert dd.max_ratio == d("130") / d("2000") and dd.max_utc == START + timedelta(hours=1)
    crossing = dd.first_review_crossing
    assert crossing is not None and crossing["utc"] == START + timedelta(hours=1)
    assert dd.peak_eur == d("2700")  # the trajectory goes on after the crossing


# ---------------------------------------------------------------- H4 absent, its H1 present


def test_an_absent_h4_with_its_h1_present_abandons_the_configuration_as_soon_as_knowable() -> None:
    specs = [*BASE, *flat("1.1250", 4)]
    ticks = ticks_for(specs)
    h4 = [b for b in candles(ticks, Timeframe.H4) if b["start_utc"] != at(0)]  # the H4 05:00-09:00 is missing
    feed = TickFeed(ticks)
    result = S2Backtest(
        candles(ticks, Timeframe.H1),  # every H1 of that slot is present
        h4,
        d1_context(),
        feed,
        feed.gaps(timedelta(minutes=10)),
        P,
        ResearchConfig(costs=COSTS, **FINE),
    ).run()
    (abandon,) = [e for e in result.journal if e.kind == "CONFIGURATION_ABANDONNÉE"]
    assert "DONNÉES_REPLI_INCOMPLÈTES" in abandon.detail and at(0).isoformat() in abandon.detail
    assert abandon.utc == at(4)  # the end of the missing slot: knowable then, not before
    assert all(r.entry_action is not EntryAction.ENTRY_DECIDED for r in result.decisions)
    assert result.trades == [] and result.open_trade is None
    # The decision line itself keeps the precise reason; a later one without configuration is "no signal".
    line = next(r for r in result.decisions if r.decision_utc == at(4))
    assert line.entry_action is EntryAction.NOT_COMPUTABLE
    assert any("DONNÉES_REPLI_INCOMPLÈTES" in reason and at(0).isoformat() in reason for reason in line.reasons)
    later = next(r for r in result.decisions if r.decision_utc == at(5))
    assert later.entry_action is EntryAction.NO_SIGNAL and later.reasons == ["pas de configuration"]


# ---------------------------------------------------------------- the sheet's §5 example, approved parameters


def _example_ticks() -> list[Tick]:
    """Synthetic history from Friday 2019-01-11 18:00 UTC (winter: H4 at 22, 02, 06, 10, 14, 18 UTC).

    The 14 true ranges up to the H4 ending at I sum to 280 pips: the ATR is seeded exactly at I
    (15th H4 of the history) at 20 pips, as in the example.
    """
    h4_path = [
        ("1.1420", "1.1430", "1.1415", "1.1425"),  # Fri 18-22
        ("1.1425", "1.1432", "1.1413", "1.1428"),  # Mon (from Sun 22:00)
        ("1.1428", "1.1436", "1.1417", "1.1433"),
        ("1.1433", "1.1440", "1.1423", "1.1438"),
        ("1.1438", "1.1450", "1.1434", "1.1442"),  # Mon 10-14: K
        ("1.1442", "1.1446", "1.1432", "1.1436"),
        ("1.1436", "1.1444", "1.1430", "1.1440"),
        ("1.1440", "1.1445", "1.1435", "1.1443"),  # Tue 22-02: K confirmed at 02:00
        ("1.1443", "1.1468", "1.1441", "1.1466"),
        ("1.1466", "1.1490", "1.1462", "1.1488"),
        ("1.1488", "1.1510", "1.1485", "1.1507"),
        ("1.1507", "1.1530", "1.1503", "1.1512"),  # Tue 14-18: E
        ("1.1512", "1.1515", "1.1495", "1.1497"),
        ("1.1497", "1.1499", "1.1478", "1.1480"),
    ]
    hours: list[Spec] = [spec for o, h, low, c in h4_path for spec in block(o, h, low, c)]
    hours += [
        h1("1.1480", "1.1482", "1.1476", "1.1478"),  # Wed 02-06: E confirmed at 06:00 (I)
        h1("1.1478", "1.1479", "1.1468", "1.1470"),
        h1("1.1470", "1.1474", "1.1459", "1.1465"),  # 04-05: meets the zone before I, does not count
        h1("1.1465", "1.1468", "1.1461", "1.1462"),
        h1("1.1462", "1.1470", "1.1461", "1.1466"),  # 06-13: above the zone
        h1("1.1466", "1.1472", "1.1463", "1.1468"),
        h1("1.1468", "1.1474", "1.1465", "1.1470"),
        h1("1.1470", "1.1475", "1.1466", "1.1472"),
        h1("1.1472", "1.1476", "1.1468", "1.1474"),
        h1("1.1474", "1.1477", "1.1470", "1.1473"),
        h1("1.1473", "1.1475", "1.1466", "1.1469"),
        h1("1.1469", "1.1471", "1.1455", "1.1460"),  # 13-14: contact
        h1("1.1460", "1.1470", "1.1457", "1.1468"),
        h1("1.1468", "1.1478", "1.1464", "1.1470"),  # 15-16: recovery pivot 1.1478
        h1("1.1470", "1.1472", "1.1458", "1.1462"),
        h1("1.1462", "1.1465", "1.1451", "1.1463"),  # 17-18: PL 1.1451; threshold confirmed at 18:00
        h1("1.1463", "1.1477", "1.1460", "1.1476"),  # 18-19: below the threshold
        h1("1.1476", "1.1480", "1.1474", "1.1481"),  # 19-20: breakout, last bid 1.1481 / ask 1.1482
    ]
    ticks, moment = [], utc(2019, 1, 11, 18)
    for o, h, low, c in hours:
        while market_state(moment) is not MarketState.OPEN:
            moment += timedelta(hours=1)
        for j in range(12):
            bid = o if j == 0 else h if j == 1 else low if j == 2 else c
            ticks.append(Tick(moment + j * STEP, bid, bid + SPREAD))
        moment += timedelta(hours=1)
    first_after = moment + timedelta(milliseconds=180)  # 20:00:00.180, strictly after D = 20:00
    ticks += [Tick(first_after + j * STEP, d("1.1483"), d("1.1484")) for j in range(12)]
    return ticks


def _example_d1_history() -> list[dict[str, Any]]:
    """Seven trading days before the ticks: rising highs (days 2, 5) and lows (days 3, 6), p = 2."""
    rows = [
        ("1.1300", "1.1330", "1.1280", "1.1320"),
        ("1.1320", "1.1350", "1.1300", "1.1340"),
        ("1.1340", "1.1410", "1.1330", "1.1380"),
        ("1.1380", "1.1390", "1.1290", "1.1330"),
        ("1.1330", "1.1395", "1.1320", "1.1380"),
        ("1.1380", "1.1460", "1.1350", "1.1400"),
        ("1.1400", "1.1440", "1.1310", "1.1420"),
    ]
    bars = []
    for day, (o, h, low, c) in zip((2, 3, 4, 7, 8, 9, 10), rows, strict=True):
        start = candle_start(utc(2019, 1, day, 12), Timeframe.D1)
        prices = {"open": d(o), "high": d(h), "low": d(low), "close": d(c)}
        bars.append(
            {
                "start_utc": start,
                "end_utc": candle_end(start, Timeframe.D1),
                **{f"bid_{k}": v for k, v in prices.items()},
                **{f"ask_{k}": v + SPREAD for k, v in prices.items()},
                "complete_at_close": True,
                "flags_at_close": [],
            }
        )
    return bars


def test_the_sheet_example_is_reproduced_end_to_end_with_the_approved_parameters() -> None:
    ticks = _example_ticks()
    feed = TickFeed(ticks)
    result = S2Backtest(
        candles(ticks, Timeframe.H1),
        candles(ticks, Timeframe.H4),
        _example_d1_history() + candles(ticks, Timeframe.D1),
        feed,
        feed.gaps(timedelta(minutes=10)),
        S2Params(),  # approved values: pivots 2 / 3 / 2, ATR 14, z 0.5, b 0.25, R_min 1, T_max 30, H_max 60
        ResearchConfig(costs=RESEARCH_COSTS),  # engine defaults: 2 000 EUR, 0.25 %, minimum and step 0.1
    ).run()
    (setup,) = result.setups
    assert setup.side is Side.LONG and setup.extreme.level == d("1.1530") and setup.known_level.level == d("1.1450")
    assert setup.identified_utc == utc(2019, 1, 16, 6) and setup.atr == d("0.0020")
    assert (setup.lower, setup.upper) == (d("1.1440"), d("1.1460"))
    assert setup.contact is not None and f"contact {utc(2019, 1, 16, 13).isoformat()}" in setup.history
    decision = utc(2019, 1, 16, 20)
    (record,) = [r for r in result.decisions if r.entry_action is EntryAction.ENTRY_DECIDED]
    assert record.decision_utc == decision and record.signal is not None and record.order is not None
    assert record.signal["threshold"] == d("1.1478")
    assert record.signal["threshold_confirmed_utc"] == utc(2019, 1, 16, 18)
    assert record.signal["stop"] == d("1.1446") and record.signal["target"] == d("1.1530")
    assert record.signal["reward_risk"].quantize(d("0.01")) == d("1.19")
    assert record.order["size"] == d("0.1") and record.order["budget"] == d("5.0000")
    assert record.order["estimated_stop_loss"].quantize(d("0.01")) == d("3.39")
    assert record.known["quote"]["bid"] == d("1.1481") and record.known["quote"]["ask"] == d("1.1482")
    trade = result.open_trade
    assert trade is not None
    assert trade.entry_utc == decision + timedelta(milliseconds=180) and trade.entry_price == d("1.1484")


# ---------------------------------------------------------------- time exit: a deadline of its own


def test_time_exit_deadline_does_not_need_a_decision_candle() -> None:
    params = S2Params(pivot_d1=1, pivot_h4=1, pivot_h1=1, atr_period=2, max_hold_h4=2)
    # Deadline 21:00 (2nd H4 starting after the 09:05 execution). The H1 20:00-21:00 is absent: no
    # decision closes at 21:00; quotes resume at 21:00 (a tick exactly at the deadline) then 21:05.
    specs = [*PRE, CONTACT, RECOVERY, CONFIRM, BREAK, *flat("1.1100", 11), None, *flat("1.1100", 3)]
    a = run(specs, params)
    assert all(r.decision_utc != at(16) for r in a.decisions)
    (trade,) = a.trades
    assert trade.exit_reason == "SORTIE_TEMPORELLE" and trade.exit_utc == at(16) + STEP  # 21:05, not 22:05
    assert kinds(a, "ÉCHÉANCE_TEMPORELLE") == [at(16).isoformat()]
    # The gap scenarios keep their priority: the tick closing the gap (21:00) comes first.
    (b_trade,) = run(specs, params, GapScenario.STOP_FIRST).trades
    (c_trade,) = run(specs, params, GapScenario.TARGET_FIRST).trades
    assert (b_trade.exit_reason, b_trade.exit_utc) == ("STOP_SCÉNARIO_B", at(16))
    assert (c_trade.exit_reason, c_trade.exit_utc) == ("CIBLE_SCÉNARIO_C", at(16))
    # Target and deadline on the same first tick after the deadline: the target comes first.
    on_target = [
        *PRE,
        CONTACT,
        RECOVERY,
        CONFIRM,
        BREAK,
        *flat("1.1100", 12),
        h1("1.1100", "1.1260", "1.1100", "1.1260"),
    ]
    (trade,) = run(on_target, params).trades
    assert (trade.exit_reason, trade.exit_utc) == ("CIBLE", at(16) + STEP)


def test_time_exit_deadline_in_the_h4_comparison_mode() -> None:
    params = S2Params(pivot_d1=1, pivot_h4=1, pivot_h1=1, atr_period=2, trigger=Timeframe.H4, max_hold_h4=2)
    specs = PRE + block("1.1090", "1.1092", "1.1070", "1.1072")
    specs += block("1.1072", "1.1110", "1.1068", "1.1075")
    specs += block("1.1075", "1.1080", "1.1060", "1.1065")
    specs += block("1.1065", "1.1115", "1.1063", "1.1112")  # entry decided at 21:00, executed 21:05
    holed: list[Spec | None] = [*specs, *flat("1.1112", 8), *[None] * 4, *flat("1.1112", 4)]  # H4 05-09 absent
    result = run(holed, params)
    (trade,) = result.trades
    # Deadline: end of the 2nd H4 starting after 21:05 (01-05, 05-09) = 09:00, with no H4 decision then.
    assert all(r.decision_utc != at(28) for r in result.decisions)
    assert trade.exit_reason == "SORTIE_TEMPORELLE" and trade.exit_utc == at(28) + STEP


# ---------------------------------------------------------------- ATR: continuity of the expected H4


def _h4_slots(first: datetime, count: int) -> list[datetime]:
    slots: list[datetime] = []
    moment = first
    while len(slots) < count:
        if candle_start(moment, Timeframe.H4) == moment and market_state(moment) is MarketState.OPEN:
            slots.append(moment)
        moment += timedelta(hours=1)
    return slots


def _constant_range_bars(starts: list[datetime]) -> list[dict[str, Any]]:
    return [
        {
            "start_utc": s,
            "end_utc": candle_end(s, Timeframe.H4),
            "bid_high": d("1.1010"),
            "bid_low": d("1.0990"),
            "bid_close": d("1.1000"),
        }
        for s in starts
    ]


def test_s2_atr_restarts_after_an_absent_h4_but_not_after_the_weekly_closure() -> None:
    period = 3
    # Thursday to the next Tuesday: the weekly closure is inside, nothing is absent.
    weekend = _constant_range_bars(_h4_slots(utc(2019, 3, 7, 21), 20))
    s1_atr, s2_atr = WilderAtr(weekend, period), ContinuousWilderAtr(weekend, period)
    assert [s2_atr.at(t, ok) for t in range(20)] == [s1_atr.at(t, ok) for t in range(20)]
    assert s2_atr.at(19, ok) == d("0.0020")
    # One expected H4 absent mid-week (index 6 removed).
    slots = _h4_slots(START, 14)
    holed = _constant_range_bars(slots[:6] + slots[7:])
    s1_atr, s2_atr = WilderAtr(holed, period), ContinuousWilderAtr(holed, period)
    assert s1_atr.at(7, ok) is not None  # S1's reading chains the true ranges across the hole
    # Candle 6 now follows the hole: its close is the new reference, 3 valid true ranges are needed.
    assert [s2_atr.at(t, ok) for t in (6, 7, 8)] == [None, None, None]
    assert s2_atr.at(9, ok) == d("0.0020")


def test_an_h4_hole_before_the_pullback_makes_the_atr_unavailable_at_i() -> None:
    params = S2Params(pivot_d1=1, pivot_h4=1, pivot_h1=1, atr_period=3)
    specs: list[Spec | None] = [
        *block("1.1000", "1.1005", "1.0995", "1.1000") * 4,
        *block("1.1000", "1.1040", "1.0998", "1.1030"),  # K
        *block("1.1030", "1.1035", "1.1010", "1.1020"),
        *flat("1.1020", 4),
        *[None] * 4,  # an expected H4 without any quote, before E: outside the pullback
        *flat("1.1020", 4),
        *block("1.1020", "1.1250", "1.1015", "1.1240"),  # E
        *block("1.1240", "1.1245", "1.1080", "1.1090"),  # confirms E: I
        CONTACT,
        RECOVERY,
        CONFIRM,
        BREAK,
        *flat("1.1098", 2),
    ]
    identified = START + timedelta(hours=44)
    result = run(specs, params)
    assert result.setups == [] and decided(result) == []
    line = next(r for r in result.decisions if r.decision_utc == identified)
    assert line.entry_action is EntryAction.NOT_COMPUTABLE
    assert line.reasons == ["configuration refusée, LONG : ATR H4 indisponible à I"]
    # Without the continuity rule (S1's reading), the ATR would have been available at I.
    h4 = candles(ticks_for(specs), Timeframe.H4)
    i_bar = next(k for k, b in enumerate(h4) if b["end_utc"] == identified)
    assert WilderAtr(h4, 3).at(i_bar, ok) is not None


# ---------------------------------------------------------------- decision line: data first (sheet §8)


def test_an_unusable_trigger_candle_without_configuration_is_not_computable_not_no_signal() -> None:
    ticks = ticks_for(BASE)
    h1_bars = candles(ticks, Timeframe.H1)
    degraded = 2  # Sunday 23:00-00:00, long before any configuration
    h1_bars[degraded] = {**h1_bars[degraded], "complete_at_close": False, "flags_at_close": ["trou de cotation"]}
    feed = TickFeed(ticks)
    result = S2Backtest(
        h1_bars,
        candles(ticks, Timeframe.H4),
        d1_context(),
        feed,
        feed.gaps(timedelta(minutes=10)),
        P,
        ResearchConfig(costs=COSTS, **FINE),
    ).run()
    line = next(r for r in result.decisions if r.decision_utc == h1_bars[degraded]["end_utc"])
    assert line.position_action is PositionAction.FLAT and line.known["setup"] is None
    assert line.entry_action is EntryAction.NOT_COMPUTABLE
    assert line.reasons[0] == "bougie de déclenchement INTERRUPTION_INEXPLIQUÉE"
    valid = next(r for r in result.decisions if r.decision_utc == h1_bars[degraded + 1]["end_utc"])
    assert valid.entry_action is EntryAction.NO_SIGNAL and valid.reasons == ["pas de configuration"]
    # The configuration lifecycle is unchanged: the same entry as BASE follows.
    assert decided(result) == [at(4)]
