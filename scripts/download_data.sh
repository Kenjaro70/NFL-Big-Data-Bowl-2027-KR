#!/usr/bin/env bash
# Download the NFL Big Data Bowl 2027 competition data into data/raw/.
# Needs KAGGLE_API_TOKEN (alias: KAGGLE_API_KEY) or KAGGLE_USERNAME + KAGGLE_KEY,
# and the competition rules accepted on kaggle.com ("Join Hackathon").
#
# Calls the REST API on www.kaggle.com with curl rather than the kaggle CLI:
# the CLI (>= 2.x) talks to api.kaggle.com, which some sandboxed networks block.
set -euo pipefail

COMP="nfl-big-data-bowl-2027"
DEST="$(cd "$(dirname "$0")/.." && pwd)/data/raw"
URL="https://www.kaggle.com/api/v1/competitions/data/download-all/$COMP"

TOKEN="${KAGGLE_API_TOKEN:-${KAGGLE_API_KEY:-}}"
if [[ -n "$TOKEN" ]]; then
  AUTH=(-H "Authorization: Bearer $TOKEN")
elif [[ -n "${KAGGLE_USERNAME:-}" && -n "${KAGGLE_KEY:-}" ]]; then
  AUTH=(-u "$KAGGLE_USERNAME:$KAGGLE_KEY")
else
  echo "No Kaggle credentials: set KAGGLE_API_TOKEN (or KAGGLE_API_KEY), or KAGGLE_USERNAME and KAGGLE_KEY." >&2
  exit 1
fi

mkdir -p "$DEST"
curl -sS -L --fail "${AUTH[@]}" -o "$DEST/$COMP.zip" "$URL"
# The archive nests files under $COMP/; flatten into data/raw/.
unzip -ojq "$DEST/$COMP.zip" -d "$DEST"
rm -f "$DEST/$COMP.zip"
ls -lh "$DEST"
