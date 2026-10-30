"""Synthetic tests of the offline S1 engine: chronology, bid/ask execution, stops, sizing, scenarios.

Candles are built from ticks whose open, high, low and close are set exactly: in each H4 candle a
tick every 5 minutes, the first at the open, the second at the high, the third at the low, all the
others at the close. Spread: 1 pip. Week of 2019-03-11, US summer time: H4 at 21, 01, 05, 09, 13,
17 UTC; trading days start at 21:00 UTC; the weekly closure runs Friday 21:00 → Sunday 21:00 UTC.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D
from typing import Any

import pytest

from forex_bot.backtest.bar_state import BarState, GapIndex, bar_state
from forex_bot.backtest.engine import (
    BacktestResult,
    ResearchConfig,
    S1Backtest,
    ScenarioPolicy,
    StopType,
)
from forex_bot.backtest.feed import Silence, Tick, TickFeed, classify_silence
from forex_bot.backtest.s1 import S1Params, WilderAtr, evaluate_entry
from forex_bot.history.bars import Gap
from forex_bot.history.calendar import MarketState, Timeframe, candle_end, candle_start, market_state
from forex_bot.risk import Cost, CostModel, CostStatus, Side

SPREAD = D("0.0001")
STEP = timedelta(minutes=5)
FIRST_H4 = datetime(2019, 3, 10, 21, tzinfo=UTC)  # Sunday 17:00 New York: Monday's first H4

FLAT = (D("1.1000"), D("1.1005"), D("1.0995"), D("1.1000"))
BREAKOUT = (D("1.1000"), D("1.1030"), D("1.0998"), D("1.1025"))  # close above the flat highs
HOLD = (D("1.1025"), D("1.1030"), D("1.1020"), D("1.1025"))

COSTS = CostModel(
    slippage_pips=Cost(CostStatus.ASSUMED, D("0.5"), "scénario de test"),
    commission_per_contract=Cost(CostStatus.ASSUMED, D("0"), "scénario de test"),
    financing_per_contract_per_night=Cost(CostStatus.ASSUMED, D("0.10"), "scénario de test"),
    conversion_fee_rate=Cost(CostStatus.ASSUMED, D("0"), "scénario de test"),
    guaranteed_stop_premium_per_contract=Cost(CostStatus.ASSUMED, D("0.30"), "scénario de test"),
)
NO_FILTER = S1Params(use_d1_filter=False)


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def h4_starts(count: int) -> list[datetime]:
    starts: list[datetime] = []
    moment = FIRST_H4
    while len(starts) < count:
        if candle_start(moment, Timeframe.H4) == moment and market_state(moment) is MarketState.OPEN:
            starts.append(moment)
        moment += timedelta(hours=1)
    return starts


def ticks_for(spec: list[tuple[D, D, D, D]]) -> list[Tick]:
    ticks = []
    for start, (o, h, low, c) in zip(h4_starts(len(spec)), spec, strict=True):
        for j in range(48):
            bid = o if j == 0 else h if j == 1 else low if j == 2 else c
            ticks.append(Tick(start + j * STEP, bid, bid + SPREAD))
    return ticks


def candles(ticks: list[Tick], timeframe: Timeframe) -> list[dict[str, Any]]:
    groups: dict[datetime, list[Tick]] = defaultdict(list)
    for tick in ticks:
        groups[candle_start(tick.ts_utc, timeframe)].append(tick)
    return [
        {
            "start_utc": start,
            "end_utc": candle_end(start, timeframe),
            "bid_open": g[0].bid,
            "bid_high": max(t.bid for t in g),
            "bid_low": min(t.bid for t in g),
            "bid_close": g[-1].bid,
            "ask_open": g[0].ask,
            "ask_high": max(t.ask for t in g),
            "ask_low": min(t.ask for t in g),
            "ask_close": g[-1].ask,
            "complete_at_close": True,
            "flags_at_close": [],
        }
        for start, g in sorted(groups.items())
    ]


def run(ticks: list[Tick], params: S1Params = NO_FILTER, **config: Any) -> tuple[BacktestResult, list[dict[str, Any]]]:
    feed = TickFeed(ticks)
    h4 = candles(ticks, Timeframe.H4)
    result = S1Backtest(
        h4,
        candles(ticks, Timeframe.D1),
        feed,
        feed.gaps(timedelta(minutes=10)),
        params,
        ResearchConfig(costs=config.pop("costs", COSTS), **config),
    ).run()
    return result, h4


def kinds(result: BacktestResult, kind: str) -> list[str]:
    return [e.detail for e in result.journal if e.kind == kind]


def first_trade(result: BacktestResult) -> Any:
    return result.trades[0] if result.trades else result.open_trade


# ---------------------------------------------------------------- chronology and bid/ask execution


def test_decision_at_close_executes_at_the_first_tick_strictly_after_it_at_the_ask() -> None:
    result, h4 = run(ticks_for([FLAT] * 25 + [BREAKOUT, HOLD, HOLD]))
    decision = h4[25]["end_utc"]
    (decided,) = [e for e in result.journal if e.kind == "ENTRÉE_DÉCIDÉE"]
    assert decided.utc == decision
    trade = first_trade(result)
    # The tick stamped exactly at the decision instant (open of the next candle) is not used.
    assert trade.entry_utc == decision + STEP
    assert trade.side is Side.LONG and trade.entry_price == HOLD[1] + SPREAD  # ask of that tick


def test_sizing_quote_is_the_last_tick_strictly_before_the_decision() -> None:
    result, _ = run(ticks_for([FLAT] * 25 + [BREAKOUT, HOLD, HOLD]))
    trade = first_trade(result)
    # Last tick of the breakout candle (its close), not the tick stamped at the decision instant.
    assert trade.estimate.entry_estimate == BREAKOUT[3] + SPREAD


def test_latency_moves_the_decision_and_the_execution() -> None:
    latency = timedelta(minutes=12)
    result, h4 = run(ticks_for([FLAT] * 25 + [BREAKOUT, HOLD, HOLD]), latency=latency)
    (decided,) = [e for e in result.journal if e.kind == "ENTRÉE_DÉCIDÉE"]
    assert decided.utc == h4[25]["end_utc"] + latency
    assert first_trade(result).entry_utc == h4[25]["end_utc"] + 3 * STEP  # first tick after 12 min
    assert first_trade(result).entry_price == HOLD[3] + SPREAD


def test_channel_exit_sells_at_the_bid_of_the_first_tick_after_the_decision() -> None:
    drop = (D("1.1025"), D("1.1026"), D("1.1015"), D("1.1016"))  # close below the 10-candle low (1.1020)
    spec = [FLAT] * 25 + [BREAKOUT] + [HOLD] * 10 + [drop, HOLD]
    result, h4 = run(spec_ticks := ticks_for(spec))
    trade = result.trades[0]
    assert trade.exit_reason == "SORTIE_CANAL"
    assert trade.exit_utc == h4[36]["end_utc"] + STEP
    tick = next(t for t in spec_ticks if t.ts_utc == trade.exit_utc)
    assert trade.exit_price == tick.bid


def test_signal_on_the_last_candle_before_the_weekend_expires() -> None:
    result, _ = run(ticks_for([FLAT] * 29 + [BREAKOUT] + [HOLD] * 3))  # candle 29: Friday 17:00-21:00 UTC
    assert kinds(result, "SIGNAL_EXPIRÉ") and not result.trades and result.open_trade is None


def test_d1_context_is_the_last_available_d1_never_a_calendar_date_join() -> None:
    params = S1Params(use_d1_filter=True, d1_channel=1)
    # Breakout on Thursday's last H4 (ends 21:00 UTC with Thursday's D1): that D1 is available and bullish.
    at_boundary, _ = run(ticks_for([FLAT] * 23 + [BREAKOUT, HOLD]), params)
    assert first_trade(at_boundary) is not None
    # Breakout on Thursday 09:00-13:00 UTC: Thursday's D1 is not closed; Wednesday's (flat) is the context.
    midday, _ = run(ticks_for([FLAT] * 21 + [BREAKOUT, HOLD, HOLD]), params)
    assert first_trade(midday) is None
    assert "cassure haussière contre le contexte D1" in kinds(midday, "ABSTENTION")


# ---------------------------------------------------------------- stops


def _guaranteed_and_normal(spec_ticks: list[Tick]) -> tuple[Any, Any]:
    guaranteed, _ = run(spec_ticks, stop_type=StopType.GUARANTEED)
    normal, _ = run(spec_ticks, stop_type=StopType.NORMAL)
    return guaranteed.trades[0], normal.trades[0]


def test_observed_crossing_on_the_bid_closes_a_long_position() -> None:
    probe, _ = run(ticks_for([FLAT] * 25 + [BREAKOUT, HOLD]))
    stop = first_trade(probe).stop
    near = (D("1.1025"), D("1.1026"), stop + D("0.00001"), D("1.1025"))  # bid just above: no trigger
    through = (D("1.1025"), D("1.1026"), stop - D("0.0004"), D("1.1025"))
    spec_ticks = ticks_for([FLAT] * 25 + [BREAKOUT, HOLD, near, through, HOLD])
    guaranteed, normal = _guaranteed_and_normal(spec_ticks)
    trigger = h4_starts(29)[28] + 2 * STEP  # low tick of the `through` candle
    for trade in (guaranteed, normal):
        assert trade.exit_reason == "STOP_OBSERVÉ" and trade.exit_utc == trigger
    assert guaranteed.exit_price == stop  # execution at S; the premium is a separate cost line
    assert guaranteed.costs_quote["prime de stop garanti"] == D("0.30") * guaranteed.size
    assert normal.exit_price == stop - D("0.0004")  # first observable bid at the trigger
    assert "prime de stop garanti" not in normal.costs_quote


def test_short_stop_is_triggered_on_the_ask() -> None:
    fall = (D("1.1000"), D("1.1002"), D("1.0970"), D("1.0975"))
    hold = (D("1.0975"), D("1.0980"), D("1.0970"), D("1.0975"))
    probe, _ = run(ticks_for([FLAT] * 25 + [fall, hold]))
    trade = first_trade(probe)
    assert trade.side is Side.SHORT and trade.entry_price == hold[1]  # sold at the bid
    ask_touch = (D("1.0975"), trade.stop - SPREAD / 2, D("1.0970"), D("1.0975"))  # bid below S, ask above
    result, _ = run(ticks_for([FLAT] * 25 + [fall, hold, ask_touch, hold]))
    assert result.trades[0].exit_reason == "STOP_OBSERVÉ"


def test_gap_through_the_stop_at_the_weekly_reopening() -> None:
    reopen = (D("1.0980"), D("1.0985"), D("1.0975"), D("1.0980"))  # Sunday open below the stop
    spec_ticks = ticks_for([FLAT] * 25 + [BREAKOUT] + [HOLD] * 4 + [reopen, reopen])
    guaranteed, normal = _guaranteed_and_normal(spec_ticks)
    sunday = h4_starts(31)[30]
    for trade in (guaranteed, normal):
        assert trade.exit_reason == "STOP_FERMETURE_CONNUE" and trade.exit_utc == sunday
        assert not trade.indeterminate
    assert guaranteed.exit_price == guaranteed.stop
    assert normal.exit_price == D("1.0980")  # first price after the closure, gap included
    assert guaranteed.costs_quote["financement overnight"] == D("0.10") * guaranteed.size * 3  # Thu → Mon


def _with_interruption(spec: list[tuple[D, D, D, D]], candle: int, first: int, last: int) -> list[Tick]:
    """Removes ticks j = first..last of an H4 candle: an unexplained silence during expected opening."""
    start = h4_starts(len(spec))[candle]
    hole = {start + j * STEP for j in range(first, last + 1)}
    return [t for t in ticks_for(spec) if t.ts_utc not in hole]


def test_unexplained_interruption_followed_by_a_price_beyond_the_stop_is_a_certain_trigger() -> None:
    after = (D("1.1025"), D("1.1026"), D("1.0980"), D("1.0980"))
    spec_ticks = _with_interruption([FLAT] * 25 + [BREAKOUT, HOLD, after, HOLD], candle=27, first=0, last=20)
    guaranteed, normal = _guaranteed_and_normal(spec_ticks)
    assert guaranteed.exit_reason == normal.exit_reason == "STOP_APRÈS_INTERRUPTION"
    assert guaranteed.exit_price == guaranteed.stop
    assert normal.exit_price == D("1.0980")
    assert any("exécution supposée" in h for h in normal.hypotheses)


# ---------------------------------------------------------------- scenarios


def _scenario_ticks() -> list[Tick]:
    """Long entry, then a 55-minute unexplained silence with both bounding quotes above the stop,
    then a second breakout once 20 usable candles have passed again."""
    second = (D("1.1025"), D("1.1065"), D("1.1024"), D("1.1060"))
    hold_high = (D("1.1060"), D("1.1065"), D("1.1055"), D("1.1060"))
    spec = [FLAT] * 25 + [BREAKOUT] + [HOLD] * 23 + [second, hold_high, hold_high]
    return _with_interruption(spec, candle=28, first=10, last=20)


def test_unobservable_crossing_gives_distinct_trajectories_propagated_to_later_decisions() -> None:
    spec_ticks = _scenario_ticks()
    h0, _ = run(spec_ticks, policy=ScenarioPolicy.NONE_TRIGGERED)
    h1, _ = run(spec_ticks, policy=ScenarioPolicy.ALL_TRIGGERED)
    # H0: the position survives the silence, is kept, flagged INDÉTERMINÉE, and blocks the second entry.
    assert not h0.trades and h0.open_trade is not None and h0.open_trade.indeterminate
    assert kinds(h0, "SCÉNARIO_H0")
    # H1: stop assumed triggered during the silence, exit at S when quotes resume; the flat
    # position lets the second breakout be taken: the scenario changes the later decisions.
    first, *_ = h1.trades
    assert first.exit_reason == "STOP_SCÉNARIO_H1" and first.indeterminate
    assert first.exit_price == first.stop and first.exit_utc == h4_starts(29)[28] + 21 * STEP
    assert h1.open_trade is not None and h1.open_trade.entry_utc > first.exit_utc
    assert h1.equity < h0.equity  # the H1 loss is booked; H0 books nothing yet
    # Same indeterminate event in both trajectories; nothing is removed.
    assert h0.open_trade.unobservable_crossings == first.unobservable_crossings


def test_second_entry_waits_for_twenty_usable_candles_after_the_interruption() -> None:
    early = (D("1.1025"), D("1.1065"), D("1.1024"), D("1.1060"))
    spec = [FLAT] * 25 + [BREAKOUT] + [HOLD] * 10 + [early, HOLD]  # breakout 8 candles after the hole
    result, _ = run(_with_interruption(spec, 28, 10, 20), policy=ScenarioPolicy.ALL_TRIGGERED)
    assert len(result.trades) == 1 and result.open_trade is None
    assert any("non utilisable dans les canaux" in d for d in kinds(result, "ABSTENTION"))


# ---------------------------------------------------------------- sizing


def test_size_is_rounded_down_on_the_up_to_date_equity() -> None:
    result, _ = run(_scenario_ticks(), policy=ScenarioPolicy.ALL_TRIGGERED)
    equity = D("2000")
    assert result.open_trade is not None
    for trade in [*result.trades, result.open_trade]:
        budget = equity * D("0.0025")
        loss = trade.estimate.loss_account_per_contract
        assert trade.size * loss <= budget < (trade.size + D("0.1")) * loss
        assert trade.estimate.complete
        if trade.net_account is not None:
            equity += trade.net_account
    assert equity == result.equity  # the second budget used the equity after the first (losing) trade


def test_unknown_cost_blocks_the_entry_instead_of_counting_zero() -> None:
    result, _ = run(ticks_for([FLAT] * 25 + [BREAKOUT, HOLD]), costs=CostModel())
    assert first_trade(result) is None
    assert any(d.startswith("coût inconnu") for d in kinds(result, "ABSTENTION"))


def test_minimum_size_above_the_budget_refuses_the_signal() -> None:
    result, _ = run(ticks_for([FLAT] * 25 + [BREAKOUT, HOLD]), min_size=D("5"))
    assert first_trade(result) is None
    assert any(d.startswith("taille minimale") for d in kinds(result, "ABSTENTION"))


# ---------------------------------------------------------------- data rules (S1 sheet §10)


def test_exit_not_computable_on_an_unusable_candle_keeps_the_stop() -> None:
    spec_ticks = ticks_for([FLAT] * 25 + [BREAKOUT, HOLD, HOLD, HOLD])
    feed = TickFeed(spec_ticks)
    h4 = candles(spec_ticks, Timeframe.H4)
    h4[27]["complete_at_close"], h4[27]["flags_at_close"] = False, ["1 tick(s) invalides exclus"]
    result = S1Backtest(h4, [], feed, [], NO_FILTER, ResearchConfig(costs=COSTS)).run()
    entry = next(e for e in result.journal if e.kind == "SORTIE_NON_CALCULABLE")
    assert entry.utc == h4[27]["end_utc"] and result.open_trade is not None


def _flat_bars(count: int) -> list[dict[str, Any]]:
    return candles(ticks_for([FLAT] * count), Timeframe.H4)


def test_atr_is_unavailable_then_reseeded_on_fourteen_valid_true_ranges() -> None:
    bars = _flat_bars(40)
    degraded = 10

    def state(i: int) -> BarState:
        return BarState.UNEXPLAINED_INTERRUPTION if i == degraded else BarState.OK

    def all_ok(i: int) -> BarState:
        return BarState.OK

    start = WilderAtr(bars, 14)
    assert start.at(13, all_ok) is None and start.at(14, all_ok) is not None  # 15th candle of the history
    atr = WilderAtr(bars, 14)
    available = [t for t in range(40) if atr.at(t, state) is not None]
    assert available[0] == degraded + 15
    assert all(atr.at(t, state) is None for t in range(degraded, degraded + 15))
    assert WilderAtr(bars, 14).at(degraded + 15, state) == D("0.0010")  # mean of TR(d+2..d+15)


def test_entry_needs_twenty_usable_candles_after_an_unusable_one() -> None:
    bars = _flat_bars(40) + candles(ticks_for([FLAT] * 40 + [BREAKOUT]), Timeframe.H4)[40:]
    degraded = 15

    def state(i: int) -> BarState:
        return BarState.UNEXPLAINED_INTERRUPTION if i == degraded else BarState.OK

    refused = evaluate_entry(degraded + 20, bars, state, WilderAtr(bars, 14), [], None, state, NO_FILTER)
    assert refused is not None and "non utilisable dans les canaux" in getattr(refused, "reason", "")


def test_bar_state_uses_only_what_is_known_at_the_decision() -> None:
    bar = _flat_bars(1)[0]
    end = bar["end_utc"]
    gap = Gap(end - timedelta(minutes=1), end + timedelta(minutes=19), 20.0)
    index, ten = GapIndex([gap]), timedelta(minutes=10)
    assert bar_state(bar, end, index, ten) is BarState.OK
    assert bar_state(bar, end + timedelta(minutes=19), index, ten) is BarState.UNEXPLAINED_INTERRUPTION
    with pytest.raises(ValueError, match="non clôturée"):
        bar_state(bar, end - timedelta(minutes=1), index, ten)


def test_probable_holiday_is_unexplained_unless_a_documented_closure_is_recorded() -> None:
    holiday: dict[str, Any] = {
        "start_utc": utc(2019, 12, 24, 22),  # winter: 25 December's trading day starts 22:00 UTC
        "end_utc": utc(2019, 12, 25, 2),
        "complete_at_close": False,
        "flags_at_close": ["jour férié probable"],
    }
    index, ten = GapIndex([]), timedelta(minutes=10)
    assert bar_state(holiday, holiday["end_utc"], index, ten) is BarState.UNEXPLAINED_INTERRUPTION
    documented = frozenset({date(2019, 12, 25)})
    assert bar_state(holiday, holiday["end_utc"], index, ten, documented) is BarState.DOCUMENTED_CLOSURE
    edge = {**holiday, "flags_at_close": ["hors couverture déclarée"]}
    assert bar_state(edge, edge["end_utc"], index, ten) is BarState.PARTIAL_COVERAGE


def test_silence_classification() -> None:
    ten = timedelta(minutes=10)
    assert classify_silence(utc(2019, 3, 13, 10), utc(2019, 3, 13, 10, 5), ten) is Silence.NONE
    assert classify_silence(utc(2019, 3, 13, 10), utc(2019, 3, 13, 10, 15), ten) is Silence.UNEXPLAINED
    weekend = (utc(2019, 3, 15, 20, 59), utc(2019, 3, 17, 21))
    assert classify_silence(*weekend, ten) is Silence.KNOWN_CLOSURE
    christmas = (utc(2019, 12, 24, 21, 59), utc(2019, 12, 25, 22, 1))  # 1 min open at each end
    assert classify_silence(*christmas, ten) is Silence.UNEXPLAINED
    assert classify_silence(*christmas, ten, frozenset({date(2019, 12, 25)})) is Silence.KNOWN_CLOSURE


def test_engine_never_imports_an_order_path() -> None:
    import forex_bot.backtest.engine as engine

    source = engine.__loader__.get_source(engine.__name__) or ""  # type: ignore[union-attr]
    for forbidden in ("ig_client", "submit", "/positions/otc", "dealReference", "IgClient"):
        assert forbidden not in source
