"""DAY_01 availability study on synthetic sessions (docs/experiments/DAY01_AVAILABILITY_2015_2021.md).

Candles come from the same ticks through the real builder (DAY_01 convention), as in test_day01;
the engine reads no tick. A = 0.00200 everywhere (synthetic H4).
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal as D
from pathlib import Path
from typing import Any

import pytest
from test_day01 import (
    CONFIG,
    _flat_session,
    at,
    candles,
    example_a,
    fill,
    h4_bars,
    range_and_breakout,
    retest_from,
    tick,
)

from forex_bot.backtest.day01 import Day01Params, Trigger, london
from forex_bot.backtest.day01_availability import (
    ATR_ABSENT_H4,
    ATR_AVAILABLE,
    ATR_INITIAL,
    ATR_UNUSABLE_H4,
    CONFIRMED,
    Anchors,
    AvailabilityBacktest,
    availability,
    controls,
    expected_params,
    main,
    run_trajectory,
    weekdays,
)
from forex_bot.backtest.feed import Tick
from forex_bot.history.intraday import Grid, intraday_table

MONDAY = date(2019, 2, 11)
DAYS = [MONDAY + timedelta(days=i) for i in range(5)]


def _invalid_after_contact(day: date) -> list[Tick]:
    """Contact and close inside the zone on [08:30, 08:45), then closes below Z_b on [08:45, 09:00)."""
    ticks = range_and_breakout(day) + fill(at(day, 8, 30), at(day, 8, 45), "1.13245")
    return ticks + fill(at(day, 8, 45), at(day, 9, 0), "1.13221") + fill(at(day, 9, 0), at(day, 16, 30), "1.13300")


def _touch_and_invalidate(day: date) -> list[Tick]:
    """[08:30, 08:45) recoupes the zone (low 1.13221) and closes below Z_b = 1.13230 at once."""
    ticks = [*range_and_breakout(day), tick(at(day, 8, 30), "1.13280")]
    return (
        ticks + fill(at(day, 8, 30, 30), at(day, 8, 45), "1.13221") + fill(at(day, 8, 45), at(day, 16, 30), "1.13300")
    )


WEEK = {
    DAYS[0]: example_a(DAYS[0]),  # confirmed at 08:45 on M5 and on M15
    DAYS[1]: _flat_session(DAYS[1]),  # no breakout
    # range incomplete: silence 03:00:30 -> 03:07:00 (6.5 min), every M5 still holds a tick
    DAYS[2]: _flat_session(DAYS[2], [(at(DAYS[2], 3, 1), at(DAYS[2], 3, 7))]),
    DAYS[3]: _flat_session(DAYS[3], low="1.12700"),  # H = 55 pips > 2 A
    DAYS[4]: retest_from(DAYS[4], at(DAYS[4], 8, 30), timedelta(minutes=5)),  # M5 D = K + 5, M15 D = K + 15
}
ANCHORS = Anchors(5, frozenset({DAYS[2]}), 0)


def study(
    tmp_path: Path, by_day: dict[date, list[Tick]], anchors: Anchors = ANCHORS, h4: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    ticks = [t for day in sorted(by_day) for t in by_day[day]]
    m5, m15 = candles(tmp_path, ticks)
    start, end = london(min(by_day), time(0)), london(max(by_day) + timedelta(days=1), time(0))
    table = intraday_table("dukascopy", "EURUSD", Grid.M15, m15)
    h4 = h4_bars(end) if h4 is None else h4
    report, details = availability({Grid.M5: m5, Grid.M15: m15}, table, h4, [], CONFIG, start, end, anchors)
    report["details"] = details
    return report


def outcomes(report: dict[str, Any], unit: str) -> dict[str, str]:
    return {d["day"]: d["outcome"] for d in report["details"] if d["trigger"] == unit}


def test_week_funnel_with_both_triggers_and_every_check_passing(tmp_path: Path) -> None:
    report = study(tmp_path, WEEK)
    assert report["failed_checks"] == [] and "results_withheld" not in report
    for unit in ("M5", "M15"):
        assert outcomes(report, unit) == {
            DAYS[0].isoformat(): CONFIRMED,
            DAYS[1].isoformat(): "AUCUNE_CASSURE",
            DAYS[2].isoformat(): "RANGE_INCOMPLET",
            DAYS[3].isoformat(): "RANGE_TROP_LARGE",
            DAYS[4].isoformat(): CONFIRMED,
        }
        total = {s["stage"]: s for s in report["funnel"][unit]["total"]}
        assert total["jours_ouvrés"]["entering"] == 5 and total["séances_attendues"]["entering"] == 5
        assert total["ranges_complets"]["entering"] == 4 and total["ranges_admissibles"]["entering"] == 3
        assert total["cassures"]["entering"] == 2 and total["confirmations"]["confirmed"] == 2
    assert report["checks"]["C2"]["incomplete_ranges"] == {DAYS[2].isoformat(): "silence > 5 min"}
    d = {(x["trigger"], x["day"]): x["confirmation_utc"] for x in report["details"]}
    assert d[("M5", DAYS[4].isoformat())] == at(DAYS[4], 8, 35).isoformat()  # K + 5 min
    assert d[("M15", DAYS[4].isoformat())] == at(DAYS[4], 8, 45).isoformat()  # K + 15 min
    assert report["checks"]["C9"]["ticks_read"] == 0
    assert report["descriptions"]["M15"]["d_minus_k_in_candles"] == {"LONG": {"1": 2}}
    assert report["descriptions"]["M5"]["d_minus_k_in_candles"] == {"LONG": {"1": 1, "3": 1}}


@pytest.mark.parametrize("unit", ["M5", "M15"])
def test_invalidations_before_and_after_contact_are_told_apart(tmp_path: Path, unit: str) -> None:
    week = {
        DAYS[0]: _invalid_after_contact(DAYS[0]),
        DAYS[1]: _touch_and_invalidate(DAYS[1]),
        DAYS[2]: range_and_breakout(DAYS[2]) + fill(at(DAYS[2], 8, 30), at(DAYS[2], 16, 30), "1.13300"),
    }
    report = study(tmp_path, week, Anchors(3, frozenset(), 0))
    assert report["failed_checks"] == []
    assert outcomes(report, unit) == {
        DAYS[0].isoformat(): "INVALIDATION_APRÈS_CONTACT",
        DAYS[1].isoformat(): "INVALIDATION_AVANT_CONTACT",  # the invalidation comes before a new contact
        DAYS[2].isoformat(): "DÉLAI_SANS_CONTACT",
    }
    total = {s["stage"]: s for s in report["funnel"][unit]["total"]}
    assert total["cassures"]["entering"] == 3 and total["confirmations"]["confirmed"] == 0


def test_a_failed_anchor_withholds_the_results(tmp_path: Path) -> None:
    report = study(tmp_path, WEEK, Anchors(6, frozenset({DAYS[2]}), 0))
    assert report["failed_checks"] == ["C1"] and report["results_withheld"]
    assert "funnel" not in report and "descriptions" not in report and report["details"] == []


def test_c9_records_and_checks_the_two_parameter_sets() -> None:
    assert expected_params(Trigger.M5) == Day01Params()
    assert expected_params(Trigger.M15) == Day01Params(trigger=Trigger.M15)
    rest = [{k: v for k, v in dataclasses.asdict(expected_params(t)).items() if k != "trigger"} for t in Trigger]
    assert rest[0] == rest[1]


def _trajectories(tmp_path: Path, params: dict[Trigger, Day01Params]) -> tuple[Any, ...]:
    ticks = [t for day in sorted(WEEK) for t in WEEK[day]]
    m5, m15 = candles(tmp_path, ticks)
    start, end = london(DAYS[0], time(0)), london(DAYS[-1] + timedelta(days=1), time(0))
    bars = {Grid.M5: m5, Grid.M15: m15}
    runs = {t: run_trajectory(m5, m15, h4_bars(end), [], CONFIG, p, start, end) for t, p in params.items()}
    return runs, bars, intraday_table("dukascopy", "EURUSD", Grid.M15, m15), start, end


def test_c9_fails_when_a_parameter_other_than_the_unit_differs(tmp_path: Path) -> None:
    changed = dataclasses.replace(Day01Params(trigger=Trigger.M15), reward_ratio=D("2"))  # guard test only
    runs, bars, table, start, end = _trajectories(tmp_path, {Trigger.M5: Day01Params(), Trigger.M15: changed})
    checks = controls(runs, bars, table, start, end, ANCHORS)
    assert not checks["C9"]["ok"] and not checks["C9"]["other_params_identical"]
    assert checks["C9"]["expected"] == {"M5": "Day01Params()", "M15": "Day01Params(trigger=Trigger.M15)"}


def test_c5_and_c6_detect_a_tampered_range(tmp_path: Path) -> None:
    runs, bars, table, start, end = _trajectories(
        tmp_path, {Trigger.M5: Day01Params(), Trigger.M15: Day01Params(trigger=Trigger.M15)}
    )
    assert all(c["ok"] for name, c in controls(runs, bars, table, start, end, ANCHORS).items())
    runs[Trigger.M5].sessions[0].range["rh"] += D("0.00001")
    checks = controls(runs, bars, table, start, end, ANCHORS)
    assert not checks["C5"]["ok"] and not checks["C6"]["ok"]


def test_weekdays_are_walked_independently_of_the_engine() -> None:
    start, end = london(MONDAY, time(0)), london(MONDAY + timedelta(days=7), time(0))
    assert weekdays(start, end, Day01Params()) == DAYS


def test_command_refuses_unaudited_candles_and_the_reserved_years(tmp_path: Path) -> None:
    directory = tmp_path / "bars" / "dukascopy" / "EURUSD"
    (directory / "intraday_2015_2021_day01_5min").mkdir(parents=True)
    for name in ("intraday_2015_2021_day01_5min/5m", "intraday_2015_2021_day01_5min/15m", "4h"):
        (directory / f"{name}.parquet").write_bytes(b"not the audited file")
    out = ["--out", str(tmp_path / "r.json"), "--details-out", str(tmp_path / "d.jsonl")]
    assert main(["--data-dir", str(tmp_path), *out]) == 2
    assert not (tmp_path / "r.json").exists()  # stopped before reading any candle
    with pytest.raises(ValueError, match="partition de développement"):
        main(["--data-dir", str(tmp_path), "--end", "2023-01-01", *out])


def test_study_reads_no_tick_and_stops_at_the_confirmation(tmp_path: Path) -> None:
    report = study(tmp_path, {DAYS[0]: example_a(DAYS[0])}, Anchors(1, frozenset(), 0))
    (m5,) = [d for d in report["details"] if d["trigger"] == "M5"]
    assert m5["outcome"] == CONFIRMED and m5["confirmation_utc"] == at(DAYS[0], 8, 45).isoformat()
    assert report["note"].startswith("une confirmation est un instant D")
    assert isinstance(datetime.fromisoformat(m5["confirmation_utc"]), datetime)


def test_command_end_to_end_on_a_synthetic_data_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reads, checks and writes as on real data; the audited hashes and the git provenance are replaced
    by those of the synthetic files and a clean tree. Partial window: no 2015-2021 anchor applies."""
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    from forex_bot.backtest import day01_availability as tool
    from forex_bot.history.intraday_audit import sha256_file

    ticks = [t for day in sorted(WEEK) for t in WEEK[day]]
    m5, m15 = candles(tmp_path / "build", ticks)
    data = tmp_path / "data"
    directory = data / "bars" / "dukascopy" / "EURUSD"
    (directory / "intraday_2015_2021_day01_5min").mkdir(parents=True)
    hashes = {}
    for grid, rows in ((Grid.M5, m5), (Grid.M15, m15)):
        path = directory / "intraday_2015_2021_day01_5min" / f"{grid.value}.parquet"
        pq.write_table(intraday_table("dukascopy", "EURUSD", grid, rows), path)
        hashes[grid] = sha256_file(path)
    pq.write_table(
        pa.Table.from_pylist(h4_bars(london(DAYS[-1] + timedelta(days=1), time(0)))), directory / "4h.parquet"
    )
    (data / "reports").mkdir()
    (data / "reports" / "quality_dukascopy_EURUSD.json").write_text(json.dumps({"gaps": []}))
    clean: dict[str, Any] = {"commit": "abc", "uncommitted_diff_sha256": None, "uncommitted_files": []}
    monkeypatch.setattr(tool, "CANDLES_SHA256", hashes)
    monkeypatch.setattr(tool, "provenance", lambda argv, name: {**clean, "command": [name]})
    monkeypatch.setattr(tool, "tree_state", lambda: dict(clean))
    out, details = tmp_path / "r.json", tmp_path / "d.jsonl"
    argv = ["--data-dir", str(data), "--start", "2019-02-11", "--end", "2019-02-16", "--init-start", "2019-01-01"]
    assert main([*argv, "--out", str(out), "--details-out", str(details)]) == 0
    report = json.loads(out.read_text())
    assert report["failed_checks"] == [] and report["anchors"] == "aucune (fenêtre partielle)"
    assert report["checks"]["C9"]["inputs_sha256"]["unchanged"] and report["checks"]["C10"]["ok"]
    assert {s["stage"]: s for s in report["funnel"]["M15"]["total"]}["confirmations"]["confirmed"] == 2
    assert len(details.read_text().splitlines()) == 10  # 5 sessions x 2 triggers
    assert out.with_suffix(".md").read_text().startswith("# DAY_01")


