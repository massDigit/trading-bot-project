"""Quality report of the imported ticks and built candles (JSON + Markdown, written under data/reports)."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from forex_bot.history.bars import DEFAULT_GAP_THRESHOLD, TickSummary, expected_weekly_closes
from forex_bot.history.calendar import (
    NEW_YORK,
    MarketState,
    Timeframe,
    expected_open_hours,
    market_state,
)
from forex_bot.history.store import HistoryStore

DISCLAIMER = (
    "Cotations historiques du fournisseur : elles ne sont pas identiques aux prix exécutables chez IG "
    "(spread, horaires, ajustements et exécution diffèrent)."
)

DECISIONS = [
    ("Ticks hors de la période déclarée du fichier", "exclus à l'import", "évite les chevauchements entre fichiers"),
    ("Prix nul ou négatif", "exclu des bougies, compté", "prix non valide"),
    ("bid > ask (cotation croisée)", "exclu des bougies, compté", "incohérence bid/ask"),
    ("Ticks simultanés (même horodatage)", "conservés, ordre du fichier", "légitimes : plusieurs cotations par ms"),
    (
        "Lignes consécutives identiques (heure, prix, volumes)",
        "conservées, comptées",
        "indiscernables d'une cotation répétée ; pas de suppression silencieuse",
    ),
    (
        "Ticks pendant la fermeture prévue",
        "conservés, bougie marquée incomplète",
        "incohérence avec l'horaire prévu ou la convention temporelle déclarée",
    ),
    ("Trou de cotation pendant l'ouverture prévue", "non comblé, bougies marquées", "aucun prix inventé"),
    ("Heure attendue sans tick", "absente, bougies H4/D1 marquées", "aucun remplissage"),
    ("Bougie dépassant la couverture", "conservée, marquée non clôturée", "inutilisable pour une décision"),
]


def _fmt(moment: datetime | None) -> str:
    return moment.isoformat(timespec="milliseconds") if moment else "—"


def weekly_transitions(summary: TickSummary) -> list[dict[str, Any]]:
    """For each expected weekly close / reopen inside the coverage, the nearest observed ticks.

    This is a CONSISTENCY check between the declared time convention and the expected schedule.
    It does not prove the time zone: that must come from the documentation of the interface used.
    """
    result = []
    for close, reopen in expected_weekly_closes(summary.coverage):
        before, after = summary.closure_neighbours.get(close, (None, None))
        result.append(
            {
                "expected_close_utc": close.isoformat(),
                "expected_reopen_utc": reopen.isoformat(),
                "new_york_close": close.astimezone(NEW_YORK).isoformat(),
                "last_tick_before_close_utc": _fmt(before),
                "first_tick_after_close_utc": _fmt(after),
                "first_tick_minus_expected_reopen_min": (
                    round((after - reopen).total_seconds() / 60, 1) if after else None
                ),
            }
        )
    return result


def build_report(
    store: HistoryStore,
    source: str,
    instrument: str,
    summary: TickSummary,
    bars: dict[Timeframe, list[dict[str, Any]]],
    gap_threshold: timedelta = DEFAULT_GAP_THRESHOLD,
) -> dict[str, Any]:
    present_hours = {b["start_utc"] for b in bars.get(Timeframe.H1, [])}
    missing_hours = [
        h.isoformat()
        for c_start, c_end in summary.coverage
        for h in expected_open_hours(c_start, c_end)
        if h not in present_hours
    ]
    gaps = []
    for gap in summary.gaps:
        if any(market_state(t) is MarketState.PROBABLE_HOLIDAY for t in (gap.start_utc, gap.end_utc)):
            kind = "jour férié probable"
        elif gap.open_minutes * 60 > gap_threshold.total_seconds():
            kind = "TROU pendant l'ouverture prévue"
        else:  # longer than the threshold, but at most the threshold while open: it spans the closure
            kind = "fermeture normale (horaire prévu)"
        gaps.append(
            {
                "start_utc": gap.start_utc.isoformat(),
                "end_utc": gap.end_utc.isoformat(),
                "duration_min": round((gap.end_utc - gap.start_utc).total_seconds() / 60, 1),
                "open_minutes": round(gap.open_minutes, 1),
                "classification": kind,
            }
        )
    candles = {}
    for timeframe, rows in bars.items():
        flags: dict[str, int] = {}
        for row in rows:
            for flag in row["flags"]:
                key = flag.split(" :")[0]
                flags[key] = flags.get(key, 0) + 1
        candles[timeframe.value] = {
            "count": len(rows),
            "complete": sum(1 for r in rows if r["complete"]),
            "incomplete": sum(1 for r in rows if not r["complete"]),
            "flags": flags,
        }
    return {
        "source": source,
        "instrument": instrument,
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "disclaimer": DISCLAIMER,
        "files": [
            {k: m[k] for k in ("sha256", "period_start_utc", "period_end_utc", "retrieved_at_utc", "partitions")}
            for m in store.manifests(source, instrument)
        ],
        "coverage": [[s.isoformat(), e.isoformat()] for s, e in summary.coverage],
        "ticks": {
            "total": summary.total,
            "valid": summary.valid,
            "non_positive_price": summary.non_positive,
            "crossed_bid_above_ask": summary.crossed,
            "out_of_order_within_file": summary.out_of_order_in_file,
            "simultaneous_timestamps": summary.simultaneous_groups,
            "simultaneous_ticks": summary.simultaneous_ticks,
            "exact_consecutive_repeats": summary.exact_repeats,
            "during_weekly_closure": summary.during_weekly_closure,
            "first_tick_utc": _fmt(summary.first_tick_utc),
            "last_tick_utc": _fmt(summary.last_tick_utc),
        },
        "gap_threshold_min": gap_threshold.total_seconds() / 60,
        "gaps": gaps,
        "missing_open_hours": missing_hours,
        "weekly_transitions": weekly_transitions(summary),
        "candles": candles,
        "decisions": [{"anomaly": a, "treatment": t, "justification": j} for a, t, j in DECISIONS],
    }


def to_markdown(report: dict[str, Any]) -> str:
    t = report["ticks"]
    lines = [
        f"# Rapport qualité — {report['instrument']} / {report['source']}",
        "",
        f"> {report['disclaimer']}",
        "",
        "## Couverture déclarée",
        *[f"- {s} → {e}" for s, e in report["coverage"]],
        f"- Fichiers : {len(report['files'])}",
        "",
        "## Ticks",
        f"- Total {t['total']}, valides {t['valid']} ; premier {t['first_tick_utc']}, dernier {t['last_tick_utc']}",
        f"- Prix nuls/négatifs {t['non_positive_price']} ; bid > ask {t['crossed_bid_above_ask']}",
        f"- Désordre chronologique dans un fichier : {t['out_of_order_within_file']}",
        f"- Horodatages partagés : {t['simultaneous_timestamps']} ({t['simultaneous_ticks']} ticks, conservés)",
        f"- Lignes consécutives identiques : {t['exact_consecutive_repeats']} (conservées)",
        f"- Ticks pendant la fermeture prévue : {t['during_weekly_closure']}",
        "",
        f"## Interruptions (> {report['gap_threshold_min']:.0f} min)",
        "| Début (UTC) | Fin (UTC) | Durée (min) | dont ouverture prévue (min) | Classement |",
        "|---|---|---|---|---|",
        *[
            f"| {g['start_utc']} | {g['end_utc']} | {g['duration_min']} | {g['open_minutes']} | {g['classification']} |"
            for g in report["gaps"]
        ],
        "",
        f"## Heures d'ouverture prévue sans tick : {len(report['missing_open_hours'])}",
        *[f"- {h}" for h in report["missing_open_hours"][:50]],
        "",
        "## Fermeture et réouverture hebdomadaires (contrôle de cohérence, pas une preuve du fuseau)",
        "| Clôture attendue (UTC) | Dernier tick avant | Réouverture attendue (UTC) | Premier tick après "
        "| Écart (min) |",
        "|---|---|---|---|---|",
        *[
            f"| {w['expected_close_utc']} | {w['last_tick_before_close_utc']} | {w['expected_reopen_utc']} | "
            f"{w['first_tick_after_close_utc']} | {w['first_tick_minus_expected_reopen_min']} |"
            for w in report["weekly_transitions"]
        ],
        "",
        "## Bougies",
        "| Unité | Total | Complètes | Incomplètes | Motifs |",
        "|---|---|---|---|---|",
        *[
            f"| {tf} | {c['count']} | {c['complete']} | {c['incomplete']} | "
            f"{'; '.join(f'{k} ({v})' for k, v in c['flags'].items()) or '—'} |"
            for tf, c in report["candles"].items()
        ],
        "",
        "## Traitement des anomalies",
        "| Anomalie | Traitement | Justification |",
        "|---|---|---|",
        *[f"| {d['anomaly']} | {d['treatment']} | {d['justification']} |" for d in report["decisions"]],
        "",
    ]
    return "\n".join(lines)


def write_report(store: HistoryStore, source: str, instrument: str, report: dict[str, Any]) -> list[Path]:
    directory = store.data_dir / "reports"
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in (
        (f"quality_{source}_{instrument}.json", json.dumps(report, indent=2, ensure_ascii=False)),
        (f"quality_{source}_{instrument}.md", to_markdown(report)),
    ):
        target = directory / name
        tmp = target.with_name(f"{target.name}.tmp-{os.getpid()}")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, target)
        written.append(target)
    return written
