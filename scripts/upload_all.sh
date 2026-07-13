#!/bin/bash
# Upload all local datasets to Yandex Disk
# Usage: ./scripts/upload_all.sh

cd "$(dirname "$0")/.."
set -a
source .env
set +a
source .venv311/bin/activate 2>/dev/null || true
export PYTHONPATH="$PWD/src:$PYTHONPATH"

TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOGDIR="runs"

SOURCES=("ekfgroup.com" "iek.ru" "dkc.ru" "ruscable.ru" "elcable.ru")

for source in "${SOURCES[@]}"; do
  path="electrical/${source}"
  if [ -d "datasets/${path}" ]; then
    echo "Uploading: ${source}..."
    python src/scraper.py --upload-local "${path}" \
      > "${LOGDIR}/upload_${source}_${TIMESTAMP}.log" 2>&1 &
    echo "  PID: $! -> ${LOGDIR}/upload_${source}_${TIMESTAMP}.log"
  fi
done

echo ""
echo "All uploads launched. Monitor with:"
echo "  tail -f ${LOGDIR}/upload_*_${TIMESTAMP}.log"
echo ""
echo "Waiting..."
wait
echo "All uploads complete."