# ---------------------------------------------------------------- cause of an unavailable H4 ATR

TUESDAY = DAYS[1]  # 2019-02-12, freeze at 08:00 UTC (GMT)
BREAK = datetime(2019, 2, 11, 22, tzinfo=UTC)  # H4 opening the trading day of the session


def _atr(tmp_path: Path, h4: list[dict[str, Any]]) -> dict[str, Any]:
    report = study(tmp_path, {TUESDAY: example_a(TUESDAY)}, Anchors(1, frozenset(), 0), h4=h4)
    assert report["failed_checks"] == []
    return {d["trigger"]: d for d in report["details"]}


def test_atr_is_available_with_the_full_h4_history(tmp_path: Path) -> None:
    rows = _atr(tmp_path, h4_bars(london(TUESDAY + timedelta(days=1), time(0))))
    assert rows["M5"]["outcome"] == rows["M15"]["outcome"] == CONFIRMED


def test_initial_h4_history_really_too_short_is_initialisation(tmp_path: Path) -> None:
    """History starting 2019-02-11 10:00 UTC: 5 H4 known at the freeze, fewer than 15."""
    first = datetime(2019, 2, 11, 10, tzinfo=UTC)
    h4 = [b for b in h4_bars(london(TUESDAY + timedelta(days=1), time(0))) if b["start_utc"] >= first]
    rows = _atr(tmp_path, h4)
    for unit in ("M5", "M15"):
        assert (rows[unit]["outcome"], rows[unit]["cause"]) == ("ATR_NON_CALCULABLE", ATR_INITIAL)
        assert rows[unit]["cause_detail"].startswith(f"5 H4 utilisables depuis {h4[0]['start_utc'].isoformat()}")


