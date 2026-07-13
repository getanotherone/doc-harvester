#!/usr/bin/env bash
# Retention policy: prune disk-hogging files that the pipeline produces.
# Run periodically (e.g. weekly via cron) or before long crawls.
#
# What it removes:
#   - runs/ingest_*.json older than $KEEP_DAYS days, keeping the most recent
#     $KEEP_LATEST regardless of age
#   - data/*.tmp.* (leaked temp files from interrupted atomic writes)
#   - data/*.bak older than $KEEP_DAYS days
#
# Usage:
#   bash scripts/cleanup_runs.sh           # default: 14-day, keep 10 latest
#   KEEP_DAYS=30 KEEP_LATEST=20 bash scripts/cleanup_runs.sh
#   DRY_RUN=1 bash scripts/cleanup_runs.sh # show what would be deleted

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEEP_DAYS="${KEEP_DAYS:-14}"
KEEP_LATEST="${KEEP_LATEST:-10}"
DRY_RUN="${DRY_RUN:-0}"

run_or_show() {
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "DRY: $*"
  else
    "$@"
  fi
}

echo "Cleanup policy: keep last $KEEP_LATEST ingest files + anything newer than $KEEP_DAYS days"

# 1. ingest_*.json — keep N latest by mtime, prune the rest if older than KEEP_DAYS
# Build set of files-to-keep (top N by mtime). Uses stat -f for BSD/macOS.
KEEP_SET=$(
  find "$ROOT/runs" -maxdepth 1 -name "ingest_*.json" -type f -exec stat -f "%m %N" {} + 2>/dev/null \
    | sort -rn | head -n "$KEEP_LATEST" | awk '{ $1=""; sub(/^ /,""); print }'
)

while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  if ! grep -Fxq "$f" <<<"$KEEP_SET"; then
    run_or_show rm "$f"
  fi
done < <(find "$ROOT/runs" -maxdepth 1 -name "ingest_*.json" -type f -mtime +"$KEEP_DAYS" 2>/dev/null)

# 2. leaked temp files — delete unconditionally (they're write-interruption garbage)
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  run_or_show rm "$f"
done < <(find "$ROOT/data" -maxdepth 1 -name "*.tmp.*" -type f 2>/dev/null)

# 3. stale .bak files
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  run_or_show rm "$f"
done < <(find "$ROOT/data" -maxdepth 1 -name "*.bak" -type f -mtime +"$KEEP_DAYS" 2>/dev/null)

echo "Done. Current sizes:"
du -sh "$ROOT/runs" "$ROOT/data" 2>/dev/null
