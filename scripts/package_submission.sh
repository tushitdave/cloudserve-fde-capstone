#!/usr/bin/env bash
# Build FirstnameLastname_Capstone_Submission.zip with exactly four top-level folders.
# Usage: scripts/package_submission.sh <FirstnameLastname> <staging-dir-with-01..03> <output-dir>
#   staging dir must contain 01_Video/ (MP4 or link .txt), 02_Report/*.pdf, 03_Workbooks/ (workbooks + effort log PDF).
set -euo pipefail
NAME="$1"; STAGE="$2"; OUT="$3"
cd "$(dirname "$0")/.."
[ -z "$(git status --porcelain)" ] || { echo "Commit or stash changes first" >&2; exit 1; }
for d in 01_Video 02_Report 03_Workbooks; do [ -n "$(ls -A "$STAGE/$d" 2>/dev/null)" ] || { echo "Missing $STAGE/$d" >&2; exit 1; }; done
WORK="$(mktemp -d)"; ROOT="$WORK/pkg"; mkdir -p "$ROOT"
cp -R "$STAGE/01_Video" "$STAGE/02_Report" "$STAGE/03_Workbooks" "$ROOT/"
git clone --quiet "$PWD" "$ROOT/04_Source_Code"
git -C "$ROOT/04_Source_Code" remote set-url origin https://github.com/tushitdave/cloudserve-fde-capstone.git
python3 "$ROOT/04_Source_Code/scripts/architecture_check.py" "$ROOT/04_Source_Code"
if grep -rIlE "(sk|api)[-_][A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY" "$ROOT" --exclude-dir=.git >/dev/null; then echo "Possible credential found; aborting" >&2; exit 1; fi
mkdir -p "$OUT"; ZIP="$OUT/${NAME}_Capstone_Submission.zip"; rm -f "$ZIP"
(cd "$ROOT" && zip -qr "$ZIP" 01_Video 02_Report 03_Workbooks 04_Source_Code -x '*/node_modules/*' '*/.DS_Store')
unzip -l "$ZIP" | awk 'NR>3{print $4}' | cut -d/ -f1 | sort -u | grep -v '^$'
echo "$ZIP"
