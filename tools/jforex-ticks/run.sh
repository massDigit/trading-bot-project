#!/usr/bin/env bash
# Read-only EUR/USD tick export from the Dukascopy JForex DEMO server.
# Usage: tools/jforex-ticks/run.sh --env-file PATH --from YYYY-MM-DD --to YYYY-MM-DD [--pause-ms N]
# Output: data/dukascopy-sdk/ticks/EURUSD/<day>.csv(+.json); SDK cache: data/dukascopy-sdk/cache.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
export JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk@21}"
mvn="${MVN:-/opt/homebrew/bin/mvn}"
cd "$here"
"$mvn" -q -B compile dependency:build-classpath -Dmdep.outputFile=target/classpath.txt
exec "$JAVA_HOME/bin/java" -cp "target/classes:$(cat target/classpath.txt)" forexbot.jforex.TickExport \
  --out "$root/data/dukascopy-sdk/ticks" --cache "$root/data/dukascopy-sdk/cache" "$@"
