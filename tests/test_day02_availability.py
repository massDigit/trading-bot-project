"""DAY_02 availability study on synthetic data (docs/experiments/DAY02_AVAILABILITY_2015_2021.md).

M5 and M15 are built by the real builder from ticks (5 min convention), the H1 are the synthetic
fixture of the engine tests (A = 10 pips). Expected values are written by hand; the checks are also
run on paths falsified on purpose, to show that each one blocks.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal as D
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
from test_day02 import (
    SHEET_M15,
    WINTER,
    at,
    candle_ticks,
    candles,
    got,
    h1_bars,
    sheet_ticks,
)

from forex_bot.backtest import day02_availability as tool
from forex_bot.backtest.day01 import london
from forex_bot.backtest.day02 import ATR_UNAVAILABLE, EXIT, PROLONGED, SESSION_START, TOO_DEEP, TOO_LONG, Trigger
from forex_bot.backtest.day02_availability import (
    CALENDAR_ANCHOR,
    NO_EXIT,
    NOT_FORMED,
    OFFICIAL_WINDOW,
    SessionPath,
    availability,
    bar_cause,
    bound_errors,
    c6_errors,
    c7_errors,
    c8_errors,
    calendar_days,
    conservation_errors,
    coverage,
    main,
    measures,
    resume_errors,
    reuse_errors,
    run_trajectory,
    silences,
    study_days,
)
from forex_bot.backtest.engine import ResearchConfig
from forex_bot.backtest.explore import RESEARCH_COSTS
from forex_bot.backtest.feed import Tick
from forex_bot.history.bars import bars_table
from forex_bot.history.calendar import Timeframe
from forex_bot.history.intraday import Content, Grid, intraday_table
from forex_bot.history.intraday_audit import sha256_file

CONFIG = ResearchConfig(costs=RESEARCH_COSTS)
MIN = timedelta(minutes=1)
M15 = timedelta(minutes=15)


def session_ticks(
    day: date, rows: dict[tuple[int, int], tuple[str, str, str, str]], end: tuple[int, int] = (17, 30)
) -> list[Tick]:
    """M15 from 07:00 to `end`, flat at 1.13010 except `rows`, each M15 built from its ticks."""
    out, cursor = [], at(day, 7, 0)
    while cursor < at(day, *end):
        key = (cursor.hour, cursor.minute)  # winter sessions only: London = UTC
        prices = rows.get(key, ("1.13010", "1.13010", "1.13010", "1.13010"))
        out += candle_ticks(cursor, M15, *prices)
        cursor += M15
    return out


Study = tuple[tuple[dict[str, Any], list[dict[str, Any]]], Any]


def study(tmp_path: Path, ticks: list[Tick], day: date = WINTER, days: int = 1) -> Study:
    m5, m15 = candles(tmp_path, sorted(ticks, key=lambda t: t.ts_utc))
    h1 = h1_bars(london(day + timedelta(days=days), time(0)), days=days + 5)
    start, end = london(day, time(0)), london(day + timedelta(days=days), time(0))
    return availability({Grid.M5: m5, Grid.M15: m15}, h1, [], CONFIG, start, end, official=False), (m5, m15, h1)


def paths_of(tmp_path: Path, ticks: list[Tick], trigger: Trigger = Trigger.M5) -> tuple[list[SessionPath], Any]:
    m5, m15 = candles(tmp_path, sorted(ticks, key=lambda t: t.ts_utc))
    h1 = h1_bars(london(WINTER + timedelta(days=1), time(0)), days=6)
    return run_trajectory(trigger, m5, m15, h1, [], CONFIG, [WINTER])


# ---------------------------------------------------------------- calendar (C1)


def test_calendar_of_the_official_window_matches_the_independent_count() -> None:
    weekdays, excluded = calendar_days(*OFFICIAL_WINDOW)
    assert (len(weekdays), len(excluded)) == (CALENDAR_ANCHOR["weekdays"], CALENDAR_ANCHOR["excluded"]) == (1827, 11)
    assert all((d.month, d.day) in ((12, 25), (1, 1)) for d in excluded)
    days = study_days(*OFFICIAL_WINDOW)
    assert len(days) == 1816 and days == sorted(set(weekdays) - set(excluded))


def test_the_anchor_applies_to_the_official_window_only(tmp_path: Path) -> None:
    (report, _), _ = study(tmp_path, sheet_ticks(WINTER))
    assert report["checks"]["C1"]["ok"] and report["checks"]["C1"]["ancrage"] is None
    assert report["checks"]["C1"]["calendrier"] == {"weekdays": 1, "excluded": 0, "sessions": 1}


# ---------------------------------------------------------------- the sheet example


def test_no_position_path_of_the_sheet_example(tmp_path: Path) -> None:
    (report, details), _ = study(tmp_path, sheet_ticks(WINTER))
    assert all(c["ok"] for c in report["checks"].values()), {k: c["errors"] for k, c in report["checks"].items()}
    (m5,) = [d for d in details if d["trigger"] == "M5"]
    first, second, *rest = m5["searches"]
    assert (first["resume_utc"], first["resume_after"]) == (at(WINTER, 7, 0), SESSION_START)
    config = first["configuration"]
    assert (config["outcome"], config["ended_utc"]) == (EXIT, at(WINTER, 10, 10))
    # The exit at D is not an entry: the search resumes at D, with M15 starting at 10:15 or later.
    assert (second["resume_utc"], second["resume_after"]) == (at(WINTER, 10, 10), EXIT)
    assert second["examined"][0]["t_utc"] == at(WINTER, 11, 15)
    assert (rest or [second])[-1]["configuration"] is None
    (m15,) = [d for d in details if d["trigger"] == "M15"]
    assert m15["searches"][0]["configuration"]["ended_utc"] == at(WINTER, 10, 15)  # exit on the M15 close
    total = report["comptes"]["M5"]["total"]["comptes"]
    assert (total["séances"], total["configurations"], total["drapeaux_formés"], total["sorties_confirmées"]) == (
        1,
        1,
        1,
        1,
    )
    assert total["m15_examinées"] == sum(len(s["examined"]) + (s["configuration"] is not None) for s in m5["searches"])


def test_session_without_configuration_is_compared_too(tmp_path: Path) -> None:
    (report, details), _ = study(tmp_path, session_ticks(WINTER, {}))
    assert all(c["ok"] for c in report["checks"].values())
    assert [len(d["searches"]) for d in details] == [1, 1]
    assert all(d["searches"][0]["configuration"] is None for d in details)


# Formed flag, then the price stays inside it (no exit, no deep pullback) until the deadline 11:00.
EXPIRY = dict(SHEET_M15) | {(10, m): ("1.13110", "1.13110", "1.13110", "1.13110") for m in (0, 15, 30, 45)}
PROLONGING = dict(SHEET_M15) | {
    (9, 30): ("1.13130", "1.13150", "1.13120", "1.13140"),
    (9, 45): ("1.13140", "1.13160", "1.13120", "1.13140"),
    (10, 0): ("1.13140", "1.13170", "1.13120", "1.13140"),
    (10, 15): ("1.13140", "1.13180", "1.13120", "1.13140"),
}


@pytest.mark.parametrize(
    ("rows", "outcome"),
    [
        (EXPIRY, TOO_LONG),  # formed, no exit, expiry at 11:00
        (PROLONGING, PROLONGED),
        (dict(SHEET_M15) | {(9, 45): ("1.13100", "1.13120", "1.13055", "1.13110")}, TOO_DEEP),
    ],
    ids=["expiry", "prolonged", "too-deep"],
)
def test_abandon_events_are_outcomes_not_check_failures(tmp_path: Path, rows: Any, outcome: str) -> None:
    (report, details), _ = study(tmp_path, session_ticks(WINTER, rows))
    assert all(c["ok"] for c in report["checks"].values()), {k: c["errors"] for k, c in report["checks"].items()}
    for line in details:
        assert line["searches"][0]["configuration"]["outcome"] == outcome
    if outcome == PROLONGED:
        assert details[0]["searches"][0]["configuration"]["ended_utc"] == at(WINTER, 10, 30)


# ---------------------------------------------------------------- falsified paths block


def test_each_check_blocks_a_path_falsified_on_purpose(tmp_path: Path) -> None:
    ticks = sheet_ticks(WINTER)
    paths, engine = paths_of(tmp_path / "m5", ticks)
    m15_paths, m15_engine = paths_of(tmp_path / "m15", ticks, Trigger.M15)
    m15_rows = engine.m15
    for check in (conservation_errors, resume_errors, reuse_errors):
        assert check(paths) == []
    assert bound_errors(paths, m15_rows) == [] and c8_errors(paths) == []
    assert c6_errors(paths, m15_rows, engine.atr_at) == [] and c7_errors(paths, m15_paths) == []

    bad = copy.deepcopy(paths)
    bad[0].searches[1].resume_utc += MIN
    assert resume_errors(bad)

    bad = copy.deepcopy(paths)
    first = got(bad[0].searches[0].configuration)
    first.flag_utc = got(first.flag_utc) + M15
    assert bound_errors(bad, m15_rows)

    bad = copy.deepcopy(paths)
    bad[0].searches.insert(1, copy.deepcopy(bad[0].searches[0]))  # the same M15 serve twice
    assert reuse_errors(bad) and conservation_errors(bad) == [] and resume_errors(bad)

    bad = copy.deepcopy(paths)
    got(bad[0].searches[0].configuration).origin -= D("0.00001")
    assert c6_errors(bad, m15_rows, engine.atr_at)

    bad = copy.deepcopy(m15_paths)
    config = got(bad[0].searches[0].configuration)
    config.flag_utc = got(config.flag_utc) + M15
    assert c7_errors(paths, bad)
    # Fields changed after F (exit, stop, target) are not part of the common path.
    bad = copy.deepcopy(m15_paths)
    got(bad[0].searches[0].configuration).stop = D("1")
    assert c7_errors(paths, bad) == []

    bad = copy.deepcopy(paths)
    line = bad[0].searches[0]
    t = got(line.configuration).recognised_utc
    cutoff, end, value = line.atr_reads[t]
    line.atr_reads[t] = (cutoff, got(end) + timedelta(hours=1), value)
    assert c8_errors(bad)

    bad = copy.deepcopy(paths)
    bad[0].searches.append(copy.deepcopy(bad[0].searches[0]))  # a configuration after the last search
    assert conservation_errors(bad)
    assert m15_engine is not None


def test_formation_and_exit_bounds_apply_only_when_f_or_d_exist(tmp_path: Path) -> None:
    rows = dict(SHEET_M15) | {(9, 45): ("1.13100", "1.13120", "1.13055", "1.13110")}
    paths, engine = paths_of(tmp_path, session_ticks(WINTER, rows))
    config = got(paths[0].searches[0].configuration)
    assert (config.flag_utc, config.deadline_utc, config.stop) == (None, None, None)
    assert bound_errors(paths, engine.m15) == []


# ---------------------------------------------------------------- measures and their domains


def test_measures_name_their_domain_and_count_absences(tmp_path: Path) -> None:
    rows = dict(SHEET_M15) | {(9, 45): ("1.13100", "1.13120", "1.13055", "1.13110")}
    paths, engine = paths_of(tmp_path / "deep", session_ticks(WINTER, rows))
    m = measures(paths, engine)
    assert m["pente_sur_A"]["absences"] == {NOT_FORMED: 1} and m["pente_sur_A"]["valeurs"] is None
    assert m["E_moins_S_pips"]["absences"] == {NOT_FORMED: 1}
    assert m["I_sur_A"]["valeurs"]["n"] == 1 and m["I_sur_A"]["absences"] == {}
    paths, engine = paths_of(tmp_path / "expiry", session_ticks(WINTER, EXPIRY))
    m = measures(paths, engine)
    assert m["pente_sur_A"]["valeurs"]["n"] == 1 and m["E_moins_S_pips"]["absences"] == {NO_EXIT: 1}


def test_sheet_measures_by_hand(tmp_path: Path) -> None:
    paths, engine = paths_of(tmp_path, sheet_ticks(WINTER))
    m = measures(paths, engine)
    one = {k: v["valeurs"]["médiane"] for k, v in m.items() if isinstance(v, dict) and v.get("valeurs")}
    assert one["A_pips"] == 10 and one["I_pips"] == 16 and one["I_sur_A"] == D("1.6")
    assert one["impulsion_M15_reconnaissance"] == 3 and one["extensions"] == 0
    assert one["profondeur_bid_sur_I"] == D("0.40625")  # (1.13140 - 1.13075) / 0.00160
    assert one["E_moins_S_pips"] == 9 and one["T_moins_E_pips"] == 16  # 1.13140 - 1.13050 ; 1.13300 - 1.13140
    assert one["approché_clôture_moins_S_pips"] == D("10.5")  # 1.13155 - 1.13050
    assert one["D_moins_F_bougies"] == 2 and one["D_moins_fin_p_minutes"] == 40
    assert m["extrême_ask_stop_vente"]["valeurs"] is None and m["extrême_ask_stop_vente"]["absences"] == {}


def test_sale_depth_is_measured_on_the_bid_and_the_stop_extreme_on_the_ask(tmp_path: Path) -> None:
    mirrored = [Tick(t.ts_utc, D("2.26") - t.bid, D("2.26") - t.bid + D("0.00002")) for t in sheet_ticks(WINTER)]
    paths, engine = paths_of(tmp_path, mirrored)
    config = got(paths[0].searches[0].configuration)
    assert config.outcome == EXIT and config.side.value == "SHORT"
    m = measures(paths, engine)
    assert m["profondeur_bid_sur_I"]["valeurs"]["médiane"] == D("0.40625")  # (1.12925 - 1.12860) / I, bid
    assert m["extrême_ask_stop_vente"]["valeurs"]["médiane"] == D("1.12927")  # ask_high of the flag


# ---------------------------------------------------------------- coverage and silences


def m5_row(
    start: datetime, first: datetime | None, last: datetime | None, ok: bool = True, flags: list[str] | None = None
) -> dict[str, Any]:
    content = Content.VALID if first is not None else Content.EMPTY
    return {
        "start_utc": start,
        "end_utc": start + 5 * MIN,
        "content": content,
        "first_tick_utc": first,
        "last_tick_utc": last,
        "complete_at_close": ok,
        "flags_at_close": flags or [],
    }


def test_silences_above_five_minutes_come_from_the_m5_first_and_last_ticks() -> None:
    s, sec = at(WINTER, 9, 0), timedelta(seconds=1)
    rows = [
        m5_row(s, s, s + 4 * MIN + 50 * sec),
        m5_row(s + 5 * MIN, s + 9 * MIN + 50 * sec, s + 9 * MIN + 55 * sec),  # exactly 5 min after: no
        m5_row(s + 10 * MIN, None, None, ok=False),
        m5_row(s + 15 * MIN, s + 15 * MIN, s + 19 * MIN),  # 5 min 5 s after 09:09:55: yes
    ]
    found = silences(rows)
    assert [(a, b) for a, b, _ in found] == [(s + 9 * MIN + 55 * sec, s + 15 * MIN)]
    friday, sunday = datetime(2019, 2, 15, 21, 59, tzinfo=UTC), datetime(2019, 2, 17, 22, 0, 1, tzinfo=UTC)
    weekend = [m5_row(friday - 4 * MIN, friday, friday), m5_row(sunday, sunday, sunday)]
    assert silences(weekend) == []  # the weekly closure is not expected-open time


def test_coverage_separates_needed_and_full_windows_with_causes(tmp_path: Path) -> None:
    ticks = [t for t in session_ticks(WINTER, {}) if not at(WINTER, 15, 30) <= t.ts_utc < at(WINTER, 15, 40)]
    ticks = [t for t in ticks if not at(WINTER, 9, 0) <= t.ts_utc < at(WINTER, 9, 5)]
    m5, m15 = candles(tmp_path, ticks)
    cov = coverage([WINTER], m5, m15)
    needed, full = cov["nécessaire_07_15"], cov["complète_07_17"]
    assert needed["5m"]["créneaux"] == 96 and full["5m"]["créneaux"] == 120
    assert needed["15m"]["créneaux"] == 32 and full["15m"]["créneaux"] == 40
    assert needed["5m"]["causes"] == {"sans tick": 1} and full["5m"]["causes"] == {"sans tick": 3}
    assert needed["silences_plus_de_5_min"]["silences_distincts"] == 1
    assert full["silences_plus_de_5_min"]["silences_distincts"] == 2
    assert bar_cause(None) == "absente"


# ---------------------------------------------------------------- command end to end


def write_data(tmp_path: Path, ticks: list[Tick], last_day: date) -> Path:
    m5, m15 = candles(tmp_path / "build", sorted(ticks, key=lambda t: t.ts_utc))
    data = tmp_path / "data"
    directory = data / "bars" / "dukascopy" / "EURUSD"
    (directory / tool.LOT).mkdir(parents=True)
    for grid, rows in ((Grid.M5, m5), (Grid.M15, m15)):
        pq.write_table(
            intraday_table("dukascopy", "EURUSD", grid, rows), directory / tool.LOT / f"{grid.value}.parquet"
        )
    h1 = h1_bars(london(last_day + timedelta(days=1), time(0)), days=12)
    pq.write_table(bars_table("dukascopy", "EURUSD", Timeframe.H1, h1), directory / "1h.parquet")
    (data / "reports").mkdir()
    (data / "reports" / "quality_dukascopy_EURUSD.json").write_text(json.dumps({"gaps": []}))
    return data


@pytest.fixture
def week(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, list[str]]:
    days = [date(2019, 2, 11) + timedelta(days=i) for i in range(5)]
    ticks = [t for d in days for t in (sheet_ticks(d) if d == WINTER else session_ticks(d, {}))]
    data = write_data(tmp_path, ticks, days[-1])
    directory = data / "bars" / "dukascopy" / "EURUSD"
    hashes = {g: sha256_file(directory / tool.LOT / f"{g.value}.parquet") for g in Grid}
    clean: dict[str, Any] = {"commit": "abc", "uncommitted_diff_sha256": None, "uncommitted_files": []}
    monkeypatch.setattr(tool, "CANDLES_SHA256", hashes)
    monkeypatch.setattr(tool, "H1_SHA256", sha256_file(directory / "1h.parquet"))
    monkeypatch.setattr(tool, "provenance", lambda argv, name: {**clean, "command": [name]})
    monkeypatch.setattr(tool, "tree_state", lambda: dict(clean))
    return data, ["--data-dir", str(data), "--start", "2019-02-11", "--end", "2019-02-16"]


def test_command_end_to_end(tmp_path: Path, week: tuple[Path, list[str]]) -> None:
    _, argv = week
    out, details = tmp_path / "r.json", tmp_path / "d.jsonl"
    assert main([*argv, "--out", str(out), "--details-out", str(details)]) == 0
    report = json.loads(out.read_text())
    assert report["failed_checks"] == [] and not report["window"]["officielle"]
    assert report["checks"]["C9"]["inputs_sha256"]["unchanged"] and report["checks"]["C10"]["ok"]
    assert report["checks"]["C9"]["ticks_lus"] == 0
    hashes = report["checks"]["C9"]["inputs_sha256"]
    assert any(path.endswith("quality_dukascopy_EURUSD.json") for path in hashes["before"])
    assert "aucune référence historique" in hashes["références"]["quality_dukascopy_EURUSD.json"]
    assert report["comptes"]["M5"]["total"]["comptes"]["sorties_confirmées"] == 1
    # Monday: the H1 history starts on the study start; the ATR bootstrap is counted, never filled.
    causes = report["comptes"]["M5"]["2019"]["m15_non_reconnues_par_cause"]
    assert causes.get(ATR_UNAVAILABLE, 0) > 0
    atr = report["comptes"]["M5"]["2019"]["atr_h1_indisponible_par_cause"]
    assert set(atr) == {tool.ATR_INITIAL} and sum(atr.values()) == causes[ATR_UNAVAILABLE]
    assert len(details.read_text().splitlines()) == 10  # 5 sessions x 2 triggers
    assert out.with_suffix(".md").read_text().startswith("# DAY_02")


def test_command_refuses_unknown_hashes_and_withholds_results_on_a_failed_check(
    tmp_path: Path, week: tuple[Path, list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, argv = week
    out, details = tmp_path / "r.json", tmp_path / "d.jsonl"
    full = tool.H1_SHA256
    monkeypatch.setattr(tool, "H1_SHA256", full[:8] + "0" * 56)  # same published prefix, other hash
    assert main([*argv, "--out", str(out), "--details-out", str(details)]) == 2 and not out.exists()
    monkeypatch.setattr(tool, "H1_SHA256", full)
    monkeypatch.setattr(tool, "resume_errors", lambda paths, *_: ["reprise falsifiée"])
    assert main([*argv, "--out", str(out), "--details-out", str(details)]) == 2
    report = json.loads(out.read_text())
    assert report["failed_checks"] == ["C3"] and "comptes" not in report and not details.exists()


def test_no_bar_after_the_end_is_read(tmp_path: Path, week: tuple[Path, list[str]]) -> None:
    _, argv = week
    out, details = tmp_path / "r.json", tmp_path / "d.jsonl"
    short = [*argv[:-1], "2019-02-13"]  # end before the last candles of the files
    assert main([*short, "--out", str(out), "--details-out", str(details)]) == 0
    report = json.loads(out.read_text())
    assert report["checks"]["C9"]["ok"] and report["inputs"]["m15"] > 0
    assert report["checks"]["C1"]["calendrier"]["sessions"] == 2


# ---------------------------------------------------------------- review of 1e6ad36


def test_prolonged_after_a_pause_is_accepted_by_c4(tmp_path: Path) -> None:
    # Origin 08:45, recognition 09:30, extensions 09:30, 09:45, 10:00 (6 M15), a pause at 10:15, then
    # an extension at 10:30: 8 M15, the first extension beyond 6, abandoned at its close 10:45.
    rows = dict(SHEET_M15) | {
        (9, 30): ("1.13130", "1.13150", "1.13120", "1.13140"),
        (9, 45): ("1.13140", "1.13160", "1.13120", "1.13140"),
        (10, 0): ("1.13140", "1.13170", "1.13120", "1.13140"),
        (10, 15): ("1.13140", "1.13150", "1.13120", "1.13140"),
        (10, 30): ("1.13140", "1.13180", "1.13120", "1.13140"),
    }
    (report, details), _ = study(tmp_path, session_ticks(WINTER, rows))
    assert all(c["ok"] for c in report["checks"].values()), {k: c["errors"] for k, c in report["checks"].items()}
    config = details[0]["searches"][0]["configuration"]
    assert (config["outcome"], config["ended_utc"]) == (PROLONGED, at(WINTER, 10, 45))
    assert config["extensions"] == [at(WINTER, 9, 30), at(WINTER, 9, 45), at(WINTER, 10, 0), at(WINTER, 10, 30)]
    paths, engine = paths_of(tmp_path / "again", session_ticks(WINTER, rows))
    bad = copy.deepcopy(paths)
    got(bad[0].searches[0].configuration).ended_utc = at(WINTER, 10, 30)  # not the close of the extension
    assert bound_errors(bad, engine.m15)


def atr_engine(h1: list[dict[str, Any]]) -> Any:
    from forex_bot.backtest.day02 import Day02Params
    from forex_bot.backtest.day02_engine import Day02Backtest

    return Day02Backtest([], [], h1, [], [], Day02Params(), CONFIG)


def test_atr_causes_are_read_from_the_h1_known_at_the_instant() -> None:
    cutoff, known = at(WINTER, 8, 0), at(WINTER, 9, 0)
    short = h1_bars(cutoff, days=1)[-10:]
    assert tool.atr_cause(atr_engine(short), cutoff, known)[0] == tool.ATR_INITIAL
    hole = at(WINTER, 0, 0)
    assert tool.atr_cause(atr_engine(h1_bars(cutoff, skip={hole})), cutoff, known)[0] == tool.ATR_ABSENT_H1
    cause, detail = tool.atr_cause(atr_engine(h1_bars(cutoff, bad={hole})), cutoff, known)
    assert cause == tool.ATR_UNUSABLE_H1 and hole.isoformat() in got(detail)
    # The last H1 known is itself unusable: same diagnosis with a truncated history and with later H1 loaded.
    last = at(WINTER, 7, 0)
    for until in (cutoff, at(WINTER, 17, 0)):
        cause, detail = tool.atr_cause(atr_engine(h1_bars(until, bad={last})), cutoff, known)
        assert cause == tool.ATR_UNUSABLE_H1 and "0 H1 utilisable" in got(detail), until
    flat_h1 = [dict(b, bid_high=b["bid_close"], bid_low=b["bid_close"]) for b in h1_bars(cutoff)]
    assert tool.atr_cause(atr_engine(flat_h1), cutoff, known) == (tool.ATR_UNDETERMINED, "ATR 0.00000 non positif")


def test_a_silence_crossing_two_windows_is_one_silence_and_two_intersections(tmp_path: Path) -> None:
    nxt = WINTER + timedelta(days=1)
    ticks = [t for t in session_ticks(WINTER, {}) if t.ts_utc < at(WINTER, 16, 30)]
    ticks += [t for t in session_ticks(nxt, {}) if t.ts_utc >= at(nxt, 7, 30)]
    m5, m15 = candles(tmp_path, ticks)
    full = coverage([WINTER, nxt], m5, m15)["complète_07_17"]["silences_plus_de_5_min"]
    assert (full["silences_distincts"], full["intersections_silence_séance"], full["séances_touchées"]) == (1, 2, 2)
