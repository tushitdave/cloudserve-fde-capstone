#!/usr/bin/env bash
# Render docs/report/report.md (+ appendices) to PDF with headless Chrome.
set -euo pipefail
cd "$(dirname "$0")/.."
CS_PYTHON="${CLOUDSERVE_PYTHON:-python3}"
OUT="${1:-build/report}"
mkdir -p "$OUT"
{
  cat docs/report/report.md
  for f in governance traceability evaluation_snapshot; do
    printf '\n<!-- pagebreak -->\n\n'
    sed -e 's/^# /### Appendix: /' -e 's/^## /#### /' "docs/$f.md"
  done
} > "$OUT/report_full.md"
"$CS_PYTHON" scripts/md_to_html.py "$OUT/report_full.md" "$OUT/report.html" --title "CloudServe Support Intelligence — Capstone Report"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$OUT/report.pdf" "file://$PWD/$OUT/report.html" 2>/dev/null
echo "$OUT/report.pdf"
