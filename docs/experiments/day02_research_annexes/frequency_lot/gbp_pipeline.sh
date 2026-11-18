#!/bin/bash
# After the GBP/USD download: import, candles, alignment, morning short GBP/USD, then SMTF / SMTT passes.
set -u
cd "$(git rev-parse --show-toplevel)"
O=data/reports/backtests/day02_frequency; L=$O/gbp_pipeline.log
log() { echo "$(date '+%F %T') $*" >> $L; }
while kill -0 71426 2>/dev/null; do sleep 60; done
log "téléchargement terminé ; dernière ligne : $(tail -1 $O/gbpusd_download.log)"
inc=$(cd data/dukascopy-sdk/ticks/GBPUSD && ls *.incomplete.json 2>/dev/null | tr '\n' ' ')
for f in data/dukascopy-sdk/ticks/GBPUSD/*.incomplete.json; do d=$(basename $f .incomplete.json); [ -f data/dukascopy-sdk/ticks/GBPUSD/$d.csv ] && continue
  case $d in 2016-09-02|2019-05-26) ;; *) log "ARRÊT : jour $d incomplet non prévu"; exit 1;; esac; done
log "jours absents laissés absents (heures vides persistantes, mêmes que EUR/USD) : 2016-09-02, 2019-05-26 ; rapports : $inc"
[ -f data/dukascopy-sdk/ticks/GBPUSD/2021-12-31.json ] || { log "ARRÊT : 2021-12-31 absent"; exit 1; }
step() { log "début $1"; shift; "$@" >> $L 2>&1; rc=$?; log "fin rc=$rc"; [ $rc -eq 0 ] || { log "ARRÊT"; exit 1; }; }
step import uv run forex-history ingest-jforex --dir data/dukascopy-sdk/ticks/GBPUSD --instrument GBPUSD
step build uv run forex-history build --instrument GBPUSD
step intraday_ref uv run forex-intraday --instrument GBPUSD --leak-cut 2018-07-01
step intraday_day01 uv run forex-intraday --instrument GBPUSD --leak-cut 2018-07-01 --convention day01_5min
step alignement uv run --with pyarrow python -I $O/align_gbp.py
step vente_matin_gbp uv run --with pyarrow --with pandas python -I data/reports/research/morning_short_gbpusd/simulate.py
log "dispo SMTF/SMTT, head $(git rev-parse HEAD) dirty=[$(git status --porcelain | tr '\n' ' ')]"
for v in SMTF SMTT; do
  uv run forex-day02-availability --variant $v --out $O/avail_$v.json --details-out $O/avail_${v}_details.jsonl > $O/avail_$v.log 2>&1 &
done; wait; log "dispo terminée : $(tail -qn1 $O/avail_SMTF.log $O/avail_SMTT.log | tr '\n' ' ')"
for v in SMTF SMTT; do
  uv run forex-day02-backtest --trigger M5 --scenario A --variant $v --end 2015-04-01 --availability $O/avail_${v}_details.jsonl --out $O/truncated/perf_$v.json --sessions-out $O/truncated/sessions_$v.jsonl > $O/truncated/$v.log 2>&1 &
done; wait
log "tronqués : $(tail -qn1 $O/truncated/SMTF.log $O/truncated/SMTT.log | tr '\n' ' ')"
grep -q "rapport écrit" $O/truncated/SMTF.log && grep -q "rapport écrit" $O/truncated/SMTT.log || { log "ARRÊT : rejeu tronqué en échec"; exit 1; }
for v in SMTF SMTT; do bash $O/run_perf.sh $v & done; wait
log "passages terminés : $(cat $O/run_SMTF.status $O/run_SMTT.status | tr '\n' ' ')"
(cd $O && uv run python -I trunc_check.py SMTF SMTT) >> $L 2>&1
log "FIN"
