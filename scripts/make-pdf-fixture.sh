#!/usr/bin/env bash
# Renders corpus/leave-policy-ar.md to an Arabic PDF fixture (tests PDF extraction of Arabic text).
# Needs uv and Google Chrome. Usage: scripts/make-pdf-fixture.sh
set -euo pipefail
cd "$(dirname "$0")/.."
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
uv run --no-project --with markdown python -I -c '
import sys, markdown
body = markdown.markdown(open(sys.argv[1], encoding="utf-8").read())
print(f"<!doctype html><html lang=\"ar\" dir=\"rtl\"><meta charset=\"utf-8\">"
      f"<style>body{{font-family:\"Geeza Pro\",\"Noto Naskh Arabic\",sans-serif;font-size:14pt;margin:2cm}}</style>"
      f"<body>{body}</body></html>")
' corpus/leave-policy-ar.md > "$tmp/leave.html"
"$CHROME" --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$PWD/corpus/fixtures/leave-policy-ar.pdf" "file://$tmp/leave.html" 2>/dev/null
echo "wrote corpus/fixtures/leave-policy-ar.pdf"
