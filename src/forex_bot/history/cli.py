"""Command line: `uv run forex-history {plan,ingest,ingest-jforex,build,status}`. No network access, no order.

plan           show a versioned sample definition and the manual exports it needs
ingest         import one manually exported file (immutable raw copy + normalized Parquet)
ingest-jforex  import every complete day written by tools/jforex-ticks (period and retrieval
               date read from the JSON sidecar written next to each CSV)
purge-dukascopy  list, then with --confirm delete, every Dukascopy-derived file (docs/DATA.md §1.3)
build   build H1/H4/D1 candles and the quality report from every imported file
status  list imported files
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from datetime import datetime, timedelta
from pathlib import Path

from forex_bot.history.bars import DEFAULT_GAP_THRESHOLD, build_bars, write_bars
from forex_bot.history.calendar import partitions_touched, require_utc
from forex_bot.history.formats import FORMATS, JFOREX_SDK_TICKS_CSV, FormatError
from forex_bot.history.purge import purge, purge_targets
from forex_bot.history.quality import build_report, write_report
from forex_bot.history.store import HistoryStore, IngestError, IngestRequest

DEFAULT_DATA_DIR = Path("data")


def _utc(text: str) -> datetime:
    return require_utc(datetime.fromisoformat(text))


def cmd_plan(args: argparse.Namespace) -> int:
    config = tomllib.loads(Path(args.sample).read_text(encoding="utf-8"))
    sample = config["sample"]
    start, end = _utc(sample["period_start_utc"]), _utc(sample["period_end_utc"])
    print(f"Échantillon : {sample['id']} — {sample['instrument']} / {sample['source']}")
    partitions = sorted(p.value for p in partitions_touched(start, end))
    print(f"Période : {start.isoformat()} → {end.isoformat()} ; partitions : {partitions}")
    print(f"Justification : {sample['rationale']}")
    print("Exports manuels attendus (un fichier par jour UTC) :")
    day = start
    while day < end:
        print(f"  - {day.date()} 00:00 → {(day + timedelta(days=1)).date()} 00:00 UTC, format {sample['format']}")
        day += timedelta(days=1)
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    store = HistoryStore(Path(args.data_dir))
    try:
        result = store.ingest(
            IngestRequest(
                file=Path(args.file),
                source=args.source,
                instrument=args.instrument,
                format_name=args.format,
                period_start_utc=_utc(args.period_start),
                period_end_utc=_utc(args.period_end),
                retrieved_at_utc=_utc(args.retrieved_at),
            )
        )
    except (IngestError, FormatError, ValueError) as exc:
        print(f"ÉCHEC : {exc}", file=sys.stderr)
        return 2
    print(
        f"{result.sha256[:12]} : brut {result.raw_status}, normalisé {result.normalized_status}, "
        f"{result.rows} ticks, {result.rows_outside_period} hors période ; partitions {list(result.partitions)}"
    )
    return 0


def cmd_ingest_jforex(args: argparse.Namespace) -> int:
    store = HistoryStore(Path(args.data_dir))
    directory = Path(args.dir)
    days = sorted(directory.glob("*.csv"))
    if not days:
        print(f"ÉCHEC : aucun fichier jour dans {directory}", file=sys.stderr)
        return 2
    failures = 0
    for csv_path in days:
        try:
            sidecar = json.loads(csv_path.with_suffix(".json").read_text(encoding="utf-8"))
            if sidecar.get("format") != JFOREX_SDK_TICKS_CSV.name or sidecar.get("instrument") != args.instrument:
                raise IngestError(f"métadonnées inattendues dans {csv_path.with_suffix('.json').name}")
            result = store.ingest(
                IngestRequest(
                    file=csv_path,
                    source=args.source,
                    instrument=args.instrument,
                    format_name=JFOREX_SDK_TICKS_CSV.name,
                    period_start_utc=_utc(sidecar["period_start_utc"]),
                    period_end_utc=_utc(sidecar["period_end_utc"]),
                    retrieved_at_utc=_utc(sidecar["retrieved_at_utc"]),
                )
            )
        except (IngestError, FormatError, ValueError, KeyError, OSError) as exc:
            print(f"ÉCHEC {csv_path.name} : {exc}", file=sys.stderr)
            failures += 1
            continue
        print(
            f"{csv_path.stem} {result.sha256[:12]} : brut {result.raw_status}, normalisé "
            f"{result.normalized_status}, {result.rows} ticks, {result.rows_outside_period} hors période"
        )
    return 2 if failures else 0


def cmd_purge(args: argparse.Namespace) -> int:
    targets = purge_targets(Path(args.data_dir))
    if not targets:
        print("Aucune donnée Dukascopy trouvée.")
        return 0
    for target in targets:
        print(f"{target.size_bytes / 1e6:12.1f} Mo  {target.path}")
    if not args.confirm:
        print("Rien n'a été supprimé : relancer avec --confirm pour supprimer ces chemins.")
        return 0
    for path in purge(targets, confirm=True):
        print(f"Supprimé : {path}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    store = HistoryStore(Path(args.data_dir))
    threshold = timedelta(minutes=args.gap_minutes)
    try:
        bars, summary = build_bars(store, args.source, args.instrument, threshold)
    except FileNotFoundError as exc:
        print(f"ÉCHEC : {exc}", file=sys.stderr)
        return 2
    for path in write_bars(store, args.source, args.instrument, bars):
        print(f"Bougies : {path}")
    report = build_report(store, args.source, args.instrument, summary, bars, threshold)
    for path in write_report(store, args.source, args.instrument, report):
        print(f"Rapport : {path}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    store = HistoryStore(Path(args.data_dir))
    for manifest in store.manifests(args.source, args.instrument):
        print(
            f"{manifest['sha256'][:12]} {manifest['period_start_utc']} → {manifest['period_end_utc']} "
            f"récupéré {manifest['retrieved_at_utc']} {manifest['partitions']}"
        )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="forex-history", description="Historique de marché (recherche).")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan")
    plan.add_argument("--sample", required=True)
    plan.set_defaults(func=cmd_plan)

    ingest = sub.add_parser("ingest")
    ingest.add_argument("--file", required=True)
    ingest.add_argument("--source", default="dukascopy")
    ingest.add_argument("--instrument", default="EURUSD")
    ingest.add_argument("--format", default="dukascopy-ticks-csv-v1", choices=sorted(FORMATS))
    ingest.add_argument("--period-start", required=True, help="début UTC inclus, ex. 2019-03-07T00:00:00+00:00")
    ingest.add_argument("--period-end", required=True, help="fin UTC exclue")
    ingest.add_argument("--retrieved-at", required=True, help="date de l'export manuel, UTC")
    ingest.set_defaults(func=cmd_ingest)

    jforex = sub.add_parser("ingest-jforex")
    jforex.add_argument("--dir", required=True, help="dossier des jours écrits par tools/jforex-ticks")
    jforex.add_argument("--source", default="dukascopy")
    jforex.add_argument("--instrument", default="EURUSD")
    jforex.set_defaults(func=cmd_ingest_jforex)

    purge_cmd = sub.add_parser("purge-dukascopy")
    purge_cmd.add_argument("--confirm", action="store_true", help="supprimer réellement (sinon liste seulement)")
    purge_cmd.set_defaults(func=cmd_purge)

    for name, func in (("build", cmd_build), ("status", cmd_status)):
        command = sub.add_parser(name)
        command.add_argument("--source", default="dukascopy")
        command.add_argument("--instrument", default="EURUSD")
        if name == "build":
            command.add_argument("--gap-minutes", type=float, default=DEFAULT_GAP_THRESHOLD.total_seconds() / 60)
        command.set_defaults(func=func)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
