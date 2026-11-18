#!/bin/bash
# Usage: run_variant.sh VARIANT [suffix extra-args...] — availability then performance M5 scenario A, 2015-2021.
set -u
cd "$(git rev-parse --show-toplevel)"
v=$1; O=data/reports/backtests/day02_frequency
echo "start $(date -u +%FT%TZ) head $(git rev-parse HEAD)" > $O/run_$v.status
/usr/bin/time -l uv run forex-day02-availability --variant $v --out $O/avail_$v.json --details-out $O/avail_${v}_details.jsonl > $O/avail_$v.log 2>&1
a=$?
/usr/bin/time -l uv run forex-day02-backtest --trigger M5 --scenario A --variant $v --availability $O/avail_${v}_details.jsonl --out $O/perf_${v}_m5_a.json --sessions-out $O/perf_${v}_m5_a_sessions.jsonl > $O/perf_${v}_m5_a.log 2>&1
p=$?
echo "end $(date -u +%FT%TZ) avail_rc=$a perf_rc=$p head $(git rev-parse HEAD) dirty=[$(git status --porcelain | tr '\n' ' ')]" >> $O/run_$v.status
