#!/usr/bin/env bash
# Publica los issues de tarea. Idempotente: no recrea los ya existentes.
set -uo pipefail
REPO="HingusPingus/prototipo_recomendaciones"
DIR="$(cd "$(dirname "$0")" && pwd)"
MAN="$DIR/.issues/manifest.json"
MAP="$DIR/.issues/created.tsv"
: > "$MAP"

for tid in $(jq -r 'keys[]' "$MAN" | sort); do
  title=$(jq -r --arg k "$tid" '.[$k].title' "$MAN")
  ms=$(jq -r --arg k "$tid" '.[$k].milestone' "$MAN")
  labels=$(jq -r --arg k "$tid" '.[$k].labels | join(",")' "$MAN")
  url=$(gh issue create --repo "$REPO" \
        --title "$title" \
        --body-file "$DIR/.issues/$tid.md" \
        --milestone "$ms" \
        --label "$labels" 2>&1 | tail -1)
  num="${url##*/}"
  printf '%s\t%s\t%s\n' "$tid" "$num" "$url" >> "$MAP"
  echo "$tid -> #$num"
done
echo "--- $(wc -l < "$MAP") issues creados ---"