def test_absent_h4_before_the_first_session_is_an_interruption_not_initialisation(tmp_path: Path) -> None:
    """Twelve days of H4 before, but the H4 of 2019-02-11 22:00 UTC is absent: the usable run restarts
    at 02:00 and holds 2 H4 at the freeze. Both trajectories used to say initialisation."""
    h4 = [b for b in h4_bars(london(TUESDAY + timedelta(days=1), time(0))) if b["start_utc"] != BREAK]
    rows = _atr(tmp_path, h4)
    for unit in ("M5", "M15"):
        assert (rows[unit]["outcome"], rows[unit]["cause"]) == ("ATR_NON_CALCULABLE", ATR_ABSENT_H4)
        assert "H4 prévue absente avant 2019-02-12T02:00:00+00:00" in rows[unit]["cause_detail"]


def test_unusable_h4_before_the_first_session_is_an_interruption(tmp_path: Path) -> None:
    h4 = h4_bars(london(TUESDAY + timedelta(days=1), time(0)))
    for bar in h4:
        if bar["start_utc"] == BREAK:
            bar["complete_at_close"], bar["flags_at_close"] = False, ["INTERRUPTION_INEXPLIQUÉE"]
    rows = _atr(tmp_path, h4)
    for unit in ("M5", "M15"):
        assert (rows[unit]["outcome"], rows[unit]["cause"]) == ("ATR_NON_CALCULABLE", ATR_UNUSABLE_H4)
        assert "H4 2019-02-11T22:00:00+00:00 inutilisable" in rows[unit]["cause_detail"]


def test_atr_cause_never_attributes_an_available_atr(tmp_path: Path) -> None:
    """Guard: asked at a freeze where the ATR is available, the diagnosis flags an inconsistency."""
    m5, m15 = candles(tmp_path, example_a(TUESDAY))
    end = london(TUESDAY + timedelta(days=1), time(0))
    engine = AvailabilityBacktest(m5, m15, h4_bars(end), [], [], Day01Params(), CONFIG)
    cause, detail = engine.atr_cause(london(TUESDAY, time(8)))
    assert cause == ATR_AVAILABLE and detail == "ATR 0.00200"
