"""Reproducible, idempotent import of raw files into an immutable raw store and normalized Parquet.

Layout under the data directory (git-ignored):
    raw/<source>/<instrument>/<sha256><ext>          immutable copy (read-only), never modified
    raw/<source>/<instrument>/<sha256>.json          manifest: source, instrument, period, retrieval date, hash
    normalized/ticks/<source>/<instrument>/<sha256>.parquet

Rules
-----
- A raw file is identified by its SHA-256. Re-importing the same file is a no-op.
  Exception: files with no data row (e.g. a Saturday, header only) are byte-identical; each
  such file is registered once per declared period (entry `<sha256>-<period start>`), so that
  the period still counts as covered. A file WITH data rows declared for another period is
  refused.
- Each file declares the UTC period [start, end) it covers. Two different files
  of the same source and instrument may not have overlapping periods: this is
  what prevents duplicates across files (ticks sharing a timestamp inside one
  file are legitimate and all kept, ordered by their line number).
- Rows outside the declared period are excluded from the normalized file and
  counted in its metadata.
- Every write goes to a temporary file then is atomically renamed; an
  interrupted run leaves no partial output and is completed by a new run.
- Periods touching the reserved final-test partition (2024-2025) are refused.
- No network access: files are exported manually by the operator or written by
  the separate JForex SDK adapter tools/jforex-ticks (see docs/DATA.md).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from forex_bot.history.calendar import Partition, partitions_touched, require_utc
from forex_bot.history.formats import FORMATS, read_ticks

MANIFEST_VERSION = 1
NORMALIZER_VERSION = "ticks-v1"
PRICE_TYPE = pa.decimal128(18, 5)

TICK_SCHEMA = pa.schema(
    [
        pa.field("source", pa.string(), nullable=False),
        pa.field("instrument", pa.string(), nullable=False),
        pa.field("ts_utc", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("raw_sha256", pa.string(), nullable=False),
        pa.field("raw_row", pa.int64(), nullable=False),  # line in the raw file: order of simultaneous ticks
        pa.field("bid", PRICE_TYPE, nullable=False),
        pa.field("ask", PRICE_TYPE, nullable=False),
        pa.field("bid_volume", pa.float64()),  # provider volume, unit unconfirmed
        pa.field("ask_volume", pa.float64()),
    ]
)


class IngestError(Exception):
    pass


@dataclass(frozen=True)
class IngestRequest:
    file: Path
    source: str
    instrument: str
    format_name: str
    period_start_utc: datetime
    period_end_utc: datetime
    retrieved_at_utc: datetime  # declared by the operator (manual export)


@dataclass(frozen=True)
class IngestResult:
    sha256: str
    raw_status: str  # "copied" | "already_present"
    normalized_status: str  # "written" | "already_present"
    rows: int
    rows_outside_period: int
    partitions: tuple[str, ...]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_bytes(target: Path, data: bytes) -> None:
    tmp = target.with_name(f"{target.name}.tmp-{os.getpid()}")
    tmp.write_bytes(data)
    os.replace(tmp, target)


def _clean_temporaries(directory: Path) -> None:
    for leftover in directory.glob("*.tmp-*"):
        leftover.unlink()


def _iso(moment: datetime) -> str:
    return require_utc(moment).isoformat()


class HistoryStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def raw_dir(self, source: str, instrument: str) -> Path:
        return self.data_dir / "raw" / source / instrument

    def ticks_dir(self, source: str, instrument: str) -> Path:
        return self.data_dir / "normalized" / "ticks" / source / instrument

    def manifests(self, source: str, instrument: str) -> list[dict[str, Any]]:
        directory = self.raw_dir(source, instrument)
        if not directory.exists():
            return []
        return [json.loads(p.read_text()) for p in sorted(directory.glob("*.json"))]

    def tick_files(self, source: str, instrument: str) -> list[Path]:
        directory = self.ticks_dir(source, instrument)
        return sorted(directory.glob("*.parquet")) if directory.exists() else []

    # ------------------------------------------------------------------ ingest

    def ingest(self, request: IngestRequest) -> IngestResult:
        start, end = require_utc(request.period_start_utc), require_utc(request.period_end_utc)
        retrieved = require_utc(request.retrieved_at_utc)
        fmt = FORMATS.get(request.format_name)
        if fmt is None:
            raise IngestError(f"format inconnu : {request.format_name}")
        touched = partitions_touched(start, end)
        if Partition.FINAL_TEST in touched:
            raise IngestError("période dans la partition de test final réservée (2024-2025) : import refusé")
        if not request.file.is_file():
            raise IngestError(f"fichier introuvable : {request.file.name}")

        digest = sha256_of(request.file)
        no_rows = next(iter(read_ticks(request.file, fmt)), None) is None
        entry = f"{digest}-{start.strftime('%Y%m%dT%H%M%SZ')}" if no_rows else digest
        raw_dir = self.raw_dir(request.source, request.instrument)
        ticks_dir = self.ticks_dir(request.source, request.instrument)
        raw_dir.mkdir(parents=True, exist_ok=True)
        ticks_dir.mkdir(parents=True, exist_ok=True)
        _clean_temporaries(raw_dir)
        _clean_temporaries(ticks_dir)

        partitions = tuple(sorted(p.value for p in touched))
        manifest: dict[str, Any] = {
            "manifest_version": MANIFEST_VERSION,
            "source": request.source,
            "instrument": request.instrument,
            "format": fmt.name,
            "period_start_utc": _iso(start),
            "period_end_utc": _iso(end),
            "retrieved_at_utc": _iso(retrieved),
            "retrieval": "export manuel déclaré par l'opérateur",
            "original_filename": request.file.name,
            "sha256": digest,
            "entry": entry,
            "size_bytes": request.file.stat().st_size,
            "partitions": list(partitions),
        }
        self._check_manifest(raw_dir, manifest, no_rows)

        raw_path = raw_dir / f"{digest}{request.file.suffix.lower()}"
        raw_status = "already_present"
        if raw_path.exists():
            if sha256_of(raw_path) != digest:
                raise IngestError(f"copie brute altérée : {raw_path.name} (empreinte différente)")
        else:
            tmp = raw_path.with_name(f"{raw_path.name}.tmp-{os.getpid()}")
            shutil.copyfile(request.file, tmp)
            if sha256_of(tmp) != digest:
                tmp.unlink()
                raise IngestError("fichier modifié pendant la copie")
            os.replace(tmp, raw_path)
            raw_status = "copied"
        raw_path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        manifest_path = raw_dir / f"{entry}.json"
        if not manifest_path.exists():
            manifest["ingested_at_utc"] = _iso(datetime.now(UTC))
            _atomic_write_bytes(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False).encode())

        parquet_path = ticks_dir / f"{entry}.parquet"
        if parquet_path.exists() and self._normalized_matches(parquet_path, digest):
            meta = pq.read_schema(parquet_path).metadata or {}
            return IngestResult(
                digest,
                raw_status,
                "already_present",
                int(meta[b"rows"]),
                int(meta[b"rows_outside_period"]),
                partitions,
            )
        rows, outside = self._normalize(raw_path, parquet_path, request, fmt.name, digest, start, end)
        return IngestResult(digest, raw_status, "written", rows, outside, partitions)

    def _check_manifest(self, raw_dir: Path, manifest: dict[str, Any], no_rows: bool) -> None:
        keys = ("source", "instrument", "format", "period_start_utc", "period_end_utc")
        for path in raw_dir.glob("*.json"):
            other = json.loads(path.read_text())
            if other["sha256"] == manifest["sha256"]:
                if all(other[k] == manifest[k] for k in keys):
                    continue
                if not no_rows:
                    raise IngestError("fichier déjà importé avec d'autres métadonnées (source, période ou format)")
            if (
                other["period_start_utc"] < manifest["period_end_utc"]
                and manifest["period_start_utc"] < other["period_end_utc"]
            ):
                raise IngestError(
                    f"période chevauchant un autre fichier importé ({other['period_start_utc']} - "
                    f"{other['period_end_utc']}) : risque de doublons, import refusé"
                )

    @staticmethod
    def _normalized_matches(path: Path, digest: str) -> bool:
        meta = pq.read_schema(path).metadata or {}
        return meta.get(b"raw_sha256") == digest.encode() and meta.get(b"normalizer") == NORMALIZER_VERSION.encode()

    def _normalize(
        self,
        raw_path: Path,
        parquet_path: Path,
        request: IngestRequest,
        format_name: str,
        digest: str,
        start: datetime,
        end: datetime,
    ) -> tuple[int, int]:
        columns: dict[str, list[Any]] = {name: [] for name in TICK_SCHEMA.names}
        outside = 0
        for tick in read_ticks(raw_path, FORMATS[format_name]):
            if not start <= tick.ts_utc < end:
                outside += 1
                continue
            columns["source"].append(request.source)
            columns["instrument"].append(request.instrument)
            columns["ts_utc"].append(tick.ts_utc)
            columns["raw_sha256"].append(digest)
            columns["raw_row"].append(tick.row)
            columns["bid"].append(tick.bid)
            columns["ask"].append(tick.ask)
            columns["bid_volume"].append(tick.bid_volume)
            columns["ask_volume"].append(tick.ask_volume)
        rows = len(columns["ts_utc"])
        metadata = {
            "raw_sha256": digest,
            "normalizer": NORMALIZER_VERSION,
            "format": format_name,
            "rows": str(rows),
            "rows_outside_period": str(outside),
            "period_start_utc": _iso(start),
            "period_end_utc": _iso(end),
        }
        table = pa.table(columns, schema=TICK_SCHEMA).replace_schema_metadata(metadata)
        tmp = parquet_path.with_name(f"{parquet_path.name}.tmp-{os.getpid()}")
        pq.write_table(table, tmp)
        os.replace(tmp, parquet_path)
        return rows, outside
