#!/usr/bin/env bash
set -euo pipefail

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "gitleaks is required. On macOS: brew install gitleaks" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel)"
snapshot="$(mktemp -d "${TMPDIR:-/tmp}/doc-harvester-scan.XXXXXX")"
trap 'rm -rf "$snapshot"' EXIT

cd "$repo_root"
echo "Scanning complete Git history..."
gitleaks git --redact --no-banner --log-opts="--all" .

echo "Scanning tracked and non-ignored working-tree files..."
while IFS= read -r -d '' file; do
  mkdir -p "$snapshot/$(dirname "$file")"
  cp "$file" "$snapshot/$file"
done < <(git ls-files --cached --others --exclude-standard -z)
gitleaks dir --redact --no-banner "$snapshot"
